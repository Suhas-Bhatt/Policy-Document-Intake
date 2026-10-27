import io
from unittest.mock import patch

import requests


class _FakeResponse:
    def raise_for_status(self):
        return None


def test_upload_document_success(client, auth_header):
    with patch.object(requests, "put", return_value=_FakeResponse()) as mock_put:
        response = client.post(
            "/api/documents/upload",
            data={
                "file": (io.BytesIO(b"%PDF-1.4 fake content"), "policy.pdf"),
                "customer_id": "CUST-001",
            },
            headers=auth_header,
            content_type="multipart/form-data",
        )

    assert response.status_code == 202
    body = response.get_json()
    assert body["status"] == "UPLOADED"
    assert "document_id" in body
    mock_put.assert_called_once()


def test_upload_document_missing_file(client, auth_header):
    response = client.post(
        "/api/documents/upload",
        data={"customer_id": "CUST-001"},
        headers=auth_header,
        content_type="multipart/form-data",
    )
    assert response.status_code == 400


def test_document_status_not_found(client, auth_header):
    response = client.get("/api/documents/does-not-exist/status", headers=auth_header)
    assert response.status_code == 404


def test_document_status_found_after_upload(client, auth_header):
    with patch.object(requests, "put", return_value=_FakeResponse()):
        upload_resp = client.post(
            "/api/documents/upload",
            data={
                "file": (io.BytesIO(b"%PDF-1.4 fake content"), "policy.pdf"),
                "customer_id": "CUST-001",
            },
            headers=auth_header,
            content_type="multipart/form-data",
        )
    document_id = upload_resp.get_json()["document_id"]

    status_resp = client.get(f"/api/documents/{document_id}/status", headers=auth_header)
    assert status_resp.status_code == 200
    assert status_resp.get_json()["status"] == "UPLOADED"
