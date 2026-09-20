"""Ländercode-Verwechslungen über die Zeit (#59).

Der Test, den #17 strukturell nicht leisten kann: dort wird ein Wert gegen die
Population derselben Zelle geprüft, und 190 Mrd sind für BBVA plausibel. Falsch
ist das **Land**, also die Koordinate.

Drei Dinge halten die Tests fest:

1. **Anteile, nicht Beträge.** Sonst schlüge jeder Skalenfehler (#83) und jede
   Bilanzausweitung an. Ein Koordinatentausch lässt die Summe unverändert.
2. **Die Paarung ist die Signatur.** „Ein Land springt stark" findet vor allem
   Fälle, in denen das HEIMATLAND von null auf über 90 % springt — dort fehlte
   es im früheren Report. Erst das Verhältnis der Gegenbewegung trennt beides.
3. **Kein Werturteil.** Der Test sagt „passt nicht zum eigenen Vorquartal".
"""

from pathlib import Path
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "country_swap.csv"


class AnteileTest(unittest.TestCase):
    def setUp(self):
        import check_country_swap as c
        self.c = c

    def test_shares_sum_to_one(self):
        a = self.c.anteile({"ES": 3.0, "DK": 1.0})
        self.assertAlmostEqual(sum(a.values()), 1.0)
        self.assertAlmostEqual(a["ES"], 0.75)

    def test_a_pure_scale_error_does_not_change_the_shares(self):
        """Der Grund für Anteile statt Beträge: ein um Faktor 10^6 falsch
        gemeldeter Report (#83) hat dieselbe Geografie."""
        klein = self.c.anteile({"ES": 3.0, "DK": 1.0})
        gross = self.c.anteile({"ES": 3.0e6, "DK": 1.0e6})
        self.assertEqual(klein, gross)

    def test_a_negative_amount_is_not_a_weight(self):
        a = self.c.anteile({"ES": 3.0, "DK": -1.0})
        self.assertNotIn("DK", a)

    def test_nothing_positive_yields_nothing(self):
        self.assertEqual(self.c.anteile({"ES": 0.0}), {})


class PaarungTest(unittest.TestCase):
    def setUp(self):
        import check_country_swap as c
        self.c = c

    def test_an_exact_swap_pairs_perfectly(self):
        self.assertAlmostEqual(self.c.paarung(0.35, -0.35), 1.0)

    def test_a_lopsided_move_pairs_badly(self):
        """Kereskedelmi: Ungarn +99,6 % gegen Slowakei −52,0 %. Das ist keine
        Vertauschung, sondern ein Report, dem vorher das Heimatland fehlte."""
        self.assertLess(self.c.paarung(0.996, -0.52), 0.8)

    def test_it_is_symmetric(self):
        self.assertAlmostEqual(self.c.paarung(0.3, -0.4),
                               self.c.paarung(0.4, -0.3))

    def test_a_missing_side_pairs_at_zero(self):
        self.assertEqual(self.c.paarung(0.3, 0.0), 0.0)


class UrteilTest(unittest.TestCase):
    def setUp(self):
        import check_country_swap as c
        self.c = c

    def test_the_bbva_case_is_a_swap_suspect(self):
        """Der Fall, an dem #59 aufgefallen ist: Dänemark +36,8 % gegen
        Spanien −35,1 %, Dänemark vorher bei 0,0 %."""
        self.assertEqual(
            self.c.urteil_von(0.368, -0.351, 0.0, False), "verdacht_tausch")

    def test_the_home_country_appearing_is_not_a_swap(self):
        """Die wichtigste Abgrenzung. Dass das Heimatland von null auf über
        90 % springt, heisst fast immer, dass der frühere Report es nicht
        enthielt. Als Verwechslung gemeldet wäre das ein Befund, den es nicht
        gibt — und er träfe sieben Institute."""
        self.assertEqual(
            self.c.urteil_von(0.947, -0.308, 0.0, True), "heimatland_ergaenzt")

    def test_a_loosely_paired_move_is_only_a_shift(self):
        self.assertEqual(
            self.c.urteil_von(0.50, -0.10, 0.0, False), "verschiebung")

    def test_a_country_that_was_already_there_did_not_appear(self):
        """Die zweite Bedingung des Issues: das Land muss NEU auftauchen. Ein
        Land, das vorher schon ein Drittel trug, ist gewachsen."""
        self.assertEqual(
            self.c.urteil_von(0.30, -0.30, 0.33, False), "verschiebung")

    def test_a_small_move_is_no_finding_at_all(self):
        self.assertEqual(self.c.urteil_von(0.02, -0.02, 0.0, False), "")

    def test_the_thresholds_are_actually_used(self):
        self.assertEqual(
            self.c.urteil_von(0.30, -0.30, 0.0, False, min_sprung=0.5), "")
        self.assertEqual(
            self.c.urteil_von(0.30, -0.25, 0.0, False, min_paarung=0.99),
            "verschiebung")


class VergleichTest(unittest.TestCase):
    def setUp(self):
        import check_country_swap as c
        self.c = c

    def test_the_largest_move_in_each_direction_is_taken(self):
        v = self.c.vergleiche({"ES": 0.9, "DK": 0.0, "FR": 0.1},
                              {"ES": 0.1, "DK": 0.8, "FR": 0.1})
        land_auf, d_auf, vorher, land_ab, d_ab = v
        self.assertEqual(land_auf, "DK")
        self.assertEqual(land_ab, "ES")
        self.assertAlmostEqual(vorher, 0.0)

    def test_a_country_only_present_afterwards_counts_as_zero_before(self):
        """„Fehlt" heisst hier tatsächlich null: das Land war im Vorquartal
        nicht gemeldet, sein Anteil war also nicht unbekannt, sondern keiner."""
        v = self.c.vergleiche({"ES": 1.0}, {"ES": 0.6, "DK": 0.4})
        self.assertEqual(v[0], "DK")
        self.assertAlmostEqual(v[2], 0.0)

    def test_an_unchanged_profile_yields_nothing(self):
        self.assertIsNone(self.c.vergleiche({"ES": 1.0}, {"ES": 1.0}))


class PaareTest(unittest.TestCase):
    def setUp(self):
        import check_country_swap as c
        self.c = c

    def test_consecutive_dates_are_paired(self):
        p = self.c.paare({("A", "CON", "2025-06-30"): {},
                          ("A", "CON", "2025-12-31"): {},
                          ("A", "CON", "2026-03-31"): {}})
        self.assertEqual(p, [("A", "CON", "2025-06-30", "2025-12-31"),
                             ("A", "CON", "2025-12-31", "2026-03-31")])

    def test_a_filer_is_never_compared_with_another_one(self):
        """Zwischen zwei Instituten wäre eine andere Länderverteilung kein
        Befund, sondern der Normalfall."""
        p = self.c.paare({("A", "CON", "2025-06-30"): {},
                          ("B", "CON", "2025-12-31"): {}})
        self.assertEqual(p, [])

    def test_the_two_scopes_are_kept_apart(self):
        """CON und IND sind nicht dasselbe Institut (DISCLAIMER.md)."""
        p = self.c.paare({("A", "CON", "2025-06-30"): {},
                          ("A", "IND", "2025-12-31"): {}})
        self.assertEqual(p, [])


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        if not OUT.exists():
            self.skipTest("country_swap.csv nicht gebaut")
        with OUT.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))

    def test_the_check_actually_runs_over_something(self):
        self.assertTrue(self.rows, "keine einzige Zeile — der Test liefe über "
                                   "nichts und meldete Erfolg")

    def test_the_bbva_case_is_still_found(self):
        """Der Fall, an dem das Issue aufgefallen ist. Fällt er heraus, misst
        die Prüfung etwas anderes als das, wofür sie gebaut wurde."""
        bbva = [r for r in self.rows
                if "Bilbao" in r["bank_name"] and r["urteil"] == "verdacht_tausch"]
        self.assertTrue(bbva, "BBVA/Dänemark nicht mehr als Tauschverdacht")

    def test_no_swap_suspect_rises_in_its_own_home_country(self):
        for r in self.rows:
            if r["urteil"] == "verdacht_tausch":
                with self.subTest(bank=r["bank_name"]):
                    self.assertEqual(r["auf_ist_heimatland"], "nein")

    def test_every_swap_suspect_is_tightly_paired(self):
        import check_country_swap as c
        for r in self.rows:
            if r["urteil"] == "verdacht_tausch":
                with self.subTest(bank=r["bank_name"]):
                    self.assertGreaterEqual(float(r["paarung"]), c.MIN_PAARUNG)
                    self.assertLessEqual(float(r["anteil_vorher"]), c.MAX_VORHER)

    def test_the_two_directions_really_are_opposite(self):
        for r in self.rows:
            with self.subTest(bank=r["bank_name"]):
                self.assertGreater(float(r["delta_auf"]), 0)
                self.assertLess(float(r["delta_ab"]), 0)
                self.assertNotEqual(r["land_auf"], r["land_ab"])

    def test_a_finding_never_compares_a_date_with_itself(self):
        for r in self.rows:
            self.assertLess(r["von"], r["bis"])

    def test_the_order_is_stable(self):
        k = [(r["von"], r["lei"], r["scope"]) for r in self.rows]
        self.assertEqual(k, sorted(k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
