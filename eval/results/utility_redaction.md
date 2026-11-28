# Utility cost of redaction (goal 4)

Run on 2026-11-27 with `eval/run_utility.py`. 200 fresh synthetic notes (`deid_data.generate_notes`, seed 20261127, no injected text; average 555 characters) were each summarized by Claude Haiku 4.5 under five conditions, through the real gateway code. No real patient data was sent to Bedrock. Raw replies and scores: `utility_raw_haiku45.json`.

**Conditions** (R = input redaction, G = guard, i.e. `<CLINICAL_NOTE>` wrapping + security rules; the output filter is on in all five):

| Condition | R | G |
|---|---|---|
| Direct app prompt | – | – (typical app prompt) |
| Gateway prompt, both off | – | – |
| Redaction only | ✓ | – |
| Guard only | – | ✓ |
| Full gateway | ✓ | ✓ |

**Measures:**

- **Facts kept.** The generator marks each note's clinical facts: conditions, medications, doses, vitals and findings, 4–9 per note. A fact counts as kept when its text appears in the summary, ignoring case and punctuation ("strict"), or when each of its words of 4+ letters and its numbers appear ("lenient").
- **Judge.** Claude Sonnet 4.6, a different and larger model, rates each summary 1–5 for clinical completeness and accuracy against the original note. It is blind to the condition and told to ignore identifiers and placeholders.
- **Pairwise.** The judge picks the better of the full-gateway and guard-only summaries, shown in random order.

## Results

| Condition | Facts kept (strict) | Facts kept (lenient) | Completeness (1–5) | Accuracy (1–5) | Latency median / p90 (ms) |
|---|---|---|---|---|---|
| Direct app prompt (+ output filter) | 88.8% | 96.3% | 4.96 (n=200) | 4.84 | 1420 / 1730 |
| Gateway prompt, redaction and guard off | 88.8% | 95.2% | 4.88 (n=200) | 4.57 | 1664 / 1977 |
| Redaction only (guard off) | 87.5% | 94.2% | 4.85 (n=200) | 4.55 | 1688 / 1983 |
| Guard only (redaction off) | 71.8% | 81.9% | 4.61 (n=200) | 4.86 | 1369 / 1626 |
| Full gateway (redaction + guard) | 76.3% | 87.1% | 4.83 (n=200) | 4.78 | 1424 / 1676 |

Paired differences (95% bootstrap over notes; fact shares are per-note means, judge scores on 1–5):

| Measure | Redaction cost: full − guard only | Guard cost: full − redaction only | Redaction cost without guard: redaction only − neither |
|---|---|---|---|
| strict | +0.039 (+0.006 to +0.073) | -0.102 (-0.127 to -0.078) | -0.008 (-0.023 to +0.008) |
| lenient | +0.050 (+0.018 to +0.084) | -0.059 (-0.081 to -0.038) | -0.005 (-0.018 to +0.009) |
| completeness | +0.220 (+0.130 to +0.315) | -0.020 (-0.105 to +0.075) | -0.025 (-0.120 to +0.065) |
| accuracy | -0.075 (-0.165 to +0.010) | +0.230 (+0.120 to +0.345) | -0.015 (-0.150 to +0.110) |

Pairwise judge, full vs no input redaction (200 notes, order randomized): full better 96, no redaction better 38, tie 66.

Redaction step alone (rules + NER + lexicon, CPU in-process): median 100 ms, p90 119 ms; notes average 555 characters.

Failed calls: {'direct': 0, 'none': 0, 'no_guard': 0, 'no_redact': 0, 'full': 0}. Judge: us.anthropic.claude-sonnet-4-6; summaries: us.anthropic.claude-haiku-4-5-20251001-v1:0.

## What this shows

- **Redaction itself costs no measurable summary quality.**
  - Without the guard, redaction changed nothing: facts kept −0.8 points (−2.3 to +0.8), completeness −0.03 and accuracy −0.02, all within noise.
  - With the guard on, summaries of redacted notes were *better* than of unredacted ones: facts +3.9 points (+0.6 to +7.3), completeness +0.22 (+0.13 to +0.32). The judge preferred them 96 to 38 (66 ties).
  - The gap is mostly medication names that the guard-only summaries leave out (for example apixaban and metoprolol in 12 notes). The cause is not clear. One run cannot tell whether the model drops more when it has to scrub PHI itself (security rule 2), so this should be read as "no cost", not as a benefit.
- **The guard has a real trade-off.**
  - It lowers facts kept by 10.2 points (strict, −12.7 to −7.8) against redaction alone, which matches rule 3 ("summarize at a high level").
  - It raises accuracy by 0.23 (+0.12 to +0.35). Without it, 13–20 of 200 summaries scored accuracy ≤ 3, against 3–8 with it. The judge's reasons for those (checked on a sample) were unsupported additions, such as a cardiology consult the note never mentions or an interpretation of an imaging finding.
  - The completeness judge saw no difference (−0.02), so most of the lost facts may be detail the judge did not consider important. Rule 3 could be loosened ("keep all medications, doses and findings") and re-tested.
- **The full gateway's summaries stay close to the direct app's** on the judge's scale (completeness 4.83 vs 4.96, accuracy 4.78 vs 4.84), but keep fewer facts (76% vs 89% strict).

## Latency

| Step | Median | 90th percentile |
|---|---|---|
| Redaction alone (rules + Stanford model + lexicon, Mac CPU, in-process) | 100 ms | 119 ms |
| One summary call, full gateway (in-process, includes Bedrock) | 1.42 s | 1.68 s |
| One summary call, direct | 1.42 s | 1.73 s |
| Deployed gateway on Lambda, warm (3,008 MB; `lambda_cold_start.md`) | 2.9–3.4 s end to end | |
| Deployed gateway on Lambda, cold | 11–14 s end to end | |

Redaction adds about 0.1 s per note on CPU, small next to the Bedrock call's variance. The deployed gateway's extra time comes from Lambda's slower CPU and the audit writes, and on cold starts from loading the model.

## Limits

- **Synthetic notes,** short and templated, with clinical facts from fixed pools. Real notes are longer, and redaction errors there (for example a drug name taken for a name) would cost more. On PhysioNet the redactor removes 1.75% of non-PHI words.
- **One summary per note and condition** (temperature 0.2), one judge model, and no human ratings.
- **The fact check is string matching,** so a paraphrase ("blood thinner" for apixaban) counts as lost.
