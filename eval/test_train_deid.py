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


STANFORD = {name: index for index, name in enumerate(
    ["O", "VENDOR", "DATE", "HCW", "HOSPITAL", "ID", "PATIENT", "PHONE", "AGE"]
)}


class PlainLabelTests(unittest.TestCase):
    def test_plain_labels_map_onto_stanford_types(self):
        offsets = [(0, 3), (3, 6), (7, 11), (12, 18), (19, 22), (23, 25)]
        spans = [
            {"start": 0, "end": 6, "label": "NAME", "role": "patient"},
            {"start": 7, "end": 11, "label": "NAME", "role": "care_team"},
            {"start": 12, "end": 18, "label": "LOCATION"},
            {"start": 19, "end": 22, "label": "EMAIL"},
            {"start": 23, "end": 25, "label": "AGE_OVER_89"},
        ]
        expected = [STANFORD[t] for t in ("PATIENT", "PATIENT", "HCW", "HOSPITAL", "ID", "AGE")]
        self.assertEqual(window_labels(offsets, spans, STANFORD), expected)

    def test_age_label_is_added_to_a_plain_label_head(self):
        import torch
        from types import SimpleNamespace

        from train_deid import ensure_age_label

        labels = ["O", "DATE", "PATIENT"]
        config = SimpleNamespace(id2label=dict(enumerate(labels)), label2id={l: i for i, l in enumerate(labels)}, num_labels=3)
        model = SimpleNamespace(config=config, classifier=torch.nn.Linear(4, 3), num_labels=3)
        before = model.classifier.weight.detach().clone()
        ensure_age_label(model, torch)
        self.assertEqual(model.classifier.out_features, 4)
        self.assertEqual((config.label2id["AGE"], config.id2label[3], config.num_labels, model.num_labels), (3, "AGE", 4, 4))
        self.assertTrue(torch.equal(model.classifier.weight[:3], before))
        ensure_age_label(model, torch)  # a second call changes nothing
        self.assertEqual(model.classifier.out_features, 4)


class PatientSplitTests(unittest.TestCase):
    def test_split_is_stable_and_near_expected_proportions(self):
        splits = [patient_split(str(subject)) for subject in range(20000)]
        self.assertEqual(patient_split("123"), patient_split(" 123 "))
        self.assertAlmostEqual(splits.count("train") / 20000, 0.8, delta=0.02)
        self.assertAlmostEqual(splits.count("test") / 20000, 0.1, delta=0.02)


if __name__ == "__main__":
    unittest.main()
