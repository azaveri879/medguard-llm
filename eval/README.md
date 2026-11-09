# MedGuard Evaluation Harness

Comprehensive evaluation framework for baseline comparisons, ablation studies, and publication-ready metrics generation.

## Overview

The evaluation harness supports:
- **Baseline Comparisons**: Direct Bedrock vs MedGuard
- **Ablation Studies**: Individual defense layer contribution
- **Metrics Calculation**: PHI leakage, injection ASR, utility, latency
- **Table Generation**: Publication-ready tables (LaTeX, CSV, Markdown)

## Quick Start

### 1. Install Dependencies

```bash
cd eval
pip3 install -r requirements.txt
```

### 2. Run Baseline Comparison

**Quick Start (with default API URL):**
```bash
./run_evaluation.sh
```

**Manual run:**
```bash
python3 run_eval.py \
  --medguard-url https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/v1/chat \
  --baseline-model us.anthropic.claude-haiku-4-5-20251001-v1:0 \
  --mode baseline \
  --output-dir results
```

### 3. Generate Tables

```bash
python3 generate_tables.py \
  --results results/baseline_comparison_results.json \
  --output-dir results \
  --format both
```

## Usage

### Baseline Comparison

Compare MedGuard against direct Bedrock invocation:

```bash
python3 run_eval.py \
  --medguard-url $API_URL \
  --baseline-model us.anthropic.claude-haiku-4-5-20251001-v1:0 \
  --suite datasets/test_suite.json \
  --test-type all \
  --mode baseline \
  --output-dir results
```

**Output:**
- `baseline_comparison_results.json` - Raw results
- `baseline_comparison.csv` - CSV table
- `baseline_comparison.tex` - LaTeX table (for paper)
- `baseline_comparison.md` - Markdown table

### Ablation Studies

Evaluate individual defense layers (requires handler modifications):

```bash
python3 run_eval.py \
  --medguard-url $API_URL \
  --mode ablation \
  --output-dir results
```

### Custom Test Suite

Create your own test suite JSON:

```json
{
  "phi_test_cases": [
    {
      "id": "custom_001",
      "name": "Custom PHI Test",
      "prompt": "Your test prompt here",
      "expected_phi_types": ["EMAIL", "PHONE"],
      "category": "clinical_note"
    }
  ],
  "injection_test_cases": [
    {
      "id": "custom_inj_001",
      "name": "Custom Injection Test",
      "prompt": "Your attack prompt here",
      "is_attack": true,
      "severity": "high",
      "expected_detection": true
    }
  ]
}
```

Then run:
```bash
python3 run_eval.py --suite your_suite.json ...
```

## Metrics

### PHI Metrics
- **Detection Rate**: % of PHI detected in input
- **Leakage Rate**: % of outputs containing PHI
- **Types Detected**: Breakdown by PHI type

### Injection Metrics
- **Detection Rate**: % of attacks detected (score > 0)
- **Attack Success Rate (ASR)**: % of attacks that succeeded
- **Average Score**: Mean injection score

### Utility Metrics
- **Response Length**: Average response length
- **Quality Score**: BERTScore/ROUGE (if references provided)

### Performance Metrics
- **Latency**: Mean, P50, P95 latencies

## Output Formats

### LaTeX Tables

Generated tables are ready for JAMIA / npj Digital Medicine style papers:

```latex
\begin{table}[h]
\centering
\begin{tabular}{lcccccc}
\toprule
Configuration & PHI Det. & PHI Leak & Inj. Det. & ASR & Latency (ms) \\
\midrule
Baseline & -- & -- & -- & -- & 1200 \\
MedGuard & 96.3 & 0.0 & 100.0 & 0.0 & 2600 \\
\bottomrule
\end{tabular}
\caption{Comparison of MedGuard configurations}
\label{tab:config-comparison}
\end{table}
```

### CSV Tables

For analysis in Excel/Python:

```csv
Configuration,PHI Detection (%),PHI Leakage (%),Injection Detection (%),ASR (%),Avg Latency (ms)
baseline,0.00,0.00,0.00,0.00,1200.0
medguard,96.30,0.00,100.00,0.00,2600.0
```

## Integration with Paper

The evaluation harness directly supports paper Results section:

1. **Run evaluations** → Generate metrics
2. **Generate tables** → LaTeX tables for paper
3. **Analyze results** → Calculate statistical significance
4. **Write Results** → Use tables and metrics

## Example Workflow

```bash
# 1. Run baseline comparison
python3 run_eval.py \
  --medguard-url $API_URL \
  --mode baseline \
  --output-dir results

# 2. Generate publication tables
python3 generate_tables.py \
  --results results/baseline_comparison_results.json \
  --output-dir results \
  --format latex

# 3. Copy LaTeX tables into paper
# results/table_phi_leakage.tex
# results/table_injection_asr.tex
# results/table_latency.tex
```

## MIMIC Evaluation

Evaluate MedGuard on real-world clinical notes from MIMIC (de-identified dataset).

### Prepare MIMIC Notes

**From CSV:**
```bash
python3 prepare_mimic.py \
  --input your_mimic_notes.csv \
  --output datasets/mimic_notes.csv \
  --format csv
```

**From MIMIC-III Database:**
```bash
python3 prepare_mimic.py \
  --input mimic3.db \
  --output datasets/mimic_notes.csv \
  --format mimic3_db \
  --limit 100
```

**From MIMIC-IV Database:**
```bash
python3 prepare_mimic.py \
  --input mimic4.db \
  --output datasets/mimic_notes.csv \
  --format mimic4_db \
  --limit 100
```

### Run MIMIC Evaluation

```bash
python3 mimic_eval.py \
  --mimic-path datasets/mimic_notes.csv \
  --medguard-url https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/v1/chat \
  --baseline-model us.anthropic.claude-haiku-4-5-20251001-v1:0 \
  --task problem_list \
  --num-notes 100 \
  --num-injections 50 \
  --output-dir results
```

**Tasks:**
- `problem_list` - Extract problem list
- `medication_summary` - Summarize medications
- `clinical_course` - One-paragraph clinical course summary

**Output:**
- `mimic_evaluation_results.json` - Full results
- `table_mimic_utility.tex` - Utility comparison table
- `table_mimic_false_positives.tex` - False positive analysis

### MIMIC Evaluation Focus

MIMIC evaluation tests:
1. **Utility Preservation**: Are summaries still clinically coherent?
2. **False Positives**: PHI detector over-redaction on de-identified notes
3. **Indirect Injection**: Attacks embedded in realistic note structure

**Note:** MIMIC is de-identified, so it does NOT test PHI leakage. Use synthetic PHI suite for that.

## Future Enhancements

- [ ] BERTScore/ROUGE integration for utility metrics
- [ ] Statistical significance testing
- [ ] Confidence intervals
- [ ] Visualization (plots, charts)
- [ ] Automated report generation
- [ ] Clinician-rated utility assessment