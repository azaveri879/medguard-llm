#!/usr/bin/env python3
"""
Compare detectors on the same notes using per-note counts from deid_benchmark.py.

Each argument is RESULTS.json:DETECTOR. The first is the baseline; each later one
is compared with it on the notes both runs scored, with a paired bootstrap
interval for the difference. With several candidates (for example one per
training seed), it also prints their mean and range.

Usage (from eval/):
    python deid_compare.py results/original.json:pipeline results/seed11.json:pipeline results/seed12.json:pipeline
"""

import argparse
import json
import random
import statistics
from typing import Dict, List, Optional, Tuple


def load(argument: str) -> Tuple[str, Dict[str, Dict]]:
    path, _, detector = argument.rpartition(":")
    per_note = json.loads(open(path).read())[detector]
    return argument, {note["key"]: note for note in per_note}


def counts(note: Dict, label: Optional[str]) -> Tuple[int, int]:
    if label is None:
        return sum(note["caught"].values()), sum(note["total"].values())
    return note["caught"].get(label, 0), note["total"].get(label, 0)


def rate(pairs: List[Tuple[int, int]]) -> float:
    total = sum(t for _, t in pairs)
    return sum(c for c, _ in pairs) / total if total else float("nan")


def paired_difference(base: Dict, candidate: Dict, label: Optional[str], rounds: int = 2000,
                      seed: int = 0) -> Dict:
    keys = sorted(set(base) & set(candidate))
    rows = [(counts(base[k], label), counts(candidate[k], label)) for k in keys]
    rows = [row for row in rows if row[0][1]]
    if not rows:
        nan = float("nan")
        return {"notes": len(keys), "base": nan, "candidate": nan, "difference": nan, "low": nan, "high": nan}
    observed = rate([c for _, c in rows]) - rate([b for b, _ in rows])
    rng = random.Random(seed)
    diffs = []
    for _ in range(rounds):
        sample = [rows[rng.randrange(len(rows))] for _ in rows]
        diffs.append(rate([c for _, c in sample]) - rate([b for b, _ in sample]))
    diffs = sorted(d for d in diffs if d == d)
    return {
        "notes": len(keys),
        "base": rate([b for b, _ in rows]),
        "candidate": rate([c for _, c in rows]),
        "difference": observed,
        "low": diffs[int(0.025 * (len(diffs) - 1))],
        "high": diffs[int(0.975 * (len(diffs) - 1))],
    }


def main():
    parser = argparse.ArgumentParser(description="Paired comparison of PHI detectors")
    parser.add_argument("runs", nargs="+", help="RESULTS.json:DETECTOR; the first is the baseline")
    parser.add_argument("--labels", default="ALL,NAME", help="Comma-separated; ALL means every PHI type")
    args = parser.parse_args()
    if len(args.runs) < 2:
        parser.error("Give a baseline and at least one candidate")

    base_name, base = load(args.runs[0])
    candidates = [load(run) for run in args.runs[1:]]
    for label_name in args.labels.split(","):
        label = None if label_name == "ALL" else label_name
        print(f"\n{label_name}: baseline {base_name}")
        print("| Candidate | Notes | Baseline | Candidate | Difference (95% CI) |")
        print("|---|---|---|---|---|")
        rates = []
        for name, candidate in candidates:
            result = paired_difference(base, candidate, label)
            if result["candidate"] == result["candidate"]:
                rates.append(result["candidate"])
            print(
                f"| {name} | {result['notes']} | {result['base'] * 100:.1f}% | "
                f"{result['candidate'] * 100:.1f}% | {result['difference'] * 100:+.1f} "
                f"({result['low'] * 100:+.1f} to {result['high'] * 100:+.1f}) |"
            )
        if len(rates) > 1:
            print(
                f"\nAcross {len(rates)} candidates: mean {statistics.mean(rates) * 100:.1f}%, "
                f"SD {statistics.stdev(rates) * 100:.2f}, range {min(rates) * 100:.1f}–{max(rates) * 100:.1f}%"
            )


if __name__ == "__main__":
    main()
