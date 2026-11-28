# Retraining pilot: original vs MIMIC-retrained model

Run on Colab (T4) on 2026-11-14 with `eval/train_deid_colab.ipynb` at commit `322ffe7`.

- **Training:** 5,000 MIMIC-III notes (1,000 each from Nursing/other, Radiology, Nursing, Physician and Discharge summary), train patient split only, train name pool only. That gave 20,912 windows. Training ran 2 epochs, batch 16, lr 2e-5, seed 11. Mean loss fell from 0.0074 in epoch 1 to 0.0035 in epoch 2, with no non-finite loss. Training took 2,730 s.
- **Test:** 1,000 notes (200 per category) from held-out test-split patients, with held-out Faker test names. Name spans by role: care team 1,157, other 1,921, patient 300.
- **Scoring:** the gateway pipeline (rules, then the model). `known-patient-care` also gets the patient and care-team names an EHR could supply. Timing was measured on a GPU runtime, not on the gateway.

## Original model (`obi/deid_roberta_i2b2`)

| Detector | PHI found | ADDRESS | AGE_OVER_89 | DATE | FACILITY | ID | LOCATION | MONTH | NAME | PHONE | Clinical terms intact | Other words removed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pipeline | 90.9% | 87.5% | 70.0% | 96.1% | 97.1% | 98.7% | 86.2% | 89.6% | 71.8% | 94.6% | 99.9% | 0.5% |
| known-patient-care | 92.9% | 87.5% | 70.0% | 96.1% | 97.0% | 98.5% | 87.1% | 89.6% | 81.2% | 94.6% | 99.9% | 0.5% |

## Retrained (seed 11)

| Detector | PHI found | ADDRESS | AGE_OVER_89 | DATE | FACILITY | ID | LOCATION | MONTH | NAME | PHONE | Clinical terms intact | Other words removed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pipeline | 99.3% | 100.0% | 70.0% | 99.7% | 100.0% | 99.8% | 100.0% | 100.0% | 98.6% | 94.3% | 99.9% | 0.2% |
| known-patient-care | 99.4% | 100.0% | 70.0% | 99.7% | 100.0% | 99.8% | 100.0% | 100.0% | 99.0% | 94.3% | 99.9% | 0.2% |
| Spans scored | 16111 | 8 | 30 | 9964 | 1496 | 453 | 217 | 106 | 3378 | 459 | 7450 | 604670 |

## Limits

- **Same source and same generator.** Training and test notes come from the same source, and their fake dates, IDs, phones and places come from the same generator (`mimic_surrogates.py`). Part of the gain may come from learning that generator's formats. The original model was trained on i2b2/n2c2 notes, so this test favors the retrained model. An external test on the n2c2 2014 test set is needed.
- **One run, no intervals.** This was a single seed with no confidence intervals. The notebook now trains several seeds and reports paired bootstrap intervals.
- **Age over 89 stayed at 70%** (30 spans) because the gateway ignored the model's AGE label. Retrained models now record that their AGE label means over 89 (`medguard_age_over_89` in `config.json`), and the gateway redacts it for those models. This hasn't been measured yet.
- **The test notes are not the same as earlier MIMIC tables.** These are 5 categories from BigQuery. `deid_benchmark_mimic.md` used 400 Nursing/other and Radiology notes from a local file. Don't compare the two tables row by row.
- **Weights are not published.** They derive from MIMIC and are kept locally in the git-ignored `eval/models/`.
