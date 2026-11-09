#!/bin/bash
# Script to review MedGuard audit logs

BUCKET="${AUDIT_BUCKET:-medguardstack-auditbucketb01e0ae8-x1f2sv7sqpug}"
TABLE="${AUDIT_TABLE:-MedGuardStack-AuditTableB07F8EEB-9RJ529G9YEZD}"

echo "=== MedGuard Audit Log Review ==="
echo ""

# List recent audit files in S3
echo "Recent audit files in S3:"
aws s3 ls "s3://${BUCKET}/events/" --recursive | tail -10
echo ""

# Get latest audit file
LATEST_FILE=$(aws s3 ls "s3://${BUCKET}/events/" --recursive | sort | tail -1 | awk '{print $4}')
if [ -n "$LATEST_FILE" ]; then
    echo "Latest audit record:"
    aws s3 cp "s3://${BUCKET}/${LATEST_FILE}" - 2>/dev/null | jq '.'
    echo ""
fi

# Query DynamoDB for recent requests
echo "Recent requests from DynamoDB (last 5):"
aws dynamodb scan \
  --table-name "$TABLE" \
  --limit 5 \
  --query 'Items[*].{request_id:request_id.S, user_id:user_id.S, role:role.S, injection_score:injection_score.N, model_id:model_id.S, timestamp:ts.N}' \
  --output json | jq '.'
echo ""

# Summary statistics
echo "Summary Statistics:"
TOTAL=$(aws dynamodb scan --table-name "$TABLE" --select COUNT --output text | grep -o '[0-9]*')
echo "Total requests: $TOTAL"

