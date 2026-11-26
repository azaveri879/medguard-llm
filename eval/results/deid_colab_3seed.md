# Retraining, 3 seeds: original vs MIMIC-retrained model

Run on Colab (L4, Python 3) on 2026-11-25/26 with `eval/train_deid_colab.ipynb` at commit `73ff39a`, `SEEDS = [11, 12, 13]`.

- **Training:** for each seed, 5,000 MIMIC-III notes (1,000 each from Nursing/other, Radiology, Nursing, Physician and Discharge summary). Notes come from train-split patients only, with names from the train name pool only. Each seed draws its own training sample, giving 20,821, 21,038 and 21,040 windows. Training ran 2 epochs at batch 16 and lr 2e-5, taking 5,552 s, 5,614 s and 5,607 s. Mean loss in epoch 2 was 0.0033–0.0034 for every seed, with no non-finite loss.
- **Test:** the same 1,000 notes for every model (200 per category), from held-out test-split patients, with held-out Faker test names. Name spans by role: other 1,951, care team 1,172, patient 407. Notes are downloaded with the BigQuery Storage Read API and sorted by `row_id` before seeded sampling, so this sample can be drawn again exactly. That was not true before `73ff39a`, so the test set differs from the pilot's.
- **Scoring:** the gateway pipeline (rules, then the model). `known-patient-care` also gets the patient and care-team names an EHR could supply. Differences are paired by note, with 95% bootstrap intervals (2,000 resamples of notes) from `deid_compare.py`. Timing (ms/note) was measured on the Colab runtime's CPU, not on the gateway.

## Summary, gateway pipeline

| Measure | Original | Retrained, mean of 3 (SD, range) | Difference vs original, per seed (95% CI) |
|---|---|---|---|
| PHI found, all types | 90.3% | 99.2% (0.13, 99.0–99.3%) | +9.0 (+8.3 to +9.7), +8.9 (+8.2 to +9.6), +8.7 (+8.0 to +9.4) |
| Names found | 71.3% | 97.8% (0.79, 97.2–98.7%) | +27.5 (+25.0 to +30.0), +26.3 (+23.8 to +28.8), +25.9 (+23.5 to +28.4) |
| Ages over 89 found (42 spans) | 66.7% | 87.3% (1.37, 85.7–88.1%) | +19.0 (+4.9 to +36.1), +21.4 (+7.3 to +38.3), +21.4 (+7.0 to +39.0) |
| Dates found | 95.9% | 99.8% (0.11, 99.6–99.9%) | +3.7 to +3.9; every lower bound ≥ +3.2 |
| Locations found | 81.2% | 99.2% (0.41, 98.8–99.6%) | +17.6 to +18.4; every lower bound ≥ +12.0 |
| Clinical terms intact | 100.0% | 100.0% | |
| Other words removed | 0.5% | 0.2% | |

With EHR-supplied names (`known-patient-care`): PHI found rose from 92.6% to a mean of 99.3% (SD 0.12, range 99.2–99.4%), with seeds at +6.8, +6.7 and +6.5 points and every lower bound ≥ +6.0. Names rose from 81.2% to a mean of 98.4% (SD 0.78, range 97.8–99.3%), with every lower bound ≥ +14.9.

**Ages over 89 are now caught more often, but not always.** The retrained models catch 36 or 37 of 42 spans (85.7–88.1%), against 28 (66.7%) for the original. Every seed's interval excludes zero, but the intervals are wide (lower bounds +4.9 to +7.3 points) because there are only 42 spans. About 1 in 8 ages over 89 still gets through.

## Original model (`obi/deid_roberta_i2b2`)

| Detector | PHI found | ADDRESS | AGE_OVER_89 | DATE | EMAIL | FACILITY | ID | LOCATION | MONTH | NAME | PHONE | Clinical terms intact | Other words removed | ms/note (CPU) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pipeline | 90.3% | 73.7% | 66.7% | 95.9% | 100.0% | 98.8% | 98.9% | 81.2% | 84.9% | 71.3% | 95.1% | 100.0% | 0.5% | 205 |
| known-patient-care | 92.6% | 73.7% | 66.7% | 96.0% | 100.0% | 98.9% | 98.9% | 82.0% | 85.7% | 81.2% | 95.1% | 100.0% | 0.5% | 197 |

95% intervals (notes resampled): pipeline PHI found 89.6–91.0%, names 68.7–73.8%. known-patient-care PHI found 92.1–93.2%, names 79.3–83.1%.

## Retrained, per seed

| Seed | Detector | PHI found | ADDRESS | AGE_OVER_89 | DATE | EMAIL | FACILITY | ID | LOCATION | MONTH | NAME | PHONE | Clinical terms intact | Other words removed | ms/note (CPU) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 11 | pipeline | 99.3% | 94.7% | 85.7% | 99.6% | 100.0% | 100.0% | 99.6% | 98.8% | 99.2% | 98.7% | 95.1% | 100.0% | 0.2% | 203 |
| 11 | known-patient-care | 99.4% | 94.7% | 85.7% | 99.6% | 100.0% | 100.0% | 99.6% | 98.8% | 99.2% | 99.3% | 95.1% | 100.0% | 0.2% | 197 |
| 12 | pipeline | 99.2% | 94.7% | 88.1% | 99.9% | 100.0% | 100.0% | 99.6% | 99.2% | 100.0% | 97.5% | 95.1% | 100.0% | 0.2% | 203 |
| 12 | known-patient-care | 99.3% | 94.7% | 88.1% | 99.9% | 100.0% | 100.0% | 99.6% | 99.2% | 100.0% | 98.1% | 95.1% | 100.0% | 0.2% | 197 |
| 13 | pipeline | 99.0% | 94.7% | 88.1% | 99.7% | 100.0% | 100.0% | 99.6% | 99.6% | 100.0% | 97.2% | 95.1% | 100.0% | 0.2% | 203 |
| 13 | known-patient-care | 99.2% | 94.7% | 88.1% | 99.7% | 100.0% | 100.0% | 99.6% | 99.6% | 100.0% | 97.8% | 95.1% | 100.0% | 0.2% | 196 |
| | Spans scored | 15765 | 19 | 42 | 9419 | 1 | 1446 | 472 | 245 | 126 | 3530 | 465 | 7529 | 602120 | |

95% intervals (notes resampled), pipeline: PHI found 99.1–99.4% / 99.0–99.3% / 98.8–99.2%; names 98.3–99.1% / 96.9–98.1% / 96.6–97.8% for seeds 11 / 12 / 13.

## Limits

- **Same source and same generator.** Training and test notes both come from MIMIC, and their fake dates, IDs, phones and places come from the same generator (`mimic_surrogates.py`). Part of the gain may come from learning that generator's formats. The original model was trained on i2b2/n2c2 notes, so this test favors the retrained model. An external test on the n2c2 2014 test set and a test with surrogate formats the generator never produces are both still needed.
- **Recall only.** "Other words removed" is the only over-redaction measure. Entity-level precision and strict/relaxed F1 need gold-annotated notes (n2c2).
- **Small categories.** ADDRESS (19 spans), AGE_OVER_89 (42) and EMAIL (1) have wide intervals. ADDRESS and PHONE did not change across seeds (94.7% and 95.1%), which points to a rules or generator limit rather than the model. Neither has been examined yet.
- **Seed variation is in names.** The spread across seeds is small for PHI found overall (SD 0.13 points) and larger for names (SD 0.79, 97.2–98.7%). Three seeds are enough to show the gain is not one lucky run, but not enough to estimate seed variance precisely.
- **Not comparable row by row with the pilot** (`deid_colab_pilot.md`). Its test sample was drawn before notes were sorted by `row_id`, and it had 30 age-over-89 spans, not 42. The pilot's "T4" label is also probably wrong: a T4 cannot run batch 16 in 2,730 s.
- **Weights are not published.** They derive from MIMIC and are kept only in the owner's Google Drive and the git-ignored `eval/models/`.
