"""Tests für den Referenzdaten-Guard (scripts/check_reference_data.py)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_reference_data as g  # noqa: E402


class MissingKeysTest(unittest.TestCase):
    def test_full_coverage_is_clean(self):
        needed = [(("EUR", "2025-12-31"), 100), (("SEK", "2025-12-31"), 50)]
        have = {("EUR", "2025-12-31"), ("SEK", "2025-12-31")}
        self.assertEqual(g.missing_keys(needed, have), [])

    def test_missing_pair_reported(self):
        needed = [(("BGN", "2025-12-31"), 26824)]
        self.assertEqual(g.missing_keys(needed, set()),
                         [(("BGN", "2025-12-31"), 26824)])

    def test_sorted_by_impact_worst_first(self):
        needed = [(("USD", "2025-12-31"), 1565), (("BGN", "2025-12-31"), 26824)]
        result = g.missing_keys(needed, set())
        self.assertEqual([k for k, _ in result],
                         [("BGN", "2025-12-31"), ("USD", "2025-12-31")])

    def test_extra_reference_rows_are_harmless(self):
        # Kurse für Stichtage, die (noch) keine Fakten haben, sind kein Problem
        needed = [(("EUR", "2025-12-31"), 10)]
        have = {("EUR", "2025-12-31"), ("EUR", "2099-01-01"), ("XXX", "2025-12-31")}
        self.assertEqual(g.missing_keys(needed, have), [])

    def test_works_for_scalar_keys_too(self):
        # gleiche Funktion trägt den entity_meta-Check (Schlüssel = LEI)
        needed = [("LEI_A", 5), ("LEI_B", 9)]
        self.assertEqual(g.missing_keys(needed, {"LEI_A"}), [("LEI_B", 9)])

    def test_empty_input(self):
        self.assertEqual(g.missing_keys([], set()), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
