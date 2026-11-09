#!/usr/bin/env python3
"""
Generate publication-ready tables from evaluation results
Supports JAMIA / npj Digital Medicine style formatting
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List
from metrics import EvaluationMetrics, compare_configurations, generate_comparison_table


def generate_phi_leakage_table(
    results: Dict[str, List[Dict]],
    output_format: str = "latex"
) -> str:
    """
    Generate PHI leakage comparison table
    
    Format suitable for paper Results section
    """
    comparison = compare_configurations(results)
    
    if output_format == "latex":
        lines = [
            "\\begin{table}[h]",
            "\\centering",
            "\\begin{tabular}{lcc}",
            "\\toprule",
            "Configuration & PHI Detection Rate (\\%) & PHI Leakage Rate (\\%) \\\\",
            "\\midrule"
        ]
        
        for config_name, metrics in comparison.items():
            config_display = config_name.replace("_", " ").title()
            lines.append(
                f"{config_display} & "
                f"{metrics.phi_detection_rate:.1f} & "
                f"{metrics.phi_leakage_rate:.1f} \\\\"
            )
        
        lines.extend([
            "\\bottomrule",
            "\\end{tabular}",
            "\\caption{PHI Detection and Leakage Rates by Configuration}",
            "\\label{tab:phi-leakage}",
            "\\end{table}"
        ])
        
        return "\n".join(lines)
    
    elif output_format == "csv":
        lines = ["Configuration,PHI Detection (%),PHI Leakage (%)"]
        for config_name, metrics in comparison.items():
            lines.append(
                f"{config_name},{metrics.phi_detection_rate:.2f},{metrics.phi_leakage_rate:.2f}"
            )
        return "\n".join(lines)


def generate_injection_asr_table(
    results: Dict[str, List[Dict]],
    output_format: str = "latex"
) -> str:
    """
    Generate Injection Attack Success Rate (ASR) table
    """
    comparison = compare_configurations(results)
    
    if output_format == "latex":
        lines = [
            "\\begin{table}[h]",
            "\\centering",
            "\\begin{tabular}{lcc}",
            "\\toprule",
            "Configuration & Injection Detection Rate (\\%) & Attack Success Rate (\\%) \\\\",
            "\\midrule"
        ]
        
        for config_name, metrics in comparison.items():
            config_display = config_name.replace("_", " ").title()
            lines.append(
                f"{config_display} & "
                f"{metrics.injection_detection_rate:.1f} & "
                f"{metrics.attack_success_rate:.1f} \\\\"
            )
        
        lines.extend([
            "\\bottomrule",
            "\\end{tabular}",
            "\\caption{Injection Attack Detection and Success Rates}",
            "\\label{tab:injection-asr}",
            "\\end{table}"
        ])
        
        return "\n".join(lines)
    
    elif output_format == "csv":
        lines = ["Configuration,Injection Detection (%),ASR (%)"]
        for config_name, metrics in comparison.items():
            lines.append(
                f"{config_name},{metrics.injection_detection_rate:.2f},{metrics.attack_success_rate:.2f}"
            )
        return "\n".join(lines)


def generate_latency_table(
    results: Dict[str, List[Dict]],
    output_format: str = "latex"
) -> str:
    """
    Generate latency comparison table
    """
    comparison = compare_configurations(results)
    
    if output_format == "latex":
        lines = [
            "\\begin{table}[h]",
            "\\centering",
            "\\begin{tabular}{lccc}",
            "\\toprule",
            "Configuration & Mean (ms) & P50 (ms) & P95 (ms) \\\\",
            "\\midrule"
        ]
        
        for config_name, metrics in comparison.items():
            config_display = config_name.replace("_", " ").title()
            lines.append(
                f"{config_display} & "
                f"{metrics.latency_ms:.0f} & "
                f"{metrics.latency_p50:.0f} & "
                f"{metrics.latency_p95:.0f} \\\\"
            )
        
        lines.extend([
            "\\bottomrule",
            "\\end{tabular}",
            "\\caption{Latency Comparison by Configuration}",
            "\\label{tab:latency}",
            "\\end{table}"
        ])
        
        return "\n".join(lines)
    
    elif output_format == "csv":
        lines = ["Configuration,Mean (ms),P50 (ms),P95 (ms)"]
        for config_name, metrics in comparison.items():
            lines.append(
                f"{config_name},{metrics.latency_ms:.1f},{metrics.latency_p50:.1f},{metrics.latency_p95:.1f}"
            )
        return "\n".join(lines)


def generate_ablation_table(
    ablation_results: Dict[str, Dict[str, List[Dict]]],
    output_format: str = "latex"
) -> str:
    """
    Generate ablation study table showing contribution of each defense layer
    """
    # This would compare configurations and show marginal benefit
    # Placeholder for when full ablation is implemented
    
    if output_format == "latex":
        return """\\begin{table}[h]
\\centering
\\begin{tabular}{lcc}
\\toprule
Defense Layer & PHI Leakage Reduction & Injection ASR Reduction \\\\
\\midrule
PHI Detection Only & -- & -- \\\\
Injection Detection Only & -- & -- \\\\
Full Stack & -- & -- \\\\
\\bottomrule
\\end{tabular}
\\caption{Ablation Study: Contribution of Individual Defense Layers}
\\label{tab:ablation}
\\end{table}"""
    
    return "Ablation table (placeholder)"


def main():
    parser = argparse.ArgumentParser(description="Generate publication-ready tables")
    parser.add_argument("--results", required=True, help="Results JSON file")
    parser.add_argument("--output-dir", default="results", help="Output directory")
    parser.add_argument("--format", choices=["latex", "csv", "both"], default="both", help="Output format")
    
    args = parser.parse_args()
    
    # Load results
    with open(args.results, "r") as f:
        results = json.load(f)
    
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    
    # Generate tables
    if args.format in ["latex", "both"]:
        phi_table = generate_phi_leakage_table(results, "latex")
        injection_table = generate_injection_asr_table(results, "latex")
        latency_table = generate_latency_table(results, "latex")
        
        (Path(args.output_dir) / "table_phi_leakage.tex").write_text(phi_table)
        (Path(args.output_dir) / "table_injection_asr.tex").write_text(injection_table)
        (Path(args.output_dir) / "table_latency.tex").write_text(latency_table)
        
        print("LaTeX tables generated:")
        print(f"  - table_phi_leakage.tex")
        print(f"  - table_injection_asr.tex")
        print(f"  - table_latency.tex")
    
    if args.format in ["csv", "both"]:
        phi_csv = generate_phi_leakage_table(results, "csv")
        injection_csv = generate_injection_asr_table(results, "csv")
        latency_csv = generate_latency_table(results, "csv")
        
        (Path(args.output_dir) / "table_phi_leakage.csv").write_text(phi_csv)
        (Path(args.output_dir) / "table_injection_asr.csv").write_text(injection_csv)
        (Path(args.output_dir) / "table_latency.csv").write_text(latency_csv)
        
        print("\nCSV tables generated:")
        print(f"  - table_phi_leakage.csv")
        print(f"  - table_injection_asr.csv")
        print(f"  - table_latency.csv")


if __name__ == "__main__":
    main()
