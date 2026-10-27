-- Snowflake Data Platform setup
-- Diagram: "Centralized policy document analytics"

CREATE DATABASE IF NOT EXISTS POLICY_INTELLIGENCE;

USE DATABASE POLICY_INTELLIGENCE;

-- RAW_POLICY_DOCUMENTS and POLICY_DOCUMENT_STATUS are landing/history tables
CREATE SCHEMA IF NOT EXISTS RAW;

-- CURATED_POLICY and POLICY_DOCUMENT are the cleaned, query-ready layer
CREATE SCHEMA IF NOT EXISTS CURATED;

-- Analytics & Search-Ready Views
CREATE SCHEMA IF NOT EXISTS ANALYTICS;

CREATE WAREHOUSE IF NOT EXISTS POLICY_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;
-- AUTO_SUSPEND=60s / AUTO_RESUME keep this "Free-Tier / cost-efficient"
-- per the diagram's callout box: no compute billed while idle.
