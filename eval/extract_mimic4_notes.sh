#!/bin/bash
# Quick script to extract MIMIC-IV notes from downloaded data

set -e

# Configuration
MIMIC_DIR="${1:-DESTINATION}"  # Directory where MIMIC-IV was downloaded
OUTPUT_DIR="${2:-datasets}"    # Output directory
NUM_NOTES="${3:-100}"          # Number of notes to extract

echo "=========================================="
echo "Extracting MIMIC-IV Notes"
echo "=========================================="
echo ""
echo "MIMIC Directory: $MIMIC_DIR"
echo "Output Directory: $OUTPUT_DIR"
echo "Number of Notes: $NUM_NOTES"
echo ""

# Check if note file exists
NOTE_FILE="$MIMIC_DIR/note/note.csv.gz"

if [ ! -f "$NOTE_FILE" ]; then
    echo "Looking for note.csv.gz in alternative locations..."
    # Try alternative paths
    if [ -f "$MIMIC_DIR/mimiciv/note/note.csv.gz" ]; then
        NOTE_FILE="$MIMIC_DIR/mimiciv/note/note.csv.gz"
    elif [ -f "$MIMIC_DIR/mimiciv/3.1/note/note.csv.gz" ]; then
        NOTE_FILE="$MIMIC_DIR/mimiciv/3.1/note/note.csv.gz"
    else
        echo "Error: Could not find note.csv.gz"
        echo "Please specify the correct MIMIC directory path"
        exit 1
    fi
fi

echo "Found notes file: $NOTE_FILE"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Extract notes using Python script
python3 prepare_mimic.py \
    --input "$MIMIC_DIR" \
    --output "$OUTPUT_DIR/mimic_notes.csv" \
    --format mimic4_csv \
    --limit "$NUM_NOTES"

echo ""
echo "=========================================="
echo "Extraction Complete!"
echo "=========================================="
echo ""
echo "Notes saved to: $OUTPUT_DIR/mimic_notes.csv"
echo ""
echo "Next step: Run MIMIC evaluation"
echo "  python3 mimic_eval.py \\"
echo "    --mimic-path $OUTPUT_DIR/mimic_notes.csv \\"
echo "    --medguard-url https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/v1/chat \\"
echo "    --task problem_list \\"
echo "    --num-notes $NUM_NOTES"
echo ""
