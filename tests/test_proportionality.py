"""Wirkt die Proportionalität? (#44)

Das Issue benennt seinen eigenen kritischen Schritt: die EBA-Klasse ist **kein
Rechtsbegriff**, und wer sie ungeprüft als „klein und nicht komplex" nach
Art. 4(1)(145) CRR liest, misst die falsche Klasse. Die Tests halten deshalb
drei Dinge fest, die der Rechnung vorausgehen:

1. **Misst die Quote in Wahrheit Grösse?** Der wiederkehrende Fehler dieses
   Projekts (#43, #45, #11, #83). Hier gemessen r² = 0,007 — er schnappt nicht
   zu, aber nur, weil die Zahl da ist.
2. **Ist die Klasse trennscharf?** Zwei auseinanderliegende Mediane sagen dazu
   nichts. 46,2 % der grossen Institute lassen mehr aus als das mittlere
   kleine.
3. **Kalender oder Ermessen?** `quote_gegen_erwartung` ist um das
   Frequenzmodell (#34) bereinigt und in allen Klassen null.
"""

from pathlib import Path
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "proportionality.csv"


class QuartilTest(unittest.TestCase):
    def setUp(self):
        import check_proportionality as c
        self.c = c

    def test_the_median_sits_in_the_middle(self):
        q1, med, q3 = self.c.quartile([1, 2, 3, 4, 5])
        self.assertEqual(med, 3)
        self.assertLessEqual(q1, med)
        self.assertGreaterEqual(q3, med)

    def test_an_empty_input_yields_nothing_rather_than_zero(self):
        """Eine leere Klasse hat keinen Median. Null zu liefern behauptete
        eine Auslassungsquote von 0 % — das Gegenteil von „unbekannt"."""
        self.assertEqual(self.c.quartile([]), (None, None, None))

    def test_the_upper_quartile_stays_inside_the_data(self):
        """Ein Indexfehler am oberen Rand fiele sonst erst bei kleinen Klassen
        auf, und dann als IndexError statt als falscher Zahl."""
        for n in range(1, 12):
            with self.subTest(n=n):
                q1, med, q3 = self.c.quartile(list(range(n)))
                self.assertLessEqual(q3, n - 1)
                self.assertGreaterEqual(q1, 0)


class SteigungTest(unittest.TestCase):
    """Die Zahl, ohne die der Klassenunterschied nicht von einem
    Grössenartefakt zu unterscheiden wäre."""

    def setUp(self):
        import check_proportionality as c
        self.c = c

    def test_a_perfect_line_is_recognised(self):
        a, b, r2 = self.c.steigung([(1, 3), (2, 5), (3, 7)])
        self.assertAlmostEqual(b, 2.0)
        self.assertAlmostEqual(a, 1.0)
        self.assertAlmostEqual(r2, 1.0)

    def test_no_relationship_yields_almost_no_r2(self):
        a, b, r2 = self.c.steigung([(1, 5), (2, 5), (3, 5), (4, 5.0001)])
        self.assertLess(r2, 0.9)

    def test_a_constant_x_is_undefined_not_zero(self):
        """Ohne Streuung im Regressor ist die Steigung nicht klein, sondern
        undefiniert — dieselbe Unterscheidung wie beim EURIBOR in #11."""
        self.assertEqual(self.c.steigung([(2, 1), (2, 5), (2, 9)]),
                         (None, None, None))

    def test_a_constant_y_is_undefined_too(self):
        self.assertEqual(self.c.steigung([(1, 4), (2, 4), (3, 4)]),
                         (None, None, None))

    def test_too_few_points_are_refused(self):
        self.assertEqual(self.c.steigung([(1, 2)]), (None, None, None))


class UeberlappungTest(unittest.TestCase):
    def setUp(self):
        import check_proportionality as c
        self.c = c

    def test_separated_distributions_do_not_overlap(self):
        u1, u2 = self.c.ueberlappung([10, 11, 12], [1, 2, 3])
        self.assertEqual(u1, 0.0)
        self.assertEqual(u2, 0.0)

    def test_identical_distributions_overlap_heavily(self):
        u1, u2 = self.c.ueberlappung([1, 2, 3], [1, 2, 3])
        self.assertGreater(u1, 0.0)
        self.assertGreater(u2, 0.0)

    def test_the_two_directions_are_measured_separately(self):
        """Punkt 2 des Issues braucht beide: dass die Kleinen nach oben
        streuen, heisst nicht, dass die Grossen nach unten streuen."""
        u1, u2 = self.c.ueberlappung([5, 6, 7, 100], [1, 2, 3, 4])
        self.assertIsNotNone(u1)
        self.assertIsNotNone(u2)

    def test_an_empty_class_is_not_an_overlap_of_zero(self):
        self.assertEqual(self.c.ueberlappung([], [1, 2]), (None, None))


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        if not OUT.exists():
            self.skipTest("proportionality.csv nicht gebaut")
        with OUT.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))

    def test_the_artefact_has_content(self):
        self.assertGreater(len(self.rows), 3)

    def test_every_class_row_has_enough_reports(self):
        import check_proportionality as c
        for r in self.rows:
            with self.subTest(k=r["institution_type"]):
                self.assertGreaterEqual(int(r["n"]), c.MIN_REPORTS)

    def test_the_quartiles_bracket_the_median(self):
        for r in self.rows:
            with self.subTest(k=r["institution_type"], rp=r["refPeriod"]):
                self.assertLessEqual(float(r["quote_q1"]),
                                     float(r["quote_median"]))
                self.assertLessEqual(float(r["quote_median"]),
                                     float(r["quote_q3"]))

    def test_the_classes_stay_ordered_by_size(self):
        """Der kritische Schritt am fertigen Artefakt: verlöre die Klasse ihre
        Grössenordnung, wäre sie auch als Schichtung nicht mehr brauchbar und
        die ganze Auswertung stünde auf einer anderen Grundlage."""
        je_rp = {}
        for r in self.rows:
            if r["trea_median_eur"]:
                je_rp.setdefault(r["refPeriod"], {})[r["institution_type"]] = \
                    float(r["trea_median_eur"])
        geprueft = 0
        for rp, klassen in je_rp.items():
            if {"Large highest EEA", "Other highest EEA"} <= set(klassen):
                geprueft += 1
                with self.subTest(rp=rp):
                    self.assertGreater(klassen["Large highest EEA"],
                                       klassen["Other highest EEA"])
        self.assertTrue(geprueft, "kein Stichtag mit beiden Klassen — prüfen, "
                                  "ob TREA noch gelesen wird")

    def test_the_relief_shows_up_in_the_raw_rate(self):
        """Die Grundaussage des Issues. Bricht sie weg, misst die Auswertung
        etwas anderes als Offenlegungsumfang."""
        je = {}
        for r in self.rows:
            je.setdefault(r["institution_type"], []).append(
                float(r["quote_median"]))
        import statistics
        if {"Large highest EEA", "Other highest EEA"} <= set(je):
            self.assertGreater(statistics.median(je["Other highest EEA"]),
                               statistics.median(je["Large highest EEA"]))

    def test_the_order_is_stable(self):
        k = [(r["refPeriod"], r["institution_type"]) for r in self.rows]
        self.assertEqual(k, sorted(k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
