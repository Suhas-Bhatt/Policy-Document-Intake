import csv
import io
import threading

from flask import Blueprint, current_app, jsonify, request

from app.models.schemas import REQUIRED_CSV_COLUMNS, validate_csv_upload, validate_upload_request
from app.services.auth_service import require_auth
from app.services.aws_service import (
    get_document_status,
    upload_csv_to_s3,
    upload_document_via_api_gateway,
)
from app.services.snowflake_service import bulk_upsert_policy_documents
from app.utils.errors import ValidationError

bp = Blueprint("documents", __name__)


@bp.post("/api/documents/upload")
@require_auth
def upload_document():
    """
    POST /api/documents/upload  (multipart/form-data: file, customer_id, [policy_id])

    Flask business logic: validate request/file -> store metadata ->
    trigger document processing (via API Gateway -> S3 -> EventBridge -> Lambda).
    """
    payload = validate_upload_request(request.form, request.files)
    result = upload_document_via_api_gateway(
        file_storage=payload["file"],
        customer_id=payload["customer_id"],
        policy_id=payload["policy_id"],
    )
    return jsonify(result), 202


@bp.get("/api/documents/<document_id>/status")
@require_auth
def document_status(document_id):
    item = get_document_status(document_id)
    return jsonify(item)


@bp.post("/api/documents/bulk-upload")
@require_auth
def bulk_upload_documents():
    """
    POST /api/documents/bulk-upload  (multipart/form-data: file)

    Bulk-imports policy/document rows from a CSV: archives the raw file to
    S3 (AWS side) synchronously, then loads the rows into Snowflake in a
    background thread so the response returns as soon as the S3 archival
    (the slow Snowflake MERGE loop no longer blocks the HTTP response) --
    trades an immediate "rows_loaded" confirmation for a fast "queued" ack.
    """
    file_storage = validate_csv_upload(request.files)
    file_bytes = file_storage.read()

    reader = csv.DictReader(io.StringIO(file_bytes.decode("utf-8-sig")))
    missing = REQUIRED_CSV_COLUMNS - set(reader.fieldnames or [])
    if missing:
        raise ValidationError(f"CSV is missing required columns: {sorted(missing)}")
    rows = list(reader)

    s3_key = upload_csv_to_s3(file_bytes, file_storage.filename)

    app = current_app._get_current_object()

    def _load_in_background():
        with app.app_context():
            try:
                bulk_upsert_policy_documents(rows)
                app.logger.info("bulk_upload_snowflake_load_complete s3_key=%s rows=%d", s3_key, len(rows))
            except Exception:
                app.logger.exception("bulk_upload_snowflake_load_failed s3_key=%s", s3_key)

    threading.Thread(target=_load_in_background, daemon=True).start()

    return jsonify({"s3_key": s3_key, "rows_queued": len(rows), "status": "snowflake_load_in_progress"}), 202
