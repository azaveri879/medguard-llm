#!/usr/bin/env python3
"""
Re-score saved baseline results and regenerate their tables, without AWS.

Usage (from eval/):
    python rescore.py --results results/baseline_comparison_results.json
"""

import argparse
import json
from pathlib import Path

from generate_tables import (
    generate_injection_asr_table,
    generate_latency_table,
    generate_phi_leakage_table,
)
from metrics import compare_configurations, generate_comparison_table
from run_eval import load_test_suite, prepare_test_cases
from scoring import score_results


def main():
    parser = argparse.ArgumentParser(description="Re-score saved MedGuard results")
    parser.add_argument("--results", required=True, help="Saved results JSON file")
    parser.add_argument("--suite", default="datasets/test_suite.json", help="Test suite JSON file")
    args = parser.parse_args()

    results_path = Path(args.results)
    output_dir = results_path.parent
    test_cases = prepare_test_cases(load_test_suite(args.suite))

    raw = json.loads(results_path.read_text())
    scored = {name: score_results(rows, test_cases) for name, rows in raw.items()}
    results_path.write_text(json.dumps(scored, indent=2))

    comparison = compare_configurations(scored)
    for fmt, extension in [("csv", "csv"), ("latex", "tex"), ("markdown", "md")]:
        table = generate_comparison_table(comparison, fmt)
        (output_dir / f"baseline_comparison.{extension}").write_text(table)

    table_builders = {
        "table_phi_leakage": generate_phi_leakage_table,
        "table_injection_asr": generate_injection_asr_table,
        "table_latency": generate_latency_table,
    }
    for name, build in table_builders.items():
        (output_dir / f"{name}.csv").write_text(build(scored, "csv"))
        (output_dir / f"{name}.tex").write_text(build(scored, "latex"))

    print(generate_comparison_table(comparison, "markdown"))


if __name__ == "__main__":
    main()
