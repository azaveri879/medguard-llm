#!/usr/bin/env python3
"""
Seeded synthetic notes with exact PHI spans, for comparing de-identification tools.

Notes are built from templates, so this ranks detectors on known difficulties
but does not replace validation on real clinical text.
"""

import random
import re
from typing import Dict, List

FIRST_NAMES = [
    "Sophia", "Liam", "Aisha", "Mateo", "Priya", "Noah", "Mei", "Elijah", "Fatima",
    "Hiroshi", "Olga", "Kwame", "Ingrid", "Diego", "Amara", "Tomasz", "Leila", "Ravi",
    "Grace", "Hannah", "Omar", "Yuki", "Chloe", "Andre", "Nadia", "Samuel", "Rosa",
    "Vikram", "Eleanor", "Jamal", "Thuy", "Patrick", "Zara", "Henrik", "Carmen", "Dmitri",
]
LAST_NAMES = [
    "Martinelli", "Stone", "Okonkwo", "Young", "Nakamura", "Rose", "Haddad", "White",
    "Kowalczyk", "Hill", "Banerjee", "Long", "Nguyen", "Bush", "Fitzgerald", "Brown",
    "Castellano", "Green", "Abdullah", "Woods", "Petrov", "Rivers", "Tanaka", "Black",
    "Oyelaran", "Price", "Lindqvist", "Day", "Mbeki", "Banks", "Delacroix", "Reed",
    "Vasquez", "Moon", "Sandhu", "Bishop",
]
STREETS = ["Birch", "Lakeview", "Maple Grove", "Oak", "Sunset", "River Bend", "Cedar", "Highland"]
STREET_TYPES = ["St", "Street", "Ave", "Avenue", "Road", "Blvd", "Lane", "Drive", "Court", "Terrace"]
CITIES = [
    ("Madison", "WI"), ("Springfield", "IL"), ("Fort Worth", "TX"), ("Albany", "NY"),
    ("Salem", "OR"), ("Tucson", "AZ"), ("Portland", "ME"), ("Durham", "NC"),
]
MONTHS = [
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
]
RELATIONS = ["daughter", "son", "wife", "husband", "sister", "brother", "niece"]

EPONYMS = [
    "Parkinson disease", "Crohn disease", "Hodgkin lymphoma", "Bell palsy", "Graves disease",
    "Alzheimer dementia", "Cushing syndrome", "Foley catheter", "Barrett esophagus",
    "Hashimoto thyroiditis", "Guillain-Barre syndrome", "Swan-Ganz catheter", "Sjogren syndrome",
]
CONDITIONS = [
    "Type 2 Diabetes Mellitus", "Atrial Fibrillation", "Stable Angina", "CKD Stage 3",
    "community-acquired pneumonia", "acute pancreatitis", "heart failure", "syncope",
]
MEDICATIONS = [
    "Aspirin, Lisinopril, Metformin", "Warfarin, Digoxin, Furosemide",
    "Levothyroxine, Atorvastatin", "Apixaban, Metoprolol", "Insulin, Gabapentin, Sertraline",
]
DOSES = ["prednisone 5/10/20 mg", "levothyroxine 25/50/75 mcg", "Aspirin 81 mg", "Lasix 40 mg IV"]
VITALS = ["BP 128/76", "HR 88, SpO2 97%", "Temp 37.2, RR 16", "WBC 12.3, Hgb 13.1"]
FINDINGS = ["Heart, Lungs clear", "CT Chest, Abdomen negative", "Right, Lower lobe opacity"]

HEADERS = [
    "Patient Name: {FULL}", "PATIENT: {FULL_UPPER}", "Name: {LAST_FIRST}", "Pt: {FULL}",
    "MRN: {MRN}", "MR#: {MRN}", "ACCT#: {MRN}", "Account Number: {MRN}", "Unit No: {MRN}",
    "Medical Record #{MRN}", "DOB: {DATE}", "D.O.B. {DATE}", "Date of Birth: {DATE}",
    "Admission Date: {DATE}", "SSN: {SSN}", "Social Security: {SSN}", "Phone: {PHONE}",
    "Cell {PHONE}", "Email: {EMAIL}", "Address: {ADDRESS}, {CITY_LINE}", "Home address: {ADDRESS}",
]
BODY = [
    "{FULL} is a {AGE}-year-old with a history of {EPONYM} and {CONDITION}.",
    "{FIRST} presented to the emergency department with {CONDITION} on {DATE}.",
    "Mr. {LAST} reports improvement since starting {MEDS}.",
    "Ms. {LAST} tolerated the procedure without complication.",
    "{LAST} denies chest pain and was seen by Dr. {DOCTOR_LAST}.",
    "Spoke with {RELATION} {RELATIVE_FULL} at {PHONE} about the plan.",
    "{RELATIVE_FULL}, the patient's {RELATION}, is the health care proxy.",
    "Case discussed with {DOCTOR_FULL}, the covering cardiologist.",
    "Seen today with {DOCTOR_FULL} from neurology.",
    "Exam notable for {EPONYM} and {FINDING}. Vitals {VITAL}.",
    "Continue {MEDS}. Titrate {DOSE}.",
    "Discharged to {ADDRESS} with home services.",
    "Follow up in clinic on {DATE}; call {PHONE} with questions.",
    "Patient lives alone in {CITY_LINE}.",
]


def _format_date(rng: random.Random) -> str:
    month, day, year = rng.randint(1, 12), rng.randint(1, 28), rng.randint(1945, 2025)
    name = MONTHS[month - 1]
    return rng.choice([
        f"{month:02d}/{day:02d}/{year}",
        f"{month}/{day}/{year % 100:02d}",
        f"{year}-{month:02d}-{day:02d}",
        f"{month:02d}-{day:02d}-{year}",
        f"{name} {day}, {year}",
        f"{name[:3]}. {day}, {year}",
        f"{day} {name} {year}",
        f"{name} {day}",
    ])


def _format_phone(rng: random.Random) -> str:
    area, line = rng.randint(201, 989), rng.randint(0, 9999)
    return rng.choice([
        f"({area}) 555-{line:04d}", f"({area})555-{line:04d}", f"{area}-555-{line:04d}",
        f"{area}.555.{line:04d}", f"1-{area}-555-{line:04d}",
    ])


class NoteFactory:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.first = rng.choice(FIRST_NAMES)
        self.last = rng.choice(LAST_NAMES)
        self.relative = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
        self.doctor_first = rng.choice(FIRST_NAMES)
        self.doctor_last = rng.choice(LAST_NAMES)
        self.relation = rng.choice(RELATIONS)

    def slot(self, name: str):
        """Return (value, label). Label is a PHI type, KEEP, or None."""
        rng = self.rng
        city, state = rng.choice(CITIES)
        slots = {
            "FULL": lambda: (f"{self.first} {self.last}", "NAME"),
            "FULL_UPPER": lambda: (f"{self.first} {self.last}".upper(), "NAME"),
            "LAST_FIRST": lambda: (f"{self.last}, {self.first}", "NAME"),
            "FIRST": lambda: (self.first, "NAME"),
            "LAST": lambda: (self.last, "NAME"),
            "RELATIVE_FULL": lambda: (self.relative, "NAME"),
            "DOCTOR_FULL": lambda: (f"{self.doctor_first} {self.doctor_last}", "NAME"),
            "DOCTOR_LAST": lambda: (self.doctor_last, "NAME"),
            "MRN": lambda: (str(rng.randint(10 ** 5, 10 ** 9)), "ID"),
            "SSN": lambda: (
                rng.choice(["{}-{}-{}", "{}{}{}", "{} {} {}"]).format(
                    rng.randint(100, 899), rng.randint(10, 99), rng.randint(1000, 9999)
                ),
                "ID",
            ),
            "DATE": lambda: (_format_date(rng), "DATE"),
            "PHONE": lambda: (_format_phone(rng), "PHONE"),
            "EMAIL": lambda: (f"{self.first}.{self.last}@mail.example".lower(), "EMAIL"),
            "ADDRESS": lambda: (
                f"{rng.randint(4, 9999)} {rng.choice(STREETS)} {rng.choice(STREET_TYPES)}",
                "ADDRESS",
            ),
            "CITY_LINE": lambda: (f"{city}, {state} {rng.randint(10000, 99999)}", "ADDRESS"),
            "RELATION": lambda: (self.relation, None),
            "AGE": lambda: (str(rng.randint(21, 88)), None),
            "EPONYM": lambda: (rng.choice(EPONYMS), "KEEP"),
            "CONDITION": lambda: (rng.choice(CONDITIONS), "KEEP"),
            "MEDS": lambda: (rng.choice(MEDICATIONS), "KEEP"),
            "DOSE": lambda: (rng.choice(DOSES), "KEEP"),
            "VITAL": lambda: (rng.choice(VITALS), "KEEP"),
            "FINDING": lambda: (rng.choice(FINDINGS), "KEEP"),
        }
        return slots[name]()


def render(templates: List[str], factory: NoteFactory, separator: str, text: str, spans: List):
    for index, template in enumerate(templates):
        if index:
            text += separator
        for part_index, part in enumerate(re.split(r"\{(\w+)\}", template)):
            if part_index % 2 == 0:
                text += part
                continue
            value, label = factory.slot(part)
            if label:
                spans.append({"start": len(text), "end": len(text) + len(value), "label": label})
            text += value
    return text


def generate_notes(count: int = 300, seed: int = 20261109) -> List[Dict]:
    """Return notes as {'text': str, 'spans': [{'start', 'end', 'label'}]}."""
    rng = random.Random(seed)
    notes = []
    for _ in range(count):
        factory = NoteFactory(rng)
        spans: List[Dict] = []
        text = render(rng.sample(HEADERS, rng.randint(3, 6)), factory, "\n", "", spans)
        text += "\n\n"
        text = render(rng.sample(BODY, rng.randint(5, 9)), factory, " ", text, spans)
        notes.append({"text": text, "spans": spans})
    return notes
