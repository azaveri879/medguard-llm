#!/bin/bash
# Download MIMIC-IV notes from S3 and extract for evaluation

set -e

S3_BASE="s3://arn:aws:s3:us-east-1:724665945834:accesspoint/mimiciv-v3-1-01/mimiciv/3.1"
REGION="us-east-1"
OUTPUT_DIR="datasets"
NUM_NOTES="${1:-100}"

echo "=========================================="
echo "Downloading MIMIC-IV Notes"
echo "=========================================="
echo ""

# Find note file in S3
echo "Locating note.csv.gz in S3..."
NOTE_S3_PATH=$(aws s3 ls "$S3_BASE/" --recursive --region "$REGION" 2>/dev/null | grep -i "note.csv.gz" | head -1 | awk '{print $4}')

if [ -z "$NOTE_S3_PATH" ]; then
    echo "❌ Could not find note.csv.gz in S3"
    echo "Trying alternative path..."
    NOTE_S3_PATH="note/note.csv.gz"
fi

FULL_S3_PATH="$S3_BASE/$NOTE_S3_PATH"
echo "S3 Path: $FULL_S3_PATH"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Download note file
echo "Downloading note.csv.gz..."
aws s3 cp "$FULL_S3_PATH" "$OUTPUT_DIR/note.csv.gz" --region "$REGION"

if [ ! -f "$OUTPUT_DIR/note.csv.gz" ]; then
    echo "❌ Download failed"
    exit 1
fi

FILE_SIZE=$(du -h "$OUTPUT_DIR/note.csv.gz" | cut -f1)
echo "✅ Downloaded: $OUTPUT_DIR/note.csv.gz ($FILE_SIZE)"
echo ""

# Extract notes
echo "Extracting $NUM_NOTES notes..."
python3 prepare_mimic.py \
    --input "$OUTPUT_DIR/note.csv.gz" \
    --output "$OUTPUT_DIR/mimic_notes.csv" \
    --format csv \
    --limit "$NUM_NOTES"

if [ -f "$OUTPUT_DIR/mimic_notes.csv" ]; then
    NOTE_COUNT=$(wc -l < "$OUTPUT_DIR/mimic_notes.csv")
    echo "✅ Extracted $NOTE_COUNT notes to $OUTPUT_DIR/mimic_notes.csv"
else
    echo "❌ Extraction failed"
    exit 1
fi

echo ""
echo "=========================================="
echo "Ready for Evaluation"
echo "=========================================="
echo ""
echo "Run MIMIC evaluation:"
echo "  python3 mimic_eval.py \\"
echo "    --mimic-path $OUTPUT_DIR/mimic_notes.csv \\"
echo "    --medguard-url https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/v1/chat \\"
echo "    --task problem_list \\"
echo "    --num-notes $NUM_NOTES \\"
echo "    --num-injections $((NUM_NOTES / 2))"
echo ""
