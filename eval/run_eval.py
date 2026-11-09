#!/usr/bin/env python3
"""
Main evaluation harness for MedGuard
Supports baseline comparisons, ablation studies, and metrics generation
"""

import json
import argparse
import sys
from pathlib import Path
from typing import Dict, List
import time

import sys
from pathlib import Path

# Add eval directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from metrics import aggregate_metrics, compare_configurations, generate_comparison_table
from baseline import run_baseline_comparison
from ablation import AblationEvaluator
from scoring import score_results


def load_test_suite(suite_path: str) -> Dict:
    """Load test suite from JSON file"""
    with open(suite_path, "r") as f:
        return json.load(f)


def prepare_test_cases(suite: Dict, test_type: str = "all") -> List[Dict]:
    """
    Prepare test cases from suite
    
    Args:
        suite: Loaded test suite JSON
        test_type: "phi", "injection", "utility", or "all"
    """
    test_cases = []
    
    if test_type in ["phi", "all"]:
        for case in suite.get("phi_test_cases", []):
            test_cases.append({
                "prompt": case["prompt"],
                "expected_phi": case.get("expected_phi_types", []),
                "phi_values": case.get("phi_values", []),
                "is_attack": False,
                "test_id": case["id"],
                "test_name": case["name"]
            })
    
    if test_type in ["injection", "all"]:
        for case in suite.get("injection_test_cases", []):
            test_cases.append({
                "prompt": case["prompt"],
                "is_attack": case.get("is_attack", False),
                "severity": case.get("severity", "unknown"),
                "test_id": case["id"],
                "test_name": case["name"]
            })
    
    if test_type in ["utility", "all"]:
        for case in suite.get("utility_test_cases", []):
            test_cases.append({
                "prompt": case["prompt"],
                "is_attack": False,
                "test_id": case["id"],
                "test_name": case["name"]
            })
    
    return test_cases


def run_baseline_evaluation(
    test_cases: List[Dict],
    medguard_url: str,
    baseline_model_id: str,
    output_dir: str,
    auth_token: str = None
):
    """Run baseline comparison evaluation"""
    print("="*60)
    print("BASELINE COMPARISON EVALUATION")
    print("="*60)
    
    results = run_baseline_comparison(
        test_cases,
        medguard_url,
        baseline_model_id,
        auth_token
    )
    
    results = {name: score_results(rows, test_cases) for name, rows in results.items()}

    # Save raw results
    output_path = Path(output_dir) / "baseline_comparison_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {output_path}")
    
    # Calculate metrics
    from metrics import compare_configurations, generate_comparison_table
    
    comparison = compare_configurations(results)
    
    # Generate tables
    csv_table = generate_comparison_table(comparison, "csv")
    latex_table = generate_comparison_table(comparison, "latex")
    markdown_table = generate_comparison_table(comparison, "markdown")
    
    # Save tables
    (Path(output_dir) / "baseline_comparison.csv").write_text(csv_table)
    (Path(output_dir) / "baseline_comparison.tex").write_text(latex_table)
    (Path(output_dir) / "baseline_comparison.md").write_text(markdown_table)
    
    print("\nTables generated:")
    print(f"  - baseline_comparison.csv")
    print(f"  - baseline_comparison.tex (LaTeX for paper)")
    print(f"  - baseline_comparison.md")
    
    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for config_name, metrics in comparison.items():
        print(f"\n{config_name.upper()}:")
        print(f"  PHI Detection Rate: {metrics.phi_detection_rate:.2f}%")
        print(f"  PHI Leakage Rate: {metrics.phi_leakage_rate:.2f}%")
        print(f"  Injection Detection Rate: {metrics.injection_detection_rate:.2f}%")
        print(f"  Attack Success Rate: {metrics.attack_success_rate:.2f}%")
        print(f"  Avg Latency: {metrics.latency_ms:.1f}ms (P50: {metrics.latency_p50:.1f}ms, P95: {metrics.latency_p95:.1f}ms)")
    
    return comparison


def run_ablation_evaluation(
    test_cases: List[Dict],
    medguard_url: str,
    output_dir: str,
    auth_token: str = None
):
    """Run ablation study evaluation"""
    print("="*60)
    print("ABLATION STUDY EVALUATION")
    print("="*60)
    print("\nNote: Full ablation requires handler modifications to disable individual defenses.")
    print("Current implementation evaluates full stack configuration.")
    
    evaluator = AblationEvaluator(medguard_url, auth_token)
    results = evaluator.run_ablation_study(test_cases)
    
    # Save results
    output_path = Path(output_dir) / "ablation_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {output_path}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="MedGuard Evaluation Harness")
    parser.add_argument("--suite", default="datasets/test_suite.json", help="Test suite JSON file")
    parser.add_argument("--medguard-url", required=True, help="MedGuard API URL")
    parser.add_argument("--baseline-model", default="anthropic.claude-3-haiku-20240307-v1:0", help="Baseline model ID")
    parser.add_argument("--output-dir", default="results", help="Output directory")
    parser.add_argument("--auth-token", help="Authentication token (if auth enabled)")
    parser.add_argument("--test-type", choices=["phi", "injection", "utility", "all"], default="all", help="Test type to run")
    parser.add_argument("--mode", choices=["baseline", "ablation", "both"], default="both", help="Evaluation mode")
    
    args = parser.parse_args()
    
    # Create output directory
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    
    # Load test suite
    print(f"Loading test suite: {args.suite}")
    suite = load_test_suite(args.suite)
    test_cases = prepare_test_cases(suite, args.test_type)
    print(f"Loaded {len(test_cases)} test cases")
    
    # Run evaluations
    if args.mode in ["baseline", "both"]:
        baseline_comparison = run_baseline_evaluation(
            test_cases,
            args.medguard_url,
            args.baseline_model,
            args.output_dir,
            args.auth_token
        )
    
    if args.mode in ["ablation", "both"]:
        ablation_results = run_ablation_evaluation(
            test_cases,
            args.medguard_url,
            args.output_dir,
            args.auth_token
        )
    
    print("\n" + "="*60)
    print("EVALUATION COMPLETE")
    print("="*60)
    print(f"\nResults saved to: {args.output_dir}/")


if __name__ == "__main__":
    main()
