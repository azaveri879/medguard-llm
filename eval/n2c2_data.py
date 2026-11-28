"""
Load the n2c2 2014 de-identification corpus (i2b2 2014 track 1) as labeled notes.

Each XML file holds the note in <TEXT><![CDATA[...]]></TEXT> and gold PHI tags with
character offsets in <TAGS>. The text is read raw rather than through an XML parser,
which would normalize line endings and shift the offsets.

Use only the test set for comparisons: obi/deid_roberta_i2b2 was trained on the
training set, so the original model has seen those notes.

Labels follow HIPAA Safe Harbor. Tags that are not Safe Harbor identifiers are SKIP:
they are neither required to be removed nor counted against a detector.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TEXT = re.compile(r"<TEXT><!\[CDATA\[(.*?)\]\]></TEXT>", re.S)
TAGS = re.compile(r"<TAGS>.*?</TAGS>", re.S)

# (tag, TYPE) -> benchmark label. A None TYPE matches any TYPE for that tag.
LABELS: Dict[Tuple[str, Optional[str]], str] = {
    ("NAME", "PATIENT"): "NAME",
    ("NAME", "DOCTOR"): "NAME",
    ("NAME", "USERNAME"): "ID",
    ("PROFESSION", None): "SKIP",
    ("LOCATION", "HOSPITAL"): "FACILITY",
    ("LOCATION", "ORGANIZATION"): "ORGANIZATION",
    ("LOCATION", "STREET"): "ADDRESS",
    ("LOCATION", "CITY"): "LOCATION",
    ("LOCATION", "ZIP"): "LOCATION",
    ("LOCATION", "LOCATION-OTHER"): "LOCATION",
    ("LOCATION", "STATE"): "SKIP",
    ("LOCATION", "COUNTRY"): "SKIP",
    ("DATE", None): "DATE",
    ("CONTACT", "PHONE"): "PHONE",
    ("CONTACT", "FAX"): "PHONE",
    ("CONTACT", "EMAIL"): "EMAIL",
    ("CONTACT", "URL"): "ID",
    ("CONTACT", "IPADDR"): "ID",
    ("ID", None): "ID",
}
ROLES = {"PATIENT": "patient", "DOCTOR": "care_team"}


def label_for(tag: str, phi_type: str, text: str) -> str:
    if tag == "AGE":
        digits = re.sub(r"\D", "", text)
        return "AGE_OVER_89" if digits and int(digits) > 89 else "SKIP"
    return LABELS.get((tag, phi_type), LABELS.get((tag, None), "SKIP"))


def parse_note(raw: str) -> Dict:
    """Return {text, spans, known_names, mismatched} for one n2c2 XML document."""
    text = TEXT.search(raw).group(1)
    tags = ET.fromstring(TAGS.search(raw).group(0))
    spans, mismatched = [], 0
    known_names: Dict[str, List[str]] = {"patient": [], "care_team": [], "other": []}
    for tag in tags:
        start, end = int(tag.get("start")), int(tag.get("end"))
        value = tag.get("text", "")
        if text[start:end] != value:
            mismatched += 1
            continue
        phi_type = tag.get("TYPE", "")
        span = {"start": start, "end": end, "label": label_for(tag.tag, phi_type, value)}
        if tag.tag == "NAME" and phi_type in ROLES:
            role = ROLES[phi_type]
            span["role"] = role
            if value not in known_names[role]:
                known_names[role].append(value)
        spans.append(span)
    return {"text": text, "spans": spans, "known_names": known_names, "mismatched": mismatched}


def load_n2c2(directory: str) -> List[Dict]:
    files = sorted(Path(directory).rglob("*.xml"))
    if not files:
        raise FileNotFoundError(f"No .xml files under {directory}")
    notes = []
    for path in files:
        # newline="" keeps \r\n as written; the offsets count those characters.
        with open(path, encoding="utf-8", newline="") as handle:
            notes.append(parse_note(handle.read()))
    return notes
