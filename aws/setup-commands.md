# AWS Resource Setup (CLI)

Run these once per environment. Region assumed `us-east-1`; replace the
account id `123456789012` throughout with your real account id.

## 1. DynamoDB — operational metadata (`PolicyDocumentProcessing`)

```bash
aws dynamodb create-table \
  --table-name PolicyDocumentProcessing \
  --attribute-definitions AttributeName=document_id,AttributeType=S \
  --key-schema AttributeName=document_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

`PAY_PER_REQUEST` keeps this Free-Tier friendly for low POC volume (no
provisioned capacity to pay for while idle).

## 2. SNS — completion notifications

```bash
aws sns create-topic --name policy-document-notifications

aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:123456789012:policy-document-notifications \
  --protocol email \
  --notification-endpoint ops-team@example.com
```

## 3. Lambda — Document Processor

```bash
cd aws/lambda/document_processor
pip install -r requirements.txt -t package
cp handler.py package/
cd package && zip -r ../function.zip . && cd ..

aws iam create-role \
  --role-name DocumentProcessorLambdaRole \
  --assume-role-policy-document file://../../iam/lambda-trust-policy.json

aws iam put-role-policy \
  --role-name DocumentProcessorLambdaRole \
  --policy-name DocumentProcessorPolicy \
  --policy-document file://../../iam/document-processor-lambda-policy.json

aws lambda create-function \
  --function-name policy-document-processor \
  --runtime python3.12 \
  --role arn:aws:iam::123456789012:role/DocumentProcessorLambdaRole \
  --handler handler.handler \
  --zip-file fileb://function.zip \
  --timeout 30 \
  --memory-size 256 \
  --environment "Variables={DYNAMODB_TABLE_NAME=PolicyDocumentProcessing,SNS_TOPIC_ARN=arn:aws:sns:us-east-1:123456789012:policy-document-notifications}"
```

## 4. EventBridge rule -> Lambda target

```bash
aws events put-rule --cli-input-json file://aws/eventbridge/rule.json

aws lambda add-permission \
  --function-name policy-document-processor \
  --statement-id AllowEventBridgeInvoke \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:us-east-1:123456789012:rule/policy-document-uploaded-rule
```

## 5. Lambda — Snowflake Loader (SNS-triggered)

```bash
cd aws/lambda/snowflake_loader
pip install -r requirements.txt -t package
cp handler.py package/
cd package && zip -r ../function.zip . && cd ..

aws iam create-role \
  --role-name SnowflakeLoaderLambdaRole \
  --assume-role-policy-document file://../../iam/lambda-trust-policy.json

aws iam put-role-policy \
  --role-name SnowflakeLoaderLambdaRole \
  --policy-name SnowflakeLoaderPolicy \
  --policy-document file://../../iam/snowflake-loader-lambda-policy.json

aws lambda create-function \
  --function-name policy-snowflake-loader \
  --runtime python3.12 \
  --role arn:aws:iam::123456789012:role/SnowflakeLoaderLambdaRole \
  --handler handler.handler \
  --zip-file fileb://function.zip \
  --timeout 30 \
  --memory-size 256 \
  --environment "Variables={DYNAMODB_TABLE_NAME=PolicyDocumentProcessing,SNOWFLAKE_ACCOUNT=xxx,SNOWFLAKE_USER=xxx,SNOWFLAKE_PASSWORD=xxx,SNOWFLAKE_DATABASE=POLICY_INTELLIGENCE,SNOWFLAKE_SCHEMA=RAW,SNOWFLAKE_WAREHOUSE=POLICY_WH}"

aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:123456789012:policy-document-notifications \
  --protocol lambda \
  --notification-endpoint arn:aws:lambda:us-east-1:123456789012:function:policy-snowflake-loader

aws lambda add-permission \
  --function-name policy-snowflake-loader \
  --statement-id AllowSNSInvoke \
  --action lambda:InvokeFunction \
  --principal sns.amazonaws.com \
  --source-arn arn:aws:sns:us-east-1:123456789012:policy-document-notifications
```

## 6. CloudWatch — alarm on Lambda errors

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name document-processor-errors \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=policy-document-processor \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --evaluation-periods 1 \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:policy-document-notifications
```

## 7. Trust policy shared by both Lambdas

Save as `aws/iam/lambda-trust-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Principal": { "Service": "lambda.amazonaws.com" }, "Action": "sts:AssumeRole" }
  ]
}
```
