# Format-bias check: MIMIC test notes with unseen surrogate formats

Run on Colab (T4) on 2026-11-26 with `eval/train_deid_colab.ipynb` (cell "unseen") at commit `6ab3af2`. The test uses the same 1,000 held-out MIMIC-III notes as `deid_colab_3seed.md`, with the same held-out names, but `--surrogate-style unseen` writes the other fake values in formats the training generator never produces:
- dates such as "14 Mar 2026", "14.03.2026", "Mar. 14th 2026";
- IDs with letters, dashes or "#";
- phones such as "(608) 555 0143", "608.555.0143" or "x2145";
- "PO Box" and "Rural Route" addresses;
- unseen cities and facility names;
- ages over 89 written "ninety-two" or "92yo".

Scoring is the gateway pipeline, paired by note against the original model.

| Model | PHI found | ADDRESS | AGE_OVER_89 | DATE | FACILITY | ID | LOCATION | MONTH | NAME | PHONE | Other words removed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Original `obi/deid_roberta_i2b2` | 85.0% (84.2–85.9) | 21.1% | 0.0% | 94.0% | 62.7% | 66.5% | 80.8% | 84.1% | 72.6% | 97.2% | 0.5% |
| Retrained seed 11 | 76.7% (75.5–77.8) | 0.0% | 14.3% | 72.1% | 53.4% | 64.0% | 95.9% | 92.1% | 98.7% | 82.2% | 0.2% |
| Retrained seed 12 | 72.3% (71.0–73.5) | 0.0% | 14.3% | 65.8% | 50.9% | 63.8% | 88.2% | 92.9% | 97.3% | 82.4% | 0.2% |
| Retrained seed 13 | 70.7% (69.4–72.0) | 5.3% | 14.3% | 62.9% | 55.6% | 64.0% | 82.9% | 84.1% | 96.9% | 79.6% | 0.2% |

Clinical terms stayed 100% intact for every model.

## Paired differences from the original (95% CI)

| Label | Seed 11 | Seed 12 | Seed 13 | Mean of 3 (range) |
|---|---|---|---|---|
| All PHI | −8.3 (−9.6 to −7.1) | −12.7 (−14.2 to −11.3) | −14.3 (−15.8 to −12.9) | 73.2% (70.7–76.7) |
| NAME | +26.1 (+23.7 to +28.5) | +24.6 (+22.4 to +26.9) | +24.3 (+22.0 to +26.7) | 97.6% (96.9–98.7) |
| DATE | −22.0 (−23.7 to −20.2) | −28.2 (−30.1 to −26.2) | −31.1 (−33.2 to −29.1) | 66.9% (62.9–72.1) |
| ID | −2.5 (−4.0 to −1.1) | −2.8 (−4.3 to −1.3) | −2.5 (−4.0 to −1.1) | 63.9% (63.8–64.0) |
| AGE_OVER_89 | +14.3 (+2.3 to +29.5) | +14.3 (+2.3 to +29.5) | +14.3 (+2.3 to +29.5) | 14.3% |
| PHONE | | | | 81.4% (79.6–82.4), vs 97.2% |
| LOCATION | | | | 89.0% (82.9–95.9), vs 80.8% |

## What this shows

- **Retraining learned the generator's formats.** With the usual formats the retrained models found 99.2% of PHI against the original's 90.3% (`deid_colab_3seed.md`). With unseen formats they find 73.2% against 85.0%. The largest loss is dates, down 22 to 31 points. The original model, trained on i2b2's human-made surrogates, handles the new date formats well (94.0%); the retrained models no longer do.
- **Names still transfer.** Names come from held-out Faker pools in both tests and stay near 97–99%, so the name gain is not a format effect. The PhysioNet gold test (`deid_physionet_gold.md`) shows names do not transfer to independently written surrogates either, though.
- **Ages over 89 written out are almost never caught.** Only 14.3% for the retrained models and 0% for the original, against 87% for numeric ages in the main test.
- **Phone recall drops for the retrained models** on the new formats (81% against 97%).

This agrees with the PhysioNet gold result and motivates the "rich" generator (`mimic_surrogates.py`, style `rich`), which draws values from large pools in many formats.

## Limits

- The unseen formats were written by us, so they test format variety, not every format real notes use.
- One sample of 1,000 notes; ADDRESS has 19 spans and AGE_OVER_89 has 42, so those intervals are wide.
- A model trained on the rich generator will have seen some of these formats, so this test is no longer "unseen" for it; the PhysioNet gold test half is the clean check there.
