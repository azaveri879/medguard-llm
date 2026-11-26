# Closing the gap on PhysioNet's gold notes: date rule, threshold and model union

Run on 2026-11-26, on CPU, inference only. PhysioNet's 2,434 gold nursing notes (`deid_physionet_gold.md`) are split by patient (`physionet_deid.physionet_split`) into a tune half (1,333 notes, 78 patients) and a test half (1,101 notes, 85 patients). Every choice below was made on the tune half. The test half was scored once, for the settings chosen there.

All settings use the gateway pipeline with `StanfordAIMI/stanford-deidentifier-base`, the best model on these notes. The selection rule is the most PHI found with no more than 2% of other words removed (the agreed target in the progress log).

## 1. A rule for bare month/day dates

Our rules found 7% of dates here, because nursing notes write most dates as `3/12` or `3-12`. Gold-date shapes on the tune half (digits as 9): `9/99` 127, `99/99` 53, `9/9` 45, `9-9` 29, `99/9` 26, and so on. A plain month/day pattern also matched 193 non-dates: "q 2-4 hrs", "RR 18-22", "CVP 8-12", "CPAP 5/5", "D5 1/2 NS", "1/2 tab". So the new rule (`MONTH_DAY` in `services/gateway/phi_redaction.py`) rules out matches after measurement words and before units.

On the tune half it hits 265 of 331 gold dates (80%), with 41 false matches in about 180,000 words.

## 2–3. Decision threshold and union with the original model

The pipeline can mark a token as PHI when a PHI label is the model's top choice (default), or when the total PHI probability reaches a threshold. The union adds whatever `obi/deid_roberta_i2b2` flags on its own.

| Setting (tune half, 1,333 notes) | PHI found | Names | Dates | Facilities | Other words removed |
|---|---|---|---|---|---|
| top label | 80.9% | 73.5% | 94.0% | 79.6% | 0.97% |
| top label + obi union | 81.8% | 74.2% | 94.3% | 83.1% | 1.14% |
| PHI prob ≥ 0.5 | 81.2% | 74.1% | 94.0% | 79.6% | 0.97% |
| PHI prob ≥ 0.5 + obi union | 82.1% | 74.8% | 94.3% | 83.1% | 1.15% |
| PHI prob ≥ 0.3 | 81.8% | 74.2% | 94.3% | 83.1% | 1.05% |
| PHI prob ≥ 0.3 + obi union | 82.5% | 75.0% | 94.3% | 85.2% | 1.22% |
| PHI prob ≥ 0.2 | 82.2% | 74.2% | 94.6% | 85.2% | 1.11% |
| PHI prob ≥ 0.2 + obi union | 82.7% | 75.0% | 94.6% | 86.6% | 1.28% |
| PHI prob ≥ 0.1 | 82.6% | 74.6% | 94.6% | 86.6% | 1.22% |
| PHI prob ≥ 0.1 + obi union | 83.2% | 75.4% | 94.6% | 88.0% | 1.37% |
| PHI prob ≥ 0.05 | 82.8% | 74.8% | 94.6% | 86.6% | 1.35% |
| **PHI prob ≥ 0.05 + obi union** (chosen) | **83.4%** | **75.6%** | **94.6%** | **88.0%** | **1.49%** |

Recall rises steadily as the threshold falls, while over-redaction stays well under 2% throughout. The lowest threshold tried was chosen. Lower thresholds were not tried and may help further.

## Test half (1,101 notes), reported once

| Setting | PHI found (95% CI) | Names | Dates | Facilities | Other words removed |
|---|---|---|---|---|---|
| Stanford pipeline, old rules | 71.3% | 69.6% | 71.6% | 81.7% | 1.03% |
| + month/day date rule | 77.6% (74.1–80.9) | 69.6% | 91.8% | 81.7% | 1.06% |
| + threshold 0.05 + obi union (chosen) | **80.1% (76.8–83.3)** | 71.8% | 93.2% | 88.5% | 1.56% |

Paired differences on the same notes:

| Comparison | PHI found | Names | Dates | Facilities |
|---|---|---|---|---|
| Date rule vs old rules | +6.2 (+4.6 to +8.0) | +0.0 | +20.2 (+15.2 to +25.8) | +0.0 |
| Threshold + union vs date rule alone | +2.5 (+1.6 to +3.5) | +2.2 (+1.0 to +3.7) | — | +6.7 (+2.6 to +11.9) |
| All three vs old rules | +8.7 (+7.0 to +10.8) | +2.2 (+1.0 to +3.7) | +21.6 (+16.4 to +27.2) | +6.7 (+2.6 to +11.9) |

## Where this leaves the 90% target

- **80.1% of PHI on unseen notes**, up from 71.3% for the same model with the old rules and 64.8% for the original gateway (`deid_physionet_gold.md`, full corpus).
- **Dates are nearly solved** (93%) and facilities are at 89%.
- **Names are the bottleneck at 72%.** Neither rules nor threshold moved them much, and they are the most common PHI type here (about half of all spans). Getting near 90% overall needs names near 90%. That is what retraining the Stanford model on the rich generator plus this tune half is for. That run is in progress; its models are stored as `stanford_rich_seed*` on Drive.

## Limits

- One corpus (MIMIC-II nursing notes), split by patient. The test half has 85 patients, so the intervals are wide.
- The union and low threshold raise over-redaction from 1.06% to 1.56% of other words. Clinical terms were not separately scored here, because the corpus marks no dose or eponym spans.
- The threshold grid stopped at 0.05.
