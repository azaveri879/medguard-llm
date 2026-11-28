#!/usr/bin/env python3
"""
Choose a PHI pipeline setting on one half of PhysioNet's gold notes, then report it on the other.

Settings are combinations of: our rules, the Stanford model in the gateway pipeline at
a decision threshold (top label, or total PHI probability >= t), and optionally the
original obi model's own detections added on top (a union). Each component runs once
per note; combinations reuse those spans.

The chosen setting is the one with the most PHI found on the tune half while removing
no more than MAX_OTHER_WORDS of other words. Only aggregate tables are printed.

Usage (from eval/):
    python deid_tune_physionet.py --data DESTINATION/physionet_deid --output results/deid_physionet_tuning.md
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "gateway"))

from deid_benchmark import ROBERTA_MODEL, bootstrap_ci, score_notes, spans_from_redacted, token_classifier_detector
from physionet_deid import load_physionet_deid

STANFORD = "StanfordAIMI/stanford-deidentifier-base"
THRESHOLDS: List[Optional[float]] = [None, 0.5, 0.3, 0.2, 0.1, 0.05]
MAX_OTHER_WORDS = 2.0


def pipeline_spans(notes: List[Dict], threshold: Optional[float]) -> List[List[Tuple[int, int]]]:
    import ner_redaction

    if threshold is None:
        os.environ.pop("PHI_NER_THRESHOLD", None)
    else:
        os.environ["PHI_NER_THRESHOLD"] = str(threshold)
    return [spans_from_redacted(n["text"], ner_redaction.phi_redact_with_ner(n["text"])[0]) for n in notes]


def evaluate(notes: List[Dict], spans: List[List[Tuple[int, int]]]) -> Dict:
    lookup = {id(n["text"]): s for n, s in zip(notes, spans)}
    result = score_notes(notes, lambda text: lookup[id(text)])
    return result


def other_removed(result: Dict) -> float:
    return 100 * result["other_words_redacted"] / result["other_words"]


def run(notes: List[Dict], obi_spans) -> List[Tuple[str, Optional[float], bool, Dict]]:
    rows = []
    for threshold in THRESHOLDS:
        base = pipeline_spans(notes, threshold)
        for union in (False, True):
            spans = [b + o for b, o in zip(base, obi_spans)] if union else base
            rows.append((STANFORD, threshold, union, evaluate(notes, spans)))
    return rows


def table(rows) -> str:
    lines = ["| Setting | PHI found | Names | Dates | Facilities | Other words removed |", "|---|---|---|---|---|---|"]
    for _, threshold, union, result in rows:
        t, c = result["total"], result["caught"]
        pct = lambda label=None: 100 * (sum(c.values()) if label is None else c.get(label, 0)) / (sum(t.values()) if label is None else t.get(label, 1))
        name = ("top label" if threshold is None else f"PHI prob >= {threshold}") + (" + obi union" if union else "")
        lines.append(f"| {name} | {pct():.1f}% | {pct('NAME'):.1f}% | {pct('DATE'):.1f}% | {pct('FACILITY'):.1f}% | {other_removed(result):.2f}% |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--data", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    os.environ["PHI_NER_MODEL"] = STANFORD
    out = []
    obi = token_classifier_detector(ROBERTA_MODEL)
    for split in ("tune", "test"):
        notes = load_physionet_deid(args.data, split)
        notes = [n for n in notes if not n["mismatched"]]
        obi_spans = [obi(n["text"]) for n in notes]
        if split == "tune":
            rows = run(notes, obi_spans)
            eligible = [r for r in rows if other_removed(r[3]) <= MAX_OTHER_WORDS]
            chosen = max(eligible, key=lambda r: sum(r[3]["caught"].values()))
            out += [f"## Tune half ({len(notes)} notes)", "", table(rows), ""]
            out.append(f"Chosen: {'top label' if chosen[1] is None else f'PHI prob >= {chosen[1]}'}"
                       f"{' + obi union' if chosen[2] else ''} (most PHI found with <= {MAX_OTHER_WORDS}% other words removed).")
        else:
            base = pipeline_spans(notes, chosen[1])
            spans = [b + o for b, o in zip(base, obi_spans)] if chosen[2] else base
            default = pipeline_spans(notes, None)
            test_rows = [(STANFORD, None, False, evaluate(notes, default)), (STANFORD, chosen[1], chosen[2], evaluate(notes, spans))]
            out += ["", f"## Test half ({len(notes)} notes), reported once", "", table(test_rows), ""]
            for label, (_, _, _, result) in zip(("default", "chosen"), test_rows):
                lo, hi = bootstrap_ci(result["per_note"])
                out.append(f"{label}: PHI found 95% CI {100 * lo:.1f}-{100 * hi:.1f}%")
    text = "\n".join(out)
    print(text)
    if args.output:
        Path(args.output).write_text(text + "\n")


if __name__ == "__main__":
    main()
