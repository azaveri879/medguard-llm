#!/bin/bash
# Quick-start evaluation script for MedGuard

set -e

# MedGuard API URL
API_URL="https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/v1/chat"

# Configuration
BASELINE_MODEL="us.anthropic.claude-haiku-4-5-20251001-v1:0"
OUTPUT_DIR="results"

echo "=========================================="
echo "MedGuard Evaluation"
echo "=========================================="
echo ""
echo "API URL: $API_URL"
echo "Baseline Model: $BASELINE_MODEL"
echo "Output Directory: $OUTPUT_DIR"
echo ""

# Check dependencies
echo "Checking dependencies..."
if ! python3 -c "import boto3, requests" 2>/dev/null; then
    echo "Installing dependencies..."
    pip3 install -r requirements.txt
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Run baseline comparison
echo ""
echo "=========================================="
echo "Running Baseline Comparison"
echo "=========================================="
python3 run_eval.py \
    --medguard-url "$API_URL" \
    --baseline-model "$BASELINE_MODEL" \
    --mode baseline \
    --test-type all \
    --output-dir "$OUTPUT_DIR"

# Generate tables
echo ""
echo "=========================================="
echo "Generating Publication Tables"
echo "=========================================="
if [ -f "$OUTPUT_DIR/baseline_comparison_results.json" ]; then
    python3 generate_tables.py \
        --results "$OUTPUT_DIR/baseline_comparison_results.json" \
        --output-dir "$OUTPUT_DIR" \
        --format both
else
    echo "Warning: Results file not found. Skipping table generation."
fi

echo ""
echo "=========================================="
echo "Evaluation Complete!"
echo "=========================================="
echo ""
echo "Results saved to: $OUTPUT_DIR/"
echo ""
echo "To view results:"
echo "  cat $OUTPUT_DIR/baseline_comparison.csv"
echo "  cat $OUTPUT_DIR/baseline_comparison.tex"
echo ""
