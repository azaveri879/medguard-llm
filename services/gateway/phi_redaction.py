"""
Rule-based PHI redaction for clinical text.

Rules run from most structured to least, so a street address is consumed before
the name rules can misread part of it. Names are only matched with supporting
context such as a label, honorific or credential, because a bare "Word, Word"
pattern also matches medication lists and exam findings. Names in plain prose
with no such context are not caught; that needs a named-entity model.
"""

import re

NAME_TOKEN = r"[A-Z][A-Za-z'’-]+"
FULL_NAME = rf"{NAME_TOKEN}(?:[ \t]+[A-Z]\.?)?(?:[ \t]+{NAME_TOKEN}){{1,2}}"
COMMA_NAME = rf"{NAME_TOKEN},[ \t]+{NAME_TOKEN}"
NAME_LABEL = (
    r"\b(?i:patient name|pt name|patient|pt|name|attending|resident"
    r"|emergency contact|next of kin|guardian|pcp|provider)[ \t]*:[ \t]*"
)

STREET_TYPE = (
    r"(?:St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Blvd|Boulevard|Ln|Lane|Ct|Court"
    r"|Way|Pl|Place|Pkwy|Parkway|Ter|Terrace|Cir|Circle|Hwy|Highway)"
)
ZIP_CODE = r"\d{5}(?:-\d{4})?"
ADDRESS = (
    rf"\b\d{{1,6}}[ \t]+(?:[A-Z][A-Za-z'-]*[ \t]+){{1,4}}?{STREET_TYPE}\b\.?"
    r"(?:,?[ \t]*(?:Apt|Apartment|Unit|Suite|Ste|#)\.?[ \t]*[\w-]+)?"
    rf"(?:,[ \t]*[A-Z][A-Za-z .'-]*?,[ \t]*[A-Z]{{2}}(?:[ \t]+{ZIP_CODE})?)?"
)

MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?"
    r"|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?"
)
DOSE_UNIT = r"(?:mg|mcg|g|ml|mL|units?)"

# Applied in this order. Each entry is (pattern, PHI type).
STRUCTURED_RULES = [
    (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "EMAIL"),
    (r"\bMRN[:\s]*\d{6,10}\b", "MRN"),
    (r"\bMedical Record Number[:\s]*\d{6,10}\b", "MRN"),
    (r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "PHONE"),
    (r"\b\d{4}-\d{2}-\d{2}\b", "DATE"),
    (rf"\b\d{{1,2}}[/\-]\d{{1,2}}[/\-]\d{{2,4}}\b(?!\s*{DOSE_UNIT}\b)", "DATE"),
    (rf"\b{MONTH}[ \t]+\d{{1,2}}(?:st|nd|rd|th)?,?[ \t]+\d{{4}}\b", "DATE"),
    (r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b", "SSN"),
    (ADDRESS, "ADDRESS"),
    (r"\b(?:9\d|1[0-4]\d)(?=[-\s]?(?:years?|yrs?|y/?o)\b)", "AGE"),
    (r"(?i:(?:(?<=\bage )|(?<=\bage:)|(?<=\bage: )|(?<=\baged )|(?<=\baged:)|(?<=\baged: ))(?:9\d|1[0-4]\d)\b)", "AGE"),
]

NAME_RULES = [
    rf"{NAME_LABEL}(?P<name>{COMMA_NAME}|{FULL_NAME})",
    rf"\b(?:Patient|PATIENT)[ \t]+(?P<name>{FULL_NAME})",
    rf"\b(?:Dr|Mr|Mrs|Ms|Prof)\.?[ \t]+(?P<name>{NAME_TOKEN}(?:[ \t]+{NAME_TOKEN})?)",
    rf"\b(?P<name>{FULL_NAME}),?[ \t]+(?:MD|DO|RN|NP|PA-C|PA|DDS|PhD)\b",
]


def phi_redact(text: str):
    """Return (redacted text, count of redactions by PHI type)."""
    out = text or ""
    redactions = {}

    def record(phi_type: str, count: int):
        if count:
            redactions[phi_type] = redactions.get(phi_type, 0) + count

    for pattern, phi_type in STRUCTURED_RULES:
        out, count = re.subn(pattern, f"[PHI_{phi_type}]", out)
        record(phi_type, count)

    found_names = []

    def replace_name(match):
        name = match.group("name")
        found_names.append(name)
        start = match.start("name") - match.start()
        whole = match.group(0)
        return whole[:start] + "[PHI_NAME]" + whole[start + len(name):]

    for pattern in NAME_RULES:
        out, count = re.subn(pattern, replace_name, out)
        record("NAME", count)

    # Later mentions of a known name, such as "Smith denies fever".
    tokens = {
        token
        for name in found_names
        for token in re.findall(r"[A-Za-z'’-]{3,}", name)
    }
    for token in sorted(tokens, key=len, reverse=True):
        pattern = rf"(?<![\w'’-]){re.escape(token)}(?![\w'’-])"
        out, count = re.subn(pattern, "[PHI_NAME]", out)
        record("NAME", count)

    return out, redactions
