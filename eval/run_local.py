#!/usr/bin/env python3
"""
Compare direct Bedrock with the gateway handler, without deploying the gateway.

Runs the real handler code in-process and calls Bedrock directly. Audit writes
are skipped, so no S3 bucket or DynamoDB table is needed.

Usage (from eval/):
    python run_local.py --model MODEL_ID --output results/local.json --repeats 3
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

GATEWAY_DIR = Path(__file__).resolve().parent.parent / "services" / "gateway"
REGION = os.environ.get("AWS_REGION", "us-east-1")


def load_handler(model_id: str):
    """Import the gateway handler with local settings and audit writes disabled."""
    os.environ.setdefault("AWS_DEFAULT_REGION", REGION)
    os.environ.setdefault("AUDIT_BUCKET", "local-eval-unused")
    os.environ.setdefault("DDB_TABLE", "local-eval-unused")
    os.environ["BEDROCK_MODEL_ID"] = model_id
    sys.path.insert(0, str(GATEWAY_DIR))
    import handler

    handler.write_audit = lambda *_: None
    return handler


def invoke_handler(handler, prompt: str, role: str = "resident") -> dict:
    """Call the handler and return a record in the same shape as the live evaluator."""
    start = time.time()
    event = {"body": json.dumps({"user_id": "eval_user", "role": role, "prompt": prompt})}
    response = handler.handler(event, None)
    latency_ms = (time.time() - start) * 1000
    body = json.loads(response["body"])
    if response["statusCode"] != 200:
        return {
            "response": "",
            "latency_ms": latency_ms,
            "success": False,
            "error": body.get("message", ""),
            "input": prompt,
            "phi_counts_input": {},
            "injection_score": 0,
        }
    return {
        "response": body["response"],
        "latency_ms": latency_ms,
        "success": True,
        "input": prompt,
        "phi_counts_input": body["redaction_summary"],
        "injection_score": body["safety_flags"]["injection_score"],
    }


def main():
    parser = argparse.ArgumentParser(description="Run the MedGuard eval locally")
    parser.add_argument("--model", required=True, help="Bedrock model or inference profile ID")
    parser.add_argument("--output", required=True, help="Where to save scored results")
    parser.add_argument("--suite", default="datasets/test_suite.json", help="Test suite JSON file")
    parser.add_argument("--repeats", type=int, default=1, help="Runs per test case")
    args = parser.parse_args()

    handler = load_handler(args.model)

    from baseline import BaselineEvaluator
    from metrics import compare_configurations, generate_comparison_table
    from run_eval import load_test_suite, prepare_test_cases
    from scoring import score_results

    test_cases = prepare_test_cases(load_test_suite(args.suite))
    baseline = BaselineEvaluator(args.model, REGION)
    raw = {"baseline": [], "medguard": []}
    for _ in range(args.repeats):
        for case in test_cases:
            raw["baseline"].append(baseline.invoke_direct(case["prompt"]))
            raw["medguard"].append(invoke_handler(handler, case["prompt"]))

    scored = {name: score_results(rows, test_cases) for name, rows in raw.items()}
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(scored, indent=2))

    print(generate_comparison_table(compare_configurations(scored), "markdown"))
    for name, rows in scored.items():
        failures = [r.get("error", "") for r in rows if not r.get("success", True)]
        if failures:
            print(f"{name}: {len(failures)} failed requests, e.g. {failures[0][:200]}")


if __name__ == "__main__":
    main()
