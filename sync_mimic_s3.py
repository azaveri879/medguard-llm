#!/usr/bin/env python3
"""
Copy MIMIC-IV data from S3 access point to destination bucket
without reading object tags (which causes AccessDenied errors)
"""

import boto3
import sys
from botocore.exceptions import ClientError

SOURCE_ACCESS_POINT = "arn:aws:s3:us-east-1:724665945834:accesspoint/mimiciv-v3-1-01"
SOURCE_PREFIX = "mimiciv/3.1/"
DEST_BUCKET = "mimic-iv-azaveri"
REGION = "us-east-1"

def copy_without_tags(s3_client, source_key, dest_bucket, dest_key):
    """Copy object without reading tags by streaming download/upload"""
    try:
        # Use streaming download/upload - this definitely doesn't read tags
        # Download from source (access point) - streaming
        response = s3_client.get_object(
            Bucket=SOURCE_ACCESS_POINT,
            Key=source_key
        )
        
        # Upload to destination - stream directly from response body
        s3_client.upload_fileobj(
            Fileobj=response['Body'],
            Bucket=dest_bucket,
            Key=dest_key
        )
        
        return True
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code == 'AccessDenied':
            # Try copy_object as fallback (might still fail on tags)
            try:
                s3_client.copy_object(
                    CopySource={
                        'Bucket': SOURCE_ACCESS_POINT,
                        'Key': source_key
                    },
                    Bucket=dest_bucket,
                    Key=dest_key,
                    MetadataDirective='REPLACE'  # Don't copy metadata/tags
                )
                return True
            except:
                pass
        print(f"Failed to copy {source_key}: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Failed to copy {source_key}: {e}", file=sys.stderr)
        return False

def main():
    print("=" * 50)
    print("S3 Copy: MIMIC-IV Access Point to Bucket")
    print("=" * 50)
    print()
    print(f"Source: {SOURCE_ACCESS_POINT}/{SOURCE_PREFIX}")
    print(f"Destination: s3://{DEST_BUCKET}/")
    print(f"Region: {REGION}")
    print()
    
    # Create S3 client
    s3_client = boto3.client('s3', region_name=REGION)
    
    # List all objects in source
    print("Listing objects in source...")
    paginator = s3_client.get_paginator('list_objects_v2')
    
    source_arn = f"{SOURCE_ACCESS_POINT}/{SOURCE_PREFIX}"
    
    # Try to list using access point
    try:
        # Use the access point ARN format
        pages = paginator.paginate(
            Bucket=SOURCE_ACCESS_POINT,
            Prefix=SOURCE_PREFIX
        )
    except Exception as e:
        print(f"Error listing source: {e}", file=sys.stderr)
        print("Trying alternative method...")
        # Alternative: construct the access point endpoint
        access_point_name = SOURCE_ACCESS_POINT.split('/')[-1]
        account_id = SOURCE_ACCESS_POINT.split(':')[4]
        bucket_name = f"{access_point_name}-{account_id}.s3-accesspoint.{REGION}.amazonaws.com"
        pages = paginator.paginate(
            Bucket=bucket_name,
            Prefix=SOURCE_PREFIX
        )
    
    total_files = 0
    copied_files = 0
    failed_files = 0
    
    print("Starting copy operation...")
    print("(This may take a while)")
    print()
    
    for page in pages:
        if 'Contents' not in page:
            continue
            
        for obj in page['Contents']:
            source_key = obj['Key']
            # Remove the prefix if it's duplicated
            if source_key.startswith(SOURCE_PREFIX):
                dest_key = source_key
            else:
                dest_key = f"{SOURCE_PREFIX}{source_key}"
            
            total_files += 1
            
            # Copy file
            if copy_without_tags(s3_client, source_key, DEST_BUCKET, dest_key):
                copied_files += 1
                if copied_files % 5 == 0 or copied_files == total_files:
                    print(f"Progress: {copied_files}/{total_files} files copied ({failed_files} failed)", end='\r')
            else:
                failed_files += 1
                if failed_files % 5 == 0:
                    print(f"Progress: {copied_files}/{total_files} files copied ({failed_files} failed)", end='\r')
    
    print()
    print()
    print("=" * 50)
    print("Copy Complete")
    print("=" * 50)
    print()
    print(f"Total files: {total_files}")
    print(f"Successfully copied: {copied_files}")
    print(f"Failed: {failed_files}")
    print()
    print(f"Synced to: s3://{DEST_BUCKET}/{SOURCE_PREFIX}")

if __name__ == "__main__":
    main()
