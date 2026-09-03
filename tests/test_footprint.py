"""Tests für scripts/build_footprint.py — Footprint-Kennzahlen (#12).

Die Kennzahlen sind einfach zu rechnen und leicht falsch zu rechnen. Drei
Fallen sind an den Daten belegt und hier festgehalten, weil sie das Ergebnis
still verfälschen statt einen Fehler zu erzeugen:

  (a) `x1` ist die Summenzeile über alle Länder, kein Land. Median
      x1/(Rest) = 1,0000 über 137 Reports — mitsummieren verdoppelt.
      Gefiltert wird in SQL; hier wird geprüft, dass die reine Funktion mit
      bereits gefilterten Zeilen arbeitet.
  (b) `x28` ist der Residualbucket "übrige Länder". Er ist echtes Exposure und
      gehört in den NENNER, zählt aber nicht als Land. Median-Anteil 0,5 %,
      aber 9 Reports liegen über 90 %.
  (c) "Czech" (entity_meta) vs. "Czechia" (geo_names): ohne Normalisierung
      fallen 8 tschechische Institute still auf 0 % Heimatanteil.
"""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_footprint as fp  # noqa: E402


class HHITest(unittest.TestCase):
    def test_single_country_is_full_concentration(self):
        self.assertEqual(fp.hhi([100.0]), 1.0)

    def test_even_split_is_one_over_n(self):
        self.assertAlmostEqual(fp.hhi([25.0, 25.0, 25.0, 25.0]), 0.25)

    def test_many_countries_with_one_dominant_stays_concentrated(self):
        """Der Grund, warum HHI und nicht die Länderzahl: 30 Länder mit 95 % in
        einem davon sind nicht diversifiziert."""
        values = [95.0] + [5.0 / 29] * 29
        self.assertGreater(fp.hhi(values), 0.9)

    def test_negative_amounts_count_by_size(self):
        """Handelsbuch-Nettopositionen können negativ sein — für die
        Konzentration zählt die Größe, nicht das Vorzeichen."""
        self.assertEqual(fp.hhi([-100.0]), 1.0)

    def test_no_exposure_yields_no_number(self):
        self.assertIsNone(fp.hhi([]))
        self.assertIsNone(fp.hhi([0.0, 0.0]))


class NormalizeCountryTest(unittest.TestCase):
    def test_czech_alias(self):
        """Falle (c): ohne das fielen Česká spořitelna, MONETA, UniCredit CZ
        und J&T still auf 0 % Heimatanteil."""
        self.assertEqual(fp.normalize_country("Czech"), "Czechia")

    def test_known_name_passes_through(self):
        self.assertEqual(fp.normalize_country("Germany"), "Germany")

    def test_none_and_whitespace(self):
        self.assertEqual(fp.normalize_country(None), "")
        self.assertEqual(fp.normalize_country("  Spain  "), "Spain")


class FootprintTest(unittest.TestCase):
    def test_plain_domestic_share(self):
        r = fp.footprint([("Germany", 80.0), ("France", 20.0)], "Germany")
        self.assertAlmostEqual(r["domestic_share"], 0.8)
        self.assertEqual(r["n_countries"], 2)
        self.assertEqual(r["largest_country"], "Germany")
        self.assertTrue(r["reliable"])

    def test_residual_bucket_counts_in_the_denominator(self):
        """Falle (b): x28 IST Exposure — es fehlt nur die Länderangabe. Aus dem
        Nenner gelassen, überschätzte es den Heimatanteil."""
        r = fp.footprint([("Germany", 50.0), (None, 50.0)], "Germany")
        self.assertAlmostEqual(r["domestic_share"], 0.5)
        self.assertAlmostEqual(r["x28_share"], 0.5)
        self.assertEqual(r["n_countries"], 1, "x28 ist kein Land")

    def test_dominant_residual_makes_the_quota_unreliable(self):
        """Banco BPM: 101,4 Mrd im Residualbucket gegen 0,9 Mrd im größten
        benannten Land. Ohne Flag erschiene das Institut als '1 % heimisch'."""
        r = fp.footprint([("Italy", 0.9), (None, 101.4)], "Italy")
        self.assertFalse(r["reliable"])
        self.assertGreater(r["x28_share"], fp.X28_UNRELIABLE)

    def test_czech_home_country_resolves(self):
        r = fp.footprint([("Czechia", 90.0), ("Slovakia", 10.0)], "Czech")
        self.assertAlmostEqual(r["domestic_share"], 0.9)

    def test_missing_home_country_is_not_zero_percent(self):
        """Kein Heimatland in den Stammdaten heißt NICHT '0 % heimisch' — das
        wäre eine Aussage, die die Daten nicht hergeben."""
        r = fp.footprint([("France", 100.0)], "")
        self.assertFalse(r["reliable"])

    def test_largest_country_differs_from_seat(self):
        """67 von 377 Reports. Santander meldet mehr in UK als in Spanien; die
        Spalte macht den Unterschied sichtbar, statt ihn in einer niedrigen
        Quote zu verstecken."""
        r = fp.footprint([("Spain", 221.0), ("United Kingdom", 271.0)], "Spain")
        self.assertEqual(r["largest_country"], "United Kingdom")
        self.assertEqual(r["home_country"], "Spain")

    def test_largest_country_ties_break_deterministically(self):
        a = fp.footprint([("Austria", 50.0), ("Belgium", 50.0)], "Austria")
        b = fp.footprint([("Belgium", 50.0), ("Austria", 50.0)], "Austria")
        self.assertEqual(a["largest_country"], b["largest_country"])

    def test_same_country_twice_is_summed_not_counted_twice(self):
        r = fp.footprint([("Germany", 30.0), ("Germany", 50.0), ("Italy", 20.0)],
                         "Germany")
        self.assertEqual(r["n_countries"], 2)
        self.assertAlmostEqual(r["domestic_share"], 0.8)

    def test_no_exposure_yields_nothing(self):
        self.assertIsNone(fp.footprint([], "Germany"))
        self.assertIsNone(fp.footprint([("Germany", 0.0)], "Germany"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
