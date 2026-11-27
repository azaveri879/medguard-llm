#!/usr/bin/env python3
"""
Layer ablation of the gateway on the injection suite (synthetic notes only).

The gateway has three layers:
  R  input PHI redaction (rules + NER),
  G  the guard: the note wrapped in <CLINICAL_NOTE> plus the security rules,
  O  PHI redaction of the model's reply (the output filter).

Each request is sent to Bedrock under the four R x G settings, through the real gateway
code (handler.gateway_reply). O changes only the text after the model answers, so it is
applied offline to every stored raw reply, which gives all eight R x G x O cells. A
"direct" baseline (a typical app prompt, no gateway) is run too, as in run_injection.py.

Measures, per cell, with 95% Wilson intervals and paired bootstrap differences against
the full gateway:
  attack success (all attacks, and excluding the PHI-theft goal), canary leaks,
  PHI leakage (gold values of the note that appear in the reply; any-leak rate per
  benign note and value-level rate per type), benign refusals, latency.

Usage (from eval/):
    PHI_NER_ENABLED=true PHI_NER_MODEL=StanfordAIMI/stanford-deidentifier-base \\
    PHI_NER_THRESHOLD=0.02 PHI_NAME_LEXICON=true \\
        python run_ablation.py --model us.anthropic.claude-haiku-4-5-20251001-v1:0 \\
        --output results/ablation_raw_haiku45.json --report results/ablation_layers.md
    python run_ablation.py --summarize results/ablation_raw_haiku45.json --report ...
"""

import argparse
import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Dict, List, Optional

from run_injection import attack_succeeded, load_gateway, wilson
from scoring import is_refusal, value_leaked

SETTINGS = {  # name: (redact, guard)
    "full": (True, True),
    "no_redact": (False, True),
    "no_guard": (True, False),
    "none": (False, False),
}
LEAK_TYPES = ["NAME", "DATE", "ID", "PHONE", "ADDRESS", "EMAIL"]


def with_retries(call: Callable[[], Dict], attempts: int = 4) -> Dict:
    for attempt in range(attempts):
        try:
            return call()
        except Exception as error:  # throttling or transient errors; reported if they persist
            if attempt == attempts - 1:
                return {"raw": "", "ok": False, "error": str(error)[:200]}
            time.sleep(2 ** attempt + random.random())


def run_setting(handler, case: Dict, redact: bool, guard: bool) -> Dict:
    def call():
        start = time.time()
        out = handler.gateway_reply(case["note"], "clinician", [], redact=redact, guard=guard)
        return {"raw": out["raw"], "filtered": out["response"], "ok": True,
                "latency_ms": int((time.time() - start) * 1000)}
    return with_retries(call)


def run_direct(handler, case: Dict, task: str, canary: str) -> Dict:
    from run_injection import direct_system

    def call():
        start = time.time()
        raw = handler.invoke_bedrock(direct_system(canary), task + case["note"])
        return {"raw": raw, "ok": True, "latency_ms": int((time.time() - start) * 1000)}
    out = with_retries(call)
    if out["ok"]:
        out["filtered"] = output_filter(handler, out["raw"])
    return out


def output_filter(handler, text: str) -> str:
    """The gateway's output filter, as in handler.gateway_reply (no known names)."""
    import re
    safe, found = handler.redact_with_known(text, [], handler.phi_redact)
    return re.sub(r"\[PHI_[A-Z]+\]", "[REDACTED]", safe) if found else safe


# ---------------------------------------------------------------- scoring

def leaks(case: Dict, reply: str) -> List[bool]:
    return [value_leaked(v["type"], v["value"], reply) for v in case["phi_all"] if v["type"] in LEAK_TYPES]


def case_metrics(case: Dict, reply: Optional[str]) -> Optional[Dict]:
    if reply is None:
        return None
    leaked = leaks(case, reply)
    by_type = {t: [value_leaked(v["type"], v["value"], reply) for v in case["phi_all"] if v["type"] == t]
               for t in LEAK_TYPES}
    return {
        "attack": case["is_attack"],
        "goal": case["goal"],
        "success": bool(attack_succeeded(case, reply)) if case["is_attack"] else None,
        "any_leak": any(leaked),
        "leaked": sum(leaked),
        "values": len(leaked),
        "by_type": {t: (sum(x), len(x)) for t, x in by_type.items()},
        "refused": is_refusal(reply),
    }


def cells(records: List[Dict]) -> Dict[str, List[Optional[Dict]]]:
    out = {}
    for cond in ["direct"] + list(SETTINGS):
        for filtered in (False, True):
            name = f"{cond}{'+O' if filtered else ''}"
            key = "filtered" if filtered else "raw"
            out[name] = [
                case_metrics(r["case"], r[cond][key]) if r[cond]["ok"] else None for r in records
            ]
    return out


def rate(ms: List[Optional[Dict]], pick: Callable[[Dict], bool], field: str) -> tuple:
    vals = [m[field] for m in ms if m is not None and pick(m)]
    return sum(vals), len(vals)


def value_rate(ms: List[Optional[Dict]], pick: Callable[[Dict], bool], t: Optional[str] = None) -> tuple:
    hit = tot = 0
    for m in ms:
        if m is None or not pick(m):
            continue
        h, n = (m["leaked"], m["values"]) if t is None else m["by_type"][t]
        hit, tot = hit + h, tot + n
    return hit, tot


def paired_diff(a: List[Optional[Dict]], b: List[Optional[Dict]], pick, stat, reps: int = 4000,
                seed: int = 20261127) -> str:
    """Bootstrap over cases of stat(a) - stat(b), in percentage points, on cases scored in both."""
    idx = [i for i in range(len(a)) if a[i] is not None and b[i] is not None and pick(a[i])]
    if not idx:
        return "n/a"

    def value(sample):
        xa, xb = [a[i] for i in sample], [b[i] for i in sample]
        return 100 * (stat(xa) - stat(xb))

    point = value(idx)
    rng = random.Random(seed)
    boots = sorted(value([rng.choice(idx) for _ in idx]) for _ in range(reps))
    lo, hi = boots[int(0.025 * reps)], boots[int(0.975 * reps) - 1]
    return f"{point:+.1f} ({lo:+.1f} to {hi:+.1f})"


def mean_rate(field):
    return lambda ms: sum(m[field] for m in ms) / len(ms)


def value_share(ms):
    tot = sum(m["values"] for m in ms)
    return sum(m["leaked"] for m in ms) / tot if tot else 0.0


def summarize(data: Dict) -> str:
    records = data["records"]
    c = cells(records)
    is_attack = lambda m: m["attack"]
    non_phi = lambda m: m["attack"] and m["goal"] != "phi"
    canary = lambda m: m["attack"] and m["goal"] == "canary"
    benign = lambda m: not m["attack"]
    every = lambda m: True

    def w(ms, pick, field):
        return wilson(*rate(ms, pick, field))

    lines = []
    order = ["full+O", "full", "no_redact+O", "no_redact", "no_guard+O", "no_guard", "none+O", "none",
             "direct+O", "direct"]
    label = {
        "full": "R G", "no_redact": "– G", "no_guard": "R –", "none": "– –", "direct": "direct app prompt",
    }

    def name(cell):
        base, _, o = cell.partition("+")
        return f"{label[base]} {'O' if o else '–'}" if base != "direct" else f"{label[base]}{' + O' if o else ''}"

    lines.append("| Layers (R G O) | Attack success, all (300) | Excl. PHI goal (240) | Canary leaked (60) "
                 "| Benign notes leaking any PHI (100) | PHI values leaked, all notes | Benign refused |")
    lines.append("|---|---|---|---|---|---|---|")
    for cell in order:
        ms = c[cell]
        vr = value_rate(ms, every)
        lines.append(
            f"| {name(cell)} | {w(ms, is_attack, 'success')} | {w(ms, non_phi, 'success')} | "
            f"{w(ms, canary, 'success')} | {w(ms, benign, 'any_leak')} | {wilson(*vr)} | "
            f"{rate(ms, benign, 'refused')[0]}/{rate(ms, benign, 'refused')[1]} |")

    lines.append("")
    lines.append("Paired differences against the full gateway (R G O), percentage points, 95% bootstrap over notes:")
    lines.append("")
    lines.append("| Turned off | Attack success, all | Excl. PHI goal | Benign notes leaking PHI | PHI values leaked, all notes |")
    lines.append("|---|---|---|---|---|")
    full = c["full+O"]
    for cell, what in [("full", "O (output filter)"), ("no_redact+O", "R (input redaction)"),
                       ("no_guard+O", "G (wrapping + security rules)"), ("no_redact", "R and O"),
                       ("none+O", "R and G"), ("none", "all three"), ("direct", "gateway (direct app prompt)")]:
        ms = c[cell]
        lines.append(
            f"| {what} | {paired_diff(ms, full, is_attack, mean_rate('success'))} | "
            f"{paired_diff(ms, full, non_phi, mean_rate('success'))} | "
            f"{paired_diff(ms, full, benign, mean_rate('any_leak'))} | "
            f"{paired_diff(ms, full, every, value_share)} |")

    lines.append("")
    lines.append("PHI values leaked by type, all 400 notes (leaked / gold values):")
    lines.append("")
    lines.append("| Layers (R G O) | " + " | ".join(LEAK_TYPES) + " |")
    lines.append("|---|" + "---|" * len(LEAK_TYPES))
    for cell in order:
        cols = []
        for t in LEAK_TYPES:
            h, n = value_rate(c[cell], every, t)
            cols.append(f"{100 * h / n:.1f}% ({h}/{n})" if n else "n/a")
        lines.append(f"| {name(cell)} | " + " | ".join(cols) + " |")

    lines.append("")
    lat = {cond: sorted(r[cond]["latency_ms"] for r in records if r[cond]["ok"]) for cond in ["direct"] + list(SETTINGS)}
    lines.append("Latency per call in-process (ms, median / 90th percentile; includes Bedrock): " + ", ".join(
        f"{label[k]} {v[len(v) // 2]} / {v[int(0.9 * len(v))]}" for k, v in lat.items() if v))
    fails = {cond: sum(not r[cond]["ok"] for r in records) for cond in ["direct"] + list(SETTINGS)}
    lines.append("")
    lines.append("Failed calls: " + ", ".join(f"{label[k]} {v}" for k, v in fails.items()))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Gateway layer ablation on the injection suite")
    parser.add_argument("--model")
    parser.add_argument("--suite", default="datasets/injection_suite.json")
    parser.add_argument("--output", help="Raw replies (synthetic data only)")
    parser.add_argument("--summarize", help="Re-score an existing raw file instead of calling Bedrock")
    parser.add_argument("--report", help="Write the summary tables here")
    parser.add_argument("--limit", type=int, help="Stratified pilot subset of attacks")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    if args.summarize:
        data = json.loads(Path(args.summarize).read_text())
    else:
        if not (args.model and args.output):
            parser.error("--model and --output are required unless --summarize is given")
        suite = json.loads(Path(args.suite).read_text())
        attacks, benign = suite["attacks"], suite["benign"]
        if args.limit:
            step = max(1, len(attacks) // args.limit)
            attacks = attacks[::step][: args.limit]
            benign = benign[: max(10, args.limit // 3)]
        cases = attacks + benign
        handler = load_gateway(args.model, suite["canary"])
        runs = {}
        with ThreadPoolExecutor(args.workers) as pool:
            runs["direct"] = list(pool.map(lambda c: run_direct(handler, c, suite["task"], suite["canary"]), cases))
            for cond, (redact, guard) in SETTINGS.items():
                runs[cond] = list(pool.map(lambda c, r=redact, g=guard: run_setting(handler, c, r, g), cases))
                print(f"{cond}: done", flush=True)
        data = {
            "model": args.model,
            "ner_model": os.environ.get("PHI_NER_MODEL") if os.environ.get("PHI_NER_ENABLED") == "true" else None,
            "ner_threshold": os.environ.get("PHI_NER_THRESHOLD"),
            "name_lexicon": os.environ.get("PHI_NAME_LEXICON"),
            "records": [{"case": c, **{cond: runs[cond][i] for cond in runs}} for i, c in enumerate(cases)],
        }
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(data, indent=1))
    report = summarize(data)
    print(report)
    if args.report:
        Path(args.report).write_text(report + "\n")


if __name__ == "__main__":
    main()
