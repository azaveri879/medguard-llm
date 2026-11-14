#!/usr/bin/env python3
"""Offline tests for the n2c2 loader, intervals, and paired comparison. Run from eval/."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "gateway"))

from deid_benchmark import bootstrap_ci, note_key, score_notes
from deid_compare import paired_difference
from n2c2_data import label_for, load_n2c2, parse_note

TEXT = "Record date: 2091-04-02\r\nJane Roe, 93 yo, seen by Dr. Kim at Lakeside in Ohio.\r\nAge 45 sister."


def tag(name, value, phi_type, text=TEXT):
    start = text.index(value)
    return (f'<{name} id="P" start="{start}" end="{start + len(value)}" '
            f'text="{value}" TYPE="{phi_type}" comment="" />')


DOCUMENT = (
    '<?xml version="1.0" encoding="UTF-8" ?>\n<deIdi2b2>\n<TEXT><![CDATA[' + TEXT + "]]></TEXT>\n<TAGS>\n"
    + "\n".join([
        tag("DATE", "2091-04-02", "DATE"),
        tag("NAME", "Jane Roe", "PATIENT"),
        tag("AGE", "93", "AGE"),
        tag("NAME", "Kim", "DOCTOR"),
        tag("LOCATION", "Lakeside", "HOSPITAL"),
        tag("LOCATION", "Ohio", "STATE"),
        tag("AGE", "45", "AGE"),
        '<NAME id="P9" start="0" end="4" text="Nope" TYPE="PATIENT" comment="" />',
    ])
    + "\n</TAGS>\n</deIdi2b2>\n"
)


class N2c2Tests(unittest.TestCase):
    def setUp(self):
        self.note = parse_note(DOCUMENT)

    def labels(self):
        return {self.note["text"][s["start"]:s["end"]]: s["label"] for s in self.note["spans"]}

    def test_offsets_survive_windows_line_endings(self):
        self.assertIn("\r\n", self.note["text"])
        self.assertEqual(self.labels()["Jane Roe"], "NAME")

    def test_safe_harbor_mapping(self):
        labels = self.labels()
        self.assertEqual(labels["93"], "AGE_OVER_89")
        self.assertEqual(labels["45"], "SKIP")
        self.assertEqual(labels["Ohio"], "SKIP")
        self.assertEqual(labels["Lakeside"], "FACILITY")
        self.assertEqual(labels["2091-04-02"], "DATE")

    def test_mismatched_offsets_are_counted_not_used(self):
        self.assertEqual(self.note["mismatched"], 1)
        self.assertNotIn("Reco", self.labels())

    def test_names_are_known_by_role(self):
        self.assertEqual(self.note["known_names"]["patient"], ["Jane Roe"])
        self.assertEqual(self.note["known_names"]["care_team"], ["Kim"])

    def test_loading_from_disk_keeps_line_endings(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "100-01.xml").write_bytes(DOCUMENT.encode("utf-8"))
            notes = load_n2c2(directory)
        self.assertEqual(notes[0]["mismatched"], 1)
        self.assertEqual(len(notes[0]["spans"]), 7)

    def test_unknown_tags_are_skipped(self):
        self.assertEqual(label_for("PROFESSION", "", "nurse"), "SKIP")
        self.assertEqual(label_for("ID", "MEDICALRECORD", "123"), "ID")


class IntervalTests(unittest.TestCase):
    def test_interval_contains_the_rate(self):
        per_note = [{"caught": {"NAME": 1}, "total": {"NAME": 1}}] * 8 + \
                   [{"caught": {}, "total": {"NAME": 1}}] * 2
        low, high = bootstrap_ci(per_note, "NAME")
        self.assertLessEqual(low, 0.8)
        self.assertGreaterEqual(high, 0.8)
        self.assertLess(high - low, 0.6)

    def test_score_notes_records_per_note_counts(self):
        note = {"text": "Jane saw Bob.", "spans": [
            {"start": 0, "end": 4, "label": "NAME"}, {"start": 9, "end": 12, "label": "NAME"}]}
        result = score_notes([note], lambda text: [(0, 4)])
        self.assertEqual(result["per_note"], [{"key": note_key(note["text"]),
                                               "caught": {"NAME": 1}, "total": {"NAME": 2}}])


class PairedTests(unittest.TestCase):
    def test_difference_uses_shared_notes(self):
        base = {f"n{i}": {"caught": {"NAME": 0}, "total": {"NAME": 1}} for i in range(20)}
        candidate = {f"n{i}": {"caught": {"NAME": 1}, "total": {"NAME": 1}} for i in range(20)}
        candidate["extra"] = {"caught": {}, "total": {"NAME": 5}}
        result = paired_difference(base, candidate, "NAME", rounds=200)
        self.assertEqual(result["notes"], 20)
        self.assertAlmostEqual(result["difference"], 1.0)
        self.assertAlmostEqual(result["low"], 1.0)


if __name__ == "__main__":
    unittest.main()
