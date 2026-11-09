#!/bin/bash
# Run all MedGuard test suites

set -e

echo "=========================================="
echo "MedGuard Test Suite Runner"
echo "=========================================="
echo ""

# Check if Python dependencies are installed
if ! python3 -c "import requests" 2>/dev/null; then
    echo "Installing Python dependencies..."
    pip3 install -r requirements.txt
fi

# Set API URL (can be overridden)
export API_URL="${API_URL:-https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/v1/chat}"

echo "API URL: $API_URL"
echo ""

# Run PHI redaction tests
echo "=========================================="
echo "1. PHI Redaction Tests"
echo "=========================================="
python3 test_phi_redaction.py
PHI_EXIT=$?

echo ""
echo "=========================================="
echo "2. Injection Attack Tests"
echo "=========================================="
python3 test_injection_attacks.py
INJECTION_EXIT=$?

# Summary
echo ""
echo "=========================================="
echo "TEST SUMMARY"
echo "=========================================="
if [ $PHI_EXIT -eq 0 ]; then
    echo "✅ PHI Redaction Tests: PASSED"
else
    echo "❌ PHI Redaction Tests: FAILED"
fi

if [ $INJECTION_EXIT -eq 0 ]; then
    echo "✅ Injection Attack Tests: PASSED"
else
    echo "❌ Injection Attack Tests: FAILED"
fi

if [ $PHI_EXIT -eq 0 ] && [ $INJECTION_EXIT -eq 0 ]; then
    echo ""
    echo "🎉 All tests passed!"
    exit 0
else
    echo ""
    echo "⚠️  Some tests failed. Review output above."
    exit 1
fi
