"""Tests für scripts/check_plausibility.py (Issue #17).

Schwerpunkt liegt auf den beiden Eigenschaften, die beim Bau teuer erkauft
wurden und beim Weiterentwickeln leicht wieder verloren gehen:

  * `robust_z` ist EINSEITIG (nur oberhalb des Medians). Symmetrisch geprüft
    lagen 9.750 von 12.744 Befunden unter dem Median — Rauschen aus der
    natürlichen unteren Flanke von Exposure-Verteilungen.
  * eine Zelle, deren Rumpf über >= 6 Größenordnungen streut, gilt als
    unbrauchbar; dort darf KEIN Institut belastet werden.

Dazu seit #53 der Schweregrad. Er misst nicht mehr nur absolute
Größenordnungen — diese Skala war auf Einheiten-Verwechslungen geeicht und
stufte deshalb 14 beweisbare Meldeartefakte in der CET1-Zelle als `niedrig`
ein, gemeinsam mit dem einen Institut, dessen Ausreißer nachprüfbar KORREKT
ist. Beide Fälle stehen jetzt als Test da, mit ihren echten Zahlen.
"""

from pathlib import Path
import math
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
    """Schweregrad aus zwei Maßen (#53).

    Die absolute Skala allein war auf Einheiten-Verwechslungen geeicht und für
    enge Zellen unbrauchbar: eine Quote in Prozent statt als Bruch zu melden
    sind genau 2 Größenordnungen und lag damit unter jeder Schwelle. Die
    absoluten Schwellen bleiben, weil sie für ihren Zweck richtig sind —
    dazugekommen ist der Abstand in Rumpfbreiten der eigenen Zelle.
    """

    def test_the_absolute_scale_is_unchanged(self):
        self.assertEqual(cp.severity(6.0), "hoch")     # volle Einheiten-Verwechslung
        self.assertEqual(cp.severity(4.0), "mittel")
        self.assertEqual(cp.severity(1.0), "niedrig")

    def test_a_narrow_cell_is_judged_by_its_own_body_width(self):
        """Der Fall, an dem die alte Skala scheiterte: 2 Größenordnungen sind
        absolut wenig und in einer Quotenzelle enorm."""
        self.assertEqual(cp.severity(2.0), "niedrig")            # ohne Rumpfbreite
        self.assertEqual(cp.severity(2.0, relative=5.3), "hoch")  # 5,3 Rumpfbreiten

    def test_the_higher_of_the_two_wins(self):
        """Ein absoluter Einheitenfehler bleibt `hoch`, auch wenn die Zelle so
        breit ist, dass er relativ unauffällig wirkt."""
        self.assertEqual(cp.severity(7.0, relative=0.5), "hoch")
        self.assertEqual(cp.severity(0.5, relative=7.0), "hoch")

    def test_a_missing_body_width_falls_back_to_the_absolute_scale(self):
        """Bei spread ~ 0 und bei den fachlichen Korridoren gibt es keine
        Rumpfbreite — dann darf nicht stillschweigend `niedrig` herauskommen,
        sondern es gilt das absolute Maß."""
        self.assertEqual(cp.severity(6.5, relative=None), "hoch")
        self.assertEqual(cp.severity(3.5, relative=None), "mittel")

    def test_the_calibration_separates_the_documented_cases(self):
        """Die Eichung stammt nicht aus einem Perzentil, sondern aus 20
        Befunden in KM1 r0050 c0010, deren Wahrheit unabhängig feststeht — am
        Kapital und am Gesamtrisikobetrag derselben Meldung.

        Rumpfbreite dieser Zelle: 0,35 Größenordnungen.
        """
        spread = 0.35
        # Beweisbare Artefakte: Quote in Prozent statt als Bruch gemeldet.
        # Der kleinste Fall ist RCI Banque mit 12,519 (Kapital/TREA = 0,1252).
        for dev in (1.83, 1.87, 2.16, 3.35, 8.97):
            self.assertEqual(cp.severity(dev, dev / spread), "hoch",
                             f"Artefakt bei {dev} Größenordnungen nicht als hoch erkannt")
        # Kommuninvest: 355 % CET1 sind korrekt — 12,026 Mrd SEK Kapital gegen
        # 3,385 Mrd SEK TREA. Ein Kommunalfinanzierer hält fast nur
        # nullgewichtete Aktiva. Das darf NICHT `hoch` werden.
        for dev in (1.28, 1.29, 1.31, 1.32):
            self.assertEqual(cp.severity(dev, dev / spread), "mittel",
                             "Kommuninvests nachprüfbar korrekter Wert wird als "
                             "hoch eingestuft — die Prüfung behauptet damit einen "
                             "Meldefehler, den es nicht gibt")


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

    def test_the_violated_bound_is_still_named(self):
        v = cp.ratio_violations(self.rule, [("k", 2e9, 1)])[0]   # 100x über hi
        self.assertEqual(v["bound"], self.rule["hi"])

    def test_deviation_is_measured_from_the_centre_not_the_edge(self):
        """Geändert mit #53, und zwar bewusst. Der Rand ist der falsche
        Nullpunkt: bei den Zell-Ausreißern ist der Bezug der Median, also die
        Mitte. Dieser Korridor ist 4,3 Größenordnungen weit, und ab seinem Rand
        gemessen erschien der schlimmste Fall im Bestand als `mittel`."""
        centre = math.sqrt(self.rule["lo"] * self.rule["hi"])
        v = cp.ratio_violations(self.rule, [("k", 2e9, 1)])[0]
        self.assertEqual(v["center"], centre)
        self.assertAlmostEqual(v["deviation_orders"],
                               math.log10(2e9 / centre), places=6)

    def test_the_worst_case_in_the_corpus_is_graded_high(self):
        """Rabobank: 11,7 Bio. EUR fixe Vergütung für 9 Vorstandsmitglieder,
        also 1,3 Bio. pro Kopf. Am Korridorrand gemessen waren das 4,81
        Größenordnungen und damit `mittel` — bei der öffentlich am meisten
        beachteten Kennzahl des Datensatzes (#18)."""
        v = cp.ratio_violations(self.rule, [("k", 1.1736e13, 9)])[0]
        self.assertEqual(v["severity"], "hoch")

    def test_a_value_just_outside_the_corridor_stays_low(self):
        """Die Gegenprobe: der Korridor ist bewusst weit gewählt, damit ein
        knappes Überschreiten keine Behauptung ist."""
        v = cp.ratio_violations(self.rule, [("k", 900.0, 1)])[0]
        self.assertEqual(v["severity"], "niedrig")

    def test_a_reported_zero_is_graded_on_its_merits_not_by_a_placeholder(self):
        """Vorher stand hier `dev = ... if ratio > 0 else SEVERITY_HIGH`: ein
        Platzhalter für einen undefinierten Logarithmus, der anschließend als
        gemessener Abstand eingestuft wurde. So bekam eine gemeldete Null
        `hoch` und Rabobanks 1,3 Bio. pro Kopf `mittel` — die Null stand eine
        Stufe über dem extremsten Wert im ganzen Bestand."""
        v = cp.ratio_violations(self.rule, [("k", 0.0, 9)])[0]
        self.assertEqual(v["severity"], "hoch")
        self.assertIsNone(v["deviation_orders"],
                          "ein nicht definierter Abstand wird wieder als Zahl "
                          "ausgewiesen")

    def test_a_zero_never_outranks_a_measured_extreme(self):
        rows = cp.ratio_violations(self.rule, [("null", 0.0, 9), ("rabo", 1.1736e13, 9)])
        by_key = {r["key"]: r for r in rows}
        self.assertIsNone(by_key["null"]["deviation_orders"])
        self.assertGreater(by_key["rabo"]["deviation_orders"], cp.SEVERITY_HIGH)


if __name__ == "__main__":
    unittest.main(verbosity=2)
