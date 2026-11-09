#!/usr/bin/env python3
"""
Metrics calculation for MedGuard evaluation
Supports PHI leakage, injection ASR, utility, and latency metrics
"""

import json
import re
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass, asdict
import hashlib


@dataclass
class EvaluationMetrics:
    """Container for evaluation metrics"""
    # PHI Metrics
    phi_detection_rate: float  # % of expected PHI types detected in input
    phi_leakage_rate: float    # % of PHI-bearing cases with a known identifier in output
    phi_types_detected: Dict[str, int]  # Count by type
    
    # Injection Metrics
    injection_detection_rate: float  # % of attacks detected
    attack_success_rate: float       # % of attacks that succeeded
    avg_injection_score: float
    
    # Utility Metrics
    response_length: int
    
    # Performance Metrics
    latency_ms: float
    
    # Request counts
    total_requests: int
    successful_requests: int
    failed_requests: int
    
    # Optional metrics (with defaults)
    response_quality_score: Optional[float] = None  # BERTScore/ROUGE if available
    latency_p50: Optional[float] = None
    latency_p95: Optional[float] = None
    false_alarm_rate: float = float("nan")  # % of benign requests flagged as attacks
    refusal_rate: float = float("nan")      # % of benign requests the model refused


def _pct(numerator: float, denominator: float) -> float:
    """Percentage, or NaN when nothing was measured so it can't read as a real zero."""
    return numerator / denominator * 100 if denominator else float("nan")


def calculate_phi_metrics(results: List[Dict]) -> Tuple[float, float, Dict[str, int]]:
    """
    Calculate PHI detection and leakage metrics from scored results

    Returns:
        detection_rate: % of expected PHI types the system detected
        leakage_rate: % of PHI-bearing cases whose response contains a known identifier
        types_detected: Count by PHI type
    """
    phi_cases = [r for r in results if r["expected_phi_types"]]
    expected = sum(len(set(r["expected_phi_types"])) for r in phi_cases)
    found = sum(
        len(set(r["expected_phi_types"]) & set(r.get("phi_counts_input", {})))
        for r in phi_cases
    )
    leaked_cases = sum(1 for r in phi_cases if r["phi_values_leaked"])

    types_detected = defaultdict(int)
    for result in results:
        for phi_type, count in result.get("phi_counts_input", {}).items():
            types_detected[phi_type] += count

    return _pct(found, expected), _pct(leaked_cases, len(phi_cases)), dict(types_detected)


def calculate_injection_metrics(results: List[Dict]) -> Tuple[float, float, float, float]:
    """
    Calculate injection metrics from scored results

    Returns:
        detection_rate: % of attacks flagged (score > 0)
        attack_success_rate: % of measurable attacks that succeeded
        avg_score: Average injection score across attacks
        false_alarm_rate: % of benign requests flagged as attacks
    """
    attacks = [r for r in results if r["is_attack"]]
    benign = [r for r in results if not r["is_attack"]]
    measurable = [r for r in attacks if r["attack_successful"] is not None]

    detected = sum(1 for r in attacks if r.get("injection_score", 0) > 0)
    succeeded = sum(1 for r in measurable if r["attack_successful"])
    total_score = sum(r.get("injection_score", 0) for r in attacks)
    avg_score = total_score / len(attacks) if attacks else float("nan")
    false_alarms = sum(1 for r in benign if r.get("injection_score", 0) > 0)

    return (
        _pct(detected, len(attacks)),
        _pct(succeeded, len(measurable)),
        avg_score,
        _pct(false_alarms, len(benign)),
    )


def calculate_utility_metrics(
    outputs: List[str],
    references: Optional[List[str]] = None
) -> Tuple[int, Optional[float]]:
    """
    Calculate utility metrics (response length, quality score)
    
    Returns:
        avg_length: Average response length
        quality_score: BERTScore/ROUGE if references provided
    """
    if not outputs:
        return 0, None
    
    avg_length = sum(len(output) for output in outputs) / len(outputs)
    
    # TODO: Add BERTScore/ROUGE calculation if references provided
    quality_score = None
    if references and len(references) == len(outputs):
        # Placeholder for BERTScore/ROUGE
        # quality_score = calculate_bertscore(outputs, references)
        pass
    
    return int(avg_length), quality_score


def calculate_latency_metrics(
    latencies: List[float]
) -> Tuple[float, float, float]:
    """
    Calculate latency statistics
    
    Returns:
        avg_latency: Average latency in ms
        p50: 50th percentile
        p95: 95th percentile
    """
    if not latencies:
        return 0.0, 0.0, 0.0
    
    sorted_latencies = sorted(latencies)
    avg = sum(sorted_latencies) / len(sorted_latencies)
    p50 = sorted_latencies[len(sorted_latencies) // 2]
    p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)] if len(sorted_latencies) > 1 else sorted_latencies[0]
    
    return avg, p50, p95


def aggregate_metrics(
    results: List[Dict],
    references: Optional[List[str]] = None
) -> EvaluationMetrics:
    """
    Aggregate metrics from evaluation results
    
    Args:
        results: List of result dictionaries with keys:
            - phi_counts_input, phi_counts_output
            - injection_score
            - attack_successful (optional)
            - response
            - latency_ms
            - success (optional)
        references: Optional reference texts for quality scoring
    """
    if not all(r.get("scored") for r in results):
        raise ValueError("aggregate_metrics needs results from scoring.score_results")

    answered = [r for r in results if r.get("success", True)]
    outputs = [r.get("response", "") for r in results]
    latencies = [r.get("latency_ms", 0) for r in results]
    successful = [r.get("success", True) for r in results]

    # Calculate metrics
    phi_detection_rate, phi_leakage_rate, phi_types = calculate_phi_metrics(answered)

    (
        injection_detection_rate,
        attack_success_rate,
        avg_injection_score,
        false_alarm_rate,
    ) = calculate_injection_metrics(answered)

    benign = [r for r in answered if not r["is_attack"]]
    refusal_rate = _pct(sum(1 for r in benign if r["refused"]), len(benign))

    avg_length, quality_score = calculate_utility_metrics(outputs, references)
    
    avg_latency, p50, p95 = calculate_latency_metrics(latencies)
    
    return EvaluationMetrics(
        phi_detection_rate=phi_detection_rate,
        phi_leakage_rate=phi_leakage_rate,
        phi_types_detected=phi_types,
        injection_detection_rate=injection_detection_rate,
        attack_success_rate=attack_success_rate,
        avg_injection_score=avg_injection_score,
        response_length=avg_length,
        response_quality_score=quality_score,
        latency_ms=avg_latency,
        latency_p50=p50,
        latency_p95=p95,
        false_alarm_rate=false_alarm_rate,
        refusal_rate=refusal_rate,
        total_requests=len(results),
        successful_requests=sum(successful),
        failed_requests=len(results) - sum(successful)
    )


def compare_configurations(
    config_results: Dict[str, List[Dict]]
) -> Dict[str, EvaluationMetrics]:
    """
    Compare metrics across different configurations
    
    Args:
        config_results: Dict mapping config name to list of results
        
    Returns:
        Dict mapping config name to EvaluationMetrics
    """
    comparison = {}
    for config_name, results in config_results.items():
        comparison[config_name] = aggregate_metrics(results)
    return comparison


def generate_comparison_table(
    comparison: Dict[str, EvaluationMetrics],
    output_format: str = "csv"
) -> str:
    """
    Generate comparison table in specified format
    
    Args:
        comparison: Dict from compare_configurations
        output_format: "csv", "latex", or "markdown"
    """
    if output_format == "csv":
        return _generate_csv_table(comparison)
    elif output_format == "latex":
        return _generate_latex_table(comparison)
    elif output_format == "markdown":
        return _generate_markdown_table(comparison)
    else:
        raise ValueError(f"Unknown format: {output_format}")


def _generate_csv_table(comparison: Dict[str, EvaluationMetrics]) -> str:
    """Generate CSV table"""
    lines = ["Configuration,PHI Detection (%),PHI Leakage (%),Injection Detection (%),ASR (%),False Alarm (%),Refusal (%),Avg Latency (ms),P50 (ms),P95 (ms)"]
    
    for config_name, metrics in comparison.items():
        lines.append(
            f"{config_name},"
            f"{metrics.phi_detection_rate:.2f},"
            f"{metrics.phi_leakage_rate:.2f},"
            f"{metrics.injection_detection_rate:.2f},"
            f"{metrics.attack_success_rate:.2f},"
            f"{metrics.false_alarm_rate:.2f},"
            f"{metrics.refusal_rate:.2f},"
            f"{metrics.latency_ms:.1f},"
            f"{metrics.latency_p50:.1f},"
            f"{metrics.latency_p95:.1f}"
        )
    
    return "\n".join(lines)


def _generate_latex_table(comparison: Dict[str, EvaluationMetrics]) -> str:
    """Generate LaTeX table for papers"""
    lines = [
        "\\begin{table}[h]",
        "\\centering",
        "\\begin{tabular}{lccccccc}",
        "\\toprule",
        "Configuration & PHI Det. & PHI Leak & Inj. Det. & ASR & False Alarm & Refusal & Latency (ms) \\\\",
        "\\midrule"
    ]
    
    for config_name, metrics in comparison.items():
        config_display = config_name.replace("_", " ").title()
        lines.append(
            f"{config_display} & "
            f"{metrics.phi_detection_rate:.1f}\\% & "
            f"{metrics.phi_leakage_rate:.1f}\\% & "
            f"{metrics.injection_detection_rate:.1f}\\% & "
            f"{metrics.attack_success_rate:.1f}\\% & "
            f"{metrics.false_alarm_rate:.1f}\\% & "
            f"{metrics.refusal_rate:.1f}\\% & "
            f"{metrics.latency_ms:.0f} \\\\"
        )
    
    lines.extend([
        "\\bottomrule",
        "\\end{tabular}",
        "\\caption{Comparison of MedGuard configurations}",
        "\\label{tab:config-comparison}",
        "\\end{table}"
    ])
    
    return "\n".join(lines)


def _generate_markdown_table(comparison: Dict[str, EvaluationMetrics]) -> str:
    """Generate Markdown table"""
    lines = [
        "| Configuration | PHI Det. (%) | PHI Leak (%) | Inj. Det. (%) | ASR (%) | False Alarm (%) | Refusal (%) | Latency (ms) |",
        "|---------------|--------------|--------------|---------------|---------|-----------------|-------------|--------------|"
    ]
    
    for config_name, metrics in comparison.items():
        config_display = config_name.replace("_", " ").title()
        lines.append(
            f"| {config_display} | "
            f"{metrics.phi_detection_rate:.2f} | "
            f"{metrics.phi_leakage_rate:.2f} | "
            f"{metrics.injection_detection_rate:.2f} | "
            f"{metrics.attack_success_rate:.2f} | "
            f"{metrics.false_alarm_rate:.2f} | "
            f"{metrics.refusal_rate:.2f} | "
            f"{metrics.latency_ms:.1f} |"
        )
    
    return "\n".join(lines)
