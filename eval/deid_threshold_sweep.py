#!/usr/bin/env python3
"""
Measure PHI recall against over-redaction at several model thresholds.

Reads a MIMIC-III NOTEEVENTS CSV from stdin and prints aggregates only. Choose a
threshold on one seed, then confirm it on another.

Usage (from eval/):
    python deid_threshold_sweep.py --seed 7 --output results/deid_threshold_tune.md < notes.csv
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "gateway"))

import ner_redaction
from deid_benchmark import known_name_detector, score_notes
from mimic_surrogates import DEFAULT_SEED, sample_notes

THRESHOLDS = [None, 0.5, 0.3, 0.2, 0.1, 0.05, 0.02]
SCENARIOS = {
    "no known names": (),
    "patient and care team known": ("patient", "care_team"),
}
MAX_OTHER_WORDS_REMOVED = 3.0
MIN_CLINICAL_INTACT = 95.0


def percent(part, whole):
    return part / whole * 100 if whole else float("nan")


def summarize(result):
    caught, total = result["caught"], result["total"]
    return {
        "phi": percent(sum(caught.values()), sum(total.values())),
        "names": percent(caught.get("NAME", 0), total.get("NAME", 0)),
        "clinical": percent(result["keep_intact"], result["keep_total"]),
        "other": percent(result["other_words_redacted"], result["other_words"]),
    }


def main():
    parser = argparse.ArgumentParser(description="Sweep the PHI model threshold")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--per-category", type=int, default=200)
    parser.add_argument("--output")
    args = parser.parse_args()

    notes = sample_notes(sys.stdin, args.per_category, args.seed)

    # Run the model once per text, then reuse its scores for every threshold.
    score_tokens = ner_redaction._token_scores
    cache = {}

    def cached_scores(text):
        if text not in cache:
            cache[text] = score_tokens(text)
        return cache[text]

    ner_redaction._token_scores = cached_scores

    lines = [
        f"Notes: {len(notes)}, seed {args.seed}",
        "",
        "| Scenario | Threshold | PHI found | Names found | Clinical terms intact | Other words removed | Eligible |",
        "|---|---|---|---|---|---|---|",
    ]
    for scenario, roles in SCENARIOS.items():
        detector = known_name_detector(notes, roles)
        best = None
        for threshold in THRESHOLDS:
            if threshold is None:
                os.environ.pop("PHI_NER_THRESHOLD", None)
            else:
                os.environ["PHI_NER_THRESHOLD"] = str(threshold)
            row = summarize(score_notes(notes, detector))
            eligible = row["other"] <= MAX_OTHER_WORDS_REMOVED and row["clinical"] >= MIN_CLINICAL_INTACT
            label = "top label" if threshold is None else str(threshold)
            if eligible and (best is None or row["names"] > best[1]):
                best = (label, row["names"])
            lines.append(
                f"| {scenario} | {label} | {row['phi']:.1f}% | {row['names']:.1f}% | "
                f"{row['clinical']:.1f}% | {row['other']:.1f}% | {'yes' if eligible else 'no'} |"
            )
        lines.append(f"| {scenario} | **selected: {best[0] if best else 'none'}** | | | | | |")

    table = "\n".join(lines)
    print(table)
    if args.output:
        Path(args.output).write_text(table + "\n")


if __name__ == "__main__":
    main()
