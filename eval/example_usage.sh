#!/bin/bash
# Example usage of MedGuard evaluation harness

set -e

# Configuration
MEDGUARD_URL="${MEDGUARD_URL:-https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/v1/chat}"
BASELINE_MODEL="${BASELINE_MODEL:-us.anthropic.claude-haiku-4-5-20251001-v1:0}"
OUTPUT_DIR="${OUTPUT_DIR:-results}"

echo "=========================================="
echo "MedGuard Evaluation Harness"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  MedGuard URL: $MEDGUARD_URL"
echo "  Baseline Model: $BASELINE_MODEL"
echo "  Output Directory: $OUTPUT_DIR"
echo ""

# Check dependencies
echo "Checking dependencies..."
python3 -c "import boto3, requests" 2>/dev/null || {
    echo "Installing dependencies..."
    pip3 install -r requirements.txt
}

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Run baseline comparison
echo ""
echo "=========================================="
echo "Running Baseline Comparison"
echo "=========================================="
python3 run_eval.py \
    --medguard-url "$MEDGUARD_URL" \
    --baseline-model "$BASELINE_MODEL" \
    --mode baseline \
    --test-type all \
    --output-dir "$OUTPUT_DIR"

# Generate tables
echo ""
echo "=========================================="
echo "Generating Publication Tables"
echo "=========================================="
python3 generate_tables.py \
    --results "$OUTPUT_DIR/baseline_comparison_results.json" \
    --output-dir "$OUTPUT_DIR" \
    --format both

echo ""
echo "=========================================="
echo "Evaluation Complete!"
echo "=========================================="
echo ""
echo "Results saved to: $OUTPUT_DIR/"
echo ""
echo "Generated files:"
echo "  - baseline_comparison_results.json (raw results)"
echo "  - baseline_comparison.csv (CSV table)"
echo "  - baseline_comparison.tex (LaTeX table for paper)"
echo "  - table_phi_leakage.tex (PHI metrics table)"
echo "  - table_injection_asr.tex (Injection ASR table)"
echo "  - table_latency.tex (Latency comparison table)"
echo ""
