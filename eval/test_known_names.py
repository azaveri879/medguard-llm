#!/usr/bin/env python3
"""Offline tests for known-name redaction. Run from eval/: python -m unittest test_known_names"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "gateway"))

from known_names import known_names_from_fhir, redact_known_names, redact_with_known
from phi_redaction import phi_redact


class KnownNameTests(unittest.TestCase):
    def test_bare_surname_is_removed(self):
        out, counts = redact_known_names("Martinelli denies pain.", ["Sophia Martinelli"])
        self.assertEqual((out, counts), ("[PHI_NAME] denies pain.", {"NAME": 1}))

    def test_full_name_counts_once_in_either_order(self):
        self.assertEqual(
            redact_known_names("Sophia Martinelli and Martinelli, Sophia", ["Sophia Martinelli"]),
            ("[PHI_NAME] and [PHI_NAME]", {"NAME": 2}),
        )

    def test_distinctive_name_matches_any_case(self):
        out, _ = redact_known_names("pt martinelli and MARTINELLI", ["Sophia Martinelli"])
        self.assertEqual(out, "pt [PHI_NAME] and [PHI_NAME]")

    def test_common_word_surname_keeps_lowercase_word(self):
        out, _ = redact_known_names("Mr. Stone has a kidney stone.", ["John Stone"])
        self.assertEqual(out, "Mr. [PHI_NAME] has a kidney stone.")

    def test_titles_are_not_treated_as_names(self):
        out, _ = redact_known_names("The Do not resuscitate order.", ["Dr. Ravi Banerjee, DO"])
        self.assertEqual(out, "The Do not resuscitate order.")

    def test_name_inside_a_longer_word_is_left_alone(self):
        out, _ = redact_known_names("Hillsborough clinic.", ["Anna Hillsbo"])
        self.assertEqual(out, "Hillsborough clinic.")

    def test_bad_input_is_ignored(self):
        self.assertEqual(redact_known_names("Stable.", [None, 5, ""]), ("Stable.", {}))
        self.assertEqual(redact_known_names("Stable.", None), ("Stable.", {}))

    def test_counts_combine_with_the_next_redactor(self):
        out, counts = redact_with_known("Martinelli SSN 555-12-3456", ["Sophia Martinelli"], phi_redact)
        self.assertEqual(out, "[PHI_NAME] SSN [PHI_SSN]")
        self.assertEqual(counts, {"NAME": 1, "SSN": 1})


class FhirTests(unittest.TestCase):
    def test_collects_names_from_supported_resources(self):
        resources = [
            {"resourceType": "Patient", "name": [{"given": ["Sophia", "M"], "family": "Martinelli"}]},
            {"resourceType": "Practitioner", "name": [{"text": "Ravi Banerjee"}]},
            {"resourceType": "CareTeam", "participant": [{"member": {"display": "Grace Okoye"}}]},
            {"resourceType": "Observation", "name": [{"family": "Ignored"}]},
            {"resourceType": "Patient", "name": [{"given": ["Sophia", "M"], "family": "Martinelli"}]},
        ]
        self.assertEqual(
            known_names_from_fhir(resources),
            ["Sophia M Martinelli", "Ravi Banerjee", "Grace Okoye"],
        )


class AgeRuleTests(unittest.TestCase):
    def test_ages_over_89_are_removed(self):
        for text in ("92 year old", "92-year-old", "101 y/o", "92yo", "age 95", "Age: 90", "aged 104"):
            out, counts = phi_redact(text)
            self.assertEqual(counts, {"AGE": 1}, text)
            self.assertIn("[PHI_AGE]", out)

    def test_other_numbers_are_kept(self):
        for text in ("89 year old", "age 45", "92 mg", "HR 95", "SpO2 92%"):
            self.assertEqual(phi_redact(text), (text, {}), text)


if __name__ == "__main__":
    unittest.main()
