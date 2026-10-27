-- "Analytics & Search-Ready Views - SQL queries for reporting, Search-ready
-- datasets, Business intelligence and insights" -- feeds the Business
-- Outcomes column (Policy Lookup, Processing Dashboard, Audit & Compliance).

USE DATABASE POLICY_INTELLIGENCE;

-- Backs GET /api/search
CREATE OR REPLACE VIEW ANALYTICS.POLICY_DOCUMENT_SEARCH_VIEW AS
SELECT
    d.document_id,
    d.policy_id,
    d.customer_id,
    d.document_type,
    d.status,
    d.updated_at,
    CONCAT_WS(' ', d.document_id, d.policy_id, d.customer_id, d.document_type, d.status) AS search_text
FROM CURATED.POLICY_DOCUMENT d;

-- Backs the Processing Dashboard business outcome
CREATE OR REPLACE VIEW ANALYTICS.PROCESSING_DASHBOARD_VIEW AS
SELECT
    document_type,
    status,
    COUNT(*) AS document_count,
    DATE_TRUNC('day', updated_at) AS processing_day
FROM CURATED.POLICY_DOCUMENT
GROUP BY document_type, status, DATE_TRUNC('day', updated_at)
ORDER BY processing_day DESC;

-- Backs Audit & Compliance Reporting
CREATE OR REPLACE VIEW ANALYTICS.AUDIT_TRAIL_VIEW AS
SELECT
    document_id,
    status,
    event_timestamp,
    error_details
FROM RAW.POLICY_DOCUMENT_STATUS
ORDER BY document_id, event_timestamp;
