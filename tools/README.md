# MedGuard Tools

Utility tools for managing and auditing MedGuard deployments.

## Compliance Audit Tool (`compliance_audit.py`)

Generates comprehensive compliance reports from audit logs.

### Features

- **PHI Statistics**: Tracks PHI detection and leakage
- **Security Incidents**: Identifies injection attempts and PHI leaks
- **User Activity**: Summarizes user access patterns
- **Compliance Checks**: Validates HIPAA and security requirements

### Usage

```bash
cd tools
python3 compliance_audit.py [days]
```

**Arguments:**
- `days` (optional): Number of days to analyze (default: 7)

**Example:**
```bash
# Analyze last 7 days
python3 compliance_audit.py

# Analyze last 30 days
python3 compliance_audit.py 30
```

### Configuration

Update these constants in the script:
```python
AUDIT_BUCKET = "your-bucket-name"
AUDIT_PREFIX = "events/"
AUDIT_TABLE = "your-table-name"
```

Or get from stack outputs:
```bash
cd cdk
cdk output MedGuardStack.AuditBucketName
cdk output MedGuardStack.AuditTableName
```

### Output

The tool generates:
1. **Console Report**: Formatted summary printed to console
2. **JSON Report**: Detailed report saved as `compliance_report_YYYYMMDD_HHMMSS.json`

### Report Sections

1. **PHI Statistics**
   - Total PHI detected
   - PHI in input vs output
   - Breakdown by PHI type

2. **Security Incidents**
   - Injection attempts (with scores)
   - PHI leakage events
   - Severity classification

3. **Compliance Checks**
   - Audit logging status
   - PHI protection status
   - Injection detection status
   - Access control status

4. **User Activity**
   - Most active users
   - Role distribution
   - Request counts

### Example Output

```
============================================================
COMPLIANCE AUDIT REPORT
============================================================

Report Date: 2026-01-03T20:00:00
Period: Last 7 days
Total Requests: 42

------------------------------------------------------------
PHI STATISTICS
------------------------------------------------------------
Total PHI Detected: 127
Requests with PHI in Input: 15
Requests with PHI in Output: 0
✅ No PHI leakage detected

PHI Types Detected:
  EMAIL: 15
  PHONE: 23
  DATE: 45
  NAME: 44

------------------------------------------------------------
SECURITY INCIDENTS
------------------------------------------------------------
Total Incidents: 8
  Injection Attempts: 8
  PHI Leakage Events: 0

Top Injection Attempts:
  - Request 06f6d897059d... Score: 2 (HIGH)
  - Request 2b0a4ad861ca... Score: 1 (MEDIUM)

------------------------------------------------------------
COMPLIANCE CHECKS
------------------------------------------------------------
✅ AUDIT LOGGING: PASS
   42 audit records found
✅ PHI PROTECTION: PASS
   PHI detected in output: 0 times
✅ INJECTION DETECTION: PASS
   8 injection attempts detected
✅ ACCESS CONTROL: PASS
   5 unique users
```

### Integration

Use in CI/CD pipelines:

```bash
# Run audit and check exit code
python3 compliance_audit.py 7
if [ $? -ne 0 ]; then
    echo "Compliance check failed!"
    exit 1
fi
```

### Requirements

```bash
pip3 install boto3
```

Ensure AWS credentials are configured:
```bash
aws configure
```
