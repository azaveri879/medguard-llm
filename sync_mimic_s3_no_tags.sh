#!/bin/bash
# Copy MIMIC-IV data from S3 access point to destination bucket
# This script copies files individually to avoid tag permission issues

set -e

SOURCE_ACCESS_POINT="arn:aws:s3:us-east-1:724665945834:accesspoint/mimiciv-v3-1-01"
SOURCE_PREFIX="mimiciv/3.1/"
DEST_BUCKET="mimic-iv-azaveri"
REGION="us-east-1"

echo "=========================================="
echo "S3 Copy: MIMIC-IV Access Point to Bucket"
echo "=========================================="
echo ""
echo "Source: ${SOURCE_ACCESS_POINT}/${SOURCE_PREFIX}"
echo "Destination: s3://${DEST_BUCKET}/"
echo "Region: ${REGION}"
echo ""

# Create temp file for file list
FILE_LIST=$(mktemp)
trap "rm -f $FILE_LIST" EXIT

# List all files from source
echo "Listing files in source..."
aws s3 ls "s3://${SOURCE_ACCESS_POINT}/${SOURCE_PREFIX}" --recursive --region "${REGION}" > "$FILE_LIST" || {
    echo "❌ Error: Could not list source files"
    exit 1
}

TOTAL_FILES=$(wc -l < "$FILE_LIST")
echo "Found $TOTAL_FILES files to copy"
echo ""

# Copy files one by one using s3api copy-object
# This avoids the tag reading issue
COPIED=0
FAILED=0

echo "Starting copy operation..."
echo "(This may take a while)"
echo ""

while IFS= read -r line; do
    # Parse the line: DATE TIME SIZE KEY
    SIZE=$(echo "$line" | awk '{print $3}')
    KEY=$(echo "$line" | awk '{print $4}')
    
    # Skip if key is empty
    [ -z "$KEY" ] && continue
    
    # Copy using s3api copy-object with metadata-directive REPLACE
    # This doesn't try to read tags from source
    if aws s3api copy-object \
        --bucket "$DEST_BUCKET" \
        --copy-source "${SOURCE_ACCESS_POINT}/${KEY}" \
        --key "$KEY" \
        --metadata-directive REPLACE \
        --region "$REGION" \
        > /dev/null 2>&1; then
        COPIED=$((COPIED + 1))
        if [ $((COPIED % 10)) -eq 0 ]; then
            echo "Copied $COPIED/$TOTAL_FILES files..." 
        fi
    else
        # If copy-object fails, try regular cp as fallback
        if aws s3 cp \
            "s3://${SOURCE_ACCESS_POINT}/${KEY}" \
            "s3://${DEST_BUCKET}/${KEY}" \
            --region "$REGION" \
            > /dev/null 2>&1; then
            COPIED=$((COPIED + 1))
            if [ $((COPIED % 10)) -eq 0 ]; then
                echo "Copied $COPIED/$TOTAL_FILES files..."
            fi
        else
            FAILED=$((FAILED + 1))
            echo "Failed: $KEY" >&2
        fi
    fi
done < "$FILE_LIST"

echo ""
echo "=========================================="
echo "Copy Complete"
echo "=========================================="
echo ""
echo "Total files: $TOTAL_FILES"
echo "Successfully copied: $COPIED"
echo "Failed: $FAILED"
echo ""
echo "Synced to: s3://${DEST_BUCKET}/${SOURCE_PREFIX}"
echo ""
echo "Verify sync:"
echo "  aws s3 ls s3://${DEST_BUCKET}/${SOURCE_PREFIX} --recursive --region ${REGION} | wc -l"
