#!/usr/bin/env python3
"""Offline tests for the detector benchmark. Run from eval/: python -m unittest test_deid_benchmark"""

import unittest

from deid_benchmark import char_class, ignored_labels, score_notes, spans_from_redacted
from deid_data import generate_notes


class GeneratedNoteTests(unittest.TestCase):
    def test_generation_is_repeatable(self):
        self.assertEqual(generate_notes(5), generate_notes(5))

    def test_spans_point_at_non_empty_text_inside_the_note(self):
        for note in generate_notes(50):
            for span in note["spans"]:
                self.assertGreater(span["end"], span["start"])
                self.assertLessEqual(span["end"], len(note["text"]))
                self.assertTrue(note["text"][span["start"]:span["end"]].strip())


class AlignmentTests(unittest.TestCase):
    def test_recovers_removed_ranges(self):
        original = "Seen John Smith on 01/02/2020 today"
        redacted = "Seen [PHI_NAME] on [PHI_DATE] today"
        found = [original[a:b] for a, b in spans_from_redacted(original, redacted)]
        self.assertEqual(found, ["John Smith", "01/02/2020"])

    def test_handles_placeholder_at_the_end(self):
        original = "DOB 01/02/2020"
        found = spans_from_redacted(original, "DOB [PHI_DATE]")
        self.assertEqual([original[a:b] for a, b in found], ["01/02/2020"])


class ScoreTests(unittest.TestCase):
    NOTE = {
        "text": "John Smith has Parkinson disease and sees us",
        "spans": [
            {"start": 0, "end": 10, "label": "NAME"},
            {"start": 15, "end": 32, "label": "KEEP"},
        ],
    }

    def test_partial_coverage_is_a_miss(self):
        result = score_notes([self.NOTE], lambda text: [(0, 4)])
        self.assertEqual(result["caught"].get("NAME", 0), 0)

    def test_full_coverage_is_caught_and_keep_terms_counted(self):
        result = score_notes([self.NOTE], lambda text: [(0, 10), (15, 24)])
        self.assertEqual(result["caught"]["NAME"], 1)
        self.assertEqual(result["keep_intact"], 0)

    def test_other_words_removed_are_counted(self):
        result = score_notes([self.NOTE], lambda text: [(42, 44)])
        self.assertEqual(result["other_words_redacted"], 1)


class MissContextTests(unittest.TestCase):
    def test_char_class_hides_letters_and_digits(self):
        text = "a1 (\n"
        self.assertEqual([char_class(text, i) for i in range(-1, 6)],
                         ["edge", "letter", "digit", "space", "'('", "newline", "edge"])

    def test_misses_are_tallied_by_context_without_text(self):
        text = "call pager201-555-0143 or (608) 555-0199"
        notes = [{"text": text, "spans": [
            {"start": 10, "end": 22, "label": "PHONE"},
            {"start": 26, "end": 40, "label": "PHONE"},
        ]}]
        detector = lambda t: [(27, 40)]  # catches every digit of the second number
        result = score_notes(notes, detector, ("PHONE",))
        self.assertEqual(dict(result["misses"]), {("PHONE", "none", "letter", "space"): 1})
        self.assertEqual(result["caught"]["PHONE"], 1)


class IgnoredLabelTests(unittest.TestCase):
    def test_outside_and_age_labels_are_ignored(self):
        id2label = {0: "O", 1: "B-AGE", 2: "I-AGE", 3: "B-PATIENT", 4: "AGE", 5: "DATE"}
        self.assertEqual(ignored_labels(id2label), {0, 1, 2, 4})

    def test_string_ids_from_a_config_file_become_ints(self):
        self.assertEqual(ignored_labels({"0": "O", "1": "PATIENT"}), {0})


if __name__ == "__main__":
    unittest.main()
