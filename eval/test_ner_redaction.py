#!/usr/bin/env python3
"""Offline tests for model redaction, with the model stubbed. Run from eval/: python -m unittest test_ner_redaction"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "gateway"))

import ner_redaction
from ner_redaction import phi_redact_with_ner, redact_entities


def token_spans(text, *words, phi_type="NAME"):
    return [(text.index(word), text.index(word) + len(word), phi_type) for word in words]


class RedactEntitiesTests(unittest.TestCase):
    def run_with(self, text, entities):
        with mock.patch.object(ner_redaction, "_token_entities", return_value=entities):
            return redact_entities(text)

    def test_adjacent_tokens_become_one_entity(self):
        text = "Sophia Martinelli presented with syncope."
        out, counts = self.run_with(text, token_spans(text, "Sophia", "Martinelli"))
        self.assertEqual(out, "[PHI_NAME] presented with syncope.")
        self.assertEqual(counts, {"NAME": 1})

    def test_duplicate_tokens_from_overlapping_windows_count_once(self):
        text = "Sophia presented."
        out, counts = self.run_with(text, token_spans(text, "Sophia") * 2)
        self.assertEqual((out, counts), ("[PHI_NAME] presented.", {"NAME": 1}))

    def test_partial_word_is_expanded(self):
        text = "ID 704621788 noted."
        out, _ = self.run_with(text, [(3, 6, "ID")])
        self.assertEqual(out, "ID [PHI_ID] noted.")

    def test_dose_schedule_is_protected(self):
        text = "Taper prednisone 5/10/20 mg weekly."
        out, counts = self.run_with(text, token_spans(text, "5/10", phi_type="DATE"))
        self.assertEqual((out, counts), (text, {}))

    def test_existing_placeholder_is_left_alone(self):
        text = "Seen by [PHI_NAME] today."
        out, counts = self.run_with(text, token_spans(text, "PHI_NAME"))
        self.assertEqual((out, counts), (text, {}))

    def test_different_types_stay_separate(self):
        text = "Anna Boston"
        entities = [(0, 4, "NAME"), (5, 11, "LOCATION")]
        out, counts = self.run_with(text, entities)
        self.assertEqual(out, "[PHI_NAME] [PHI_LOCATION]")
        self.assertEqual(counts, {"NAME": 1, "LOCATION": 1})

    def test_empty_text_skips_the_model(self):
        with mock.patch.object(ner_redaction, "_token_entities") as model:
            self.assertEqual(redact_entities(None), ("", {}))
        model.assert_not_called()


class PipelineTests(unittest.TestCase):
    def test_rules_run_first_and_counts_combine(self):
        text = "SSN: 555-12-3456. Anna Kowalski called."

        def only_name(redacted):
            return token_spans(redacted, "Anna", "Kowalski")

        with mock.patch.object(ner_redaction, "_token_entities", side_effect=only_name):
            out, counts = phi_redact_with_ner(text)
        self.assertEqual(out, "SSN: [PHI_SSN]. [PHI_NAME] called.")
        self.assertEqual(counts, {"SSN": 1, "NAME": 1})

    def test_model_failure_propagates_instead_of_returning_text(self):
        with mock.patch.object(ner_redaction, "_load_model", side_effect=OSError("no model")):
            with self.assertRaises(OSError):
                phi_redact_with_ner("Anna Kowalski called.")


if __name__ == "__main__":
    unittest.main()
