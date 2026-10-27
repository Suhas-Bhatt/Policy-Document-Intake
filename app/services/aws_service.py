"""
AWS integration service.

Implements the Flask-side half of the diagram's intake pipeline:

    Flask --"Validated Document"--> API Gateway --> S3 --> EventBridge --> Lambda

Flask never talks to S3 directly for the upload itself; per the diagram it
hands the validated document to API Gateway, which is configured with a
native AWS-service proxy integration that performs the S3 PutObject (see
aws/apigateway/s3-proxy-integration.md). Flask *does* talk directly to
DynamoDB (status lookups) and SNS (only used by AWS-side components, not
Flask, per the diagram — kept here for completeness of the boto3 client set).
"""
import uuid

import boto3
import requests
from flask import current_app

from app.utils.errors import UpstreamServiceError, NotFoundError


def _dynamodb_table():
    resource = boto3.resource("dynamodb", region_name=current_app.config["AWS_REGION"])
    return resource.Table(current_app.config["DYNAMODB_TABLE_NAME"])


def upload_document_via_api_gateway(file_storage, customer_id, policy_id):
    """
    Sends the validated document to the API Gateway S3-proxy endpoint.
    API Gateway performs the S3 PutObject; the S3 write itself triggers the
    EventBridge -> Lambda processing chain independently of Flask.
    """
    document_id = str(uuid.uuid4())
    object_key = f"incoming/{customer_id}/{document_id}_{file_storage.filename}"

    upload_url = current_app.config["API_GATEWAY_UPLOAD_URL"]
    if not upload_url:
        raise UpstreamServiceError("API_GATEWAY_UPLOAD_URL is not configured")

    file_bytes = file_storage.read()
    try:
        response = requests.put(
            f"{upload_url}/{object_key}",
            data=file_bytes,
            headers={
                "Content-Type": file_storage.mimetype or "application/octet-stream",
                "x-amz-meta-document-id": document_id,
                "x-amz-meta-customer-id": customer_id,
            },
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise UpstreamServiceError(f"Failed to upload document via API Gateway: {exc}") from exc

    # Flask writes the initial "received" record; the processing Lambda will
    # update this same item once extraction completes (see aws/lambda/document_processor).
    table = _dynamodb_table()
    table.put_item(
        Item={
            "document_id": document_id,
            "customer_id": customer_id,
            "policy_id": policy_id or "",
            "s3_key": object_key,
            "status": "UPLOADED",
            "document_type": "UNKNOWN",
            "extracted_data": {},
        }
    )

    return {"document_id": document_id, "s3_key": object_key, "status": "UPLOADED"}


def upload_csv_to_s3(file_bytes, filename):
    """
    Archives a bulk-import CSV to S3 under csv-uploads/ (not incoming/), so it
    does NOT match the EventBridge rule that fires the Textract document
    processor -- CSV rows are parsed and loaded into Snowflake directly by
    Flask (see snowflake_service.bulk_upsert_policy_documents), this upload
    is only for keeping a copy of the raw file.
    """
    object_key = f"csv-uploads/{uuid.uuid4()}_{filename}"

    upload_url = current_app.config["API_GATEWAY_UPLOAD_URL"]
    if not upload_url:
        raise UpstreamServiceError("API_GATEWAY_UPLOAD_URL is not configured")

    try:
        response = requests.put(
            f"{upload_url}/{object_key}",
            data=file_bytes,
            headers={"Content-Type": "text/csv"},
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise UpstreamServiceError(f"Failed to archive CSV via API Gateway: {exc}") from exc

    return object_key


def get_document_status(document_id):
    table = _dynamodb_table()
    result = table.get_item(Key={"document_id": document_id})
    item = result.get("Item")
    if not item:
        raise NotFoundError(f"No document found with id {document_id}")
    return item
