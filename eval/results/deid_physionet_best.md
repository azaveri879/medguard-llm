# Reaching 90% on PhysioNet's gold notes (one seed so far)

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

## What this means

- **With EHR names, the gateway meets the 90% target on independent notes**, at 1.55% over-redaction. Without them it reaches 84%.
- **Names remain the hard part.** On the tune half, about a third of the names still missed are ordinary English words (46 of 130) and 29% are three letters or fewer. Context-free name lists or rules cannot fix these reliably.
- **Retraining now helps** where the old generator hurt (`deid_physionet_gold.md`). The difference: the rich surrogate pools plus real author-written surrogates from the tune half. A rich-only run, without the PhysioNet notes, has not been done, so the two causes cannot yet be separated.

## Limits

- **One seed.** Seeds 12 and 13 are training. This page will be updated with their spread.
- **Same source.** The tune half used in training comes from the same corpus, hospital and note type as the test half, though from different patients. This is an in-corpus held-out test, not a different hospital. n2c2 2014 remains the outside test once its portal reopens.
- **Simulated EHR names.** They are taken from gold tag roles. A real EHR supplies names in its own forms, and nicknames or misspellings in notes would be missed.
- **The lexicon's names come from Faker**, the same source as the MIMIC test's fake names. So the lexicon is credited only on PhysioNet, not on the MIMIC test.
- **Recall only.** "Other words removed" is the only over-redaction measure, and the corpus marks no clinical-term spans.
- **The deployed gateway does not yet have** the union with a second model or the lexicon. The union also means loading two models, which matters for Lambda (`lambda_cold_start.md`).
