#!/usr/bin/env python3
"""
Load PhysioNet's "Deidentified Medical Text" gold-standard corpus as benchmark notes.

The corpus (credentialed; https://physionet.org/content/deidentifiedmedicaltext/1.0/)
has two aligned files of 2,434 MIMIC-II nursing notes:
  id.text  PHI replaced by realistic surrogates chosen by the corpus authors
  id.res   the same notes with each PHI instance replaced by a MIMIC-style [** tag **]

Lining the two up gives exact spans for every surrogate, labeled with the same tag
classifier as the MIMIC-III benchmark. The surrogates were not made by
mimic_surrogates.py, so a model trained on that generator's output cannot have
learned their formats. Notes stay in memory and must never be printed or committed.
"""

import hashlib
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from mimic_surrogates import LABELS, TAG, classify, name_role

RECORD = re.compile(r"START_OF_RECORD=(\d+)\|\|\|\|(\d+)\|\|\|\|\n?(.*?)\|\|\|\|END_OF_RECORD", re.DOTALL)


def read_records(path: Path) -> Dict[Tuple[str, str], str]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return {(m.group(1), m.group(2)): m.group(3) for m in RECORD.finditer(text)}


def align(surrogate: str, tagged: str) -> Optional[List[Dict]]:
    """Return a span per tag in `tagged`, located in `surrogate`, or None if they don't line up."""
    spans: List[Dict] = []
    pieces = TAG.split(tagged)  # literal, tag, literal, tag, ..., literal
    literals, tags = pieces[0::2], pieces[1::2]
    if not surrogate.startswith(literals[0]):
        return None
    cursor = len(literals[0])
    for index, inner in enumerate(tags):
        following = literals[index + 1]
        if index + 1 == len(tags):
            end = len(surrogate) - len(following)
            if not surrogate.endswith(following) or end < cursor:
                return None
        else:
            # The next literal must appear after the surrogate value. Literals between
            # adjacent tags can be a single space, so take the nearest match.
            end = surrogate.find(following, cursor) if following else cursor
            if end < 0:
                return None
        value = surrogate[cursor:end]
        if not value.strip():
            return None
        start = cursor + (len(value) - len(value.lstrip()))
        stop = end - (len(value) - len(value.rstrip()))
        span = {"start": start, "end": stop, "label": LABELS[classify(inner)], "kind": classify(inner)}
        if span["label"] == "NAME":
            span["role"] = name_role(inner)
        spans.append(span)
        cursor = end + len(following)
    return spans


def physionet_split(patient: str) -> str:
    """Half the patients tune settings, the other half report results; a patient's notes stay together."""
    return "tune" if int(hashlib.sha256(f"physionet:{patient}".encode()).hexdigest(), 16) % 2 == 0 else "test"


def load_physionet_deid(directory: str, split: Optional[str] = None) -> List[Dict]:
    """Return [{text, spans, mismatched, patient}] for records whose two versions line up.

    split "tune" or "test" keeps one half of the patients (see physionet_split).
    """
    surrogates = read_records(Path(directory, "id.text"))
    tagged = read_records(Path(directory, "id.res"))
    notes = []
    for key in sorted(surrogates, key=lambda k: (int(k[0]), int(k[1]))):
        if key not in tagged or (split and physionet_split(key[0]) != split):
            continue
        spans = align(surrogates[key], tagged[key])
        if spans is None:
            notes.append({"text": surrogates[key], "spans": [], "mismatched": 1, "patient": key[0]})
        else:
            text = surrogates[key]
            known = {"patient": [], "care_team": [], "other": []}
            for span in spans:
                if "role" in span:
                    value = text[span["start"]:span["end"]]
                    if value not in known[span["role"]]:
                        known[span["role"]].append(value)
            notes.append({"text": text, "spans": spans, "mismatched": 0, "patient": key[0], "known_names": known})
    return notes


def write_split(directory: str, split: str, out_dir: str) -> int:
    """Copy one half's records of id.text and id.res, in the original format, to out_dir."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    kept = 0
    for name in ("id.text", "id.res"):
        text = Path(directory, name).read_text(encoding="utf-8", errors="replace")
        records = [m.group(0) for m in RECORD.finditer(text) if physionet_split(m.group(1)) == split]
        Path(out_dir, name).write_text("\n".join(records) + "\n", encoding="utf-8")
        kept = len(records)
    return kept
