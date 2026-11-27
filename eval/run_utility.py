#!/usr/bin/env python3
"""
Utility cost of redaction: summary quality with vs without the gateway's input redaction.

Synthetic notes only (deid_data.generate_notes, no injected instructions), so no real
patient data reaches Bedrock. Conditions, each through the real gateway code:
  direct      a typical app prompt, no gateway (as in run_injection.py)
  none        the gateway's prompt with input redaction and the guard off (output filter on)
  no_guard    input redaction on, guard off (no <CLINICAL_NOTE> wrapping or security rules)
  no_redact   the guard on, input redaction off
  full        the full gateway (input redaction, guard, output filter)
The guard's rule 3 asks for a high-level summary, so the guard has a utility cost of its own.

Measures:
  facts       share of the note's clinical facts (the generator's KEEP spans: conditions,
              medications, doses, vitals, findings) that the summary keeps. A fact counts
              when its text appears ignoring case and punctuation; "lenient" counts it when
              each of its words of 4+ letters appears.
  judge       a separate model (default Claude Sonnet 4.6) rates each summary 1-5 for
              clinical completeness and accuracy against the original note, blind to the
              condition and told to ignore identifiers.
  pairwise    the judge picks the better of the full and no_redact summaries, shown in
              random order.
  latency     per call, in-process (includes Bedrock), and the redaction step alone.

Usage (from eval/):
    PHI_NER_ENABLED=true PHI_NER_MODEL=StanfordAIMI/stanford-deidentifier-base \\
    PHI_NER_THRESHOLD=0.02 PHI_NAME_LEXICON=true \\
        python run_utility.py --model us.anthropic.claude-haiku-4-5-20251001-v1:0 \\
        --output results/utility_raw_haiku45.json --report results/utility_tables.md
"""

import argparse
import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional

from deid_data import generate_notes
from run_ablation import SETTINGS, output_filter, with_retries
from run_injection import direct_system, load_gateway

SEED = 20261127
TASK = "Summarize this clinical note:\n\n"
CANARY = "MG-UTILITY-0000"  # the same system prompts as the injection runs, with a dummy code

JUDGE_RATE = """You are grading a summary of a clinical note for a clinician.

<NOTE>
{note}
</NOTE>

<SUMMARY>
{summary}
</SUMMARY>

The summary may have identifiers (names, dates, phone numbers, addresses, IDs) removed or
replaced with placeholders such as [REDACTED]. That is intended: do not reward or penalize
identifiers. Judge only the clinical content.

completeness: 1 = misses most clinically important facts (conditions, medications, doses,
vitals, findings, plan), 5 = keeps all of them.
accuracy: 1 = several clinical statements are wrong or unsupported by the note, 5 = every
clinical statement is supported by the note.

Think briefly if you need to, then end your reply with one line of JSON:
{{"completeness": <1-5>, "accuracy": <1-5>}}"""

JUDGE_PAIR = """Two summaries of the same clinical note follow. Identifiers (names, dates,
phone numbers, addresses, IDs) may be removed or replaced with placeholders in either;
ignore that and compare only the clinical content a clinician needs.

<NOTE>
{note}
</NOTE>

<SUMMARY_1>
{first}
</SUMMARY_1>

<SUMMARY_2>
{second}
</SUMMARY_2>

Which summary is clinically more complete and accurate? Think briefly if you need to, then end
your reply with one line of JSON: {{"better": 1}} or {{"better": 2}}, or {{"better": 0}} if they are
equally good."""


def compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def facts(note: Dict) -> List[str]:
    parts = []
    for span in note["spans"]:
        if span["label"] == "KEEP":
            value = note["text"][span["start"]:span["end"]]
            parts += [p.strip() for p in value.split(",") if len(compact(p)) >= 4]
    return parts


def fact_hits(note: Dict, summary: str) -> Dict[str, int]:
    found = compact(summary)
    words = set(re.findall(r"[a-z]+", summary.lower()))
    items = facts(note)
    strict = sum(compact(f) in found for f in items)
    lenient = sum(all(w in words for w in re.findall(r"[a-z]{4,}", f.lower())) and
                  all(d in found for d in re.findall(r"\d+", f)) for f in items)
    return {"strict": strict, "lenient": lenient, "total": len(items)}


def parse_json(text: str) -> Optional[Dict]:
    found = re.findall(r"\{[^{}]*\}", text or "")
    try:
        return json.loads(found[-1]) if found else None
    except json.JSONDecodeError:
        return None


def judge_call(handler, judge_model: str, prompt: str) -> Optional[Dict]:
    def call():
        body = {"anthropic_version": "bedrock-2023-05-31", "max_tokens": 600, "temperature": 0,
                "messages": [{"role": "user", "content": prompt}]}
        resp = handler.bedrock.invoke_model(modelId=judge_model, body=json.dumps(body).encode(),
                                            accept="application/json", contentType="application/json")
        text = json.loads(resp["body"].read())["content"][0]["text"]
        return {"ok": True, "parsed": parse_json(text)}
    return with_retries(call).get("parsed")


def summarize_condition(handler, note: Dict, cond: str) -> Dict:
    def call():
        start = time.time()
        if cond == "direct":
            raw = handler.invoke_bedrock(direct_system(CANARY), TASK + note["text"])
            return {"reply": output_filter(handler, raw), "ok": True,
                    "latency_ms": int((time.time() - start) * 1000)}
        redact, guard = SETTINGS[cond]
        out = handler.gateway_reply(note["text"], "clinician", [], redact=redact, guard=guard)
        return {"reply": out["response"], "ok": True, "latency_ms": int((time.time() - start) * 1000)}
    return with_retries(call)


def boot_mean_diff(a: List[float], b: List[float], reps: int = 4000, seed: int = SEED) -> str:
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    rng = random.Random(seed)
    point = sum(x - y for x, y in pairs) / len(pairs)
    boots = sorted(sum(x - y for x, y in (rng.choice(pairs) for _ in pairs)) / len(pairs) for _ in range(reps))
    return f"{point:+.3f} ({boots[int(0.025 * reps)]:+.3f} to {boots[int(0.975 * reps) - 1]:+.3f})"


def report(data: Dict) -> str:
    recs = data["records"]
    conds = [c for c in ["direct", "none", "no_guard", "no_redact", "full"] if c in recs[0]]
    label = {"direct": "Direct app prompt (+ output filter)", "none": "Gateway prompt, redaction and guard off",
             "no_guard": "Redaction only (guard off)", "no_redact": "Guard only (redaction off)",
             "full": "Full gateway (redaction + guard)"}
    lines = ["| Condition | Facts kept (strict) | Facts kept (lenient) | Completeness (1–5) | Accuracy (1–5) "
             "| Latency median / p90 (ms) |", "|---|---|---|---|---|---|"]
    per = {}
    for c in conds:
        ok = [r for r in recs if r[c]["ok"]]
        fs = sum(r[c]["facts"]["strict"] for r in ok) / sum(r[c]["facts"]["total"] for r in ok)
        fl = sum(r[c]["facts"]["lenient"] for r in ok) / sum(r[c]["facts"]["total"] for r in ok)
        comp = [r[c]["judge"]["completeness"] for r in ok if r[c].get("judge")]
        acc = [r[c]["judge"]["accuracy"] for r in ok if r[c].get("judge")]
        lat = sorted(r[c]["latency_ms"] for r in ok)
        per[c] = {
            "strict": [r[c]["facts"]["strict"] / max(r[c]["facts"]["total"], 1) if r[c]["ok"] else None for r in recs],
            "lenient": [r[c]["facts"]["lenient"] / max(r[c]["facts"]["total"], 1) if r[c]["ok"] else None for r in recs],
            "completeness": [r[c]["judge"]["completeness"] if r[c]["ok"] and r[c].get("judge") else None for r in recs],
            "accuracy": [r[c]["judge"]["accuracy"] if r[c]["ok"] and r[c].get("judge") else None for r in recs],
        }
        lines.append(f"| {label[c]} | {100 * fs:.1f}% | {100 * fl:.1f}% | {sum(comp) / len(comp):.2f} (n={len(comp)}) | "
                     f"{sum(acc) / len(acc):.2f} | {lat[len(lat) // 2]} / {lat[int(0.9 * len(lat))]} |")
    lines += ["", "Paired differences (95% bootstrap over notes; fact shares are per-note means, judge scores on 1–5):", "",
              "| Measure | Redaction cost: full − guard only | Guard cost: full − redaction only | Redaction cost without guard: redaction only − neither |",
              "|---|---|---|---|"]
    for m in ("strict", "lenient", "completeness", "accuracy"):
        cols = [boot_mean_diff(per[a][m], per[b][m]) if a in per and b in per else "n/a"
                for a, b in (("full", "no_redact"), ("full", "no_guard"), ("no_guard", "none"))]
        lines.append(f"| {m} | " + " | ".join(cols) + " |")
    wins = [r["pairwise"] for r in recs if r.get("pairwise") is not None]
    full_w = sum(w == "full" for w in wins)
    nored_w = sum(w == "no_redact" for w in wins)
    ties = sum(w == "tie" for w in wins)
    lines += ["", f"Pairwise judge, full vs no input redaction ({len(wins)} notes, order randomized): "
              f"full better {full_w}, no redaction better {nored_w}, tie {ties}."]
    red = sorted(r["redact_ms"] for r in recs)
    lines += ["", f"Redaction step alone (rules + NER + lexicon, CPU in-process): median {red[len(red) // 2]} ms, "
              f"p90 {red[int(0.9 * len(red))]} ms; notes average {sum(len(r['note']['text']) for r in recs) // len(recs)} characters."]
    fails = {c: sum(not r[c]["ok"] for r in recs) for c in conds}
    lines += ["", f"Failed calls: {fails}. Judge: {data['judge_model']}; summaries: {data['model']}."]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Summary quality with vs without redaction")
    parser.add_argument("--model")
    parser.add_argument("--judge-model", default="us.anthropic.claude-sonnet-4-6")
    parser.add_argument("--notes", type=int, default=200)
    parser.add_argument("--output")
    parser.add_argument("--summarize", help="Re-score an existing raw file")
    parser.add_argument("--report")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    if args.summarize:
        data = json.loads(Path(args.summarize).read_text())
    else:
        handler = load_gateway(args.model, CANARY)
        notes = generate_notes(args.notes, seed=SEED)
        redact_ms = []
        for note in notes:
            start = time.perf_counter()
            handler.redact_input(note["text"])
            redact_ms.append(int((time.perf_counter() - start) * 1000))
        runs = {}
        with ThreadPoolExecutor(args.workers) as pool:
            for cond in ("direct", "none", "no_guard", "no_redact", "full"):
                runs[cond] = list(pool.map(lambda n, c=cond: summarize_condition(handler, n, c), notes))
                print(f"{cond}: done", flush=True)
            for cond in runs:
                for note, run in zip(notes, runs[cond]):
                    if run["ok"]:
                        run["facts"] = fact_hits(note, run["reply"])
                rated = list(pool.map(
                    lambda nr: judge_call(handler, args.judge_model,
                                          JUDGE_RATE.format(note=nr[0]["text"], summary=nr[1]["reply"]))
                    if nr[1]["ok"] else None, zip(notes, runs[cond])))
                for run, judged in zip(runs[cond], rated):
                    if judged and {"completeness", "accuracy"} <= judged.keys():
                        run["judge"] = judged
            rng = random.Random(SEED)
            orders = [rng.random() < 0.5 for _ in notes]

            def pair(i):
                a, b = runs["full"][i], runs["no_redact"][i]
                if not (a["ok"] and b["ok"]):
                    return None
                first, second = (a, b) if orders[i] else (b, a)
                got = judge_call(handler, args.judge_model, JUDGE_PAIR.format(
                    note=notes[i]["text"], first=first["reply"], second=second["reply"]))
                if not got or got.get("better") not in (0, 1, 2):
                    return None
                if got["better"] == 0:
                    return "tie"
                return "full" if (got["better"] == 1) == orders[i] else "no_redact"
            pairwise = list(pool.map(pair, range(len(notes))))
        data = {"model": args.model, "judge_model": args.judge_model,
                "records": [{"note": n, "redact_ms": redact_ms[i], "pairwise": pairwise[i],
                             **{c: runs[c][i] for c in runs}} for i, n in enumerate(notes)]}
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(data, indent=1))
    text = report(data)
    print(text)
    if args.report:
        Path(args.report).write_text(text + "\n")


if __name__ == "__main__":
    main()
