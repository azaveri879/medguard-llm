#!/usr/bin/env python3
"""Offline tests using invented text in MIMIC's tag format. Run from eval/: python -m unittest test_mimic_surrogates"""

import csv
import io
import random
import unittest

from deid_benchmark import score_notes
from mimic_surrogates import LABELS, classify, sample_notes, surrogate_note


class ClassifyTests(unittest.TestCase):
    def test_representative_tags(self):
        expected = {
            "2101-10-20": "full_date",
            "10-20": "month_day",
            "2101": "year",
            "Known lastname 123": "last",
            "First Name8 (NamePattern2) 12": "first",
            "Name (NI) 55": "last",
            "Doctor First Name 9": "first",
            "Initials (NamePattern4) 7": "skip",
            "Name Initial (PRE) 3": "skip",
            "Hospital1 18": "facility",
            "Hospital Ward Name 2": "facility",
            "Location (un) 8": "city",
            "Clip Number (Radiology) 4": "id",
            "Telephone/Fax (1) 6": "phone",
            "Month/Day (2) 1": "month_day",
            "Month (only) 5": "month_only",
            "Year (4 digits) 1": "year",
            "Age over 90 2": "age",
            "State 3": "skip",
            "": "skip",
            "Something New": "skip",
        }
        for tag, kind in expected.items():
            self.assertEqual(classify(tag), kind, tag)


class SurrogateTests(unittest.TestCase):
    def build(self, text):
        return surrogate_note(text, random.Random(1))

    def test_spans_cover_inserted_values_and_tags_are_gone(self):
        note = self.build("Seen by Dr. [**Known lastname 1**] on [**2101-10-20**] today.")
        self.assertNotIn("[**", note["text"])
        labels = [span["label"] for span in note["spans"]]
        self.assertEqual(labels, ["NAME", "DATE"])
        for span in note["spans"]:
            self.assertTrue(note["text"][span["start"]:span["end"]])

    def test_repeated_tag_gets_the_same_value(self):
        note = self.build("[**Known lastname 1**] and [**Known lastname 1**]")
        first, second = note["spans"]
        self.assertEqual(
            note["text"][first["start"]:first["end"]],
            note["text"][second["start"]:second["end"]],
        )

    def test_doses_and_eponyms_are_marked_keep(self):
        note = self.build("Lasix 40 mg given, Foley in place. [**Known lastname 1**]")
        kept = [note["text"][s["start"]:s["end"]] for s in note["spans"] if s["label"] == "KEEP"]
        self.assertEqual(sorted(kept), ["40 mg", "Foley"])

    def test_patient_tags_share_one_person_and_roles_are_recorded(self):
        note = self.build(
            "[**Known lastname 1**] [**Known lastname 2**] with Dr. [**Last Name (STitle) 3**] "
            "and [**Name (NI) 4**]"
        )
        names = note["known_names"]
        self.assertEqual(len(names["patient"]), 1)
        self.assertEqual(len(names["care_team"]), 1)
        self.assertEqual(len(names["other"]), 1)

    def test_every_kind_has_a_label(self):
        self.assertIn("SKIP", LABELS.values())


class ScoringTests(unittest.TestCase):
    def test_skip_spans_are_not_scored_or_counted_as_other_words(self):
        note = {"text": "Seen in 2101 today", "spans": [{"start": 8, "end": 12, "label": "SKIP"}]}
        result = score_notes([note], lambda text: [(8, 12)])
        self.assertEqual(result["total"], {})
        self.assertEqual(result["other_words_redacted"], 0)
        self.assertEqual(result["other_words"], 3)


class SampleTests(unittest.TestCase):
    def test_samples_tagged_notes_per_category_and_skips_errors(self):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["CATEGORY", "ISERROR", "TEXT"])
        for index in range(20):
            writer.writerow(["Radiology", "", f"Study {index} by [**Known lastname 1**]"])
        writer.writerow(["Radiology", "1", "Error note [**Known lastname 1**]"])
        writer.writerow(["Nursing/other", "", "No tags here"])
        writer.writerow(["Nursing/other", "", "Seen [**2101-10-20**]"])
        buffer.seek(0)
        notes = sample_notes(buffer, per_category=5)
        self.assertEqual(len(notes), 6)
        self.assertFalse(any("Error note" in note["text"] for note in notes))


if __name__ == "__main__":
    unittest.main()
