#!/bin/bash
# Test Bedrock model access directly

MODEL_ID="${1:-us.anthropic.claude-haiku-4-5-20251001-v1:0}"
REGION="${2:-us-east-1}"

echo "Testing Bedrock model access for: $MODEL_ID"
echo "Region: $REGION"
echo ""

# Test using bedrock-runtime
echo "Attempting to invoke model..."
BODY=$(echo '{
  "anthropic_version": "bedrock-2023-05-31",
  "max_tokens": 100,
  "messages": [{"role": "user", "content": "Say hello"}]
}' | base64)

aws bedrock-runtime invoke-model \
  --model-id "$MODEL_ID" \
  --region "$REGION" \
  --body "$BODY" \
  /tmp/bedrock-response.json 2>&1

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Success! Model is accessible."
    echo "Response:"
    cat /tmp/bedrock-response.json | jq -r '.content[0].text' 2>/dev/null || cat /tmp/bedrock-response.json
    rm -f /tmp/bedrock-response.json
else
    echo ""
    echo "❌ Model access failed. This usually means:"
    echo "1. The model requires AWS Marketplace subscription"
    echo "2. You need to subscribe via AWS Console: https://console.aws.amazon.com/bedrock/"
    echo "3. Or wait 5 minutes if you just subscribed"
    echo ""
    echo "To subscribe:"
    echo "1. Go to: https://console.aws.amazon.com/bedrock/"
    echo "2. Click 'Model catalog' in the left sidebar"
    echo "3. Find 'Claude Haiku 4.5'"
    echo "4. Click 'Subscribe' (if available)"
    echo "5. Wait a few minutes for activation"
fi

