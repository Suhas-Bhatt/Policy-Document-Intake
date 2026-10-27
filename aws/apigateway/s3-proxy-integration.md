# API Gateway -> S3 Proxy Integration

Diagram path: `Flask --"Validated Document"--> Amazon API Gateway --> Amazon S3`.

API Gateway can write directly to S3 using an AWS-service proxy integration,
with no Lambda in between for the upload itself. This is the free-tier
friendly, "serverless-first" way to implement that arrow.

## 1. Create the S3 bucket

```bash
aws s3api create-bucket \
  --bucket policy-documentz \
  --region us-east-1

aws s3api put-bucket-notification-configuration \
  --bucket policy-documentz \
  --notification-configuration '{"EventBridgeConfiguration": {}}'
```

The second command turns on the bucket's EventBridge notifications, which is
what lets `aws/eventbridge/rule.json` react to new objects (S3 -> EventBridge
in the diagram) without any extra glue code.

## 2. IAM role for API Gateway to write to S3

`aws/iam/apigateway-s3-role-policy.json` (see file in this folder) grants
`s3:PutObject` on `arn:aws:s3:::policy-documentz/incoming/*` only.

```bash
aws iam create-role \
  --role-name ApiGatewayS3ProxyRole \
  --assume-role-policy-document file://aws/iam/apigateway-trust-policy.json

aws iam put-role-policy \
  --role-name ApiGatewayS3ProxyRole \
  --policy-name ApiGatewayS3PutPolicy \
  --policy-document file://aws/iam/apigateway-s3-role-policy.json
```

## 3. Create the REST API with an S3 proxy integration

```bash
API_ID=$(aws apigateway create-rest-api --name policy-document-upload-api \
  --query 'id' --output text)

PARENT_ID=$(aws apigateway get-resources --rest-api-id $API_ID \
  --query 'items[0].id' --output text)

# resource: /documents/{proxy+}
RESOURCE_ID=$(aws apigateway create-resource --rest-api-id $API_ID \
  --parent-id $PARENT_ID --path-part "documents" --query 'id' --output text)

PROXY_ID=$(aws apigateway create-resource --rest-api-id $API_ID \
  --parent-id $RESOURCE_ID --path-part "{proxy+}" --query 'id' --output text)

aws apigateway put-method --rest-api-id $API_ID --resource-id $PROXY_ID \
  --http-method PUT --authorization-type NONE \
  --request-parameters "method.request.path.proxy=true"

aws apigateway put-integration --rest-api-id $API_ID --resource-id $PROXY_ID \
  --http-method PUT --type AWS \
  --integration-http-method PUT \
  --uri "arn:aws:apigateway:us-east-1:s3:path/policy-documentz/{proxy}" \
  --credentials arn:aws:iam::312816040566:role/ApiGatewayS3ProxyRole \
  --request-parameters "integration.request.path.proxy=method.request.path.proxy"

aws apigateway create-deployment --rest-api-id $API_ID --stage-name prod
```

Resulting endpoint (put this in `.env` as `API_GATEWAY_UPLOAD_URL`, without
the trailing object key -- `aws_service.py` appends `/{object_key}`):

```
https://<API_ID>.execute-api.us-east-1.amazonaws.com/prod/documents
```

## 4. Verify

```bash
curl -X PUT "https://<API_ID>.execute-api.us-east-1.amazonaws.com/prod/documents/incoming/test/test.pdf" \
  --data-binary @sample.pdf \
  -H "Content-Type: application/pdf"

aws s3 ls s3://policy-documentz/incoming/test/
```
