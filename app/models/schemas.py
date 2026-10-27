from app.utils.errors import ValidationError

ALLOWED_ROLES = {"policyholder", "agent", "customer_service"}


def validate_upload_request(form, files):
    if "file" not in files or files["file"].filename == "":
        raise ValidationError("A document file is required (multipart field 'file')")

    customer_id = form.get("customer_id")
    if not customer_id:
        raise ValidationError("customer_id is required")

    policy_id = form.get("policy_id")  # optional at upload time; may be assigned after extraction

    return {
        "file": files["file"],
        "customer_id": customer_id,
        "policy_id": policy_id,
    }


REQUIRED_CSV_COLUMNS = {
    "document_id", "policy_id", "customer_id", "policy_type", "product_name",
    "effective_date", "status", "document_type", "version", "s3_key", "updated_at",
}


def validate_csv_upload(files):
    if "file" not in files or files["file"].filename == "":
        raise ValidationError("A CSV file is required (multipart field 'file')")

    file_storage = files["file"]
    if not file_storage.filename.lower().endswith(".csv"):
        raise ValidationError("File must have a .csv extension")

    return file_storage


def validate_login_request(body):
    if not body:
        raise ValidationError("Request body must be JSON")

    username = body.get("username")
    role = body.get("role")

    if not username:
        raise ValidationError("username is required")
    if role not in ALLOWED_ROLES:
        raise ValidationError(f"role must be one of {sorted(ALLOWED_ROLES)}")

    return {"username": username, "role": role}
