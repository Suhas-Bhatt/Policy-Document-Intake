import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret")

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret")
    JWT_EXPIRY_MINUTES = int(os.getenv("JWT_EXPIRY_MINUTES", "60"))

    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    API_GATEWAY_UPLOAD_URL = os.getenv("API_GATEWAY_UPLOAD_URL", "")
    S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "policy-documentz")
    DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "PolicyDocumentProcessing")
    SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN", "")

    SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT", "")
    SNOWFLAKE_USER = os.getenv("SNOWFLAKE_USER", "")
    SNOWFLAKE_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD", "")
    SNOWFLAKE_ROLE = os.getenv("SNOWFLAKE_ROLE", "SYSADMIN")
    SNOWFLAKE_WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE", "POLICY_WH")
    SNOWFLAKE_DATABASE = os.getenv("SNOWFLAKE_DATABASE", "POLICY_INTELLIGENCE")
    SNOWFLAKE_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "CURATED")

    MAX_CONTENT_LENGTH = 15 * 1024 * 1024  # 15 MB upload cap
    ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
