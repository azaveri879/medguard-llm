#!/usr/bin/env python3
"""Offline tests for the PHI redactor. Run from eval/: python -m unittest test_redaction"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "gateway"))

from phi_redaction import phi_redact


class RedactionTests(unittest.TestCase):
    def test_medication_list_is_not_treated_as_names(self):
        text = "Meds: Aspirin, Lisinopril, Metformin"
        self.assertEqual(phi_redact(text), (text, {}))

    def test_labeled_name_is_removed_and_label_kept(self):
        redacted, counts = phi_redact("Patient Name: Maria Rodriguez")
        self.assertEqual(redacted, "Patient Name: [PHI_NAME]")
        self.assertEqual(counts, {"NAME": 1})

    def test_later_mentions_of_a_name_are_removed(self):
        redacted, _ = phi_redact("PATIENT: John Smith\nSmith denies fever.")
        self.assertNotIn("Smith", redacted)
        self.assertIn("denies fever", redacted)

    def test_full_address_is_removed_as_one_unit(self):
        redacted, counts = phi_redact("Address: 123 Main St, Boston, MA 02115")
        self.assertEqual(redacted, "Address: [PHI_ADDRESS]")
        self.assertEqual(counts, {"ADDRESS": 1})

    def test_dose_schedule_is_not_a_date(self):
        text = "Taper prednisone 5/10/20 mg over one week."
        self.assertEqual(phi_redact(text), (text, {}))

    def test_date_formats_are_removed(self):
        for date in ("01/15/1985", "1979-04-12", "March 4, 2025"):
            self.assertEqual(phi_redact(f"Seen {date}."), ("Seen [PHI_DATE].", {"DATE": 1}))

    def test_empty_input(self):
        self.assertEqual(phi_redact(None), ("", {}))


if __name__ == "__main__":
    unittest.main()
