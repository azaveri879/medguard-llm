#!/usr/bin/env python3
"""
Measure the PHI redactor against labeled synthetic notes. Runs offline.

Recall counts a value as caught only if it is gone from the redacted text.
Clinical retention counts terms that must survive redaction, which catches an
over-eager redactor destroying content.

Usage (from eval/):
    python eval_redaction.py --split dev --details
    python eval_redaction.py --split holdout
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from run_local import load_handler
from scoring import value_leaked


def evaluate(cases, redact):
    caught, total = defaultdict(int), defaultdict(int)
    kept, keep_total = 0, 0
    missed, lost = [], []
    for case in cases:
        redacted, _ = redact(case["text"])
        for item in case["phi"]:
            total[item["type"]] += 1
            if value_leaked(item["type"], item["value"], redacted):
                missed.append((case["id"], item["type"], item["value"]))
            else:
                caught[item["type"]] += 1
        for term in case["keep"]:
            keep_total += 1
            if term in redacted:
                kept += 1
            else:
                lost.append((case["id"], term))
    return caught, total, kept, keep_total, missed, lost


def main():
    parser = argparse.ArgumentParser(description="Measure the PHI redactor")
    parser.add_argument("--suite", default="datasets/redaction_suite.json")
    parser.add_argument("--split", choices=["dev", "holdout"], default="dev")
    parser.add_argument("--details", action="store_true", help="List each miss")
    args = parser.parse_args()

    cases = json.loads(Path(args.suite).read_text())[args.split]
    redact = load_handler("unused").phi_redact
    caught, total, kept, keep_total, missed, lost = evaluate(cases, redact)

    print(f"Split: {args.split} ({len(cases)} notes)")
    for phi_type in sorted(total):
        print(f"  {phi_type:8} {caught[phi_type]}/{total[phi_type]}")
    print(f"  PHI recall: {sum(caught.values())}/{sum(total.values())}")
    print(f"  Clinical terms kept: {kept}/{keep_total}")
    if args.details:
        for item in missed:
            print("  MISSED", item)
        for item in lost:
            print("  LOST  ", item)


if __name__ == "__main__":
    main()
