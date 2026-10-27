-- The four tables named explicitly in the diagram's Snowflake Data
-- Warehouse box: RAW_POLICY_DOCUMENTS, CURATED_POLICY, POLICY_DOCUMENT,
-- POLICY_DOCUMENT_STATUS.

USE DATABASE POLICY_INTELLIGENCE;

-- ---------------------------------------------------------------------
-- RAW.RAW_POLICY_DOCUMENTS
-- "Raw documents metadata, Extracted text and attributes, Ingestion timestamps"
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS RAW.RAW_POLICY_DOCUMENTS (
    document_id      STRING NOT NULL,
    customer_id      STRING,
    policy_id        STRING,
    s3_key           STRING,
    document_type    STRING,
    status           STRING,
    extracted_data   VARIANT,
    ingested_at      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- ---------------------------------------------------------------------
-- CURATED.CURATED_POLICY
-- "Cleaned and standardized data, Policy details (type, effective date,
--  etc.), Customer and product information"
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS CURATED.CURATED_POLICY (
    policy_id        STRING NOT NULL,
    customer_id      STRING NOT NULL,
    policy_type      STRING,
    product_name     STRING,
    effective_date   DATE,
    status           STRING,
    updated_at       TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (policy_id)
);

-- ---------------------------------------------------------------------
-- CURATED.POLICY_DOCUMENT
-- "Document level information, Document type/version/status, Links to
--  stored documents"
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS CURATED.POLICY_DOCUMENT (
    document_id      STRING NOT NULL,
    policy_id        STRING,
    customer_id      STRING,
    document_type    STRING,
    version          NUMBER DEFAULT 1,
    status           STRING,
    s3_key           STRING,
    updated_at       TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (document_id)
);

-- ---------------------------------------------------------------------
-- RAW.POLICY_DOCUMENT_STATUS
-- "Processing history, Status updates and timestamps, Error details (if any)"
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS RAW.POLICY_DOCUMENT_STATUS (
    document_id      STRING NOT NULL,
    status           STRING NOT NULL,
    event_timestamp  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    error_details    STRING
);
