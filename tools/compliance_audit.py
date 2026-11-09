#!/usr/bin/env python3
"""
Compliance Audit Log Review Tool
Generates compliance reports from MedGuard audit logs
"""

import json
import boto3
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

# Configuration - update these with your stack outputs
AUDIT_BUCKET = "medguardstack-auditbucketb01e0ae8-x1f2sv7sqpug"
AUDIT_PREFIX = "events/"
AUDIT_TABLE = "MedGuardStack-AuditTableB07F8EEB-9RJ529G9YEZD"

s3 = boto3.client("s3")
ddb = boto3.client("dynamodb")


def get_recent_audit_logs(days: int = 7) -> List[Dict]:
    """Retrieve recent audit logs from S3"""
    print(f"Fetching audit logs from last {days} days...")
    
    cutoff_time = datetime.now() - timedelta(days=days)
    logs = []
    
    try:
        # List objects in S3
        paginator = s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=AUDIT_BUCKET, Prefix=AUDIT_PREFIX)
        
        for page in pages:
            if "Contents" not in page:
                continue
                
            for obj in page["Contents"]:
                # Get object if recent (handle timezone-aware datetime)
                obj_time = obj["LastModified"]
                if obj_time.tzinfo is not None:
                    obj_time = obj_time.replace(tzinfo=None)
                
                if obj_time >= cutoff_time:
                    key = obj["Key"]
                    try:
                        response = s3.get_object(Bucket=AUDIT_BUCKET, Key=key)
                        log_data = json.loads(response["Body"].read())
                        logs.append(log_data)
                    except Exception as e:
                        print(f"Warning: Could not read {key}: {e}")
                        continue
        
        # If no recent logs found, try getting all logs (for debugging)
        if len(logs) == 0:
            print("No recent logs found. Checking all logs...")
            all_pages = paginator.paginate(Bucket=AUDIT_BUCKET, Prefix=AUDIT_PREFIX)
            all_count = 0
            for page in all_pages:
                if "Contents" in page:
                    all_count += len(page["Contents"])
            print(f"Total audit files in S3: {all_count}")
            if all_count > 0:
                print("Note: Files may be older than specified time window")
        
        print(f"Found {len(logs)} audit records from last {days} days")
        return logs
        
    except Exception as e:
        print(f"Error fetching logs: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_dynamodb_metadata(limit: int = 100) -> List[Dict]:
    """Retrieve metadata from DynamoDB"""
    print(f"Fetching metadata from DynamoDB (limit: {limit})...")
    
    try:
        response = ddb.scan(TableName=AUDIT_TABLE, Limit=limit)
        items = []
        
        for item in response.get("Items", []):
            items.append({
                "request_id": item["request_id"]["S"],
                "user_id": item["user_id"]["S"],
                "role": item["role"]["S"],
                "injection_score": int(item["injection_score"]["N"]),
                "model_id": item["model_id"]["S"],
                "timestamp": int(item["ts"]["N"])
            })
        
        print(f"Found {len(items)} metadata records")
        return items
        
    except Exception as e:
        print(f"Error fetching metadata: {e}")
        return []


def generate_compliance_report(logs: List[Dict], metadata: List[Dict]) -> Dict:
    """Generate compliance report from audit data"""
    print("\nGenerating compliance report...")
    
    report = {
        "report_date": datetime.now().isoformat(),
        "period_days": 7,
        "total_requests": len(logs),
        "summary": {},
        "phi_statistics": {},
        "security_incidents": [],
        "user_activity": {},
        "compliance_checks": {}
    }
    
    # PHI Statistics
    phi_stats = {
        "total_phi_detected": 0,
        "phi_in_input": 0,
        "phi_in_output": 0,
        "phi_types": defaultdict(int)
    }
    
    # Security Incidents
    security_incidents = []
    
    # User Activity
    user_activity = defaultdict(lambda: {"count": 0, "roles": set()})
    
    for log in logs:
        # PHI counts
        phi_counts = log.get("phi_counts", {})
        phi_in = phi_counts.get("in", {})
        phi_out = phi_counts.get("out", {})
        
        if phi_in:
            phi_stats["phi_in_input"] += 1
            phi_stats["total_phi_detected"] += sum(phi_in.values())
            for phi_type, count in phi_in.items():
                phi_stats["phi_types"][phi_type] += count
        
        if phi_out:
            phi_stats["phi_in_output"] += 1
            security_incidents.append({
                "type": "PHI_LEAKAGE",
                "request_id": log.get("request_id"),
                "user_id": log.get("user_id"),
                "timestamp": log.get("request_id"),  # Use request_id as proxy
                "severity": "HIGH"
            })
        
        # Injection attempts
        injection_score = log.get("injection_score", 0)
        if injection_score > 0:
            security_incidents.append({
                "type": "INJECTION_ATTEMPT",
                "request_id": log.get("request_id"),
                "user_id": log.get("user_id"),
                "injection_score": injection_score,
                "severity": "HIGH" if injection_score >= 3 else "MEDIUM"
            })
        
        # User activity
        user_id = log.get("user_id", "unknown")
        role = log.get("role", "unknown")
        user_activity[user_id]["count"] += 1
        user_activity[user_id]["roles"].add(role)
    
    report["phi_statistics"] = phi_stats
    report["security_incidents"] = security_incidents
    report["user_activity"] = {
        uid: {"count": data["count"], "roles": list(data["roles"])}
        for uid, data in user_activity.items()
    }
    
    # Compliance Checks
    report["compliance_checks"] = {
        "audit_logging": {
            "status": "PASS" if len(logs) > 0 else "FAIL",
            "details": f"{len(logs)} audit records found"
        },
        "phi_protection": {
            "status": "PASS" if phi_stats["phi_in_output"] == 0 else "FAIL",
            "details": f"PHI detected in output: {phi_stats['phi_in_output']} times"
        },
        "injection_detection": {
            "status": "PASS" if len([i for i in security_incidents if i["type"] == "INJECTION_ATTEMPT"]) > 0 else "WARN",
            "details": f"{len([i for i in security_incidents if i['type'] == 'INJECTION_ATTEMPT'])} injection attempts detected"
        },
        "access_control": {
            "status": "PASS" if len(user_activity) > 0 else "WARN",
            "details": f"{len(user_activity)} unique users"
        }
    }
    
    return report


def print_report(report: Dict):
    """Print formatted compliance report"""
    print("\n" + "="*60)
    print("COMPLIANCE AUDIT REPORT")
    print("="*60)
    
    print(f"\nReport Date: {report['report_date']}")
    print(f"Period: Last {report['period_days']} days")
    print(f"Total Requests: {report['total_requests']}")
    
    # PHI Statistics
    print("\n" + "-"*60)
    print("PHI STATISTICS")
    print("-"*60)
    phi_stats = report["phi_statistics"]
    print(f"Total PHI Detected: {phi_stats['total_phi_detected']}")
    print(f"Requests with PHI in Input: {phi_stats['phi_in_input']}")
    print(f"Requests with PHI in Output: {phi_stats['phi_in_output']}")
    if phi_stats['phi_in_output'] > 0:
        print("⚠️  WARNING: PHI detected in output - potential data breach!")
    print("\nPHI Types Detected:")
    for phi_type, count in phi_stats["phi_types"].items():
        print(f"  {phi_type}: {count}")
    
    # Security Incidents
    print("\n" + "-"*60)
    print("SECURITY INCIDENTS")
    print("-"*60)
    incidents = report["security_incidents"]
    print(f"Total Incidents: {len(incidents)}")
    
    injection_attempts = [i for i in incidents if i["type"] == "INJECTION_ATTEMPT"]
    phi_leaks = [i for i in incidents if i["type"] == "PHI_LEAKAGE"]
    
    print(f"  Injection Attempts: {len(injection_attempts)}")
    print(f"  PHI Leakage Events: {len(phi_leaks)}")
    
    if len(injection_attempts) > 0:
        print("\nTop Injection Attempts:")
        sorted_attempts = sorted(injection_attempts, key=lambda x: x.get("injection_score", 0), reverse=True)
        for attempt in sorted_attempts[:5]:
            print(f"  - Request {attempt['request_id'][:12]}... Score: {attempt['injection_score']} ({attempt['severity']})")
    
    if len(phi_leaks) > 0:
        print("\n⚠️  PHI Leakage Events (CRITICAL):")
        for leak in phi_leaks[:5]:
            print(f"  - Request {leak['request_id'][:12]}... User: {leak['user_id']}")
    
    # Compliance Checks
    print("\n" + "-"*60)
    print("COMPLIANCE CHECKS")
    print("-"*60)
    for check_name, check_result in report["compliance_checks"].items():
        status = check_result["status"]
        icon = "✅" if status == "PASS" else "⚠️" if status == "WARN" else "❌"
        print(f"{icon} {check_name.upper().replace('_', ' ')}: {status}")
        print(f"   {check_result['details']}")
    
    # User Activity Summary
    print("\n" + "-"*60)
    print("USER ACTIVITY SUMMARY")
    print("-"*60)
    user_activity = report["user_activity"]
    sorted_users = sorted(user_activity.items(), key=lambda x: x[1]["count"], reverse=True)
    print(f"Total Unique Users: {len(user_activity)}")
    print("\nTop 10 Most Active Users:")
    for user_id, data in sorted_users[:10]:
        print(f"  {user_id}: {data['count']} requests ({', '.join(data['roles'])})")


def main():
    """Main function"""
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    
    # Fetch data
    logs = get_recent_audit_logs(days)
    metadata = get_dynamodb_metadata(limit=1000)
    
    if not logs:
        print("No audit logs found. Exiting.")
        return
    
    # Generate report
    report = generate_compliance_report(logs, metadata)
    
    # Print report
    print_report(report)
    
    # Save to file
    output_file = f"compliance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved to: {output_file}")


if __name__ == "__main__":
    main()
