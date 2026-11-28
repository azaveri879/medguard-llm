# MedGuard project status (2026-11-27, updated in the afternoon)

MedGuard is a PHI-redaction and prompt-injection gateway in front of a clinical LLM (Claude Haiku 4.5 on Bedrock). The goal is results strong enough for a research paper. This page summarizes what has been measured, what changed in the gateway, and what is left. Details are in the linked results files.

## Goals and status

| Goal | Target (agreed 2026-11-26) | Status |
|---|---|---|
| 1. Real benchmark | PHI: gold-labeled external notes. Injection: 300+ attacks with attack success measured | PHI done (MIMIC, unseen formats, PhysioNet gold). Injection done: 300 template attacks, 375 public attacks (BIPIA, AgentDojo) and 80 adaptive episodes, all in synthetic notes. A different-hospital PHI test (SHIELD) is pending |
| 2. Better PHI detection | About 90% of PHI and names found on external notes, at most 2% of other words removed, plus precision/F1 per type | **Met with EHR-supplied names:** 90–91% on held-out PhysioNet notes (3 seeds). Without EHR names 84–85%. Precision/F1 and a different-hospital test are pending (n2c2 portal closed; SHIELD requested) |
| 3. Ablations | Each gateway layer's effect on leakage and attack success | **Done** (`eval/results/ablation_layers.md`): all 8 layer combinations on the injection suite, plus leave-one-out of the redaction parts on PhysioNet |
| 4. Utility cost | Summary quality with vs without redaction, plus latency | **Done** (`eval/results/utility_redaction.md`): redaction costs no measurable quality, and adds about 0.1 s per note. The guard keeps 10 points fewer facts but is more accurate |
| 5. Write-up | Reproducible paper draft | First draft: `docs/paper_draft.md` |
| 6. Deployable gateway | Answers within API Gateway's 29 s on a cold start, within the account's 3,008 MB Lambda cap | **Met** with the final default image (Stanford model, threshold 0.02, lexicon): 6 of 6 cold starts in 11–14 s, warm 2.9–3.4 s. The first 2 calls after a deploy still time out |

## Main results

### PHI detection

| Test | Setting | PHI found | Names | Source |
|---|---|---|---|---|
| 1,000 held-out MIMIC-III notes, default surrogates | Original gateway (rules + `obi/deid_roberta_i2b2`) | 90.3% | 71.3% | `eval/results/deid_colab_3seed.md` |
| same | obi retrained on default MIMIC surrogates (3 seeds) | 99.2% | 97.8% | same |
| same notes, unseen surrogate formats | Original / obi retrained | 85.0% / 73.2% | | `eval/results/deid_unseen_formats.md` |
| PhysioNet gold nursing notes (2,434, independent surrogates) | Original gateway / obi retrained / Stanford model alone | 64.8% / 56.0% / 71.5% | | `eval/results/deid_physionet_gold.md` |
| PhysioNet **test half** (1,101 notes, 85 patients, never used for tuning) | Stanford pipeline + month/day date rule + threshold 0.05 + obi union (public models) | 80.1% | 71.8% | `eval/results/deid_physionet_tuning.md` |
| same | **Setup A, deployable on Lambda:** public Stanford model + rules + threshold 0.02 + name lexicon | 80.9%; 87.6% with EHR names | 72.8% | `eval/results/deid_physionet_best.md` |
| same | Stanford retrained on rich MIMIC surrogates only (3 seeds; never saw PhysioNet) + setup B settings | 83.7%; **90.0% with EHR names** | 75.2% | same |
| same | **Setup B, best:** Stanford retrained on rich surrogates + PhysioNet tune half (3 seeds) + obi union + threshold 0.02 + lexicon | 85.1%; **91.0% with EHR names** | 76.4% | same |

Over-redaction stays at 1.5–2.0% of other words throughout. All retrained weights derive from MIMIC: they are kept off AWS and unpublished.

What we learned:

- **Retraining on one surrogate generator inflates in-distribution results.** obi retrained on the default generator reached 99% on MIMIC but fell to 56% on independent notes, because it learned the generator's 6 facility names, 8 cities and date formats.
- **A rich generator fixes that.** Faker-scale value pools and many formats give the Stanford model +2.8 points over the public model on independent notes. Adding real PhysioNet notes gives about +1.4 more.
- **Names are the hard part.** 62% of PhysioNet notes are typed in one case, and many names are lone surnames. Of the names still missed, about a third are ordinary English words. EHR-supplied names (`known_names`) add about 6 points overall.
- **Our rules matter for dates.** A context-aware month/day rule raised date recall from 72% to 92%.

### Injection (synthetic notes, Claude Haiku 4.5)

300 attacks (10 techniques × 5 goals × 3 positions) plus 100 benign controls (`eval/results/injection_clinical_notes.md`).

| Measure | Direct | Through the gateway |
|---|---|---|
| Attack success, all goals | 10.3% | 0.7% |
| Attack success excluding PHI theft | 2.5% | 0.8% |
| Benign summaries repeating an ID or phone number | 65% | 0% |

The gateway's security rules made Haiku quote a system-prompt canary while refusing in 2 of 60 attempts. The regex injection score flags only 20% of attacks and 24% of benign notes with instruction-like clinical language, so it should not be used to block requests.

### Layer ablation (`eval/results/ablation_layers.md`)

R = input redaction, G = guard (`<CLINICAL_NOTE>` wrapping + security rules), O = output filter. Injection suite, 400 synthetic notes, Haiku 4.5.

| Layers on | Attack success (300) | PHI values leaked (5,021) | Benign summaries leaking any PHI |
|---|---|---|---|
| none | 11.7% | 53.2% | 99% |
| O only | 4.7% | 28.3% | 97% |
| R only (+O) | 0.0% | 0.1% | 1% |
| G only (+O) | 0.0% | 0.2% | 4% |
| R + G + O | 0.0% | 0.0% | 0% |

- Either R or G alone stops nearly all leakage of the synthetic notes' PHI. G works by asking the model not to repeat PHI, which is a request, not a guarantee. On real notes R misses about 19% of PHI, so G is the backstop.
- R's effect on non-PHI attacks is partly an artifact: it scrubs the attacker's URLs and codes.
- Redaction parts on the PhysioNet test half (setup A 80.9%):
  - without the model, 47.7%;
  - without the month/day rule, 76.0%;
  - top label instead of the 0.02 threshold, 78.4%;
  - without the lexicon, 80.1%.

### Utility (`eval/results/utility_redaction.md`)

200 synthetic notes, Haiku 4.5 summaries, Sonnet 4.6 judge.

- **Redaction:** no measurable cost. Without the guard, facts kept changed by −0.8 points and judge scores by −0.03. With the guard on, redacted notes gave better summaries (+3.9 points of facts, judge preference 96 to 38).
- **The guard:** keeps 10 points fewer facts (rule 3, "summarize at a high level"), but judge accuracy is +0.23 higher, with fewer invented consults and interpretations.
- **Latency:** redaction adds about 0.1 s per note on CPU.

### Public and adaptive attacks (`eval/results/injection_public.md`, `eval/results/adaptive_attacks.md`)

| Attacks | Direct | Full gateway |
|---|---|---|
| BIPIA text attacks (225, model-judged) | 18.4% | 3.6% (translation, sentiment, emoji only) |
| AgentDojo templates (150) | 2.0% | 0.0% |
| Adaptive, Opus 4.5 attacker, 10 queries (40 episodes) | 25% (10/10 PHI theft) | 0% |

The canary leak recurred once (the model quoted it while refusing), and the new reply filter (`GATEWAY_REPLY_SECRETS`) removed it.

### Deployment (`eval/results/lambda_cold_start.md`)

At 3,008 MB, the 1.4 GB RoBERTa-large image never answers within 30 s, because image data loads lazily from the registry. The 438 MB Stanford image answers cold starts in 12–23 s and warm calls in 2.6–3.3 s. Re-measured on 2026-11-27 with the final default image (threshold 0.02 + lexicon): 6 of 6 cold starts in 11–14 s, warm 2.9–3.4 s. The first calls right after a deploy time out until Lambda caches the image. The stack is currently torn down.

## Gateway changes (services/gateway)

- `handler.py`: `gateway_reply()` runs the layers, with switches used only by the ablation; the output filter also scrubs configured secrets (`GATEWAY_REPLY_SECRETS`), including spaced-out forms.
- `phi_redaction.py`: a `MONTH_DAY` rule for bare month/day dates, with measurement contexts ruled out.
- `ner_redaction.py`:
  - `PHI_NER_THRESHOLD` (an empty value means top label);
  - `PHI_NER_EXTRA_MODELS` (union with other models);
  - `PHI_NAME_LEXICON` and `name_lexicon.txt` (built by `eval/build_name_lexicon.py`);
  - Stanford label mapping;
  - protection for clinical device words and eponyms.
- `Dockerfile`: bakes in a pinned Hub model (default: the Stanford model) or a local model via `--build-context model=DIR`.
- `cdk/lib/medguard-stack.ts`:
  - with `-c enableNer=true`, defaults to the Stanford model, threshold 0.02 and the lexicon;
  - context keys `nerModel`, `nerRevision`, `nerWeightsRevision`, `nerThreshold`, `nameLexicon` and `nerMemoryMb`.

## Evaluation tooling (eval/)

- `train_deid_colab.ipynb`: Colab training. Settings: `BASE_MODEL`, `SURROGATE_STYLE` (`default` or `rich`), `RUN_NAME`, `PHYSIONET_TUNE_DIR`. Per-seed results and models are saved to and restored from Drive, and the setup cell resets the repo clone to the branch head.
- `train_deid.py`: `--base-model`, `--surrogate-style`, `--physionet-tune`; handles plain-label models and adds an AGE output.
- `mimic_surrogates.py`: surrogate styles `default`, `unseen` (format-bias test) and `rich` (training).
- `physionet_deid.py`: loads PhysioNet's gold corpus, with a patient-level tune/test split (`physionet_split`), name roles and EHR-style known names.
- `deid_benchmark.py`:
  - `--physionet-deid DIR --split tune|test`;
  - `--surrogate-style`;
  - `--miss-context` (character class around missed spans, no text).
- `deid_tune_physionet.py`: threshold and union tuning on the tune half, then a single report on the test half.
- `deid_compare.py`: paired bootstrap comparisons across seeds.
- `injection_suite.py` and `run_injection.py`: the injection benchmark.
- `run_ablation.py` (layer ablation), `deid_ablation_physionet.py` (redaction parts), `run_utility.py` (summary quality), `injection_public.py` + `run_injection_public.py` (BIPIA, AgentDojo), `run_adaptive.py` (adaptive attacker).
- 118 offline unit tests: `python -m unittest test_*` from `eval/`.

## Open items

1. **SHIELD external test** (Stanford, 1,381 real notes, 10,229 gold spans). Access was requested on Redivis on 2026-11-26, with stated use local evaluation only and no training. When approved: write a loader, then score setups A and B, the original model and Presidio with no re-tuning. Note that the Stanford model may have a home-institution advantage.
2. **n2c2 2014**, when the DBMI portal reopens. **OpenDeID** (Australian pathology reports) is an alternative.
3. **Paper draft** (`docs/paper_draft.md`): review it, then fill in the SHIELD results.
4. **Follow-ups from today's runs:**
   - loosen the guard's rule 3 ("keep all medications, doses and findings") and re-run the utility test;
   - repeat the injection runs (one run per case so far) to firm up the rare events;
   - test an attacker without refusals, or with more queries;
   - try a second target model.
5. **Deployment:** warm the function after each deploy (the first calls time out), or use provisioned concurrency.

Done on 2026-11-27: the Lambda re-measurement, the ablations (goal 3), utility (goal 4), the public and adaptive attacks, and the canary fix.

## Data handling rules

- MIMIC and PhysioNet note text never goes into the repo, chat or screenshots; only aggregates are printed.
- Training happens on Colab, never on the Mac.
- Never send MIMIC-derived text to a cloud LLM; injection runs use synthetic notes.
- Retrained weights stay in the git-ignored `eval/models/` and the owner's private Drive. They are never pushed to a registry or published.
- Never commit `eval/DESTINATION/` (credentialed data) or `eval/models/`.
- Tune on one sample and report on another: on PhysioNet, the tune half chooses settings and the test half reports.
