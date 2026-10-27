"""
AWS Lambda: Snowflake Loader

Diagram role: "Data Ingestion - Snowflake Connector (or AWS Glue) - Load
processed data from DynamoDB/S3 into Snowflake", fed by the DynamoDB -->
Snowflake "Processed Data" arrow. The diagram's SNS box says it "Trigger[s]
downstream actions" -- this Lambda is that downstream action: it subscribes
to the same SNS completion topic the Document Processor Lambda publishes to,
reads the full item back from DynamoDB, and loads it into Snowflake's
RAW_POLICY_DOCUMENTS table, then merges it into CURATED_POLICY.

Implementation Assumption: AWS Glue is not used for this POC (it is not
Free-Tier eligible and is heavier than a low-volume POC needs); the
"Snowflake Connector" option in the diagram is implemented directly via
snowflake-connector-python inside this Lambda instead.
"""
import json
import logging
import os

import boto3
import snowflake.connector

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]

SNOWFLAKE_CONN_PARAMS = dict(
    account=os.environ["SNOWFLAKE_ACCOUNT"],
    user=os.environ["SNOWFLAKE_USER"],
    password=os.environ["SNOWFLAKE_PASSWORD"],
    role=os.environ.get("SNOWFLAKE_ROLE", "SYSADMIN"),
    warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "POLICY_WH"),
    database=os.environ.get("SNOWFLAKE_DATABASE", "POLICY_INTELLIGENCE"),
    schema=os.environ.get("SNOWFLAKE_SCHEMA", "RAW"),
)


def handler(event, context):
    for record in event.get("Records", []):
        message = json.loads(record["Sns"]["Message"])
        document_id = message["document_id"]
        logger.info("loading_start document_id=%s", document_id)

        item = _get_dynamodb_item(document_id)
        if not item:
            logger.error("dynamodb_item_missing document_id=%s", document_id)
            continue

        _load_raw(item)
        _merge_curated(item)
        logger.info("loading_complete document_id=%s", document_id)

    return {"statusCode": 200}


def _get_dynamodb_item(document_id):
    table = dynamodb.Table(TABLE_NAME)
    return table.get_item(Key={"document_id": document_id}).get("Item")


def _load_raw(item):
    conn = snowflake.connector.connect(**SNOWFLAKE_CONN_PARAMS)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO RAW.RAW_POLICY_DOCUMENTS
                (document_id, customer_id, policy_id, s3_key, document_type,
                 status, extracted_data, ingested_at)
            SELECT %(document_id)s, %(customer_id)s, %(policy_id)s, %(s3_key)s,
                   %(document_type)s, %(status)s, PARSE_JSON(%(extracted_data)s),
                   CURRENT_TIMESTAMP()
            """,
            {
                "document_id": item["document_id"],
                "customer_id": item.get("customer_id"),
                "policy_id": item.get("policy_id"),
                "s3_key": item.get("s3_key"),
                "document_type": item.get("document_type"),
                "status": item.get("status"),
                "extracted_data": json.dumps(item.get("extracted_data", {})),
            },
        )
    finally:
        conn.close()


def _merge_curated(item):
    policy_id = item.get("policy_id") or item["document_id"]
    conn = snowflake.connector.connect(**SNOWFLAKE_CONN_PARAMS)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            MERGE INTO CURATED.CURATED_POLICY tgt
            USING (
                SELECT %(policy_id)s AS policy_id,
                       %(customer_id)s AS customer_id,
                       %(document_type)s AS policy_type,
                       PARSE_JSON(%(extracted_data)s):effective_date::STRING AS effective_date
            ) src
            ON tgt.policy_id = src.policy_id
            WHEN MATCHED THEN UPDATE SET
                status = 'ACTIVE', updated_at = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN INSERT
                (policy_id, customer_id, policy_type, effective_date, status, updated_at)
            VALUES
                (src.policy_id, src.customer_id, src.policy_type, src.effective_date,
                 'ACTIVE', CURRENT_TIMESTAMP())
            """,
            {
                "policy_id": policy_id,
                "customer_id": item.get("customer_id"),
                "document_type": item.get("document_type"),
                "extracted_data": json.dumps(item.get("extracted_data", {})),
            },
        )

        # Also populate CURATED.POLICY_DOCUMENT so this document shows up in
        # /api/search (backed by ANALYTICS.POLICY_DOCUMENT_SEARCH_VIEW, which
        # reads from this table) -- previously only the bulk-CSV import path
        # wrote here, so single-document uploads never appeared in search.
        cur.execute(
            """
            MERGE INTO CURATED.POLICY_DOCUMENT tgt
            USING (SELECT %(document_id)s AS document_id) src
            ON tgt.document_id = src.document_id
            WHEN MATCHED THEN UPDATE SET
                policy_id = %(policy_id)s,
                customer_id = %(customer_id)s,
                document_type = %(document_type)s,
                status = %(status)s,
                s3_key = %(s3_key)s,
                updated_at = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN INSERT
                (document_id, policy_id, customer_id, document_type, version, status, s3_key, updated_at)
            VALUES
                (%(document_id)s, %(policy_id)s, %(customer_id)s, %(document_type)s,
                 1, %(status)s, %(s3_key)s, CURRENT_TIMESTAMP())
            """,
            {
                "document_id": item["document_id"],
                "policy_id": policy_id,
                "customer_id": item.get("customer_id"),
                "document_type": item.get("document_type"),
                "status": item.get("status"),
                "s3_key": item.get("s3_key"),
            },
        )
    finally:
        conn.close()
