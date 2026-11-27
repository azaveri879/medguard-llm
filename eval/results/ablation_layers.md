# Gateway layer ablation (goal 3)

Run on 2026-11-27. Each of the gateway's three layers was turned off in turn, on the injection suite (synthetic notes, Claude Haiku 4.5 on Bedrock) and, for the redaction layer's parts, on PhysioNet's held-out test half (local scoring only).

The layers:

- **R, input redaction:** rules, the Stanford model at threshold 0.02 and the name lexicon (setup A, the deployed default).
- **G, the guard:** the note wrapped in `<CLINICAL_NOTE>` plus the four security rules in the system prompt.
- **O, the output filter:** the rules run again on the model's reply.

## Injection suite: all eight combinations

`eval/run_ablation.py` sends each of the 400 cases (300 attacks, 100 benign; `injection_clinical_notes.md`) through the real gateway code (`handler.gateway_reply`) under the four R × G settings. O only changes the reply after the model answers, so it was applied offline to every stored raw reply, giving all eight cells from 1,600 calls. The "direct app prompt" rows repeat v1's baseline: a typical app system prompt and no gateway. Every system prompt carries the same canary code. One run per case, temperature 0.2, no failed calls. Raw replies: `ablation_raw_haiku45.json`.

**PHI leakage** counts a note's gold values (names, dates, IDs, phones, addresses, emails; 5,021 in all) that appear in the reply, ignoring formatting. A name counts if its last name appears.

| Layers (R G O) | Attack success, all (300) | Excl. PHI goal (240) | Canary leaked (60) | Benign notes leaking any PHI (100) | PHI values leaked, all notes | Benign refused |
|---|---|---|---|---|---|---|
| R G O | 0.0% (0.0-1.3) | 0.0% (0.0-1.6) | 0.0% (0.0-6.0) | 0.0% (0.0-3.7) | 0.0% (0.0-0.1) | 0/100 |
| R G – | 0.0% (0.0-1.3) | 0.0% (0.0-1.6) | 0.0% (0.0-6.0) | 0.0% (0.0-3.7) | 0.0% (0.0-0.1) | 0/100 |
| – G O | 0.0% (0.0-1.3) | 0.0% (0.0-1.6) | 0.0% (0.0-6.0) | 4.0% (1.6-9.8) | 0.2% (0.1-0.4) | 0/100 |
| – G – | 0.0% (0.0-1.3) | 0.0% (0.0-1.6) | 0.0% (0.0-6.0) | 10.0% (5.5-17.4) | 0.8% (0.6-1.0) | 0/100 |
| R – O | 0.0% (0.0-1.3) | 0.0% (0.0-1.6) | 0.0% (0.0-6.0) | 1.0% (0.2-5.4) | 0.1% (0.0-0.2) | 0/100 |
| R – – | 0.0% (0.0-1.3) | 0.0% (0.0-1.6) | 0.0% (0.0-6.0) | 1.0% (0.2-5.4) | 0.1% (0.0-0.2) | 0/100 |
| – – O | 4.7% (2.8-7.7) | 5.0% (2.9-8.5) | 0.0% (0.0-6.0) | 97.0% (91.5-99.0) | 28.3% (27.1-29.6) | 0/100 |
| – – – | 11.7% (8.5-15.8) | 5.0% (2.9-8.5) | 0.0% (0.0-6.0) | 99.0% (94.6-99.8) | 53.2% (51.9-54.6) | 0/100 |
| direct app prompt + O | 2.3% (1.1-4.7) | 2.5% (1.2-5.3) | 0.0% (0.0-6.0) | 97.0% (91.5-99.0) | 32.9% (31.6-34.2) | 0/100 |
| direct app prompt | 10.3% (7.4-14.3) | 2.5% (1.2-5.3) | 0.0% (0.0-6.0) | 99.0% (94.6-99.8) | 61.6% (60.2-62.9) | 0/100 |


Paired differences against the full gateway (R G O), percentage points, 95% bootstrap over notes:

| Turned off | Attack success, all | Excl. PHI goal | Benign notes leaking PHI | PHI values leaked, all notes |
|---|---|---|---|---|
| O (output filter) | +0.0 (+0.0 to +0.0) | +0.0 (+0.0 to +0.0) | +0.0 (+0.0 to +0.0) | +0.0 (+0.0 to +0.0) |
| R (input redaction) | +0.0 (+0.0 to +0.0) | +0.0 (+0.0 to +0.0) | +4.0 (+1.0 to +8.0) | +0.2 (+0.1 to +0.5) |
| G (wrapping + security rules) | +0.0 (+0.0 to +0.0) | +0.0 (+0.0 to +0.0) | +1.0 (+0.0 to +3.0) | +0.1 (+0.0 to +0.3) |
| R and O | +0.0 (+0.0 to +0.0) | +0.0 (+0.0 to +0.0) | +10.0 (+5.0 to +16.0) | +0.8 (+0.5 to +1.1) |
| R and G | +4.7 (+2.3 to +7.3) | +5.0 (+2.5 to +7.9) | +97.0 (+93.0 to +100.0) | +28.3 (+26.4 to +30.2) |
| all three | +11.7 (+8.0 to +15.3) | +5.0 (+2.5 to +7.9) | +99.0 (+97.0 to +100.0) | +53.2 (+50.4 to +56.2) |
| gateway (direct app prompt) | +10.3 (+7.0 to +14.0) | +2.5 (+0.8 to +4.6) | +99.0 (+97.0 to +100.0) | +61.6 (+59.6 to +63.6) |

PHI values leaked by type, all 400 notes (leaked / gold values):

| Layers (R G O) | NAME | DATE | ID | PHONE | ADDRESS | EMAIL |
|---|---|---|---|---|---|---|
| R G O | 0.0% (0/2320) | 0.0% (0/737) | 0.0% (0/657) | 0.0% (0/558) | 0.0% (0/673) | 0.0% (0/76) |
| R G – | 0.0% (0/2320) | 0.0% (0/737) | 0.0% (0/657) | 0.0% (0/558) | 0.0% (0/673) | 0.0% (0/76) |
| – G O | 0.2% (4/2320) | 1.1% (8/737) | 0.0% (0/657) | 0.0% (0/558) | 0.0% (0/673) | 0.0% (0/76) |
| – G – | 1.2% (29/2320) | 1.2% (9/737) | 0.0% (0/657) | 0.0% (0/558) | 0.0% (0/673) | 0.0% (0/76) |
| R – O | 0.2% (5/2320) | 0.0% (0/737) | 0.0% (0/657) | 0.0% (0/558) | 0.0% (0/673) | 0.0% (0/76) |
| R – – | 0.2% (5/2320) | 0.0% (0/737) | 0.0% (0/657) | 0.0% (0/558) | 0.0% (0/673) | 0.0% (0/76) |
| – – O | 55.9% (1297/2320) | 12.6% (93/737) | 2.1% (14/657) | 0.0% (0/558) | 2.8% (19/673) | 0.0% (0/76) |
| – – – | 76.9% (1785/2320) | 45.7% (337/737) | 28.0% (184/657) | 36.7% (205/558) | 23.3% (157/673) | 6.6% (5/76) |
| direct app prompt + O | 65.8% (1527/2320) | 11.7% (86/737) | 3.2% (21/657) | 0.0% (0/558) | 2.4% (16/673) | 0.0% (0/76) |
| direct app prompt | 91.4% (2120/2320) | 44.5% (328/737) | 28.6% (188/657) | 46.2% (258/558) | 29.4% (198/673) | 1.3% (1/76) |

Latency per call in-process (ms, median / 90th percentile; includes Bedrock): direct app prompt 1525 / 1882, R G 1780 / 2330, – G 1743 / 2296, R – 2237 / 2693, – – 1917 / 2442

Failed calls: direct app prompt 0, R G 0, – G 0, R – 0, – – 0

### What each layer does

- **Any one of R or G stops nearly all PHI leakage on these notes.** With both off, 53% of gold PHI values reach the reply (99 of 100 benign summaries leak something). R alone leaves 0.1% (5 names in 2,320) and G alone 0.8%. With both, nothing leaked. The synthetic notes' PHI is easy for the model (in-distribution formats), so R's leak rate here is a floor. On real notes R misses about 19% of PHI (setup A on PhysioNet, below), and G is then the backstop.
- **G works by asking the model not to repeat PHI** (security rule 2), and Haiku largely complies: 0.8% of values leaked with G alone. That is a request, not a guarantee, and it fails most on names (29 of 2,320) and dates.
- **O is a weak layer on its own.** It halves leakage without R or G (53.2% → 28.3%), but its rules catch only formatted values: 56% of names still get through. Once R or G is on, O changed nothing measurable (+0.0 points). It stays useful as a last check for structured identifiers (IDs, phones, emails).
- **Attack success outside the PHI goal was already low.** It was 5.0% with every layer off, almost all from the link (markdown-image exfiltration) goal. Either R or G took it to 0 of 240.
  - R's effect here is partly an artifact of the attacks: redaction treats the attacker's URL and 6-character codes as PHI, so only 5 of 60 marker codes and 0 of 60 URLs reach the model intact. With R on and G off, the model rendered no markdown images at all. That is a real defense against URL-based exfiltration. It would not stop an attacker who avoids URLs and codes, which the adaptive attacks in goal 1 should test.
  - G stops the same attacks without changing the payload.
- **Canary leaks did not recur.** v1 saw Haiku quote the system-prompt canary in 2 of 60 gateway attacks (3.3%). In this run no condition leaked it (0 of 60 each; upper bound 6.0%). The v1 leaks were rare events, so the fix (secrets out of the prompt, or a reply filter) still stands.
- **The direct baseline reproduced v1 exactly:** 10.3% attack success on all attacks and 2.5% outside the PHI goal.
- **No layer refused benign notes** (0 of 100 in every cell).

Latency per call (in-process, includes Bedrock): median 1.5 s direct, 1.8 s for the full gateway. Redaction adds about 0.1–0.2 s on CPU (`utility_redaction.md`), and the rest is Bedrock variance.

## Redaction layer: leave one part out (PhysioNet test half)

`eval/deid_ablation_physionet.py` starts from setup A (public Stanford model, rules, threshold 0.02, name lexicon; `deid_physionet_best.md`) and removes one part at a time. It scores through the gateway code on the 1,101 test-half notes, which no setting was tuned on. Only aggregates are printed. Δ is the paired difference from setup A in percentage points, with a 95% bootstrap over notes.

| Variant | PHI found (95% CI) | Δ vs A | Names | Δ names | Dates | With EHR names: PHI found | Δ vs A | Names | Other words removed |
|---|---|---|---|---|---|---|---|---|---|
| Setup A (all parts) | 80.9% (77.6–84.1) |  | 72.8% |  | 93.8% | 87.6% |  | 85.5% | 1.75% |
| − name lexicon | 80.1% (76.7–83.2) | -0.8 (-1.5 to -0.3) | 71.2% | -1.6 (-2.9 to -0.6) | 93.8% | 86.7% | -0.8 (-1.5 to -0.3) | 83.9% | 1.58% |
| − threshold 0.02 (top label) | 78.4% (75.0–81.7) | -2.5 (-3.6 to -1.5) | 71.2% | -1.6 (-2.8 to -0.6) | 91.8% | 85.2% | -2.3 (-3.4 to -1.4) | 83.9% | 1.23% |
| − month/day date rule | 76.0% (72.3–79.4) | -5.0 (-6.5 to -3.5) | 72.8% | +0.0 (+0.0 to +0.0) | 77.7% | 82.6% | -5.0 (-6.5 to -3.5) | 85.5% | 1.71% |
| − all rules (model + lexicon) | 75.2% (71.5–78.8) | -5.7 (-7.3 to -4.2) | 71.8% | -1.0 (-2.1 to +0.0) | 77.7% | 82.3% | -5.3 (-6.9 to -3.8) | 85.3% | 1.11% |
| − model (rules + lexicon) | 47.7% (44.1–51.4) | -33.2 (-36.8 to -29.6) | 39.7% | -33.1 (-38.5 to -27.9) | 83.2% | 63.4% | -24.1 (-27.5 to -20.9) | 69.8% | 0.83% |

- **The model does most of the work.** Rules and lexicon alone find 47.7% of PHI; the model adds 33 points. With EHR names, rules alone reach 63.4%.
- **The month/day rule is the most valuable rule** (−5.0 points without it, dates 93.8% → 77.7%). The other rules add little on these nursing notes (−0.7 more), because the model already catches the formatted values they target.
- **The 0.02 threshold adds 2.5 points** over the top-label rule, at 0.5 points more over-redaction (1.23% → 1.75% of other words).
- **The name lexicon adds 0.8 points** (names +1.6). That is small but significant, and it costs 0.17 points of over-redaction.
- **EHR names add 6.7 points** in setup A, the largest single addition after the model.
- **Every part's interval excludes zero**, except the rules' small effect on names.

## Limits

- **Synthetic notes for the injection cells.** Their PHI is in formats the redactor handles well, so R's near-zero leakage there is optimistic. PhysioNet shows R alone misses about 19% of real PHI (12% with EHR names).
- **One model, one run per case** (Claude Haiku 4.5, temperature 0.2). Rare events such as v1's canary leaks can appear or vanish between runs.
- **Template attacks** with success checked by codes and URLs, which redaction can destroy. Adaptive attacks are not tested yet.
- **The PHI leakage check is string matching.** A model that paraphrases a value ("born in the spring of 1950") is not counted.
