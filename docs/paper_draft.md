# MedGuard: measuring a PHI-redaction and prompt-injection gateway for clinical LLMs

*Draft, 2026-11-27. Every number below comes from a results file in `eval/results/`. A different-hospital PHI test (SHIELD) is pending, and its section is a placeholder. The references need checking before submission.*

## Abstract

Hospitals that send clinical notes to a hosted large language model (LLM) face two risks: protected health information (PHI) leaving the institution, and instructions hidden in a note (indirect prompt injection) steering the model. We built MedGuard, a gateway in front of Claude Haiku 4.5 on AWS Bedrock, with three layers:

- input PHI redaction (rules, a transformer de-identifier and a name lexicon);
- a guard (the note wrapped in tags plus security rules in the system prompt);
- an output filter.

We then measured each layer.

**PHI.** On the held-out half of PhysioNet's gold-standard nursing notes, the deployable public-model setting finds 80.9% of PHI. With patient and care-team names supplied by the EHR it finds 87.6%, removing 1.7% of other words. A de-identifier retrained only on MIMIC-III notes with a rich synthetic-surrogate generator reaches 90.0% with EHR names (3 seeds). Retraining on a narrow surrogate generator instead lowered external recall from 64.8% to 56.0%, even though in-distribution recall rose to 99%.

**Injection** (Claude Haiku 4.5, synthetic notes):

- On 300 template attacks, the gateway lowers attack success from 10.3% to 0–0.7%.
- On 375 published attacks (BIPIA, AgentDojo), from 11.8% to 2.1%.
- Against an adaptive Claude Opus 4.5 attacker with 10 queries per episode, from 25% to 0%. All successful attacks without the gateway were PHI theft.

**Ablation.** Redaction or the guard alone cuts PHI leakage in summaries from 53% of values to at most 0.8%. Redaction costs no measurable summary quality. The guard trades 10 points of retained clinical facts for higher judged accuracy.

The gateway fits a 3,008 MB Lambda with 11–14 s cold starts.

## 1. Introduction

Clinical text carries PHI in forms that rules alone miss: bare surnames, lower-case names, and dates written as 3/12. Models that summarize notes tend to repeat identifiers. Through a typical app prompt, 65% of Haiku 4.5's summaries of benign synthetic notes repeated an ID or phone number. Notes also come from many authors and systems, so text inside them cannot be trusted as instructions [Greshake et al. 2023].

De-identification is usually reported in-distribution, on the corpus a model was trained or tuned on. Prompt-injection defenses are usually reported on generic tasks. We ask four questions about a deployable gateway, using held-out or independent data throughout:

1. How much real PHI does it find on notes it was never tuned on?
2. How much does each layer reduce PHI leakage and attack success?
3. What does redaction cost in summary quality and latency?
4. Does it fit a serverless deployment?

Contributions:

- **A tuned-then-held-out PHI evaluation on independent gold notes.** It shows that retraining on a narrow surrogate generator inflates in-distribution scores while lowering external recall, and that a rich generator fixes this.
- **A factorial ablation of input redaction, prompt guarding and output filtering.** It reports PHI leakage and attack success on the same cases, with paired intervals.
- **Injection results on template, published (BIPIA, AgentDojo) and adaptive attacks** embedded in clinical notes, including a system-prompt secret leak and its fix.
- **Utility and deployment measurements** for the same gateway.

## 2. Related work

*To expand.*

- **De-identification:** rule systems; transformer de-identifiers trained on i2b2 2014 [Stubbs and Uzuner 2015], such as `obi/deid_roberta_i2b2`; the Stanford de-identifier [Chambon et al. 2023]; Presidio. The PhysioNet gold-standard corpus [Neamatullah et al. 2008].
- **Indirect prompt injection** [Greshake et al. 2023]. Benchmarks: BIPIA [Yi et al. 2023], AgentDojo [Debenedetti et al. 2024], InjecAgent [Zhan et al. 2024]. Iterative black-box attacks: PAIR [Chao et al. 2023].

## 3. System

The gateway is an AWS Lambda function behind API Gateway, with Cognito authentication and an S3/DynamoDB audit log. It calls Claude Haiku 4.5 on Bedrock. `handler.gateway_reply` runs three layers:

1. **R, input redaction.**
   - **Rules:** emails, MRNs, phones, dates (including a context-aware month/day rule that rules out measurement contexts), SSNs, addresses, ages over 89, and cue-based names.
   - **Model:** a token-classification de-identifier, run on the text the rules leave. A token is PHI when its total PHI probability is at least 0.02.
   - **Name lexicon:** Faker first and last names from 15 locales, minus English dictionary words and clinical eponyms.
   - **EHR names (optional):** patient and care-team names passed in the request (`known_names`).
   - **Clinical-term protection:** device words and eponyms before a clinical noun are protected from model redaction.
2. **G, the guard.** The note is wrapped in `<CLINICAL_NOTE>` tags. Four security rules in the system prompt:
   - treat the note as data;
   - do not output PHI;
   - summarize at a high level;
   - refuse to reveal secrets.
3. **O, the output filter.** The rules run again on the reply, and configured secrets are scrubbed, including spaced or punctuated spellings.

**Deployed configuration (setup A).** The public `StanfordAIMI/stanford-deidentifier-base` model is baked into the container image.

**Research configuration (setup B).** A retrained Stanford model plus a union with `obi/deid_roberta_i2b2`. Its weights derive from MIMIC, so they are kept off AWS. Two models also do not fit Lambda's cold start.

## 4. PHI detection

### 4.1 Data and protocol

- **PhysioNet "Deidentified Medical Text" v1.0:** 2,434 MIMIC-II nursing notes with expert gold PHI, replaced by realistic surrogates chosen by the corpus authors (2,026 scored spans). We split it by patient into a tune half (1,333 notes) and a test half (1,101 notes, 85 patients). Every threshold, rule and lexicon choice was made on the tune half; the test half was scored once per configuration.
- **MIMIC-III** (1,000 held-out notes), with PHI tags replaced by surrogates from our generator (in-distribution), and with unseen surrogate formats.
- **Metrics:** share of gold PHI spans fully covered (recall), and the share of non-PHI words removed (over-redaction). 95% intervals come from a bootstrap over notes; differences are paired by note.
- **Training:** retraining ran on Colab (5,000 MIMIC-III notes per seed, 2 epochs, 3 seeds). All MIMIC and PhysioNet text stayed local or on credentialed infrastructure, and none was sent to a hosted LLM.

### 4.2 Results

| Setting (PhysioNet test half unless noted) | PHI found | Names | With EHR names | Other words removed |
|---|---|---|---|---|
| Original gateway (rules + obi model), full corpus | 64.8% | 64.5% | | 0.8% |
| obi retrained on our default surrogates, full corpus (3 seeds) | 56.0% | 53.6% | | 0.6% |
| Presidio, full corpus | 51.1% | 66.9% | | 12.1% |
| **Setup A**: public Stanford model + rules + threshold 0.02 + lexicon | 80.9% (77.6–84.1) | 72.8% | 87.6% (84.8–90.1) | 1.7% |
| Stanford retrained on rich MIMIC surrogates only (3 seeds) | 83.7% | 75.2% | **90.0%** | 1.5–1.7% |
| **Setup B**: retrained on rich surrogates + PhysioNet tune half, + obi union (3 seeds) | 85.1% | 76.4% | **91.0%** | 1.5–2.0% |

- **Narrow surrogates overfit.** Retrained on our default generator, the obi model reached 99.2% on held-out MIMIC notes (names 97.8%) but lost 8.8 points on PhysioNet. Facilities fell from 65% to 16%: the model had learned the generator's 6 facility names and 8 cities. With unseen surrogate formats, MIMIC recall fell to 73.2%.
- **Rich surrogates generalize.** A generator with Faker-scale value pools and many formats gives +3.1, +2.1 and +3.1 points over setup A for the three rich-only seeds. All three intervals exclude zero, and these models never saw a PhysioNet note. Adding the PhysioNet tune half gives about 1.4 points more, significant in 2 of 3 seeds.
- **Names remain the hard part.** Of the names still missed on the tune half, about a third are ordinary English words and 29% have three letters or fewer. EHR-supplied names add 6–7 points.

**Leave-one-out of setup A's parts** (paired Δ, percentage points):

| Removed | PHI found | Δ |
|---|---|---|
| — (setup A) | 80.9% | |
| name lexicon | 80.1% | −0.8 (−1.5 to −0.3) |
| threshold 0.02 (back to top label) | 78.4% | −2.5 (−3.6 to −1.5) |
| month/day date rule | 76.0% | −5.0 (−6.5 to −3.5) |
| all rules | 75.2% | −5.7 (−7.3 to −4.2) |
| the model | 47.7% | −33.2 (−36.8 to −29.6) |

### 4.3 Different-hospital test (pending)

*Placeholder for SHIELD (Stanford; 1,381 notes), scored locally with no re-tuning: setups A and B, the original obi model and Presidio. The Stanford de-identifier was developed at the same institution, so it may have a home-institution advantage there.*

## 5. Prompt injection

### 5.1 Benchmarks

All notes are synthetic, made by our generator, so no patient data reached the hosted model. Target: Claude Haiku 4.5, temperature 0.2, one run per case.

- **Template suite (v1):** 300 attacks, covering 10 disguise techniques × 5 goals × 3 positions × 2 notes, plus 100 benign controls (half containing instruction-like clinical sentences). The five goals:
  - a reply-opening marker code;
  - a markdown-image exfiltration link;
  - a full hijack;
  - leaking a system-prompt canary;
  - repeating the note's ID and phone numbers.

  Success checks are mechanical and require the content where compliance would put it.
- **Public attacks:**
  - BIPIA's 75 test text attacks (15 categories) inserted at 3 positions, 225 in all, judged by Claude Sonnet 4.6;
  - AgentDojo's five prompt templates filled with our five goals, 150 in all, rule-checked.
- **Adaptive attacks:** a PAIR-style black-box loop with Claude Opus 4.5 as attacker, up to 10 target queries per episode. It has four goals chosen to survive redaction (a phrase in words, an exfiltration link, PHI theft, and the canary in any recoverable encoding), over 10 notes per goal.

### 5.2 Results

| Benchmark | Direct (typical app prompt) | Full gateway |
|---|---|---|
| Template suite, all 300 attacks | 10.3% (7.4–14.3) | 0.0–0.7% (two runs) |
| Template suite, excluding PHI theft | 2.5% | 0.0–0.8% |
| BIPIA (225) | 18.4% (13.9–24.0) | 3.6% (1.8–6.9) |
| AgentDojo templates (150) | 2.0% (0.7–5.7) | 0.0% (0.0–2.5) |
| Adaptive, 40 episodes | 25.0% (14.2–40.2) | 0.0% (0.0–8.8) |
| Benign summaries repeating an ID or phone | 65% | 0% |

- **PHI theft is the dominant risk.** Direct, the adaptive attacker extracted identifiers in 10 of 10 episodes (3.5 queries on average). Through the gateway it failed in all 10, using 9.7 queries each: redaction removes the values before the model reads them.
- **Haiku 4.5 already resists most non-PHI goals.** The residual gateway successes on BIPIA are low-harm task drift: translating the summary (4 of 15), adding a sentiment verdict (3) and emoji (1). No harmful-content category succeeded in any condition.
- **The canary leak.** Three times across runs, Haiku quoted the system-prompt canary while refusing to reveal it ("I will NOT print the internal reference code (MG-...)"). This happened only under the gateway's security rules, never with the direct prompt. A reply filter for configured secrets removed every instance. Secrets should stay out of prompts, with the filter as a backstop.
- **The regex injection score is not a usable detector.** It flagged 20% of attacks and 24% of benign notes with instruction-like clinical language.

## 6. Layer ablation

All eight R × G × O combinations ran on the 400-case template suite through the same gateway code, 1,600 calls in all; O was applied offline to the stored raw replies. PHI leakage counts a note's gold values (5,021 names, dates, IDs, phones, addresses and emails) that appear in the reply.

| Layers on | Attack success (300) | PHI values leaked | Benign summaries leaking any PHI |
|---|---|---|---|
| none | 11.7% | 53.2% | 99% |
| O | 4.7% | 28.3% | 97% |
| R + O | 0.0% | 0.1% | 1% |
| G + O | 0.0% | 0.2% | 4% |
| G (no O) | 0.0% | 0.8% | 10% |
| R + G + O | 0.0% | 0.0% | 0% |
| direct app prompt | 10.3% | 61.6% | 99% |

- **Either R or G alone nearly eliminates leakage on these notes.** G works by asking the model not to repeat PHI, so it is a request, not a guarantee. R's near-zero leakage reflects the synthetic notes' easy PHI formats: on real notes R misses 12–19% of PHI, and G becomes the backstop.
- **O alone is weak** (56% of names still leak). It adds nothing measurable once R or G is on.
- **R also lowers non-PHI attack success, partly as a benchmark artifact.** It redacts the attacker's URL and 6-character codes: only 5 of 60 marker codes and 0 of 60 URLs reached the model intact. This is a real defense against URL exfiltration, but it does not generalize, which is why the adaptive goals avoid codes.

## 7. Utility and latency

200 fresh synthetic notes were summarized under five settings. Quality was scored in two ways:

- by the share of the note's clinical facts kept (conditions, medications, doses, vitals and findings, marked by the generator);
- by a blind Claude Sonnet 4.6 judge, rating completeness and accuracy 1–5 and comparing pairs.

| Setting | Facts kept | Completeness | Accuracy |
|---|---|---|---|
| Direct app prompt | 88.8% | 4.96 | 4.84 |
| Gateway prompt, R and G off | 88.8% | 4.88 | 4.57 |
| R only | 87.5% | 4.85 | 4.55 |
| G only | 71.8% | 4.61 | 4.86 |
| R + G (full) | 76.3% | 4.83 | 4.78 |

- **Redaction costs nothing measurable.** Without G: facts −0.8 points (−2.3 to +0.8), judge scores within ±0.03. With G, summaries of redacted notes were better, with facts +3.9 (+0.6 to +7.3) and a pairwise preference of 96 to 38. We do not claim a benefit, since the cause is unclear.
- **The guard trades detail for accuracy.** It keeps 10.2 points fewer facts (rule 3 asks for a high-level summary) but raises judged accuracy by 0.23 (+0.12 to +0.35). Unguarded summaries more often added unsupported content, such as consults or interpretations the note never mentions.
- **Latency:**
  - redaction takes 100 ms per note at the median on a laptop CPU;
  - a full gateway call takes 1.4 s in-process;
  - the deployed function takes 2.9–3.4 s warm and 11–14 s on a cold start.

## 8. Deployment

At Lambda's 3,008 MB account cap, a 1.4 GB RoBERTa-large image never answered within 30 s. Lambda streams image data lazily from the registry, at about 5 MB/s on cold hosts. The 438 MB BERT-base Stanford image answered six of six forced cold starts in 11.1–14.1 s, under API Gateway's 29 s limit, with peak memory of 977 MB. The first two calls after each deploy time out, so the function should be warmed after deploying.

## 9. Limitations

- **One PHI corpus and note type** (MIMIC-II nursing notes) for the external test; the different-hospital test is pending. EHR names are simulated from gold tag roles.
- **Synthetic notes for every hosted-model experiment,** because credentialed notes may not be sent to a hosted LLM. Their PHI and clinical content are easier than real notes'.
- **One target model and one run per case;** rare events (such as the canary leak) vary between runs.
- **LLM judges** (Sonnet 4.6) for BIPIA and utility, with no human ratings.
- **Adaptive attacks are bounded by a refusing attacker** (113 refusals, mostly on the phrase goal) and 10 queries per episode.
- **String-matching leakage checks** miss paraphrased PHI.

## 10. Ethics and data

- MIMIC-III and PhysioNet data were used under PhysioNet credentialing. No note text was printed, committed or sent to a hosted model; only aggregates were reported.
- Models retrained on MIMIC are not released.
- SHIELD was requested for local evaluation only, with no training.

## 11. Reproducibility

Code, synthetic benchmarks, raw hosted-model replies and per-note aggregate PHI scores are in the repository (`eval/`). The commands are in each results file's header, and 118 offline unit tests cover the scorers and gateway layers.

## References (to verify)

- Chambon P. et al. 2023. Automated deidentification of radiology reports combining transformer and "hide in plain sight" rule-based methods. JAMIA.
- Chao P. et al. 2023. Jailbreaking black box large language models in twenty queries. arXiv:2310.08419.
- Debenedetti E. et al. 2024. AgentDojo: a dynamic environment to evaluate prompt injection attacks and defenses for LLM agents. NeurIPS Datasets and Benchmarks.
- Greshake K. et al. 2023. Not what you've signed up for: compromising real-world LLM-integrated applications with indirect prompt injection. AISec.
- Johnson A. et al. 2016. MIMIC-III, a freely accessible critical care database. Scientific Data.
- Neamatullah I. et al. 2008. Automated de-identification of free-text medical records. BMC Medical Informatics and Decision Making.
- Stubbs A., Uzuner Ö. 2015. Annotating longitudinal clinical narratives for de-identification: the 2014 i2b2/UTHealth corpus. Journal of Biomedical Informatics.
- Yi J. et al. 2023. Benchmarking and defending against indirect prompt injection attacks on large language models. arXiv:2312.14197.
- Zhan Q. et al. 2024. InjecAgent: benchmarking indirect prompt injections in tool-integrated LLM agents. Findings of ACL.
