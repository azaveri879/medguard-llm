"""
Time the parts of a gateway cold start inside the Lambda image, on synthetic text.

Run inside the image, for example:
    docker run --rm --cpus 3.5 --memory 6g --entrypoint python \
        -e PHI_NER_ENABLED=true -e AUDIT_BUCKET=x -e DDB_TABLE=x -e BEDROCK_MODEL_ID=x \
        -e AWS_DEFAULT_REGION=us-east-1 IMAGE /var/task/cold_start_probe.py

Prints one JSON line: seconds to import the handler (Lambda's init phase), to load
the model and redact the first note (the first request), and a warm redaction.
The handler loads the model on the first request, not at init.
"""

import json
import time

NOTE = (
    "Patient Jane Doe, MRN 48213377, seen 03/14/2026 at Lakeview Clinic. "
    "Daughter can be reached at 608-555-0143. 92 year old female with CHF, "
    "on furosemide 40 mg daily and lisinopril 10 mg. Lives at 412 Birch Street, Madison, WI. "
) * 6

start = time.perf_counter()
import handler  # noqa: E402,F401  (init phase: imports and boto3 clients)

init_s = time.perf_counter() - start

start = time.perf_counter()
handler.redact_input(NOTE)
first_s = time.perf_counter() - start

start = time.perf_counter()
handler.redact_input(NOTE)
warm_s = time.perf_counter() - start

print(json.dumps({
    "init_s": round(init_s, 2),
    "first_request_s": round(first_s, 2),
    "warm_request_s": round(warm_s, 2),
    "chars": len(NOTE),
}))
