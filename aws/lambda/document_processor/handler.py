"""
AWS Lambda: Document Processor

Diagram role: "AWS Lambda (Document Processor) - Extract text (OCR),
Classify document type, Extract key policy details, Validate and enrich data"

Trigger: Amazon EventBridge rule matching S3 "Object Created" events for the
policy-documents bucket (see aws/eventbridge/rule.json). EventBridge is what
the diagram shows firing the workflow after S3 stores the document.

Implementation note: OCR/extraction is done via the Gemini API instead of
Amazon Textract. The AWS account this POC runs under does not have Textract
enabled (SubscriptionRequiredException), so a single Gemini multimodal call
does OCR + classification + field extraction in one shot, called via
urllib.request (stdlib only -- no extra Lambda packaging required).

On completion this function:
  1. Updates the DynamoDB item created by Flask at upload time
     ("Processing Complete" -> DynamoDB, per diagram).
  2. Publishes to the SNS completion topic ("Completion Notification" ->
     notify via email/SMS, alert agents/ops, trigger downstream actions --
     the downstream action being the Snowflake loader, see
     aws/lambda/snowflake_loader/handler.py).

CloudWatch: Lambda's own invocation/duration/error metrics are captured
automatically; this handler additionally emits structured log lines so they
are queryable in CloudWatch Logs Insights by document_id.
"""
import base64
import json
import logging
import os
import re
import urllib.error
import urllib.request

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")

TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)

DOCUMENT_ID_PATTERN = re.compile(r"incoming/[^/]+/([0-9a-fA-F-]{36})_")

MIME_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}

VALID_DOCUMENT_TYPES = {"AUTO_POLICY", "HOME_POLICY", "LIFE_POLICY", "UNKNOWN"}

EXTRACTION_PROMPT = """
Analyze this insurance policy document. Extract the following fields and
return ONLY a valid JSON object. Do not include markdown code fences, text
formatting, or explanations. Just the raw JSON.

Required schema:
{
    "DocumentType": "AUTO_POLICY" | "HOME_POLICY" | "LIFE_POLICY" | "UNKNOWN",
    "PolicyNumber": "string or null",
    "EffectiveDate": "YYYY-MM-DD or null",
    "RawTextExcerpt": "string, the first ~500 characters of visible text"
}
"""


def handler(event, context):
    detail = event.get("detail", {})
    bucket = detail.get("bucket", {}).get("name")
    key = detail.get("object", {}).get("key")

    if not bucket or not key:
        logger.error("event missing bucket/key: %s", json.dumps(event))
        return {"statusCode": 400, "body": "invalid event"}

    document_id = _extract_document_id(key)
    logger.info("processing_start document_id=%s bucket=%s key=%s", document_id, bucket, key)

    try:
        document_type, policy_fields = _extract_with_gemini(bucket, key)

        _update_dynamodb(document_id, document_type, policy_fields, status="PROCESSED")
        _publish_completion(document_id, document_type, policy_fields)

        logger.info("processing_complete document_id=%s document_type=%s", document_id, document_type)
        return {"statusCode": 200, "body": "processed"}

    except Exception as exc:  # noqa: BLE001 - Lambda boundary, must not raise unhandled
        logger.exception("processing_failed document_id=%s error=%s", document_id, exc)
        _update_dynamodb(document_id, "UNKNOWN", {}, status="FAILED", error=str(exc))
        raise


def _extract_document_id(key):
    match = DOCUMENT_ID_PATTERN.search(key)
    return match.group(1) if match else key


def _extract_with_gemini(bucket, key):
    obj = s3.get_object(Bucket=bucket, Key=key)
    file_bytes = obj["Body"].read()

    _, ext = os.path.splitext(key.lower())
    mime_type = MIME_TYPES.get(ext, "application/octet-stream")

    request_body = json.dumps(
        {
            "contents": [
                {
                    "parts": [
                        {"text": EXTRACTION_PROMPT},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": base64.b64encode(file_bytes).decode("ascii"),
                            }
                        },
                    ]
                }
            ]
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{GEMINI_URL}?key={GEMINI_API_KEY}",
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            response_json = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Gemini API error {exc.code}: {exc.read().decode('utf-8', 'replace')}") from exc

    raw_text = response_json["candidates"][0]["content"]["parts"][0]["text"]
    parsed = _parse_gemini_json(raw_text)

    document_type = parsed.get("DocumentType") or "UNKNOWN"
    if document_type not in VALID_DOCUMENT_TYPES:
        document_type = "UNKNOWN"

    policy_fields = {
        "policy_number": parsed.get("PolicyNumber"),
        "effective_date": parsed.get("EffectiveDate"),
        "raw_text_excerpt": parsed.get("RawTextExcerpt"),
    }
    return document_type, policy_fields


def _parse_gemini_json(raw_text):
    """Gemini is asked to return raw JSON, but strip markdown fences defensively
    in case it wraps the response in ```json ... ``` anyway."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned.strip(), flags=re.MULTILINE)
    return json.loads(cleaned)


def _update_dynamodb(document_id, document_type, policy_fields, status, error=None):
    table = dynamodb.Table(TABLE_NAME)
    update_expr = "SET #status = :status, document_type = :doc_type, extracted_data = :fields"
    expr_values = {
        ":status": status,
        ":doc_type": document_type,
        ":fields": policy_fields,
    }
    if error:
        update_expr += ", error_details = :error"
        expr_values[":error"] = error

    table.update_item(
        Key={"document_id": document_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues=expr_values,
    )


def _publish_completion(document_id, document_type, policy_fields):
    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject="Policy document processed",
        Message=json.dumps(
            {
                "document_id": document_id,
                "document_type": document_type,
                "policy_fields": policy_fields,
                "status": "PROCESSED",
            }
        ),
        MessageAttributes={
            "event_type": {"DataType": "String", "StringValue": "document.processed"},
        },
    )
