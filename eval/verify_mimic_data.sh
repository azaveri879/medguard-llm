#!/bin/bash
# Verify MIMIC-IV data availability (S3 or local)

set -e

echo "=========================================="
echo "MIMIC-IV Data Verification"
echo "=========================================="
echo ""

# Check local DESTINATION directory
if [ -d "DESTINATION" ]; then
    echo "✅ Found local DESTINATION directory"
    echo ""
    echo "Searching for note files..."
    
    NOTE_FILES=$(find DESTINATION -name "*note*.csv*" -type f 2>/dev/null | head -5)
    if [ -n "$NOTE_FILES" ]; then
        echo "✅ Found note files:"
        echo "$NOTE_FILES" | while read -r file; do
            SIZE=$(du -h "$file" 2>/dev/null | cut -f1)
            echo "   - $file ($SIZE)"
        done
    else
        echo "⚠️  No note files found in DESTINATION"
        echo ""
        echo "Directory structure:"
        find DESTINATION -type d -maxdepth 2 | head -20
        echo ""
        echo "Note: MIMIC-IV notes may be in a separate download."
        echo "Check: https://physionet.org/content/mimiciv/3.1/"
        echo "Look for: note/note.csv.gz"
    fi
else
    echo "⚠️  No local DESTINATION directory found"
fi

echo ""
echo "Checking S3 access..."
S3_BASE="s3://arn:aws:s3:us-east-1:724665945834:accesspoint/mimiciv-v3-1-01/mimiciv/3.1"

# Try to list S3 (may fail if no network/credentials)
if aws s3 ls "$S3_BASE/note/" --region us-east-1 2>/dev/null | grep -q "note.csv.gz"; then
    echo "✅ Found note.csv.gz in S3"
    aws s3 ls "$S3_BASE/note/" --region us-east-1 2>/dev/null | grep "note.csv.gz"
elif aws s3 ls "$S3_BASE/" --recursive --region us-east-1 2>/dev/null | grep -i "note.csv.gz" | head -1; then
    echo "✅ Found note.csv.gz in S3 (different location)"
    aws s3 ls "$S3_BASE/" --recursive --region us-east-1 2>/dev/null | grep -i "note.csv.gz" | head -1
else
    echo "⚠️  Could not verify S3 access (may need network/credentials)"
    echo "   S3 Path: $S3_BASE"
fi

echo ""
echo "=========================================="
echo "Next Steps"
echo "=========================================="
echo ""
echo "If you have note.csv.gz locally:"
echo "  python3 prepare_mimic.py \\"
echo "    --input /path/to/note.csv.gz \\"
echo "    --output datasets/mimic_notes.csv \\"
echo "    --format csv \\"
echo "    --limit 100"
echo ""
echo "If you have DESTINATION directory:"
echo "  python3 prepare_mimic.py \\"
echo "    --input DESTINATION \\"
echo "    --output datasets/mimic_notes.csv \\"
echo "    --format mimic4_csv \\"
echo "    --limit 100"
echo ""
echo "If you need to download notes from S3:"
echo "  aws s3 cp s3://.../note/note.csv.gz datasets/note.csv.gz --region us-east-1"
echo ""
