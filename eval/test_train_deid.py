#!/usr/bin/env python3
"""Offline tests for training data preparation. Run from eval/: python -m unittest test_train_deid"""

import unittest

from mimic_surrogates import patient_split
from train_deid import IGNORE_INDEX, window_labels

LABELS = {name: index for index, name in enumerate(
    ["O", "B-PATIENT", "I-PATIENT", "L-PATIENT", "U-PATIENT", "U-STAFF", "U-DATE"]
)}


class WindowLabelTests(unittest.TestCase):
    def test_multi_token_span_uses_bilou_labels(self):
        offsets = [(0, 0), (0, 3), (3, 6), (6, 9), (10, 12), (0, 0)]
        spans = [{"start": 0, "end": 9, "label": "NAME", "role": "patient"}]
        expected = [IGNORE_INDEX, LABELS["B-PATIENT"], LABELS["I-PATIENT"], LABELS["L-PATIENT"], LABELS["O"], IGNORE_INDEX]
        self.assertEqual(window_labels(offsets, spans, LABELS), expected)

    def test_single_tokens_and_care_team_role(self):
        offsets = [(0, 4), (5, 9)]
        spans = [
            {"start": 0, "end": 4, "label": "NAME", "role": "care_team"},
            {"start": 5, "end": 9, "label": "DATE"},
        ]
        self.assertEqual(window_labels(offsets, spans, LABELS), [LABELS["U-STAFF"], LABELS["U-DATE"]])

    def test_skip_spans_are_ignored_and_keep_spans_are_o(self):
        offsets = [(0, 4), (5, 9)]
        spans = [{"start": 0, "end": 4, "label": "SKIP"}, {"start": 5, "end": 9, "label": "KEEP"}]
        self.assertEqual(window_labels(offsets, spans, LABELS), [IGNORE_INDEX, LABELS["O"]])


class PatientSplitTests(unittest.TestCase):
    def test_split_is_stable_and_near_expected_proportions(self):
        splits = [patient_split(str(subject)) for subject in range(20000)]
        self.assertEqual(patient_split("123"), patient_split(" 123 "))
        self.assertAlmostEqual(splits.count("train") / 20000, 0.8, delta=0.02)
        self.assertAlmostEqual(splits.count("test") / 20000, 0.1, delta=0.02)


if __name__ == "__main__":
    unittest.main()
