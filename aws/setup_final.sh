#!/usr/bin/env bash
# Provision the final-project AWS backend from AWS CloudShell in us-east-1.
# The script creates only named course resources and stores the private key in
# CloudShell's non-versioned certs directory for the duration of the experiment.
set -euo pipefail

REGION="us-east-1"
THING="psi5120-final-jmr-device01"
TABLE="psi5120-final-jmr-telemetry"
FUNCTION="psi5120-final-jmr-ingest"
ROLE="psi5120-final-jmr-lambda-role"
POLICY="psi5120-final-jmr-device-policy"
RULE="psi5120_final_jmr_telemetry_to_lambda"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# DynamoDB uses the simulated device identifier as partition key and a
# monotonically increasing sequence number as sort key.
if ! aws dynamodb describe-table --region "$REGION" --table-name "$TABLE" >/dev/null 2>&1; then
  aws dynamodb create-table --region "$REGION" --table-name "$TABLE" \
    --attribute-definitions AttributeName=device_id,AttributeType=S AttributeName=sequence,AttributeType=N \
    --key-schema AttributeName=device_id,KeyType=HASH AttributeName=sequence,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST >/dev/null
  aws dynamodb wait table-exists --region "$REGION" --table-name "$TABLE"
fi

# The Lambda role receives only log permissions and PutItem on this table.
if ! aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE" \
    --assume-role-policy-document "file://$REPO_ROOT/aws/lambda-trust-policy.json" >/dev/null
fi
aws iam put-role-policy --role-name "$ROLE" --policy-name "psi5120-final-jmr-minimum" \
  --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"logs:CreateLogGroup\",\"logs:CreateLogStream\",\"logs:PutLogEvents\"],\"Resource\":\"arn:aws:logs:$REGION:$ACCOUNT_ID:*\"},{\"Effect\":\"Allow\",\"Action\":\"dynamodb:PutItem\",\"Resource\":\"arn:aws:dynamodb:$REGION:$ACCOUNT_ID:table/$TABLE\"}]}"

# Package exactly the reviewed handler; boto3 is supplied by Lambda Python.
rm -f /tmp/psi5120-final-lambda.zip
(cd "$REPO_ROOT/iot" && zip -q /tmp/psi5120-final-lambda.zip lambda_function.py)
sleep 10
ROLE_ARN="arn:aws:iam::$ACCOUNT_ID:role/$ROLE"
if aws lambda get-function --region "$REGION" --function-name "$FUNCTION" >/dev/null 2>&1; then
  aws lambda update-function-code --region "$REGION" --function-name "$FUNCTION" \
    --zip-file fileb:///tmp/psi5120-final-lambda.zip >/dev/null
else
  aws lambda create-function --region "$REGION" --function-name "$FUNCTION" \
    --runtime python3.12 --handler lambda_function.lambda_handler --role "$ROLE_ARN" \
    --environment "Variables={TELEMETRY_TABLE=$TABLE}" \
    --zip-file fileb:///tmp/psi5120-final-lambda.zip >/dev/null
fi
aws lambda wait function-active-v2 --region "$REGION" --function-name "$FUNCTION"

# Connect the telemetry topic to Lambda and authorize only this IoT rule.
FUNCTION_ARN="arn:aws:lambda:$REGION:$ACCOUNT_ID:function:$FUNCTION"
aws iot create-topic-rule --region "$REGION" --rule-name "$RULE" \
  --topic-rule-payload "{\"sql\":\"SELECT * FROM 'psi5120/final/$THING/telemetry'\",\"awsIotSqlVersion\":\"2016-03-23\",\"actions\":[{\"lambda\":{\"functionArn\":\"$FUNCTION_ARN\"}}],\"ruleDisabled\":false}"
aws lambda add-permission --region "$REGION" --function-name "$FUNCTION" \
  --statement-id "psi5120-final-iot-rule" --action lambda:InvokeFunction \
  --principal iot.amazonaws.com \
  --source-arn "arn:aws:iot:$REGION:$ACCOUNT_ID:rule/$RULE" >/dev/null 2>&1 || true

# Create the Thing and a least-privilege policy before issuing its certificate.
aws iot create-thing --region "$REGION" --thing-name "$THING" >/dev/null 2>&1 || true
sed "s/ACCOUNT_ID/$ACCOUNT_ID/g" "$REPO_ROOT/aws/iot-policy.json" >/tmp/psi5120-final-iot-policy.json
aws iot create-policy --region "$REGION" --policy-name "$POLICY" \
  --policy-document file:///tmp/psi5120-final-iot-policy.json >/dev/null 2>&1 || true

mkdir -p "$REPO_ROOT/iot/certs"
chmod 700 "$REPO_ROOT/iot/certs"
CERTIFICATE_ARN="$(aws iot create-keys-and-certificate --region "$REGION" --set-as-active \
  --certificate-pem-outfile "$REPO_ROOT/iot/certs/device.pem.crt" \
  --public-key-outfile "$REPO_ROOT/iot/certs/public.pem.key" \
  --private-key-outfile "$REPO_ROOT/iot/certs/private.pem.key" \
  --query certificateArn --output text)"
chmod 600 "$REPO_ROOT/iot/certs/private.pem.key"
curl -fsS https://www.amazontrust.com/repository/AmazonRootCA1.pem \
  -o "$REPO_ROOT/iot/certs/AmazonRootCA1.pem"
aws iot attach-policy --region "$REGION" --policy-name "$POLICY" --target "$CERTIFICATE_ARN"
aws iot attach-thing-principal --region "$REGION" --thing-name "$THING" --principal "$CERTIFICATE_ARN"
aws iot describe-endpoint --region "$REGION" --endpoint-type iot:Data-ATS --query endpointAddress --output text
printf 'Provisioning complete. Certificate ARN: %s\n' "$CERTIFICATE_ARN"
