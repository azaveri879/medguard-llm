#!/bin/bash
# Sync MIMIC-IV data from S3 access point to destination bucket

# Don't exit on errors - continue copying other files
set +e

SOURCE_ACCESS_POINT="arn:aws:s3:us-east-1:724665945834:accesspoint/mimiciv-v3-1-01"
SOURCE_PREFIX="mimiciv/3.1/"
DEST_BUCKET="mimic-iv-azaveri"
REGION="us-east-1"

echo "=========================================="
echo "S3 Sync: MIMIC-IV Access Point to Bucket"
echo "=========================================="
echo ""
echo "Source: ${SOURCE_ACCESS_POINT}/${SOURCE_PREFIX}"
echo "Destination: s3://${DEST_BUCKET}/"
echo "Region: ${REGION}"
echo ""

# First, verify destination bucket exists
echo "Verifying destination bucket..."
if ! aws s3 ls "s3://${DEST_BUCKET}/" --region "${REGION}" > /dev/null 2>&1; then
    echo "❌ Error: Destination bucket '${DEST_BUCKET}' does not exist or is not accessible"
    echo "   Please verify the bucket name and your permissions"
    exit 1
fi
echo "✅ Destination bucket accessible"
echo ""

# Try to list source (this will help diagnose access issues)
echo "Checking source access point..."
if aws s3 ls "s3://${SOURCE_ACCESS_POINT}/${SOURCE_PREFIX}" --region "${REGION}" > /dev/null 2>&1; then
    echo "✅ Source access point accessible"
    echo ""
    echo "Listing first few objects in source..."
    aws s3 ls "s3://${SOURCE_ACCESS_POINT}/${SOURCE_PREFIX}" --region "${REGION}" --recursive | head -10
    echo ""
else
    echo "⚠️  Warning: Could not list source access point"
    echo "   This might be a permissions issue, but sync may still work"
    echo ""
fi

# Perform copy using cp --recursive
# Note: sync fails with AccessDenied on GetObjectTagging for many files
# Using cp --recursive instead, which doesn't try to preserve tags
echo "Starting copy operation..."
echo "This may take a while depending on data size..."
echo ""
echo "Using 'cp --recursive' to avoid tag permission issues"
echo "(Note: This will copy all files, even if they already exist)"
echo ""

# Copy files - some may fail due to tag permissions, but continue anyway
aws s3 cp \
    "s3://${SOURCE_ACCESS_POINT}/${SOURCE_PREFIX}" \
    "s3://${DEST_BUCKET}/${SOURCE_PREFIX}" \
    --recursive \
    --region "${REGION}" \
    --no-progress \
    || echo "Some files failed to copy (likely due to tag permissions)"

echo ""
echo "Note: Files that failed with 'AccessDenied' on GetObjectTagging"
echo "      can be copied individually. See sync_mimic_s3_no_tags.sh for"
echo "      a script that handles this case."

echo ""
echo "=========================================="
echo "Sync Complete"
echo "=========================================="
echo ""
echo "Synced to: s3://${DEST_BUCKET}/${SOURCE_PREFIX}"
echo ""
echo "Verify sync:"
echo "  aws s3 ls s3://${DEST_BUCKET}/${SOURCE_PREFIX} --recursive --region ${REGION} | wc -l"
