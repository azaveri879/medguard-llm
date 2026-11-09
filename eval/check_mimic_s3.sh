#!/bin/bash
# Check if MIMIC-IV notes exist in S3 before extraction

set -e

S3_BASE="s3://arn:aws:s3:us-east-1:724665945834:accesspoint/mimiciv-v3-1-01/mimiciv/3.1"
REGION="us-east-1"

echo "=========================================="
echo "Checking MIMIC-IV S3 Data Availability"
echo "=========================================="
echo ""
echo "S3 Base Path: $S3_BASE"
echo "Region: $REGION"
echo ""

# Check for note directory
echo "Checking for note directory..."
NOTE_FILES=$(aws s3 ls "$S3_BASE/" --recursive --region "$REGION" 2>/dev/null | grep -i "note.csv.gz" || true)

if [ -z "$NOTE_FILES" ]; then
    echo "❌ Could not find note.csv.gz in S3"
    echo ""
    echo "Listing available top-level directories:"
    aws s3 ls "$S3_BASE/" --region "$REGION" 2>/dev/null | head -20
    exit 1
fi

# Extract the first matching path
NOTE_RELATIVE_PATH=$(echo "$NOTE_FILES" | head -1 | awk '{print $4}')
NOTE_PATH="$S3_BASE/$NOTE_RELATIVE_PATH"
echo "✅ Found note.csv.gz: $NOTE_RELATIVE_PATH"

echo ""
echo "Note file path: $NOTE_PATH"
echo ""

# Check file size
echo "Checking file size..."
FILE_SIZE=$(aws s3 ls "$NOTE_PATH" --region "$REGION" 2>/dev/null | awk '{print $3}')
if [ -n "$FILE_SIZE" ]; then
    echo "✅ File size: $FILE_SIZE bytes"
    # Convert to human readable
    SIZE_GB=$(echo "scale=2; $FILE_SIZE / 1024 / 1024 / 1024" | bc)
    echo "   (~${SIZE_GB} GB)"
else
    echo "⚠️  Could not determine file size"
fi

# Check if already downloaded locally
echo ""
echo "Checking local DESTINATION directory..."
if [ -d "DESTINATION" ]; then
    LOCAL_NOTE=$(find DESTINATION -name "note.csv.gz" -type f 2>/dev/null | head -1)
    if [ -n "$LOCAL_NOTE" ]; then
        echo "✅ Found local copy: $LOCAL_NOTE"
        LOCAL_SIZE=$(du -h "$LOCAL_NOTE" | cut -f1)
        echo "   Size: $LOCAL_SIZE"
        echo ""
        echo "You can use the local file directly:"
        echo "  python3 prepare_mimic.py \\"
        echo "    --input DESTINATION \\"
        echo "    --output datasets/mimic_notes.csv \\"
        echo "    --format mimic4_csv \\"
        echo "    --limit 100"
    else
        echo "⚠️  DESTINATION directory exists but note.csv.gz not found"
        echo "   Listing contents:"
        ls -la DESTINATION/ | head -10
    fi
else
    echo "⚠️  No local DESTINATION directory found"
fi

echo ""
echo "=========================================="
echo "S3 Check Complete"
echo "=========================================="
echo ""
echo "S3 Note Path: $NOTE_PATH"
echo ""
echo "To download and extract notes:"
echo "  # Download note file (if not already downloaded)"
echo "  aws s3 cp \"$NOTE_PATH\" datasets/note.csv.gz --region $REGION"
echo ""
echo "  # Extract notes from downloaded file"
echo "  python3 prepare_mimic.py \\"
echo "    --input datasets/note.csv.gz \\"
echo "    --output datasets/mimic_notes.csv \\"
echo "    --format csv \\"
echo "    --limit 100"
echo ""
echo "Or if you already have DESTINATION directory:"
echo "  python3 prepare_mimic.py \\"
echo "    --input DESTINATION \\"
echo "    --output datasets/mimic_notes.csv \\"
echo "    --format mimic4_csv \\"
echo "    --limit 100"
echo ""
