"""Die Kreditverschlechterungs-Kette über Templates hinweg (#16).

Vier Dinge halten die Tests fest:

1. **Der Frühwarn-Indikator hat eine eingebaute Falle.** Roh gerechnet führt
   Agence France Locale die Liste mit dem 377-fachen an — bei einer NPL-Quote
   von 0,00 %. Das ist eine Division durch fast nichts, dieselbe Falle wie der
   AIB-Fall in `check_plausibility`.
2. **Alle drei Bedingungen sind nötig.** Ohne die dritte (NPL unter dem
   Peer-Median) stünden dort Institute, deren Schwierigkeiten längst in der
   NPL-Quote stehen — eine Spätmeldung, keine Frühwarnung.
3. **Die Wertberichtigung hat kein einheitliches Vorzeichen.** 344 Reports
   melden sie negativ, 20 positiv. Das Skript rechnet mit dem Betrag und
   schreibt die Konvention daneben, statt sich für eine Lesart zu entscheiden.
4. **CON und IND werden nicht gemischt.** Ihre NPL-Mediane liegen messbar
   auseinander: 2,36 % gegen 1,91 %.
"""

from pathlib import Path
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "credit_chain.csv"


class QuoteTest(unittest.TestCase):
    def setUp(self):
        import build_credit_chain as c
        self.c = c

    def test_a_plain_share(self):
        self.assertAlmostEqual(self.c.quote(2.0, 8.0), 0.25)

    def test_a_missing_numerator_is_not_zero(self):
        """Eine Null wäre eine Aussage („kein notleidendes Exposure"), wo in
        Wahrheit keine vorliegt."""
        self.assertIsNone(self.c.quote(None, 8.0))

    def test_a_missing_denominator_is_not_zero_either(self):
        self.assertIsNone(self.c.quote(2.0, 0))
        self.assertIsNone(self.c.quote(2.0, None))


class VorzeichenTest(unittest.TestCase):
    def setUp(self):
        import build_credit_chain as c
        self.c = c

    def test_the_usual_convention_is_negative(self):
        self.assertEqual(self.c.vorzeichen(-500.0), "negativ")

    def test_a_positive_value_is_recorded_not_silently_flipped(self):
        """20 von 369 Reports melden sie positiv. Ob das eine andere
        Konvention ist oder ein Vorzeichenfehler, entscheidet das Skript
        nicht — aber es verschweigt es auch nicht."""
        self.assertEqual(self.c.vorzeichen(500.0), "positiv")

    def test_a_missing_value_has_no_convention(self):
        self.assertEqual(self.c.vorzeichen(None), "")


class VerhaeltnisTest(unittest.TestCase):
    def setUp(self):
        import build_credit_chain as c
        self.c = c

    def test_the_plain_ratio(self):
        self.assertAlmostEqual(self.c.verhaeltnis(0.0466, 0.0220), 2.118, 3)

    def test_a_vanishing_npl_ratio_yields_nothing(self):
        """Agence France Locale: NPL 0,00 %, Vorstufe 0,75 %. Ein Verhältnis
        von 377 ist dort kein grosses Signal, sondern gar keines."""
        self.assertIsNone(self.c.verhaeltnis(0.0075, 0.0))
        self.assertIsNone(self.c.verhaeltnis(0.0075, None))

    def test_a_missing_forbearance_yields_nothing(self):
        self.assertIsNone(self.c.verhaeltnis(None, 0.02))


class FruehwarnungTest(unittest.TestCase):
    def setUp(self):
        import build_credit_chain as c
        self.c = c

    def test_the_ikb_pattern_is_caught(self):
        """Der Fall, den das Issue selbst nennt: 2,20 % NPL, 4,66 % Vorstufe —
        mehr als das Doppelte in der Vorstufe."""
        self.assertEqual(
            self.c.fruehwarnung_von(0.0466, 2.12, True), "ja")

    def test_an_immaterial_forbearance_is_no_warning(self):
        """Der Wesentlichkeitsboden. Ohne ihn führte ein Haus mit 0,09 %
        Vorstufe und verschwindender NPL-Quote die Liste an."""
        self.assertEqual(
            self.c.fruehwarnung_von(0.0009, 6.77, True), "nein")

    def test_an_ordinary_ratio_is_no_warning(self):
        self.assertEqual(
            self.c.fruehwarnung_von(0.03, 0.28, True), "nein")

    def test_a_high_npl_ratio_is_a_late_report_not_an_early_warning(self):
        """Die dritte Bedingung, und sie trägt die ganze Aussage: das Problem
        muss in der etablierten Kennzahl NOCH NICHT sichtbar sein."""
        self.assertEqual(
            self.c.fruehwarnung_von(0.0466, 2.12, False), "nein")

    def test_missing_inputs_never_become_a_warning(self):
        self.assertEqual(self.c.fruehwarnung_von(None, 2.0, True), "nein")
        self.assertEqual(self.c.fruehwarnung_von(0.05, None, True), "nein")

    def test_the_thresholds_are_actually_used(self):
        self.assertEqual(
            self.c.fruehwarnung_von(0.0466, 2.12, True, min_vorstufe=0.10),
            "nein")
        self.assertEqual(
            self.c.fruehwarnung_von(0.0466, 2.12, True, min_verhaeltnis=3.0),
            "nein")


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        if not OUT.exists():
            self.skipTest("credit_chain.csv nicht gebaut")
        with OUT.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))

    def test_the_chain_links_a_real_population(self):
        """Drei Templates über zwei Joins. Bricht einer, fällt die Zeilenzahl
        ein und die Auswertung liefe über fast nichts."""
        self.assertGreater(len(self.rows), 300)

    def test_the_prototype_of_the_issue_still_reproduces(self):
        """Median-NPL 2,36 % und Vorstufe 0,63 % laut Issue. Weicht das stark
        ab, misst die Kette etwas anderes als damals."""
        import statistics
        akt = [r for r in self.rows if r["refPeriod"] == "2025-12-31"]
        npl = [float(r["npl_quote"]) for r in akt if r["npl_quote"]]
        self.assertAlmostEqual(statistics.median(npl), 0.0236, delta=0.004)

    def test_the_npl_ratio_is_a_ratio(self):
        for r in self.rows:
            if r["npl_quote"]:
                with self.subTest(bank=r["bank_name"]):
                    self.assertGreaterEqual(float(r["npl_quote"]), 0.0)
                    self.assertLessEqual(float(r["npl_quote"]), 1.0)

    def test_every_warning_clears_all_three_conditions(self):
        import build_credit_chain as c
        for r in self.rows:
            if r["fruehwarnung"] == "ja":
                with self.subTest(bank=r["bank_name"]):
                    self.assertGreaterEqual(float(r["vorstufe_quote"]),
                                            c.MIN_VORSTUFE)
                    self.assertGreaterEqual(float(r["vorstufe_verhaeltnis"]),
                                            c.MIN_VERHAELTNIS)
                    self.assertEqual(r["npl_unter_median"], "ja")

    def test_the_warning_list_is_neither_empty_nor_everything(self):
        """Eine leere Liste liefe über nichts; eine, die halb so lang ist wie
        der Bestand, misst keine Auffälligkeit mehr."""
        warn = [r for r in self.rows if r["fruehwarnung"] == "ja"]
        self.assertTrue(warn)
        self.assertLess(len(warn), len(self.rows) * 0.1)

    def test_the_named_institutions_of_the_issue_are_found(self):
        namen = {r["bank_name"] for r in self.rows
                 if r["fruehwarnung"] == "ja"}
        for gesucht in ("IKB", "HANDLOWY"):
            with self.subTest(bank=gesucht):
                self.assertTrue(any(gesucht.lower() in n.lower()
                                    for n in namen))

    def test_the_coverage_ratio_uses_the_magnitude(self):
        """Gerechnet wird mit dem Betrag — sonst wäre die Deckungsquote bei
        344 der 369 Reports negativ.

        Null ist dabei erlaubt und kein Rechenfehler: Merkanti Bank meldet
        0,8 Mio EUR notleidende Kredite und **keine** Wertberichtigung
        darauf. Ein strengeres `> 0` hätte diesen echten Fall zu einem
        Testfehler gemacht.
        """
        for r in self.rows:
            if r["deckungsquote"]:
                with self.subTest(bank=r["bank_name"]):
                    self.assertGreaterEqual(float(r["deckungsquote"]), 0.0)
                    self.assertLess(float(r["deckungsquote"]), 2.0)

    def test_both_sign_conventions_occur(self):
        """Gegenprobe zur Spalte: gäbe es nur eine Konvention, wäre sie
        überflüssig — und ihr Verschwinden fiele niemandem auf."""
        vz = {r["wb_vorzeichen"] for r in self.rows if r["wb_vorzeichen"]}
        self.assertIn("negativ", vz)
        self.assertIn("positiv", vz)

    def test_the_order_is_stable(self):
        k = [(r["refPeriod"], r["lei"], r["scope"]) for r in self.rows]
        self.assertEqual(k, sorted(k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
