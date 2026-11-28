# Reaching 90% on PhysioNet's gold notes

Run on 2026-11-26. Scored on the **test half** of PhysioNet's gold nursing notes (1,101 notes, 85 patients; `deid_physionet_tuning.md`). Neither the settings nor the retrained model ever saw those notes. Inference ran on CPU.

## What changed from the original gateway

1. **Base model:** `StanfordAIMI/stanford-deidentifier-base` instead of `obi/deid_roberta_i2b2` (`deid_physionet_gold.md`).
2. **Date rule:** bare month/day dates such as 3/12, with measurement contexts ruled out (`phi_redaction.MONTH_DAY`).
3. **Retraining:** the Stanford model fine-tuned on 5,000 MIMIC-III notes with "rich" surrogates plus the 1,333 notes of PhysioNet's tune half. The rich surrogates draw facilities, cities and streets from Faker's large pools in many formats. Run on Colab (T4), 2 epochs, batch 16, seed 11. The model is stored on Drive as `stanford_rich_seed11`; the name omits the PhysioNet part, but it was trained with it.
4. **Decision rule and union:** a token counts as PHI at total PHI probability ≥ 0.02. The original model's own detections are added (a union).
5. **Name lexicon:** words on Faker's first- and last-name lists (15 locales), minus ordinary English words (`/usr/share/dict/words`) and clinical eponyms such as Foley.
6. **EHR names (optional):** the patient and care-team names an EHR could pass in the request's `known_names` field. On this corpus they come from the gold tags' roles.

Items 4 and 5 were chosen on the tune half with the base Stanford model. The rule was the most PHI found with no more than 2% of other words removed. The retrained model was scored with those settings fixed in advance, because it trained on the tune half.

## Results, test half

| Setting | PHI found (95% CI) | Names (95% CI) | Dates | Facilities | Other words removed |
|---|---|---|---|---|---|
| Original gateway (obi model, old rules), full corpus | 64.8% | 64.5% | 64.4% | 65.0% | 0.8% |
| Stanford model + old rules | 71.3% | 69.6% | 71.6% | 81.7% | 1.03% |
| + date rule | 77.6% (74.1–80.9) | 69.6% | 91.8% | 81.7% | 1.06% |
| + threshold 0.05 + obi union | 80.1% (76.8–83.3) | 71.8% | 93.2% | 88.5% | 1.56% |
| Retrained Stanford (seed 11), alone | 77.4% | 66.5% | 93.5% | 92.3% | 0.73% |
| Retrained + threshold 0.05 + obi union | 82.7% (79.6–85.7) | 72.8% (67.8–77.8) | 96.6% | 98.1% | 1.17% |
| Retrained + threshold 0.02 + obi union + name lexicon | 84.3% (81.3–87.3) | 75.0% (70.1–79.8) | 97.9% | 98.1% | 1.53% |
| **Same, with EHR patient and care-team names** | **90.3% (88.1–92.5)** | **86.5% (82.8–89.9)** | 97.9% | 98.1% | **1.55%** |

Paired differences on the same notes:
- Retraining, within the 0.05 + union setting: +2.6 PHI points over the base Stanford model's 80.1%. Facilities rose from 88.5% to 98.1%, dates from 93.2% to 96.6%, and over-redaction fell from 1.56% to 1.17%.
- EHR names: +6.2 points (+4.2 to +8.3) and names +11.9 (+8.0 to +16.0), at threshold 0.05.
- Threshold 0.02 + lexicon over 0.05, with EHR names: +1.4 points (+0.6 to +2.2).

## Three seeds

The retrained model was trained three times, seeds 11, 12 and 13, each on its own MIMIC sample plus the same PhysioNet tune half. Each was scored through the gateway code (`deid_benchmark.py`, setup B below) on the test half with the settings fixed in advance.

| Seed | PHI found | Names | With EHR names: PHI found (95% CI) | Names | Other words removed |
|---|---|---|---|---|---|
| 11 | 84.2% | 74.8% | 90.1% (87.8–92.3) | 86.1% | 1.5% |
| 12 | 85.0% | 77.2% | 91.0% (88.9–93.2) | 88.9% | 1.7% |
| 13 | 86.0% | 77.2% | 92.0% (89.9–94.0) | 88.7% | 2.0% |
| **Mean (SD)** | **85.1% (0.90)** | 76.4% | **91.0% (0.95)** | 87.9% | 1.7% |

Paired against setup A (public Stanford model only, same notes):
- without EHR names, +3.3 (+1.9 to +4.8), +4.1 (+2.7 to +5.6) and +5.1 (+3.5 to +6.6);
- with them, +2.5 (+1.2 to +4.0), +3.5 (+2.2 to +4.9) and +4.4 (+3.0 to +5.9).

Every seed reaches 90% with EHR names. Seed 13 sits at the 2% over-redaction limit.

On the MIMIC tests run in Colab, the same three models score as follows:
- **Default formats:** 97.5% of PHI (97.1–97.8%), against 91.2% for the base Stanford model. Names rise from 75.6% to 95.6%.
- **Unseen formats:** 90.3% against 88.9%.

Unlike the earlier retraining on the default generator (73.2% with unseen formats, `deid_unseen_formats.md`), this one did not collapse. The rich generator does produce some formats close to the unseen ones, though, so PhysioNet remains the clean test.

## Where the gain comes from: rich surrogates vs PhysioNet notes

A second run trained the Stanford model on the rich surrogates only: the same 5,000 MIMIC notes per seed, without the PhysioNet tune half. Its models are stored as `stanford_richonly_seed*`. A rich-only model has never seen any note from the PhysioNet corpus, so for it the test half is fully independent.

Mean of 3 seeds, test half, setup B settings:

| Model | PHI found (range) | Names | With EHR names (range) | Names | Other words removed |
|---|---|---|---|---|---|
| Public Stanford model (setup A) | 80.9% | 72.8% | 87.6% | 85.5% | 1.7% |
| Retrained, rich surrogates only | 83.7% (83.0–84.0) | 75.2% | **90.0% (89.6–90.2)** | 87.3% | 1.5–1.7% |
| Retrained, rich surrogates + PhysioNet tune half | 85.1% (84.2–86.0) | 76.4% | 91.0% (90.1–92.0) | 87.9% | 1.5–2.0% |

Paired differences on the same notes:
- **Rich-only over setup A:** +3.1 (+1.6 to +4.6), +2.1 (+0.8 to +3.5) and +3.1 (+1.9 to +4.3); with EHR names +2.5, +2.0 and +2.6, all significant.
- **Adding the PhysioNet tune half, seed by seed:** +0.2 (−0.6 to +1.1), +2.0 (+1.0 to +3.1) and +2.0 (+1.0 to +3.1); with EHR names +0.0, +1.5 and +1.8.

So **most of the gain comes from the rich surrogate generator** (about +2.8 points over the public model). The PhysioNet notes add about +1.4 more, significant in 2 of 3 seeds. The cleanest result is the rich-only model with EHR names: 90.0% on notes from a corpus it never saw, trained only on MIMIC with synthetic surrogates.

## Built into the gateway

Everything above now runs in the gateway (`services/gateway/ner_redaction.py`), configured by environment variables:

| Variable | Effect | Best setting |
|---|---|---|
| `PHI_NER_MODEL` | Primary model | `StanfordAIMI/stanford-deidentifier-base`, or a retrained copy kept off AWS |
| `PHI_NER_THRESHOLD` | Token is PHI at this total PHI probability (empty = top label) | `0.02` |
| `PHI_NER_EXTRA_MODELS` | Comma-separated models whose top-label detections are added | `obi/deid_roberta_i2b2` (not on Lambda) |
| `PHI_NAME_LEXICON` | Redact words on `name_lexicon.txt` (built by `eval/build_name_lexicon.py`) | `true` |
| request `known_names` | Patient and care-team names from the EHR | pass when available |

Device words (Foley, PICC, Swan-Ganz) and eponyms before a clinical noun ("Parkinson disease", "Bell's palsy") are protected from model redaction. A bare surname is still redacted.

Measured through the gateway code with `deid_benchmark.py` on the test half. The threshold for setup A was chosen on the tune half: 0.02 found 84.8% with 1.7% of other words removed, against 0.05's 83.8%.

| Setup | PHI found (95% CI) | Names | With EHR names: PHI found (95% CI) | Names | Other words removed |
|---|---|---|---|---|---|
| A. Deployable on Lambda: public Stanford model, rules, threshold 0.02, lexicon | 80.9% (77.6–84.1) | 72.8% | 87.6% (84.8–90.1) | 85.5% | 1.7% |
| B. Best: retrained Stanford (seed 11) + obi union, rules, threshold 0.02, lexicon (before the clinical-term protection) | 84.2% (81.4–87.2) | 74.8% | **90.1% (87.8–92.3)** | 86.1% | 1.5% |

B reproduces the analysis-script numbers above within 0.2 points. The clinical-term protection changed A by 0.1 points (81.0% to 80.9%) and lowered its over-redaction from 1.8% to 1.7%.

The deployment defaults are now setup A. With `-c enableNer=true` the image bakes in the Stanford model, and the stack sets `PHI_NER_THRESHOLD=0.02` and `PHI_NAME_LEXICON=true`. Each can be overridden with CDK context (`nerModel`, `nerThreshold`, `nameLexicon`). Setup B cannot run on Lambda as built. Its retrained weights derive from MIMIC and must stay off AWS, and two models do not fit Lambda's cold start (`lambda_cold_start.md`).

## What this means

- **With EHR names, the gateway meets the 90% target on independent notes**, at 1.55% over-redaction. Without them it reaches 84%.
- **Names remain the hard part.** On the tune half, about a third of the names still missed are ordinary English words (46 of 130) and 29% are three letters or fewer. Context-free name lists or rules cannot fix these reliably.
- **Retraining now helps** where the old generator hurt (`deid_physionet_gold.md`). The rich surrogate pools explain most of the change, and the PhysioNet tune half adds a little more (see above).

## Limits

- **Three seeds,** but one corpus. The spread across seeds is about 1 point.
- **Same source, for the PhysioNet-trained models.** Their tune half comes from the same corpus, hospital and note type as the test half, though from different patients. The rich-only models never saw the corpus at all and still reach 90.0% with EHR names. A different-hospital test is pending: SHIELD (Stanford, requested 2026-11-26) and n2c2 2014, once its portal reopens.
- **Simulated EHR names.** They are taken from gold tag roles. A real EHR supplies names in its own forms, and nicknames or misspellings in notes would be missed.
- **The lexicon's names come from Faker**, the same source as the MIMIC test's fake names. So the lexicon is credited only on PhysioNet, not on the MIMIC test.
- **Recall only.** "Other words removed" is the only over-redaction measure, and the corpus marks no clinical-term spans.
- **The deployed gateway does not yet have** the union with a second model or the lexicon. The union also means loading two models, which matters for Lambda (`lambda_cold_start.md`).
