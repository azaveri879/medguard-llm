# MedGuard: PHI-Aware Security and Audit Layer for Clinical LLMs

MedGuard is a defense-in-depth security gateway designed to enable safe deployment of Large Language Models (LLMs) within hospital environments. It provides PHI protection, prompt injection defense, policy enforcement, and comprehensive audit logging.

## Status & Test Results

### Research Prototype - Unit Tests Passing

> **Status:** Research prototype, not production ready. Unit tests pass on a small hand-written suite, but the evaluation does not yet show an improvement over a direct-Bedrock baseline. See [Roadmap](#roadmap-revisited-november-2026).

**Last Verified:** January 3, 2026  
**Unit Test Status:** 15/15 tests passing on a small controlled suite

#### PHI Redaction Tests: ✅ 3/3 PASSED

| Test Case | Detection Rate | Status |
|-----------|---------------|--------|
| Emergency Department Note | 100.0% (9/9) | ✅ PASS |
| Discharge Summary | 88.9% (8/9) | ✅ PASS |
| Progress Note | 100.0% (8/8) | ✅ PASS |

**Average Detection Rate:** 96.3% on evaluated clinical note types  
**PHI Types Detected:** Email, Phone, Date, SSN, MRN, Name, Address  
**Security:** ✅ Zero PHI leakage detected in model outputs across all test cases

#### Injection Attack Tests: ✅ 12/12 PASSED

| Severity | Tests | Pass Rate |
|----------|-------|-----------|
| **CRITICAL** | 2/2 | 100% ✅ |
| **HIGH** | 4/4 | 100% ✅ |
| **MEDIUM** | 5/5 | 100% ✅ |
| **LOW** | 1/1 | 100% ✅ |

**Attack Block Rate:** 100% on the evaluated attack suite (12 injection scenarios)  
**Average Injection Score:** 1.67  
**Attack Types Tested:** Direct override, indirect injection, jailbreak, exfiltration, role confusion, multi-layer, hidden instructions, social engineering, Base64, Unicode, context switching, prompt leakage

#### Performance Metrics

- **PHI Detection Rate:** 96.3% (exceeds 80% target)
- **Injection Detection:** 100% of evaluated attacks detected
- **Attack Block Rate:** 100% on the evaluated attack suite (12 scenarios)
- **PHI Leakage Rate:** 0% (zero leaks in testing)
- **Test Pass Rate:** 100% (15/15 tests passing)

### Evaluation Scope

All reported metrics reflect controlled test suites designed to validate system behavior under known threat scenarios. These results should not be interpreted as guarantees against all possible attacks, but as evidence that defense-in-depth controls significantly reduce risk compared to baseline LLM deployments.

## Architecture Overview

MedGuard operates as a model-agnostic middleware positioned between clinical data sources and the LLM inference layer. The system implements multiple security controls:

1. **PHI Detection & Transformation**: Hybrid detection engine combining rule-based patterns and ML-based NER (currently regex-based, upgradeable to Presidio/medspaCy). The current implementation prioritizes deterministic, interpretable PHI detection for system validation; higher-recall ML-based detectors (Presidio, transformer NER) are planned and evaluated separately.
2. **Prompt Injection Mitigation**: Instruction-data separation with hierarchical precedence enforcement
3. **Policy Enforcement**: Role-based access control (RBAC) governing data access and output detail levels
4. **Output Guard**: Post-generation scanning for PHI leakage and verbatim document extraction
5. **Audit Logging**: Immutable, audit-ready logs stored in S3 with queryable metadata in DynamoDB

### Threat Model

MedGuard is designed to mitigate three primary threat classes identified in prior work:
1. **PHI leakage** through inadvertent or malicious prompt content
2. **Prompt injection attacks**, including direct, indirect, and multi-layer variants
3. **Policy violations** arising from role confusion or over-privileged access

The system does not attempt to prevent all model hallucinations or guarantee clinical correctness; rather, it focuses on enforceable security and governance controls at inference time.

### Infrastructure Components

- **VPC**: Private isolated subnets with VPC endpoints (no NAT gateways)
- **VPC Endpoints**: Gateway endpoints for S3 and DynamoDB; Interface endpoint for Bedrock
- **Lambda Function**: Python 3.11 handler implementing the MedGuard security pipeline
- **API Gateway**: REST API with `/v1/chat` endpoint
- **S3 Bucket**: Immutable audit logs with versioning and encryption
- **DynamoDB Table**: Queryable metadata index for audit records
- **Cognito** (optional): User Pool for authentication

### Security Pipeline

The Lambda handler implements a 7-step security pipeline:

1. **Request Parsing**: Extract user_id, role, prompt from request body
2. **PHI Detection**: Scan input for PHI (7 types) and redact
3. **Injection Scoring**: Heuristic pattern matching (12 patterns) for prompt injection attempts
4. **Policy Enforcement**: Apply RBAC rules (e.g., students cannot request full notes)
5. **Bedrock Invocation**: Call Claude 3 Haiku with hardened system prompt
6. **Output Guard**: Scan output for PHI and verbatim leakage
7. **Audit Logging**: Write immutable records to S3 and metadata to DynamoDB

## Prerequisites

- AWS CLI configured with appropriate credentials
- Node.js 18+ and npm
- Python 3.11
- AWS CDK CLI installed (`npm install -g aws-cdk`)
- AWS account with permissions to create VPC, Lambda, API Gateway, S3, DynamoDB resources
- Bedrock access enabled (see [Bedrock Setup](#bedrock-setup))

## Deployment

### 1. Install Dependencies

```bash
cd cdk
npm install
```

### 2. Bootstrap CDK (First Time Only)

```bash
cdk bootstrap
```

### 3. Deploy the Stack

**Without authentication (for testing):**
```bash
cdk deploy -c enableAuth=false
```

**With Cognito authentication (production):**
```bash
cdk deploy
# or explicitly:
cdk deploy -c enableAuth=true
```

**Specify a different Bedrock model:**
```bash
cdk deploy -c bedrockModelId="anthropic.claude-3-sonnet-20240229-v1:0" -c enableAuth=false
```

### 4. Get Stack Outputs

```bash
cdk output MedGuardStack.ApiUrl
cdk output MedGuardStack.AuditBucketName
cdk output MedGuardStack.AuditTableName
# If auth enabled:
cdk output MedGuardStack.UserPoolId
cdk output MedGuardStack.UserPoolClientId
```

## Bedrock Setup

**Model Access:** Serverless foundation models are automatically enabled. For Anthropic Claude models:

1. Fill out the Anthropic use case form in AWS Bedrock Console
2. Some models may require AWS Marketplace subscription:
   - Go to [Bedrock Model Catalog](https://console.aws.amazon.com/bedrock/)
   - Find your model (e.g., Claude 3 Haiku)
   - Click "Subscribe" if available
   - Wait 2-5 minutes for activation

The Lambda role has Marketplace permissions (`aws-marketplace:Subscribe`, `aws-marketplace:ViewSubscriptions`).

## Usage

### API Endpoint

**POST** `/v1/chat`

**Request Body:**
```json
{
  "user_id": "user123",
  "role": "resident",
  "patient_context": {
    "mrn": "optional",
    "encounter_id": "optional"
  },
  "prompt": "Summarize this clinical note: [note text]",
  "mode": "summarize"
}
```

**Response:**
```json
{
  "request_id": "abc123...",
  "response": "[LLM-generated summary with PHI redacted]",
  "safety_flags": {
    "injection_score": 0,
    "phi_detected_in_output": false
  },
  "redaction_summary": {
    "EMAIL": 1,
    "PHONE": 1,
    "DATE": 2,
    "SSN": 1,
    "MRN": 1,
    "NAME": 2,
    "ADDRESS": 1
  }
}
```

### Example Request

```bash
curl -X POST "https://your-api-url/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "u1",
    "role": "resident",
    "prompt": "Summarize: Patient John Smith (phone 555-111-2222, email john@example.com) seen on 01/02/2026 for chest pain."
  }'
```

### With Authentication

If authentication is enabled, include the Cognito token:

```bash
TOKEN=$(aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id $USER_POOL_CLIENT_ID \
  --auth-parameters USERNAME=testuser,PASSWORD=YourPass123! \
  --query 'AuthenticationResult.IdToken' \
  --output text)

curl -X POST "https://your-api-url/v1/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"testuser","role":"resident","prompt":"..."}'
```

## Testing

### Run All Tests

```bash
cd tests
pip3 install -r requirements.txt
./run_all_tests.sh
```

### Individual Test Suites

**PHI Redaction Tests:**
```bash
cd tests
python3 test_phi_redaction.py
```

**Injection Attack Tests:**
```bash
cd tests
python3 test_injection_attacks.py
```

### Expected Results

- **PHI Detection:** >96% detection rate, zero PHI in output
- **Injection Detection:** All attacks detected and blocked
- **Test Pass Rate:** 100% (15/15 tests)

## Compliance & Audit

### Generate Compliance Report

```bash
cd tools
# Update AUDIT_BUCKET and AUDIT_TABLE in compliance_audit.py first
python3 compliance_audit.py [days]  # Default: 7 days
```

The tool generates:
- **Console Report**: Formatted summary
- **JSON Report**: `compliance_report_YYYYMMDD_HHMMSS.json`

**Report includes:**
- PHI statistics (detection, leakage tracking)
- Security incidents (injection attempts, PHI leaks)
- Compliance checks (HIPAA validation)
- User activity summary

### Audit Log Structure

**S3 Logs** (`s3://{BUCKET}/events/{request_id}.json`):
```json
{
  "request_id": "abc123...",
  "user_id": "user123",
  "role": "resident",
  "model_id": "anthropic.claude-3-haiku-20240307-v1:0",
  "prompt_hash": "sha256_hash",
  "injection_score": 0,
  "phi_counts": {"in": {...}, "out": {...}},
  "latency_ms": 2628
}
```

**DynamoDB Metadata** (queryable by `request_id` and `ts`):
- request_id, user_id, role, injection_score, model_id, timestamp

## Authentication

### Enable Authentication

```bash
cd cdk
npx cdk deploy  # Default: enabled
```

### Create Users

**Via AWS CLI:**
```bash
# Create user
aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username testuser \
  --user-attributes Name=email,Value=test@example.com \
  --temporary-password TempPass123! \
  --message-action SUPPRESS

# Set permanent password
aws cognito-idp admin-set-user-password \
  --user-pool-id $USER_POOL_ID \
  --username testuser \
  --password "YourSecurePass123!" \
  --permanent
```

**Get Token:**
```bash
aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id $USER_POOL_CLIENT_ID \
  --auth-parameters USERNAME=testuser,PASSWORD="YourSecurePass123!" \
  --query 'AuthenticationResult.IdToken' \
  --output text
```

## Configuration

### CDK Context Variables

- `bedrockModelId`: Bedrock model ID (default: `anthropic.claude-3-haiku-20240307-v1:0`)
- `enableAuth`: Enable Cognito authentication (default: `true`, set to `"false"` to disable)

### Lambda Environment Variables

- `AUDIT_BUCKET`: S3 bucket name for audit logs
- `AUDIT_PREFIX`: S3 key prefix (default: `events/`)
- `DDB_TABLE`: DynamoDB table name
- `BEDROCK_MODEL_ID`: Bedrock model identifier

## Important Notes

### VPC Endpoints

- **S3 & DynamoDB**: Gateway endpoints (no NAT required)
- **Bedrock**: Interface endpoint (PrivateLink) - availability varies by region
- If Bedrock endpoint unavailable, add NAT gateway or deploy in supported region

### S3 Object Lock (WORM)

For true Write-Once-Read-Many compliance, enable Object Lock in `medguard-stack.ts`:
```typescript
objectLockEnabled: true
```
Requires account-level Object Lock settings.

### PHI Detection Upgrade Path

Current implementation uses regex patterns. For production:
1. Replace with Microsoft Presidio
2. Add transformer-based NER (ClinicalBERT/RoBERTa)
3. Add hospital-specific dictionaries (MRN formats, provider IDs)

## Development

### Local Testing

```bash
cd services/gateway
pip install -r requirements.txt
python -m pytest  # Add tests as needed
```

### CDK Development

```bash
cd cdk
npm run build      # Compile TypeScript
npm run watch      # Watch mode
cdk synth          # Synthesize CloudFormation
cdk diff           # Compare with deployed stack
```

## Readiness Checklist

- [x] ✅ PHI detection and redaction (96.3% detection rate)
- [x] ✅ Injection detection and blocking (100% on evaluated suite)
- [x] ✅ Audit logging operational (S3 + DynamoDB)
- [x] ✅ All tests passing (15/15)
- [x] ✅ Error handling implemented
- [x] ✅ VPC endpoints configured
- [x] ✅ Bedrock access working
- [ ] ⏳ Authentication enabled (ready, currently disabled for testing)
- [ ] ⏳ Presidio/medspaCy integration (upgrade path ready)
- [ ] ⏳ RAG implementation (future enhancement)

## Roadmap (Revisited November 2026)

### Current State

- **AWS infrastructure torn down** (Nov 2026) to stop VPC interface endpoint charges. Retained resources (MIMIC-IV S3 bucket, audit buckets, DynamoDB tables, Cognito pool) may still exist. Redeploy with `cdk deploy` only when end-to-end testing is needed.
- **The evaluation does not yet show a benefit.** In `eval/results/baseline_comparison.md`, direct Bedrock already scores 0% PHI leakage and 0% attack success rate, the same as MedGuard, which adds ~1.1s of latency. The test suite is too small (3 PHI, 5 injection, 2 utility cases) and too easy to separate the two.
- **Eval injection detection is 60%**, compared with 100% on the separate 12-attack test suite in `tests/`.
- **MIMIC-IV notes are already de-identified** (names replaced with `___`), so measuring PHI recall on them requires injecting realistic synthetic PHI or using a labeled de-ID dataset (e.g. i2b2/n2c2 2014).
- **Claude 3 Haiku is outdated.** Newer models resist injection better on their own, which makes the baseline gap harder to show.

### Goals

Goals 1–2 are the core and can be done locally (call the handler and Bedrock directly) without redeploying the VPC.

1. **Build a real benchmark**
   - Several hundred PHI cases: MIMIC notes with synthetic PHI re-inserted, labeled with spans
   - Several hundred injection attacks from public sets (BIPIA, AgentDojo, HackAPrompt), including indirect injection inside clinical notes
   - *Done when:* the unprotected baseline shows non-zero PHI leakage and non-zero attack success rate
   - *Learning:* LLM eval design, red-teaming, dataset construction

2. **Upgrade PHI detection**
   - Compare regex (current) vs Presidio vs a transformer NER model (e.g. a clinical de-ID model)
   - *Done when:* there is a precision/recall/F1 table per PHI type for each detector
   - *Learning:* NER, recall vs precision tradeoffs, HIPAA Safe Harbor identifiers

3. **Run ablations**
   - Disable one defense layer at a time (redaction, injection scoring, policy, output guard) using `eval/ablation.py`
   - *Done when:* each layer's marginal contribution to PHI leakage and attack success rate is quantified
   - *Learning:* defense-in-depth, attribution of security controls

4. **Measure utility cost**
   - Check whether redaction and hardening degrade clinical answer quality (LLM-as-judge or rubric scoring)
   - *Done when:* there is a security vs utility vs latency tradeoff table
   - *Learning:* LLM-as-judge evaluation, the cost of guardrails

5. **Write it up**
   - Use `eval/generate_tables.py` for LaTeX tables; frame results against the threat model above
   - *Done when:* a short paper or blog post with reproducible results exists

### Stretch

- Replace the heuristic injection scorer with an ML classifier and compare
- Re-run the benchmark across model generations (Haiku 3 vs current Claude models) to measure how much model-level robustness reduces the need for gateway controls

## Next Steps

### Immediate
1. Enable authentication for production
2. Set up regular compliance audits
3. Monitor security incidents

### Short Term
1. Upgrade PHI detection to Presidio/medspaCy
2. Add transformer-based NER
3. Enhance injection detection with ML classifier

### Long Term
1. Implement RAG with OpenSearch/pgvector
2. Add fine-grained RBAC (OPA integration)
3. Add streaming response support
4. Upgrade to PRIVATE API Gateway endpoint

### Planned Baseline Comparisons

Ongoing evaluation includes comparison against:
- Direct Bedrock invocation without MedGuard
- PHI redaction-only pipelines
- Injection hardening-only pipelines

These ablations will quantify the marginal benefit of each security layer.

## Evaluation & Research

### Evaluation Harness

The `eval/` directory contains a comprehensive evaluation framework for baseline comparisons and ablation studies:

```bash
cd eval
pip3 install -r requirements.txt

# Quick start (uses default API URL)
./run_evaluation.sh

# Or run manually
python3 run_eval.py \
  --medguard-url https://rr7xrc9ucl.execute-api.us-east-1.amazonaws.com/prod/v1/chat \
  --baseline-model anthropic.claude-3-haiku-20240307-v1:0 \
  --mode baseline \
  --output-dir results

# Generate publication-ready tables
python3 generate_tables.py \
  --results results/baseline_comparison_results.json \
  --output-dir results \
  --format latex
```

**Features:**
- Baseline comparison (direct Bedrock vs MedGuard)
- Ablation studies (individual defense layers)
- MIMIC evaluation (real-world clinical notes)
- Publication-ready table generation (LaTeX, CSV)
- Comprehensive metrics (PHI leakage, injection ASR, latency, utility)

**Evaluation Types:**
1. **Synthetic PHI Suite**: Tests PHI protection and injection defense
2. **MIMIC Notes**: Tests utility preservation, false positives, and indirect injection

See `eval/README.md` for detailed documentation.

## File Structure

```
medguard-llm/
├── cdk/                    # CDK infrastructure code
│   ├── bin/cdk.ts
│   ├── lib/medguard-stack.ts
│   └── package.json
├── services/
│   └── gateway/
│       ├── handler.py      # Lambda handler
│       └── requirements.txt
├── tests/                   # Test suites
│   ├── test_phi_redaction.py
│   ├── test_injection_attacks.py
│   └── run_all_tests.sh
├── eval/                    # Evaluation harness
│   ├── run_eval.py         # Main evaluation script
│   ├── baseline.py         # Baseline comparison
│   ├── ablation.py         # Ablation studies
│   ├── metrics.py          # Metrics calculation
│   ├── generate_tables.py  # Table generation
│   └── datasets/           # Test datasets
├── tools/                    # Utility tools
│   └── compliance_audit.py
└── README.md
```

## License

[Add your license here]

## References

- NIST AI Risk Management Framework (2023)
- HIPAA Safe Harbor De-identification (HHS, 2012)
- Greshake et al. (2023): "Not What You've Signed Up For: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection"
