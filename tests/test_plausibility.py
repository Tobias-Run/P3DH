"""Tests für scripts/check_plausibility.py (Issue #17).

Schwerpunkt liegt auf den beiden Eigenschaften, die beim Bau teuer erkauft
wurden und beim Weiterentwickeln leicht wieder verloren gehen:

  * `robust_z` ist EINSEITIG (nur oberhalb des Medians). Symmetrisch geprüft
    lagen 9.750 von 12.744 Befunden unter dem Median — Rauschen aus der
    natürlichen unteren Flanke von Exposure-Verteilungen.
  * eine Zelle, deren Rumpf über >= 6 Größenordnungen streut, gilt als
    unbrauchbar; dort darf KEIN Institut belastet werden.
"""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_plausibility as cp  # noqa: E402


def _pop(exponent, n=None):
    """n Werte derselben Größenordnung — eine enge, auswertbare Zellpopulation."""
    n = n or cp.MIN_INSTITUTES
    return [10 ** exponent * (1 + i / 100) for i in range(n)]


class CellStatsTest(unittest.TestCase):
    def test_too_few_values_yields_none(self):
        self.assertIsNone(cp.cell_stats(_pop(6, cp.MIN_INSTITUTES - 1)))

    def test_zeros_and_none_are_ignored(self):
        vals = _pop(6) + [0, 0.0, None]
        st = cp.cell_stats(vals)
        self.assertEqual(st["n"], cp.MIN_INSTITUTES)

    def test_tight_population_is_coherent(self):
        st = cp.cell_stats(_pop(6))
        self.assertFalse(st["incoherent"])
        self.assertAlmostEqual(st["median"], 6, places=1)

    def test_population_spanning_many_orders_is_incoherent(self):
        """Nachbau von 09.05 c0020: die Zelle ist selbst gespalten (halb
        Dezimalquote, halb Betrag) — dort ist keine Zuschreibung zu
        verantworten."""
        vals = [10 ** -1 * (1 + i / 100) for i in range(30)] + \
               [10 ** 8 * (1 + i / 100) for i in range(30)]
        st = cp.cell_stats(vals)
        self.assertTrue(st["incoherent"])
        self.assertGreaterEqual(st["spread"], cp.INCOHERENT_SPREAD)

    def test_natural_bank_size_spread_stays_coherent(self):
        """Echte Größenunterschiede (Median 3,76 Größenordnungen im Bestand)
        dürfen eine Zelle NICHT unbrauchbar machen."""
        vals = [10 ** (6 + i * 0.1) for i in range(40)]   # 4 Größenordnungen
        self.assertFalse(cp.cell_stats(vals)["incoherent"])


class RobustZTest(unittest.TestCase):
    def setUp(self):
        self.st = cp.cell_stats(_pop(6))

    def test_value_far_above_median_is_flagged(self):
        z = cp.robust_z(10 ** 13, self.st)
        self.assertGreater(z, cp.OUTLIER_Z)

    def test_value_far_below_median_is_not_flagged(self):
        """Der Kern der Einseitigkeit: 10^-11 EUR in einer Zelle mit Median
        10^6 ist ein Rundungsrest, kein Meldefehler."""
        self.assertEqual(cp.robust_z(10 ** -11, self.st), 0.0)

    def test_value_at_median_is_zero(self):
        self.assertEqual(cp.robust_z(10 ** 6, self.st), 0.0)

    def test_zero_and_none_are_neutral(self):
        self.assertEqual(cp.robust_z(0, self.st), 0.0)
        self.assertEqual(cp.robust_z(None, self.st), 0.0)

    def test_negative_value_is_judged_by_magnitude(self):
        self.assertGreater(cp.robust_z(-(10 ** 13), self.st), cp.OUTLIER_Z)

    def test_zero_mad_falls_back_to_orders_of_magnitude(self):
        """Trägt mehr als die halbe Zelle exakt denselben Betrag, ist MAD 0 —
        ohne Rückfallebene wäre jeder abweichende Wert unendlich auffällig."""
        st = cp.cell_stats([10 ** 6] * 30)
        self.assertEqual(st["mad"], 0)
        self.assertAlmostEqual(cp.robust_z(10 ** 9, st), 3.0, places=6)


class SeverityTest(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(cp.severity(6.0), "hoch")     # volle Einheiten-Verwechslung
        self.assertEqual(cp.severity(4.0), "mittel")
        self.assertEqual(cp.severity(1.0), "niedrig")


class RatioViolationsTest(unittest.TestCase):
    def setUp(self):
        self.rule = dict(cp.RATIO_RULES[0])

    def test_value_inside_corridor_is_silent(self):
        # Median im Bestand: 142.516 EUR pro Kopf
        self.assertEqual(cp.ratio_violations(self.rule, [("k", 1_425_160.0, 10)]), [])

    def test_absurdly_high_ratio_is_flagged(self):
        """Der Fall aus Issue #17: 11,7 Bio. EUR fixe Vergütung für 9 Köpfe."""
        v = cp.ratio_violations(self.rule, [("k", 1.1736e13, 9)])
        self.assertEqual(len(v), 1)
        self.assertGreater(v[0]["ratio"], self.rule["hi"])

    def test_absurdly_low_ratio_is_flagged(self):
        """Untere Flanke: in Millionen gemeldet (0,15 statt 150.000). Genau
        das, was der einseitige Zell-Test bewusst NICHT prüft — hier fängt es
        die fachliche Regel."""
        v = cp.ratio_violations(self.rule, [("k", 0.15, 5)])
        self.assertEqual(len(v), 1)
        self.assertLess(v[0]["ratio"], self.rule["lo"])

    def test_zero_or_missing_denominator_is_skipped(self):
        pairs = [("a", 1e6, 0), ("b", 1e6, None), ("c", None, 5), ("d", 1e6, -3)]
        self.assertEqual(cp.ratio_violations(self.rule, pairs), [])

    def test_deviation_is_measured_against_the_violated_bound(self):
        v = cp.ratio_violations(self.rule, [("k", 2e9, 1)])[0]   # 100x über hi
        self.assertEqual(v["bound"], self.rule["hi"])
        self.assertAlmostEqual(v["deviation_orders"], 2.0, places=6)

    def test_severity_is_attached(self):
        v = cp.ratio_violations(self.rule, [("k", 2e13, 1)])[0]
        self.assertEqual(v["severity"], "hoch")


if __name__ == "__main__":
    unittest.main(verbosity=2)
