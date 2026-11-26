# External test: PhysioNet gold-standard nursing notes

Scored on 2026-11-26 with `deid_benchmark.py --physionet-deid` (loader: `eval/physionet_deid.py`), on CPU, inference only.

- **Data:** PhysioNet's "Deidentified Medical Text" v1.0 (credentialed; DOI 10.13026/jc2a-ca12): 2,434 MIMIC-II nursing notes. Experts reviewed every note, and every PHI instance was replaced by a realistic surrogate chosen by the corpus authors (`id.text`). The same notes with PHI replaced by MIMIC-style tags (`id.res`) give the gold spans. All 2,434 records lined up exactly, for 2,026 scored PHI spans (138 year-only, initials and similar spans are skipped as in the MIMIC test).
- **Why it matters:** the surrogates were not made by our generator (`mimic_surrogates.py`), so this tests what retraining learned without that generator's formats or value lists.
- **Models:** the original `obi/deid_roberta_i2b2` and the three retrained seeds from `deid_colab_3seed.md`, each in the gateway pipeline (rules, then the model), plus three baselines scored by the same code. No setting was tuned on this corpus. The Presidio threshold (0.35) and the pipeline settings come from earlier runs on other data.
- **Intervals:** 95% bootstrap over notes. Differences are paired by note (`deid_compare.py`).

## Results

| Detector | PHI found (95% CI) | ADDRESS | AGE_OVER_89 | DATE | FACILITY | LOCATION | NAME | PHONE | Other words removed |
|---|---|---|---|---|---|---|---|---|---|
| Rules only | 13.5% (11.3–15.7) | 8.3% | 60.0% | 7.4% | 0.0% | 1.6% | 19.0% | 55.1% | 0.6% |
| Presidio | 51.1% (48.3–53.9) | 0.0% | 0.0% | 18.9% | 61.4% | 73.8% | 66.9% | 67.3% | 12.1% |
| Pipeline, original model | 64.8% (62.2–67.4) | 8.3% | 60.0% | 64.4% | 65.0% | 67.2% | 64.5% | 87.8% | 0.8% |
| Pipeline, retrained seed 11 | 57.5% (54.6–60.1) | 8.3% | 60.0% | 77.2% | 14.2% | 29.5% | 57.2% | 77.6% | 0.6% |
| Pipeline, retrained seed 12 | 55.5% (52.6–58.1) | 8.3% | 60.0% | 81.4% | 15.0% | 26.2% | 50.7% | 79.6% | 0.6% |
| Pipeline, retrained seed 13 | 55.1% (52.1–57.8) | 8.3% | 60.0% | 74.6% | 18.7% | 24.6% | 53.0% | 83.7% | 0.6% |
| Stanford de-identifier (model only) | 71.5% (68.9–74.0) | 16.7% | 0.0% | 71.9% | 81.3% | 78.7% | 69.4% | 75.5% | 0.4% |
| **Pipeline, Stanford model** | **73.5% (71.0–75.8)** | 16.7% | 60.0% | 73.7% | 82.1% | 77.0% | 71.4% | 85.7% | 1.0% |
| Spans scored | 2026 | 12 | 5 | 623 | 246 | 61 | 1028 | 49 | 360858 words |

EMAIL and ID have one span each and are left out. The corpus marks no dose or eponym spans, so "clinical terms intact" is not measured here.

## Retrained vs original (paired, pipeline)

| Label | Original | Retrained, mean of 3 (range) | Per-seed difference (95% CI) |
|---|---|---|---|
| All PHI | 64.8% | 56.0% (55.1–57.5) | −7.3 (−9.7 to −5.0), −9.3 (−11.7 to −6.8), −9.7 (−12.0 to −7.4) |
| NAME | 64.5% | 53.6% (50.7–57.2) | −7.3 (−9.9 to −4.8), −13.8 (−16.9 to −11.0), −11.5 (−14.3 to −8.9) |
| DATE | 64.4% | 77.7% (74.6–81.4) | +12.8 (+9.1 to +17.0), +17.0 (+13.1 to +21.4), +10.3 (+6.8 to +14.2) |
| FACILITY | 65.0% | 16.0% (14.2–18.7) | −50.8 (−58.1 to −43.2), −50.0 (−57.1 to −42.4), −46.3 (−53.4 to −38.9) |
| LOCATION | 67.2% | 26.8% (24.6–29.5) | −37.7 (−53.1 to −23.0), −41.0 (−55.6 to −27.4), −42.6 (−57.1 to −28.6) |
| PHONE | 87.8% | 80.3% (77.6–83.7) | −10.2 (−21.4 to −2.4), −8.2 (−17.8 to −1.8), −4.1 (−11.4 to +0.0) |

**The best configuration is our pipeline with the Stanford model** (`PHI_NER_MODEL=StanfordAIMI/stanford-deidentifier-base`; its HCW, HOSPITAL and VENDOR labels map to NAME, LOCATION and OTHER). Against the original pipeline it finds +8.7 points more PHI (+7.1 to +10.5), with names +6.9 (+4.9 to +8.9), dates +9.3 (+6.3 to +12.7), facilities +17.1 (+10.9 to +23.9) and locations +9.8 (+3.3 to +17.5). Our rules add +2.0 points (+1.4 to +2.7) over the Stanford model alone. It removes 1.0% of other words, against 0.8%, and runs about 4.5 times faster on CPU (70 ms per note against 320) because it is BERT-base rather than RoBERTa-large.

Against the original pipeline, the Stanford model alone finds more PHI: +6.7 points (+5.1 to +8.4), with names +4.9 (+2.9 to +6.9), dates +7.5 (+4.6 to +10.7) and facilities +16.3 (+10.3 to +22.9). Presidio finds less: −13.7 (−16.6 to −10.7).

## What this means

- **Retraining on our MIMIC surrogates does not generalize.** It raised recall on our MIMIC test from 90.3% to 99.2% (`deid_colab_3seed.md`). On notes with independently written surrogates, every seed is significantly worse than the original model, except on dates. The losses are largest for facilities and locations. Our generator draws those from 6 fixed facility names and 8 cities, so the retrained models appear to have learned those values rather than what a facility or place looks like. Names also drop, so the training sample (5,000 notes, Faker names) may also have narrowed what the model treats as a name.
- **The in-distribution MIMIC result should not be reported as a recall gain on its own.** It needs this external result beside it.
- **Our rules contribute little on these notes** (13.5% alone). Most dates here are bare "month-day" forms such as 3-12, which the rules do not match. The missed-span tally (character class around each miss, no text) shows most date misses have a space on both sides.
- **A stronger off-the-shelf model is the better base.** Swapping in the Stanford model is the best result here, at 73.5%. That is still well short of what real notes need.

## Limits

- **Related source.** The corpus is MIMIC-II nursing notes, and MIMIC-III includes the MIMIC-II era, so a few of these notes may also appear, with different surrogates, among the 1,000 nursing notes each seed trained on. Any such overlap would favor the retrained models, so it cannot explain their drop.
- **Broad PHI labels.** Every model finds only 55–72% here, much less than on our MIMIC test. The corpus tags things our test does not count the same way: for example "Wardname" tags, which we count as FACILITY, and many short month-day dates. The comparison between models on the same notes still holds.
- **Small categories.** ADDRESS (12 spans), AGE_OVER_89 (5), EMAIL (1) and ID (1) are too small to compare.
- **Recall only.** Over-redaction is measured only as "other words removed". Gold annotations here mark PHI spans but do not let us score precision by type.
- **Note text never left the machine.** Scoring ran locally on the credentialed files in the git-ignored `eval/DESTINATION/`. Only these aggregate tables are committed.
