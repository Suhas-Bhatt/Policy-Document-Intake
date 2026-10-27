def test_login_issues_token(client):
    response = client.post("/api/auth/login", json={"username": "bob", "role": "policyholder"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["token_type"] == "Bearer"
    assert body["access_token"]


def test_login_rejects_bad_role(client):
    response = client.post("/api/auth/login", json={"username": "bob", "role": "not-a-role"})
    assert response.status_code == 400


def test_protected_route_requires_auth(client):
    response = client.get("/api/documents/some-id/status")
    assert response.status_code == 401
