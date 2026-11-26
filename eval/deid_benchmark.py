#!/usr/bin/env python3
"""
Compare PHI detectors on notes with exact spans. Runs locally; prints aggregates only.

A PHI span counts as caught only when all its letters and digits are covered.
KEEP spans are clinical terms that must not be touched.

Usage (from eval/, with requirements-deid.txt installed):
    python deid_benchmark.py --detectors regex,presidio,roberta,stanford,regex+roberta
    python deid_benchmark.py --data labeled.jsonl   # real corpus, one note per line
"""

import argparse
import hashlib
import json
import random
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "gateway"))

from deid_data import generate_notes
from phi_redaction import phi_redact

Span = Tuple[int, int]
Detector = Callable[[str], List[Span]]
ROBERTA_MODEL = "obi/deid_roberta_i2b2"
# Competitor baseline: a BERT de-identifier trained on Stanford radiology and other notes.
STANFORD_MODEL = "StanfordAIMI/stanford-deidentifier-base"
PRESIDIO_THRESHOLD = 0.35


def spans_from_redacted(original: str, redacted: str) -> List[Span]:
    """Recover removed character ranges by aligning the text around each placeholder."""
    parts = re.split(r"\[PHI_[A-Z]+\]", redacted)
    spans = []
    cursor = len(parts[0])
    for index, part in enumerate(parts[1:], start=1):
        is_last = index == len(parts) - 1
        end = len(original) if is_last and not part else original.find(part, cursor)
        spans.append((cursor, end))
        cursor = end + len(part)
    return spans


def regex_detector() -> Detector:
    return lambda text: spans_from_redacted(text, phi_redact(text)[0])


def presidio_detector() -> Detector:
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_md"}],
    }
    engine = NlpEngineProvider(nlp_configuration=configuration).create_engine()
    analyzer = AnalyzerEngine(nlp_engine=engine, supported_languages=["en"])

    def detect(text: str) -> List[Span]:
        results = analyzer.analyze(text, language="en", score_threshold=PRESIDIO_THRESHOLD)
        return [(result.start, result.end) for result in results]

    return detect


def ignored_labels(id2label: Dict) -> set:
    """Label ids a token classifier's output should not redact: outside tags and ages.

    Ages under 90 are not PHI under Safe Harbor and are clinically useful.
    """
    return {
        int(index) for index, label in id2label.items()
        if label == "O" or label.endswith("AGE")
    }


def token_classifier_detector(model_name: str) -> Detector:
    """Any Hugging Face token classifier, applied in overlapping 512-token windows."""
    import torch
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForTokenClassification.from_pretrained(model_name, use_safetensors=True)
    model.eval()
    ignored = ignored_labels(model.config.id2label)

    def detect(text: str) -> List[Span]:
        encoded = tokenizer(
            text, truncation=True, max_length=512, stride=128, padding=True,
            return_overflowing_tokens=True, return_offsets_mapping=True, return_tensors="pt",
        )
        offsets = encoded.pop("offset_mapping").tolist()
        encoded.pop("overflow_to_sample_mapping")
        with torch.no_grad():
            predictions = model(**encoded).logits.argmax(dim=-1).tolist()
        return [
            (start, end)
            for window, labels in zip(offsets, predictions)
            for (start, end), label in zip(window, labels)
            if end > start and label not in ignored
        ]

    return detect


def roberta_detector() -> Detector:
    return token_classifier_detector(ROBERTA_MODEL)


def pipeline_detector() -> Detector:
    """The gateway's production path: rules, then the model on what they left."""
    from ner_redaction import phi_redact_with_ner

    return lambda text: spans_from_redacted(text, phi_redact_with_ner(text)[0])


def known_name_detector(notes: List[Dict], roles: Tuple[str, ...]) -> Detector:
    """The pipeline given only the names an EHR could supply for these roles."""
    from known_names import redact_with_known
    from ner_redaction import phi_redact_with_ner

    names = {
        note["text"]: [name for role in roles for name in note["known_names"][role]]
        for note in notes
    }

    def detect(text: str) -> List[Span]:
        return spans_from_redacted(text, redact_with_known(text, names[text], phi_redact_with_ner)[0])

    return detect


def _covered(text: str, start: int, end: int, marks: List[bool]) -> Tuple[int, int]:
    """Return (covered, total) counts of letters and digits in a range."""
    total = covered = 0
    for index in range(start, end):
        if text[index].isalnum():
            total += 1
            covered += marks[index]
    return covered, total


def note_key(text: str) -> str:
    """A short hash that identifies a note across runs without storing its text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def bootstrap_ci(per_note: List[Dict], label: Optional[str] = None, rounds: int = 1000,
                 seed: int = 0) -> Tuple[float, float]:
    """95% interval for the share of PHI caught, resampling whole notes."""
    if label is None:
        pairs = [(sum(n["caught"].values()), sum(n["total"].values())) for n in per_note]
    else:
        pairs = [(n["caught"].get(label, 0), n["total"].get(label, 0)) for n in per_note]
    rng = random.Random(seed)
    rates = []
    for _ in range(rounds):
        sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        total = sum(t for _, t in sample)
        if total:
            rates.append(sum(c for c, _ in sample) / total)
    rates.sort()
    if not rates:
        return float("nan"), float("nan")
    return rates[int(0.025 * (len(rates) - 1))], rates[int(0.975 * (len(rates) - 1))]


def char_class(text: str, index: int) -> str:
    """Describe one character without revealing letters or digits."""
    if index < 0 or index >= len(text):
        return "edge"
    char = text[index]
    if char.isalpha():
        return "letter"
    if char.isdigit():
        return "digit"
    if char == "\n":
        return "newline"
    if char.isspace():
        return "space"
    return repr(char)


def miss_context(text: str, span: Dict, covered: int) -> Tuple[str, str, str, str]:
    """(label, how much was redacted, character class before, after) for a missed span."""
    return (span["label"], "partly" if covered else "none",
            char_class(text, span["start"] - 1), char_class(text, span["end"]))


def score_notes(notes: List[Dict], detector: Detector, miss_labels: Tuple[str, ...] = ()) -> Dict:
    caught, total = defaultdict(int), defaultdict(int)
    misses: Counter = Counter()
    keep_intact = keep_total = other_words = other_hit = 0
    per_note = []
    started = time.perf_counter()
    all_marks = []
    for note in notes:
        marks = [False] * len(note["text"])
        for start, end in detector(note["text"]):
            for index in range(max(start, 0), min(end, len(marks))):
                marks[index] = True
        all_marks.append(marks)
    seconds = time.perf_counter() - started

    for note, marks in zip(notes, all_marks):
        text = note["text"]
        phi_chars = [False] * len(text)
        note_caught, note_total = defaultdict(int), defaultdict(int)
        for span in note["spans"]:
            covered, size = _covered(text, span["start"], span["end"], marks)
            if span["label"] == "KEEP":
                keep_total += 1
                keep_intact += covered == 0
                continue
            if span["label"] != "SKIP" and size:
                total[span["label"]] += 1
                caught[span["label"]] += covered == size
                note_total[span["label"]] += 1
                note_caught[span["label"]] += covered == size
                if covered < size and span["label"] in miss_labels:
                    misses[miss_context(text, span, covered)] += 1
            for index in range(span["start"], span["end"]):
                phi_chars[index] = True
        for match in re.finditer(r"\w+", text):
            if not any(phi_chars[match.start():match.end()]):
                other_words += 1
                other_hit += any(marks[match.start():match.end()])
        per_note.append({"key": note_key(text), "caught": dict(note_caught), "total": dict(note_total)})

    return {
        "per_note": per_note,
        "misses": misses,
        "caught": dict(caught),
        "total": dict(total),
        "keep_intact": keep_intact,
        "keep_total": keep_total,
        "other_words": other_words,
        "other_words_redacted": other_hit,
        "ms_per_note": seconds / len(notes) * 1000,
    }


def markdown_table(results: Dict[str, Dict]) -> str:
    types = sorted({phi_type for result in results.values() for phi_type in result["total"]})
    header = ["Detector", "PHI found"] + types + [
        "Clinical terms intact", "Other words removed", "ms/note (CPU)",
    ]
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for name, result in results.items():
        caught, total = result["caught"], result["total"]
        cells = [name, f"{sum(caught.values()) / sum(total.values()) * 100:.1f}%"]
        cells += [f"{caught.get(t, 0) / total[t] * 100:.1f}%" for t in types]
        cells += [
            f"{result['keep_intact'] / max(result['keep_total'], 1) * 100:.1f}%",
            f"{result['other_words_redacted'] / result['other_words'] * 100:.1f}%",
            f"{result['ms_per_note']:.0f}",
        ]
        lines.append("| " + " | ".join(cells) + " |")
    any_result = next(iter(results.values()))
    counts = ["Spans scored", str(sum(any_result["total"].values()))]
    counts += [str(any_result["total"][t]) for t in types]
    counts += [str(any_result["keep_total"]), str(any_result["other_words"]), ""]
    lines.append("| " + " | ".join(counts) + " |")

    lines += ["", "95% intervals, resampling notes:", "",
              "| Detector | PHI found | Names |", "|---|---|---|"]
    for name, result in results.items():
        cells = [name]
        for label in (None, "NAME"):
            low, high = bootstrap_ci(result["per_note"], label)
            cells.append(f"{low * 100:.1f}–{high * 100:.1f}%" if low == low else "n/a")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Compare PHI detectors")
    parser.add_argument("--detectors", default="regex,presidio,roberta,regex+roberta")
    parser.add_argument("--data", help="JSONL of {text, spans}; defaults to synthetic notes")
    parser.add_argument("--mimic", action="store_true", help="Read a MIMIC-III NOTEEVENTS CSV from stdin")
    parser.add_argument("--per-category", type=int, default=200, help="MIMIC notes per category")
    parser.add_argument("--split", choices=["train", "tune", "test"], help="Use one MIMIC patient split")
    parser.add_argument("--faker-names", action="store_true", help="Use the held-out Faker test names")
    parser.add_argument("--surrogate-style", choices=["default", "unseen"], default="default",
                        help="unseen: MIMIC fake values in formats the training generator never produces")
    parser.add_argument("--notes", type=int, default=300, help="Synthetic note count")
    parser.add_argument("--n2c2", help="Directory of n2c2 2014 XML files (use the test set)")
    parser.add_argument("--output", help="Write the Markdown table to this path")
    parser.add_argument("--miss-context", default="",
                        help="Comma-separated labels; tally missed spans by the character class around them (no text)")
    parser.add_argument("--per-note-output", help="Write per-note counts (no text) as JSON for deid_compare.py")
    args = parser.parse_args()

    if args.n2c2:
        from n2c2_data import load_n2c2

        notes = load_n2c2(args.n2c2)
        mismatched = sum(note["mismatched"] for note in notes)
        print(f"n2c2 tags skipped because offsets did not match the text: {mismatched}", flush=True)
    elif args.mimic:
        from mimic_surrogates import build_name_pools, sample_notes

        pools = build_name_pools()["test"] if args.faker_names else None
        notes = sample_notes(sys.stdin, args.per_category, split=args.split, name_pools=pools,
                             style=args.surrogate_style)
    elif args.data:
        lines = Path(args.data).read_text().splitlines()
        notes = [json.loads(line) for line in lines]
    else:
        notes = generate_notes(args.notes)

    builders = {
        "regex": regex_detector,
        "presidio": presidio_detector,
        "roberta": roberta_detector,
        "stanford": lambda: token_classifier_detector(STANFORD_MODEL),
        "pipeline": pipeline_detector,
        "known-patient": lambda: known_name_detector(notes, ("patient",)),
        "known-patient-care": lambda: known_name_detector(notes, ("patient", "care_team")),
    }
    roles = Counter(s["role"] for n in notes for s in n["spans"] if "role" in s)
    if roles:
        print("Name spans by role:", dict(roles), flush=True)
    cache: Dict[str, Detector] = {}

    def built(part: str) -> Detector:
        if part not in cache:
            cache[part] = builders[part]()
        return cache[part]

    results = {}
    for name in args.detectors.split(","):
        parts = [built(part) for part in name.split("+")]
        detector = lambda text, parts=parts: [span for part in parts for span in part(text)]
        miss_labels = tuple(label for label in args.miss_context.split(",") if label)
        results[name] = score_notes(notes, detector, miss_labels)
        print(f"finished {name}", flush=True)
        if miss_labels:
            print(f"Missed spans for {name}, by label, how much was redacted, character before, character after:")
            for context, count in results[name]["misses"].most_common():
                print(f"  {count:4d}  " + " | ".join(context))

    table = markdown_table(results)
    print(f"\n{len(notes)} notes\n{table}")
    if args.output:
        Path(args.output).write_text(table + "\n")
    if args.per_note_output:
        per_note = {name: result["per_note"] for name, result in results.items()}
        Path(args.per_note_output).write_text(json.dumps(per_note))


if __name__ == "__main__":
    main()
