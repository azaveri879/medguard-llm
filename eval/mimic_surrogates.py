#!/usr/bin/env python3
"""
Turn MIMIC-III notes into a labeled de-identification benchmark.

MIMIC-III replaces PHI with typed tags such as [**Known lastname 123**]. Each tag
is swapped for a fake value of the same type, which gives real clinical writing
with exact span labels. Notes are held in memory only and must never be written
to this repository or printed; MIMIC is credentialed data.

Year-only dates and states are allowed under HIPAA Safe Harbor, and initials are
too short to score reliably, so those spans are marked SKIP and left unscored.
"""

import csv
import hashlib
import random
import re
import sys
from typing import Dict, Iterable, List, Optional

from deid_data import CITIES, EPONYMS, FIRST_NAMES, LAST_NAMES, MONTHS, STREETS, STREET_TYPES

TAG = re.compile(r"\[\*\*(.*?)\*\*\]", re.DOTALL)
DOSE = re.compile(r"\b\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)*\s*(?:mg|mcg|mL|ml|units?)\b")
EPONYM_NAMES = sorted({term.split()[0] for term in EPONYMS}, key=len, reverse=True)
EPONYM = re.compile(rf"\b(?:{'|'.join(map(re.escape, EPONYM_NAMES))})\b")

LABELS = {
    "full_date": "DATE", "month_day": "DATE", "month_year": "DATE", "date_range": "DATE",
    "month_only": "MONTH", "first": "NAME", "last": "NAME", "id": "ID", "phone": "PHONE",
    "email": "EMAIL", "street": "ADDRESS", "apartment": "ADDRESS", "city": "LOCATION",
    "facility": "FACILITY", "age": "AGE_OVER_89", "year": "SKIP", "skip": "SKIP",
}

# First matching prefix wins, so more specific prefixes come first.
PREFIX_KINDS = [
    ("clip number", "id"), ("numeric identifier", "id"), ("md number", "id"),
    ("medical record number", "id"), ("serial number", "id"), ("unit number", "id"),
    ("social security", "id"), ("telephone", "phone"), ("pager", "phone"),
    ("e-mail", "email"), ("street address", "street"), ("apartment address", "apartment"),
    ("age over", "age"), ("month/day/year", "full_date"), ("month/day", "month_day"),
    ("month/year", "month_year"), ("month day", "month_day"), ("month (only)", "month_only"),
    ("year", "year"), ("date range", "date_range"), ("holiday", "skip"),
    ("state", "skip"), ("country", "skip"), ("hospital", "facility"), ("wardname", "facility"),
    ("company", "facility"), ("university", "facility"), ("location", "city"),
    ("initial", "skip"), ("name initial", "skip"), ("name prefix", "skip"), ("name suffix", "skip"),
    ("known firstname", "first"), ("first name", "first"), ("doctor first name", "first"),
    ("female first name", "first"), ("male first name", "first"),
    ("known lastname", "last"), ("last name", "last"), ("doctor last name", "last"),
    ("name", "last"),
]
FACILITIES = [
    "Mercy General Hospital", "Lakeside Medical Center", "Riverside Clinic",
    "Northgate Community Hospital", "Hillcrest Rehabilitation", "Summit Health Partners",
]


def classify(inner: str) -> str:
    """Return the kind of PHI a MIMIC tag stands for."""
    tag = inner.strip().lower()
    if not tag:
        return "skip"
    if re.fullmatch(r"\d+", tag):
        return "year"
    if re.fullmatch(r"\d+-\d+-\d+", tag):
        return "full_date"
    if re.fullmatch(r"\d+[-/]+\d+[-/]*", tag):
        return "month_day"
    for prefix, kind in PREFIX_KINDS:
        if tag.startswith(prefix):
            return kind
    return "skip"


def name_role(inner: str) -> str:
    """Guess who a name tag refers to, standing in for what an EHR could supply."""
    tag = inner.strip().lower()
    if tag.startswith("known ") or "(ptitle)" in tag:
        return "patient"
    if tag.startswith("doctor ") or any(mark in tag for mark in ("(stitle)", "(md)", "(titles)")):
        return "care_team"
    return "other"


def patient_split(subject_id: str) -> str:
    """Assign every note from a patient to the same split: 80% train, 10% tune, 10% test."""
    bucket = int(hashlib.sha256(subject_id.strip().encode()).hexdigest(), 16) % 10
    return "test" if bucket == 9 else "tune" if bucket == 8 else "train"


def build_name_pools() -> Dict[str, Dict[str, List[str]]]:
    """Return separate train and test name lists, so a model can't pass by memorizing names."""
    from faker import Faker

    locales = ["en_US", "en_GB", "en_IN", "es_ES", "es_MX", "de_DE", "fr_FR", "it_IT", "pl_PL"]
    firsts, lasts = set(), set()
    for locale in locales:
        provider = Faker(locale)
        firsts.update(provider.provider("faker.providers.person").first_names)
        lasts.update(provider.provider("faker.providers.person").last_names)

    def clean(names: Iterable[str]) -> List[str]:
        return sorted(n for n in names if n.isascii() and n.isalpha() and len(n) >= 2)

    def in_test(name: str) -> bool:
        return int(hashlib.sha256(name.lower().encode()).hexdigest(), 16) % 5 == 0

    pools: Dict[str, Dict[str, List[str]]] = {"train": {}, "test": {}}
    for kind, names in (("first", clean(firsts)), ("last", clean(lasts))):
        pools["test"][kind] = [n for n in names if in_test(n)]
        pools["train"][kind] = [n for n in names if not in_test(n)]
    return pools


def _render(kind: str, rng: random.Random, name_pools: Optional[Dict[str, List[str]]] = None) -> str:
    month, day, year = rng.randint(1, 12), rng.randint(1, 28), rng.randint(2005, 2025)
    name = MONTHS[month - 1]
    if kind == "full_date":
        return rng.choice([f"{month:02d}/{day:02d}/{year}", f"{month}/{day}/{year % 100:02d}",
                           f"{year}-{month:02d}-{day:02d}", f"{name} {day}, {year}"])
    if kind == "month_day":
        return rng.choice([f"{month}/{day}", f"{month:02d}-{day:02d}", f"{name[:3]} {day}"])
    if kind == "month_year":
        return rng.choice([f"{month}/{year}", f"{name} {year}"])
    if kind == "date_range":
        return f"{month}/{day}-{month}/{min(day + 2, 28)}"
    if kind == "month_only":
        return name
    if kind == "year":
        return str(year)
    if kind == "first":
        return rng.choice(name_pools["first"] if name_pools else FIRST_NAMES)
    if kind == "last":
        return rng.choice(name_pools["last"] if name_pools else LAST_NAMES)
    if kind == "id":
        return str(rng.randint(10 ** 4, 10 ** 8))
    if kind == "phone":
        return f"{rng.randint(201, 989)}-555-{rng.randint(0, 9999):04d}"
    if kind == "email":
        return f"{rng.choice(FIRST_NAMES)}.{rng.choice(LAST_NAMES)}@mail.example".lower()
    if kind == "street":
        return f"{rng.randint(4, 9999)} {rng.choice(STREETS)} {rng.choice(STREET_TYPES)}"
    if kind == "apartment":
        return f"Apt {rng.randint(1, 40)}"
    if kind == "city":
        return rng.choice(CITIES)[0]
    if kind == "facility":
        return rng.choice(FACILITIES)
    if kind == "age":
        return str(rng.randint(90, 104))
    return "Unknown"


# Values and formats the default generator never produces, to test whether a model
# retrained on its output learned PHI or only learned those formats.
UNSEEN_STREETS = ["Juniper", "Old Mill", "Quarry", "Wexford", "Tamarack", "Harbor View"]
UNSEEN_CITIES = ["Bozeman", "Ann Arbor", "Duluth", "Chattanooga", "Flagstaff", "Bangor", "Ithaca", "Moab"]
UNSEEN_FACILITIES = [
    "St. Brigid's Medical Center", "Valley Ridge Hospital", "Pinecrest Family Practice",
    "Bayshore Surgical Associates", "Eastbrook Dialysis Unit", "Granite Peaks Health System",
]
ONES = ["", "-one", "-two", "-three", "-four", "-five", "-six", "-seven", "-eight", "-nine"]


def _ordinal(day: int) -> str:
    suffix = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def _render_unseen(kind: str, rng: random.Random, name_pools: Optional[Dict[str, List[str]]] = None) -> str:
    month, day, year = rng.randint(1, 12), rng.randint(1, 28), rng.randint(2005, 2025)
    name = MONTHS[month - 1]
    if kind == "full_date":
        return rng.choice([f"{day} {name[:3]} {year}", f"{day:02d}.{month:02d}.{year}",
                           f"{name[:3]}. {_ordinal(day)} {year}", f"{year}/{month:02d}/{day:02d}"])
    if kind == "month_day":
        return rng.choice([f"{day} {name}", f"{_ordinal(day)} of {name}", f"{name[:3]}. {_ordinal(day)}"])
    if kind == "month_year":
        return rng.choice([f"{name} of {year}", f"{name[:3]}-{year}", f"{name[:3]} '{year % 100:02d}"])
    if kind == "date_range":
        return f"{name[:3]} {day} to {name[:3]} {min(day + 2, 28)}"
    if kind == "month_only":
        return name[:3] + "."
    if kind == "year":
        return str(year)
    if kind in ("first", "last"):
        return _render(kind, rng, name_pools)
    if kind == "id":
        letters = "".join(rng.choice("ABCDEFGHJKMNPRTUVWXYZ") for _ in range(2))
        return rng.choice([f"{letters}{rng.randint(10 ** 5, 10 ** 6 - 1)}",
                           f"{rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(1000, 9999)}-{letters[0]}",
                           f"#{rng.randint(0, 10 ** 7):08d}"])
    if kind == "phone":
        area, line = rng.randint(201, 989), rng.randint(0, 9999)
        return rng.choice([f"({area}) 555 {line:04d}", f"{area}.555.{line:04d}", f"+1 {area} 555 {line:04d}",
                           f"{area}555{line:04d}", f"x{rng.randint(2000, 7999)}"])
    if kind == "email":
        return f"{rng.choice(FIRST_NAMES)[0]}{rng.choice(LAST_NAMES)}{rng.randint(1, 99)}@clinicmail.org".lower()
    if kind == "street":
        return rng.choice([f"{rng.randint(4, 9999)} {rng.choice('NSEW')}. {rng.choice(UNSEEN_STREETS)} Rd.",
                           f"PO Box {rng.randint(10, 9999)}", f"Rural Route {rng.randint(1, 12)}"])
    if kind == "apartment":
        return rng.choice([f"Unit {rng.randint(1, 40)}{rng.choice('ABCD')}", f"#{rng.randint(100, 999)}"])
    if kind == "city":
        return rng.choice(UNSEEN_CITIES)
    if kind == "facility":
        return rng.choice(UNSEEN_FACILITIES)
    if kind == "age":
        age = rng.randint(90, 99)
        return rng.choice([f"ninety{ONES[age - 90]}", f"{age}yo"])
    return "Unknown"


FACILITY_SUFFIXES = [
    "Hospital", "Medical Center", "Memorial Hospital", "Clinic", "Health Center", "Rehabilitation Center",
    "Nursing Home", "Surgical Associates", "Community Hospital", "Regional Medical Center", "Family Practice",
]
WARD_UNITS = ["MICU", "SICU", "CCU", "CVICU", "NICU", "PACU", "TSICU", "CSRU"]
_faker = None


def _fake(rng: random.Random):
    """A Faker instance seeded from rng, so renders stay reproducible."""
    global _faker
    if _faker is None:
        from faker import Faker

        _faker = Faker("en_US")
    _faker.seed_instance(rng.randrange(2 ** 31))
    return _faker


def _render_rich(kind: str, rng: random.Random, name_pools: Optional[Dict[str, List[str]]] = None) -> str:
    """Training values drawn from large pools in many formats, so a model learns PHI, not a list.

    The default style draws facilities and cities from short fixed lists, and models
    trained on it lost most facility and location recall on independent notes.
    """
    month, day, year = rng.randint(1, 12), rng.randint(1, 28), rng.randint(1995, 2025)
    name = MONTHS[month - 1]
    if kind == "full_date":
        return rng.choice([f"{month}/{day}/{year}", f"{month:02d}/{day:02d}/{year}", f"{month}/{day}/{year % 100:02d}",
                           f"{month}-{day}-{year % 100:02d}", f"{year}-{month:02d}-{day:02d}", f"{name} {day}, {year}",
                           f"{name[:3]} {day} {year}", f"{day} {name} {year}"])
    if kind == "month_day":
        return rng.choice([f"{month}/{day}", f"{month:02d}/{day:02d}", f"{month}-{day}", f"{name} {day}",
                           f"{name[:3]} {day}", f"{name[:3]}. {day}", f"{day} {name[:3]}"])
    if kind == "month_year":
        return rng.choice([f"{month}/{year}", f"{month:02d}/{year % 100:02d}", f"{name} {year}", f"{name[:3]} {year}"])
    if kind == "date_range":
        end = min(day + rng.randint(1, 5), 28)
        return rng.choice([f"{month}/{day}-{month}/{end}", f"{month}/{day} - {month}/{end}", f"{name[:3]} {day}-{end}"])
    if kind == "month_only":
        return rng.choice([name, name[:3]])
    if kind == "year":
        return str(year)
    if kind in ("first", "last"):
        return _render(kind, rng, name_pools)
    fake = _fake(rng)
    if kind == "id":
        digits = str(rng.randint(10 ** 3, 10 ** 10))
        return rng.choice([digits, f"{fake.bothify('??').upper()}{digits[:7]}", f"{digits[:3]}-{digits[3:7]}", f"#{digits}"])
    if kind == "phone":
        area, mid, line = rng.randint(201, 989), rng.randint(200, 999), rng.randint(0, 9999)
        return rng.choice([f"{area}-{mid}-{line:04d}", f"({area}) {mid}-{line:04d}", f"{area}.{mid}.{line:04d}",
                           f"{mid}-{line:04d}", f"{area} {mid} {line:04d}", f"x{rng.randint(1000, 9999)}"])
    if kind == "email":
        return fake.email()
    if kind == "street":
        return rng.choice([fake.street_address(), f"{rng.randint(1, 999)} {fake.street_name()}"])
    if kind == "apartment":
        return rng.choice([f"Apt {rng.randint(1, 40)}", f"Apt. {rng.randint(1, 40)}{rng.choice('ABCD')}", f"Suite {rng.randint(100, 999)}"])
    if kind == "city":
        return rng.choice([fake.city(), fake.city(), f"{fake.city()}, {fake.state_abbr()}"])
    if kind == "facility":
        return rng.choice([
            f"{fake.last_name()} {rng.choice(FACILITY_SUFFIXES)}",
            f"{fake.city()} {rng.choice(FACILITY_SUFFIXES)}",
            f"St. {fake.first_name()}'s {rng.choice(FACILITY_SUFFIXES)}",
            f"{fake.last_name()} {rng.randint(1, 12)}",
            rng.choice(WARD_UNITS),
        ])
    if kind == "age":
        return str(rng.randint(90, 104))
    return "Unknown"


RENDERERS = {"default": _render, "unseen": _render_unseen, "rich": _render_rich}


def surrogate_note(
    text: str,
    rng: random.Random,
    name_pools: Optional[Dict[str, List[str]]] = None,
    style: str = "default",
) -> Dict:
    """Replace every tag with a fake value and return {'text', 'spans'}.

    style "unseen" writes values in formats the default generator never uses.
    """
    render = RENDERERS[style]
    memo: Dict[str, str] = {}
    known_names: Dict[str, List[str]] = {"patient": [], "care_team": [], "other": []}
    pieces: List[str] = []
    spans: List[Dict] = []
    length = cursor = 0
    for match in TAG.finditer(text):
        before = text[cursor:match.start()]
        pieces.append(before)
        length += len(before)
        inner = match.group(1)
        kind = classify(inner)
        role = name_role(inner) if LABELS[kind] == "NAME" else None
        # Every patient tag in a note refers to the same person.
        key = f"patient_{kind}" if role == "patient" else inner
        value = memo.setdefault(key, render(kind, rng, name_pools))
        span = {"start": length, "end": length + len(value), "label": LABELS[kind]}
        if role:
            span["role"] = role
            if value not in known_names[role]:
                known_names[role].append(value)
        spans.append(span)
        pieces.append(value)
        length += len(value)
        cursor = match.end()
    pieces.append(text[cursor:])
    result = "".join(pieces)

    def overlaps_phi(start: int, end: int) -> bool:
        return any(start < span["end"] and span["start"] < end for span in spans)

    keep = [
        {"start": m.start(), "end": m.end(), "label": "KEEP"}
        for pattern in (DOSE, EPONYM)
        for m in pattern.finditer(result)
        if not overlaps_phi(m.start(), m.end())
    ]
    return {"text": result, "spans": spans + keep, "known_names": known_names}


DEFAULT_SEED = 20261109


def sample_notes(
    stream: Iterable[str],
    per_category: int = 200,
    seed: int = 20261109,
    split: Optional[str] = None,
    name_pools: Optional[Dict[str, List[str]]] = None,
    style: str = "default",
) -> List[Dict]:
    """Reservoir-sample tagged notes per category, optionally from one patient split.

    The same notes are chosen whatever the surrogate style.
    """
    csv.field_size_limit(sys.maxsize)
    rng = random.Random(seed)
    reader = csv.reader(stream)
    header = [name.lower() for name in next(reader)]
    category_at, text_at, error_at = (header.index(n) for n in ("category", "text", "iserror"))
    subject_at = header.index("subject_id") if split else None

    reservoirs: Dict[str, List[str]] = {}
    seen: Dict[str, int] = {}
    for row in reader:
        if len(row) != len(header) or row[error_at].strip() or "[**" not in row[text_at]:
            continue
        if split and patient_split(row[subject_at]) != split:
            continue
        category = row[category_at].strip()
        count = seen[category] = seen.get(category, 0) + 1
        reservoir = reservoirs.setdefault(category, [])
        if len(reservoir) < per_category:
            reservoir.append(row[text_at])
        else:
            slot = rng.randrange(count)
            if slot < per_category:
                reservoir[slot] = row[text_at]

    return [
        surrogate_note(text, rng, name_pools, style)
        for category in sorted(reservoirs)
        for text in reservoirs[category]
    ]
