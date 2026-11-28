#!/usr/bin/env python3
"""
Leave-one-out ablation of the redaction layer on PhysioNet's test half.

Starts from setup A (public Stanford model, rules, threshold 0.02, name lexicon), which is
what the deployed gateway runs, and removes one part at a time:
  - the name lexicon,
  - the probability threshold (back to the model's top label),
  - the month/day date rule,
  - all rules (model + lexicon only),
  - the model (rules + lexicon only).
Each variant is scored without and with EHR-supplied names (patient + care team).
Prints aggregates only; no note text leaves this process.

Usage (from eval/):
    PHI_NER_ENABLED=true PHI_NER_MODEL=StanfordAIMI/stanford-deidentifier-base \\
        python deid_ablation_physionet.py --physionet-deid DESTINATION/physionet_deid \\
        --split test --output results/deid_ablation_physionet.md
"""

import argparse
import os
import random
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "gateway"))

import ner_redaction  # noqa: E402
import phi_redaction  # noqa: E402
from deid_benchmark import bootstrap_ci, score_notes, spans_from_redacted  # noqa: E402
from known_names import redact_with_known  # noqa: E402
from physionet_deid import load_physionet_deid  # noqa: E402

BASE_ENV = {"PHI_NER_THRESHOLD": "0.02", "PHI_NAME_LEXICON": "true"}


@contextmanager
def variant(name: str):
    env = dict(BASE_ENV)
    saved_rules = list(phi_redaction.STRUCTURED_RULES)
    saved_rules_fn, saved_entities = ner_redaction.phi_redact, ner_redaction.redact_entities
    if name == "no_lexicon":
        env["PHI_NAME_LEXICON"] = "false"
    elif name == "top_label":
        env["PHI_NER_THRESHOLD"] = ""
    elif name == "no_month_day":
        phi_redaction.STRUCTURED_RULES[:] = [r for r in saved_rules if r[0] != phi_redaction.MONTH_DAY]
    elif name == "no_rules":
        ner_redaction.phi_redact = lambda text: (text or "", {})
    elif name == "no_model":
        ner_redaction.redact_entities = lambda text: (text or "", {})
    old_env = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        yield
    finally:
        phi_redaction.STRUCTURED_RULES[:] = saved_rules
        ner_redaction.phi_redact, ner_redaction.redact_entities = saved_rules_fn, saved_entities
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def detector(notes: List[Dict], ehr: bool):
    names = {n["text"]: [x for role in ("patient", "care_team") for x in n["known_names"][role]] for n in notes}

    def detect(text: str):
        known = names[text] if ehr else []
        return spans_from_redacted(text, redact_with_known(text, known, ner_redaction.phi_redact_with_ner)[0])
    return detect


def recall(result: Dict, label=None) -> float:
    if label is None:
        return sum(result["caught"].values()) / sum(result["total"].values())
    return result["caught"].get(label, 0) / result["total"][label]


def paired_diff(a: List[Dict], b: List[Dict], label=None, reps: int = 2000, seed: int = 0) -> str:
    """a minus b, percentage points, bootstrap over notes (same notes, same order)."""
    def pair(n):
        if label is None:
            return sum(n["caught"].values()), sum(n["total"].values())
        return n["caught"].get(label, 0), n["total"].get(label, 0)

    pa, pb = [pair(n) for n in a], [pair(n) for n in b]

    def diff(idx):
        ta, tb = sum(pa[i][1] for i in idx), sum(pb[i][1] for i in idx)
        return 100 * (sum(pa[i][0] for i in idx) / ta - sum(pb[i][0] for i in idx) / tb)

    idx = list(range(len(a)))
    rng = random.Random(seed)
    boots = sorted(diff([rng.randrange(len(idx)) for _ in idx]) for _ in range(reps))
    return f"{diff(idx):+.1f} ({boots[int(0.025 * reps)]:+.1f} to {boots[int(0.975 * reps) - 1]:+.1f})"


VARIANTS = [
    ("full", "Setup A (all parts)"),
    ("no_lexicon", "− name lexicon"),
    ("top_label", "− threshold 0.02 (top label)"),
    ("no_month_day", "− month/day date rule"),
    ("no_rules", "− all rules (model + lexicon)"),
    ("no_model", "− model (rules + lexicon)"),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--physionet-deid", required=True)
    parser.add_argument("--split", default="test", choices=["tune", "test"])
    parser.add_argument("--output")
    args = parser.parse_args()

    notes = [n for n in load_physionet_deid(args.physionet_deid, args.split) if not n["mismatched"]]
    print(f"{len(notes)} notes", flush=True)
    results = {}
    for key, _ in VARIANTS:
        for ehr in (False, True):
            with variant(key):
                results[(key, ehr)] = score_notes(notes, detector(notes, ehr))
            r = results[(key, ehr)]
            print(f"{key} ehr={ehr}: {100 * recall(r):.1f}%", flush=True)

    lines = [
        f"PhysioNet {args.split} half, {len(notes)} notes. Model: {os.environ.get('PHI_NER_MODEL')}.",
        "",
        "| Variant | PHI found (95% CI) | Δ vs A | Names | Δ names | Dates | With EHR names: PHI found | Δ vs A | Names | Other words removed |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for key, label in VARIANTS:
        r, re_ = results[(key, False)], results[(key, True)]
        lo, hi = bootstrap_ci(r["per_note"])
        base, base_e = results[("full", False)], results[("full", True)]
        same = key == "full"
        lines.append(
            f"| {label} | {100 * recall(r):.1f}% ({100 * lo:.1f}–{100 * hi:.1f}) | "
            f"{'' if same else paired_diff(r['per_note'], base['per_note'])} | {100 * recall(r, 'NAME'):.1f}% | "
            f"{'' if same else paired_diff(r['per_note'], base['per_note'], 'NAME')} | {100 * recall(r, 'DATE'):.1f}% | "
            f"{100 * recall(re_):.1f}% | {'' if same else paired_diff(re_['per_note'], base_e['per_note'])} | "
            f"{100 * recall(re_, 'NAME'):.1f}% | {100 * r['other_words_redacted'] / r['other_words']:.2f}% |")
    report = "\n".join(lines)
    print(report)
    if args.output:
        Path(args.output).write_text(report + "\n")


if __name__ == "__main__":
    main()
