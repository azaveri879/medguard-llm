#!/usr/bin/env python3
"""Offline tests with invented text in the corpus's format. Run from eval/: python -m unittest test_physionet_deid"""

import tempfile
import unittest
from pathlib import Path

from physionet_deid import align, load_physionet_deid, physionet_split, write_split


def record(patient, note, body):
    return f"START_OF_RECORD={patient}||||{note}||||\n{body}\n||||END_OF_RECORD\n"


class AlignTests(unittest.TestCase):
    def test_spans_cover_each_surrogate(self):
        surrogate = "Seen by Dr Alvarez on 4-12 at Mercy, call 555-0101."
        tagged = "Seen by Dr [**Last Name (STitle) 12**] on [**4-12**] at [**Hospital1 3**], call [**Telephone/Fax (1) 9**]."
        spans = align(surrogate, tagged)
        self.assertEqual([surrogate[s["start"]:s["end"]] for s in spans], ["Alvarez", "4-12", "Mercy", "555-0101"])
        self.assertEqual([s["label"] for s in spans], ["NAME", "DATE", "FACILITY", "PHONE"])

    def test_adjacent_tags_and_tag_at_end(self):
        surrogate = "Pt John Smith arrived from Boston"
        tagged = "Pt [**First Name 1**] [**Last Name (un) 2**] arrived from [**Location 3**]"
        spans = align(surrogate, tagged)
        self.assertEqual([surrogate[s["start"]:s["end"]] for s in spans], ["John", "Smith", "Boston"])

    def test_mismatch_returns_none(self):
        self.assertIsNone(align("Seen today.", "Seen by [**Last Name (STitle) 1**] yesterday."))


class LoadTests(unittest.TestCase):
    def test_loads_aligned_records_and_flags_mismatches(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "id.text").write_text(
                record(1, 1, "Seen by Dr Alvarez.") + record(1, 2, "Text that changed."))
            Path(directory, "id.res").write_text(
                record(1, 1, "Seen by Dr [**Last Name (STitle) 4**].") + record(1, 2, "Other [**Hospital 2**] text."))
            notes = load_physionet_deid(directory)
        self.assertEqual([n["mismatched"] for n in notes], [0, 1])
        self.assertEqual(notes[0]["spans"][0]["label"], "NAME")

    def test_split_keeps_patients_together_and_halves_partition(self):
        with tempfile.TemporaryDirectory() as directory:
            text = "".join(record(p, n, "Seen by Dr Alvarez.") for p in range(1, 41) for n in (1, 2))
            res = "".join(record(p, n, "Seen by Dr [**Last Name (STitle) 4**].") for p in range(1, 41) for n in (1, 2))
            Path(directory, "id.text").write_text(text)
            Path(directory, "id.res").write_text(res)
            tune, test = load_physionet_deid(directory, "tune"), load_physionet_deid(directory, "test")
        self.assertEqual(len(tune) + len(test), 80)
        self.assertTrue(tune and test)
        self.assertFalse({n["patient"] for n in tune} & {n["patient"] for n in test})
        self.assertEqual(physionet_split("7"), physionet_split("7"))

    def test_write_split_copies_only_that_half(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as out:
            Path(directory, "id.text").write_text("".join(record(p, 1, "Seen by Dr Alvarez.") for p in range(1, 21)))
            Path(directory, "id.res").write_text("".join(record(p, 1, "Seen by Dr [**Last Name (STitle) 4**].") for p in range(1, 21)))
            written = write_split(directory, "tune", out)
            copied = load_physionet_deid(out)
            expected = load_physionet_deid(directory, "tune")
        self.assertEqual(written, len(expected))
        self.assertEqual([n["patient"] for n in copied], [n["patient"] for n in expected])
        self.assertTrue(all(physionet_split(n["patient"]) == "tune" for n in copied))


if __name__ == "__main__":
    unittest.main()
