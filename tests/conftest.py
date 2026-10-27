import boto3
import pytest
from moto import mock_aws

from app import create_app
from app.config import Config


class TestConfig(Config):
    TESTING = True
    AWS_REGION = "us-east-1"
    DYNAMODB_TABLE_NAME = "PolicyDocumentProcessing"
    API_GATEWAY_UPLOAD_URL = "https://fake-api-gateway.example.com/prod/documents"
    JWT_SECRET_KEY = "test-secret"


@pytest.fixture
def aws_credentials(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture
def dynamodb_table(aws_credentials):
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName=TestConfig.DYNAMODB_TABLE_NAME,
            KeySchema=[{"AttributeName": "document_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "document_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield


@pytest.fixture
def app(dynamodb_table):
    application = create_app(TestConfig)
    application.config.update(TESTING=True)
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_header(client):
    response = client.post("/api/auth/login", json={"username": "alice", "role": "agent"})
    token = response.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
