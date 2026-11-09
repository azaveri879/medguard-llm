# MedGuard Test Suites

Comprehensive test suites for validating MedGuard security and compliance features.

## Setup

```bash
cd tests
pip3 install -r requirements.txt
```

## Test Suites

### 1. PHI Redaction Tests (`test_phi_redaction.py`)

Tests PHI detection and redaction with real clinical note examples.

**Features:**
- Tests multiple clinical note types (ED notes, discharge summaries, progress notes)
- Validates detection of various PHI types (names, emails, phones, dates, SSNs, MRNs)
- Checks for PHI leakage in model output
- Calculates detection rates

**Run:**
```bash
python3 test_phi_redaction.py
```

**Expected Output:**
- Detection rates for each PHI type
- Confirmation that no PHI appears in output
- Summary statistics

### 2. Injection Attack Tests (`test_injection_attacks.py`)

Tests prompt injection detection against various attack patterns.

**Attack Types:**
- Direct instruction override
- Indirect injection via notes
- Jailbreak attempts
- Data exfiltration requests
- Multi-layer injections
- Social engineering
- Unicode-based attacks
- And more...

**Run:**
```bash
python3 test_injection_attacks.py
```

**Expected Output:**
- Injection scores for each attack
- Attack success/failure status
- Model refusal confirmation
- Summary by severity level

### 3. Run All Tests

Run both test suites:

```bash
chmod +x run_all_tests.sh
./run_all_tests.sh
```

Or set custom API URL:

```bash
API_URL=https://your-api-url/v1/chat ./run_all_tests.sh
```

## Configuration

Update the `API_URL` constant in each test file, or set it as an environment variable:

```bash
export API_URL=https://your-api-url/v1/chat
```

## Expected Results

### PHI Redaction
- ✅ Detection rate > 80% for common PHI types
- ✅ Zero PHI in model output
- ✅ All test cases pass

### Injection Detection
- ✅ All attacks detected (score > 0)
- ✅ No successful attacks (model refuses)
- ✅ High-severity attacks score >= 2

## Troubleshooting

**"Connection refused"**
- Check API_URL is correct
- Verify API Gateway is deployed
- Check authentication (if enabled)

**"Module not found"**
- Install dependencies: `pip3 install -r requirements.txt`

**Tests failing**
- Review error messages
- Check Lambda logs
- Verify Bedrock model access
