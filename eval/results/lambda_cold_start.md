# Gateway cold start on AWS Lambda

Measured on 2026-11-26 in us-east-1. The gateway was deployed with `cdk deploy -c enableNer=true -c nerMemoryMb=3008` (the account caps Lambda memory at 3,008 MB). Each cold start was forced by changing an environment variable, then invoked directly with a synthetic 1,356-character note through the full path: rules, NER redaction, Claude Haiku 4.5 on Bedrock and the audit write. API Gateway's integration limit is 29 s, and the function's timeout is 30 s.

| NER model in the image | Weights | Calls right after deploy | Later cold starts (end to end) | Warm calls |
|---|---|---|---|---|
| `obi/deid_roberta_i2b2` (RoBERTa-large) | 1.4 GB | 6 of 6 timed out | 3 forced cold starts: all timed out | All timed out |
| `StanfordAIMI/stanford-deidentifier-base` (BERT-base) | 438 MB | 3 of 3 timed out | 5 of 5 succeeded: 15.1, 22.9, 12.1, 11.9, 12.6 s | 2.6–3.3 s |

- **Why the large model fails.** Lambda pulls container-image data lazily from the registry as it is first read. The logs show the 1.4 GB weight file arriving at roughly 5 MB/s on cold hosts. The model loads, but the first inference then pages weights in slowly and runs past 30 s. Reading the file up front during init made it worse: init hit Lambda's 10 s limit and the call then timed out (that change was reverted).
- **Why the Stanford model works.** It is about a third the size. Once Lambda has cached the image, which took the first few calls after deploying, cold starts settled at about 12 s. That is under API Gateway's 29 s.
- **Local timings mislead.** In Docker on a Mac, both images answered their first request in 3–9 s, because the disk is local.

## Re-measured with the final default image (2026-11-27)

Same method and note, us-east-1, 3,008 MB. The image is the deployment default after the PhysioNet work: the Stanford model, `PHI_NER_THRESHOLD=0.02` and the name lexicon (`PHI_NAME_LEXICON=true`), deployed with `cdk deploy -c enableNer=true -c nerMemoryMb=3008`. Six cold starts were forced; the reply's redaction summary confirmed the rules, model and lexicon all ran.

| Calls | Result | End to end (wall, from the Mac) | Lambda duration | Init |
|---|---|---|---|---|
| First 3 right after deploy | 2 timed out at 30 s, the 3rd succeeded | 32.7, 31.1, 15.8 s | 30.0, 30.0, 14.7 s | 1.1 s (first call) |
| 6 forced cold starts | 6 of 6 succeeded | 11.1–14.1 s (median 12.5) | 9.1–11.9 s | 0.6–1.0 s |
| 5 warm calls | 5 of 5 succeeded | 2.9–3.4 s | 1.9–2.3 s | |

Peak memory was 977 MB of the 3,008 MB. The lexicon and the lower threshold did not slow cold starts: they were 11–14 s here against 12–23 s for the earlier Stanford image. The first calls after a deploy still time out, so warming the function after each deploy (or provisioned concurrency) is still needed. The stack was destroyed after the measurement.

## Implications

- **Use the Stanford model for a deployed gateway.** It is also the most accurate option on external notes (`deid_physionet_gold.md`).
- **The first calls after each deploy fail.** Warming the function after deploying with a few direct invocations, or provisioned concurrency, would avoid that. A cold start of 12–23 s is still slow for users; provisioned concurrency would remove it.
- **The original model needs a different design on Lambda.** For example, the weights could be fetched from S3 at init, or the model run on an always-on service.

## Limits

- Few samples: 5 successful cold starts and 3 to 6 failed ones per model, in one region on one day.
- 3,008 MB of memory only. At 6,144 MB Lambda gives more CPU, which would shorten inference but not the image pull.
- Direct invocation, not through API Gateway. The stack's API uses Cognito auth, and API Gateway adds little latency.
