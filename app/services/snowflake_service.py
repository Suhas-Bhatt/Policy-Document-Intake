"""
Snowflake integration service.

Implements the read side of the diagram's "Business Outcomes" column
(Policy Lookup, Document Status history, Processing Dashboard, Audit &
Compliance Reporting) by querying the curated tables / analytics views
defined in sql/02_tables.sql and sql/03_views.sql.
"""
from datetime import datetime, timedelta

from flask import current_app

from app.utils.errors import UpstreamServiceError

try:
    import snowflake.connector

    SNOWFLAKE_AVAILABLE = True
except ImportError:
    # See requirements-snowflake.txt: the connector is installed separately
    # because its `cffi` dependency may lack a prebuilt wheel on very new
    # Python versions. Routes that need Snowflake fail with a clear 502
    # instead of the whole app refusing to start.
    SNOWFLAKE_AVAILABLE = False


def _require_snowflake():
    if not SNOWFLAKE_AVAILABLE:
        raise UpstreamServiceError(
            "snowflake-connector-python is not installed. "
            "Run: pip install -r requirements-snowflake.txt",
            code="snowflake_unavailable",
        )


def _get_connection():
    _require_snowflake()
    cfg = current_app.config
    return snowflake.connector.connect(
        account=cfg["SNOWFLAKE_ACCOUNT"],
        user=cfg["SNOWFLAKE_USER"],
        password=cfg["SNOWFLAKE_PASSWORD"],
        role=cfg["SNOWFLAKE_ROLE"],
        warehouse=cfg["SNOWFLAKE_WAREHOUSE"],
        database=cfg["SNOWFLAKE_DATABASE"],
        schema=cfg["SNOWFLAKE_SCHEMA"],
    )


def _query(sql, params=None):
    conn = _get_connection()
    try:
        cur = conn.cursor(snowflake.connector.DictCursor)
        cur.execute(sql, params or {})
        return cur.fetchall()
    finally:
        conn.close()


def get_policy_by_id(policy_id):
    sql = """
        SELECT policy_id, customer_id, policy_type, effective_date,
               status, product_name, updated_at
        FROM CURATED.CURATED_POLICY
        WHERE policy_id = %(policy_id)s
    """
    rows = _query(sql, {"policy_id": policy_id})
    return rows[0] if rows else None


def search_policies_and_documents(query_text, limit=25):
    sql = """
        SELECT document_id, policy_id, customer_id, document_type,
               status, search_text, updated_at
        FROM ANALYTICS.POLICY_DOCUMENT_SEARCH_VIEW
        WHERE search_text ILIKE %(pattern)s
        ORDER BY updated_at DESC
        LIMIT %(limit)s
    """
    return _query(sql, {"pattern": f"%{query_text}%", "limit": limit})


def bulk_upsert_policy_documents(rows):
    """
    Loads CSV rows (columns: document_id, policy_id, customer_id, policy_type,
    product_name, effective_date, status, document_type, version, s3_key,
    updated_at) into CURATED_POLICY and POLICY_DOCUMENT via MERGE, so
    re-uploading the same CSV is safe (upsert by policy_id / document_id).
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()
        for row in rows:
            cur.execute(
                """
                MERGE INTO CURATED.CURATED_POLICY tgt
                USING (SELECT %(policy_id)s AS policy_id) src
                ON tgt.policy_id = src.policy_id
                WHEN MATCHED THEN UPDATE SET
                    customer_id = %(customer_id)s,
                    policy_type = %(policy_type)s,
                    product_name = %(product_name)s,
                    effective_date = %(effective_date)s,
                    status = %(status)s,
                    updated_at = CURRENT_TIMESTAMP()
                WHEN NOT MATCHED THEN INSERT
                    (policy_id, customer_id, policy_type, product_name, effective_date, status, updated_at)
                VALUES
                    (%(policy_id)s, %(customer_id)s, %(policy_type)s, %(product_name)s,
                     %(effective_date)s, %(status)s, CURRENT_TIMESTAMP())
                """,
                row,
            )
            cur.execute(
                """
                MERGE INTO CURATED.POLICY_DOCUMENT tgt
                USING (SELECT %(document_id)s AS document_id) src
                ON tgt.document_id = src.document_id
                WHEN MATCHED THEN UPDATE SET
                    policy_id = %(policy_id)s,
                    customer_id = %(customer_id)s,
                    document_type = %(document_type)s,
                    version = %(version)s,
                    status = %(status)s,
                    s3_key = %(s3_key)s,
                    updated_at = CURRENT_TIMESTAMP()
                WHEN NOT MATCHED THEN INSERT
                    (document_id, policy_id, customer_id, document_type, version, status, s3_key, updated_at)
                VALUES
                    (%(document_id)s, %(policy_id)s, %(customer_id)s, %(document_type)s,
                     %(version)s, %(status)s, %(s3_key)s, CURRENT_TIMESTAMP())
                """,
                row,
            )
        conn.commit()
    finally:
        conn.close()


def _dummy_processing_dashboard_metrics():
    today = datetime.utcnow().date()
    samples = [
        ("AUTO", "PROCESSED", 14, 0),
        ("AUTO", "FAILED", 2, 0),
        ("HOME", "PROCESSED", 9, 0),
        ("HOME", "UPLOADED", 3, 1),
        ("LIFE", "PROCESSED", 6, 1),
        ("LIFE", "FAILED", 1, 2),
        ("HEALTH", "UPLOADED", 5, 2),
        ("HEALTH", "PROCESSED", 11, 3),
    ]
    return [
        {
            "DOCUMENT_TYPE": doc_type,
            "STATUS": status,
            "DOCUMENT_COUNT": count,
            "PROCESSING_DAY": (today - timedelta(days=days_ago)).isoformat(),
        }
        for doc_type, status, count, days_ago in samples
    ]


def get_processing_dashboard_metrics():
    if not SNOWFLAKE_AVAILABLE:
        return _dummy_processing_dashboard_metrics()
    sql = "SELECT * FROM ANALYTICS.PROCESSING_DASHBOARD_VIEW"
    return _query(sql)


def get_audit_trail(document_id):
    sql = """
        SELECT document_id, status, event_timestamp, error_details
        FROM RAW.POLICY_DOCUMENT_STATUS
        WHERE document_id = %(document_id)s
        ORDER BY event_timestamp ASC
    """
    return _query(sql, {"document_id": document_id})
