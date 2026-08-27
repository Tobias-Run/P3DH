"""Tests für scripts/check_unit_consistency.py (Issue #9)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_unit_consistency as u  # noqa: E402


class GapScanTest(unittest.TestCase):
    def test_continuous_spread_not_flagged(self):
        # echte Bankgrößen: 3 Größenordnungen, aber kontinuierlich verteilt
        vals = [1e6, 3e6, 1e7, 3e7, 1e8, 3e8, 1e9]
        flagged = u.gap_scan({"cell": vals})
        self.assertEqual(flagged, [])

    def test_bimodal_units_mix_flagged(self):
        # 3 Institute in Millionen (~1e3-1e4), 3 in Basiswährung (~1e9-1e10):
        # genau das 41.00-Muster (Faktor 10^6)
        vals = [5e3, 8e3, 2e4] + [5e9, 8e9, 2e10]
        flagged = u.gap_scan({"cell": vals})
        self.assertEqual(len(flagged), 1)
        self.assertGreaterEqual(flagged[0]["gap"], 3.0)
        self.assertEqual(flagged[0]["below"], 3)
        self.assertEqual(flagged[0]["above"], 3)

    def test_single_outlier_not_flagged(self):
        # eine einzelne sehr große Bank ist keine "Einheiten-Lücke",
        # sondern die Norm — MIN_SIDE schützt davor
        vals = [1e6, 2e6, 3e6, 4e6, 5e6, 1e12]
        flagged = u.gap_scan({"cell": vals})
        self.assertEqual(flagged, [], "ein Ausreißer allein darf nicht anschlagen")

    def test_too_few_values_skipped(self):
        vals = [1e6, 1e12]  # unter 2*MIN_SIDE
        self.assertEqual(u.gap_scan({"cell": vals}), [])

    def test_zero_and_negative_handled(self):
        # abs() vor log10, 0 wird vom Aufrufer bereits gefiltert, aber die
        # Funktion selbst darf bei negativen Werten nicht crashen
        vals = [-5e3, -8e3, -2e4, 5e9, 8e9, 2e10]
        flagged = u.gap_scan({"cell": vals})
        self.assertEqual(len(flagged), 1)

    def test_sorted_worst_gap_first(self):
        cells = {
            "small_gap": [1e6, 1e7, 1e8, 1e9, 1e10, 1e11],
            "big_gap": [1e3, 2e3, 3e3, 1e11, 2e11, 3e11],
        }
        flagged = u.gap_scan(cells)
        self.assertEqual(flagged[0]["key"], "big_gap")


class LabelCheckTest(unittest.TestCase):
    def test_finds_mln_eur_label(self):
        rows = [{"template": "K_41.00", "col_label": "a. Gross carrying amount (Mln EUR)"}]
        hits = u.find_label_ambiguous_templates(rows)
        self.assertIn("K_41.00", hits)

    def test_case_insensitive_and_variants(self):
        rows = [
            {"template": "K_A", "col_label": "Amount (Mio EUR)"},
            {"template": "K_B", "col_label": "Amount in '000"},
            {"template": "K_C", "col_label": "Plain Amount"},
        ]
        hits = u.find_label_ambiguous_templates(rows)
        self.assertIn("K_A", hits)
        self.assertIn("K_B", hits)
        self.assertNotIn("K_C", hits)

    def test_clean_labels_not_flagged(self):
        rows = [{"template": "K_61.00", "col_label": "Amount"},
                {"template": "K_61.00", "col_label": "Percentage"}]
        self.assertEqual(u.find_label_ambiguous_templates(rows), {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
