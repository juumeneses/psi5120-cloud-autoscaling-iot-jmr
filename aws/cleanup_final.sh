#!/usr/bin/env bash
# Delete only the explicitly named final-project resources after evidence review.
set -euo pipefail
REGION="us-east-1"
THING="psi5120-final-jmr-device01"
TABLE="psi5120-final-jmr-telemetry"
FUNCTION="psi5120-final-jmr-ingest"
ROLE="psi5120-final-jmr-lambda-role"
POLICY="psi5120-final-jmr-device-policy"
RULE="psi5120_final_jmr_telemetry_to_lambda"

# Certificates must be detached and deactivated before deletion.
for ARN in $(aws iot list-thing-principals --region "$REGION" --thing-name "$THING" --query principals[] --output text 2>/dev/null); do
  aws iot detach-policy --region "$REGION" --policy-name "$POLICY" --target "$ARN" || true
  aws iot detach-thing-principal --region "$REGION" --thing-name "$THING" --principal "$ARN" || true
  ID="${ARN##*/}"
  aws iot update-certificate --region "$REGION" --certificate-id "$ID" --new-status INACTIVE || true
  aws iot delete-certificate --region "$REGION" --certificate-id "$ID" || true
done
aws iot delete-topic-rule --region "$REGION" --rule-name "$RULE" || true
aws iot delete-policy --region "$REGION" --policy-name "$POLICY" || true
aws iot delete-thing --region "$REGION" --thing-name "$THING" || true
aws lambda delete-function --region "$REGION" --function-name "$FUNCTION" || true
aws dynamodb delete-table --region "$REGION" --table-name "$TABLE" || true
aws iam delete-role-policy --role-name "$ROLE" --policy-name "psi5120-final-jmr-minimum" || true
aws iam delete-role --role-name "$ROLE" || true
rm -rf "$(cd "$(dirname "$0")/.." && pwd)/iot/certs"
