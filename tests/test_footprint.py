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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
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

    def test_a_scale_finding_invalidates_the_amount_not_the_quota(self):
        """Der Aufhänger von #83, und der Kern der Unterscheidung.

        ING Bank Śląski meldet am 2025-06-30 ein Gesamtexposure von 39.863 EUR
        und am 2025-12-31 von 41,8 Mrd — Faktor 10^6. Die Domestizitätsquote
        liegt bei 0,9820 gegen 0,9858, also praktisch unverändert.

        Ein gleichmässiger Skalenfehler kürzt sich in jedem Verhältnis heraus.
        Deshalb: `reliable` wird falsch (die Zeile ist nicht im Ganzen zu
        gebrauchen), aber `vorbehalt` nennt den Grund, damit eine reine
        Domestizitätsauswertung die Zeile zurückholen kann."""
        ohne = fp.footprint([("Poland", 98.2), ("Germany", 1.8)], "Poland")
        mit = fp.footprint([("Poland", 98.2), ("Germany", 1.8)], "Poland",
                           skalenbefund="skaliert")
        self.assertTrue(ohne["reliable"])
        self.assertFalse(mit["reliable"])
        self.assertEqual(mit["vorbehalt"], "skala")
        self.assertEqual(mit["skalenbefund"], "skaliert")
        # Und die Quoten sind Zeichen fuer Zeichen dieselben.
        for feld in ("domestic_share", "country_hhi", "x28_share", "n_countries"):
            with self.subTest(feld=feld):
                self.assertEqual(ohne[feld], mit[feld])

    def test_the_reason_names_every_reservation_not_just_one(self):
        """Bank of Valletta traegt beide: dominanter Residualbucket UND
        Skalenbefund. Wer nur den ersten sieht, haelt den Betrag fuer nutzbar."""
        r = fp.footprint([("Malta", 0.9), (None, 101.4)], "Malta",
                         skalenbefund="skaliert")
        self.assertEqual(r["vorbehalt"], "residual|skala")

    def test_an_unflagged_report_carries_no_reservation(self):
        """Eine leere Spalte muss auch wirklich leer sein — sonst filtert
        niemand danach."""
        r = fp.footprint([("Germany", 80.0), ("France", 20.0)], "Germany")
        self.assertEqual(r["vorbehalt"], "")
        self.assertEqual(r["skalenbefund"], "")

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


class SkalenmarkenTest(unittest.TestCase):
    """Welche Marken aus #83 hier ueberhaupt zaehlen — und warum beide Ebenen."""

    def _datei(self, zeilen):
        import csv as _csv
        import tempfile
        fh = tempfile.NamedTemporaryFile("w", suffix=".csv", newline="",
                                         delete=False, encoding="utf-8")
        w = _csv.DictWriter(fh, ["ebene", "lei", "scope", "refPeriod",
                                 "template_id", "urteil"])
        w.writeheader()
        w.writerows(zeilen)
        fh.close()
        return fh.name

    def test_the_template_level_of_ccyb1_counts(self):
        """Der Fall, den eine Filterung nur auf die Reportebene durchliesse:
        ING Bank Śląski ist reportweit unauffaellig (Versatz -0,15), skaliert
        ist genau `67.01.A` — die QUELLE dieser Datei."""
        pfad = self._datei([{"ebene": "template", "lei": "A", "scope": "CON",
                             "refPeriod": "2025-06-30", "template_id": "67.01.A",
                             "urteil": "skaliert"}])
        self.assertEqual(fp.lade_skalenmarken(pfad),
                         {("A", "CON", "2025-06-30"): "skaliert"})
        Path(pfad).unlink()

    def test_a_scaled_template_elsewhere_does_not_count(self):
        """Ein skaliertes `30.01` (Verguetung) sagt nichts ueber das
        Laenderexposure. Wer jede Templatemarke uebernimmt, verwirft Zeilen
        wegen eines Defekts in einer ganz anderen Tabelle."""
        pfad = self._datei([{"ebene": "template", "lei": "A", "scope": "CON",
                             "refPeriod": "2025-06-30", "template_id": "30.01",
                             "urteil": "skaliert"}])
        self.assertEqual(fp.lade_skalenmarken(pfad), {})
        Path(pfad).unlink()

    def test_a_suspicion_is_reservation_enough_for_an_amount(self):
        """Bei einer Zahl, die in keine Summe eingehen darf, reicht ein
        Verdacht. Das ist strenger als in check_plausibility.py — dort geht es
        um die Grundgesamtheit, hier um einen einzelnen Betrag."""
        pfad = self._datei([{"ebene": "report", "lei": "B", "scope": "CON",
                             "refPeriod": "2025-06-30", "template_id": "",
                             "urteil": "verdacht"}])
        self.assertEqual(fp.lade_skalenmarken(pfad),
                         {("B", "CON", "2025-06-30"): "verdacht"})
        Path(pfad).unlink()

    def test_scaled_beats_suspicion_when_both_apply(self):
        pfad = self._datei([
            {"ebene": "report", "lei": "C", "scope": "CON",
             "refPeriod": "2025-06-30", "template_id": "", "urteil": "verdacht"},
            {"ebene": "template", "lei": "C", "scope": "CON",
             "refPeriod": "2025-06-30", "template_id": "67.01.A",
             "urteil": "skaliert"}])
        self.assertEqual(fp.lade_skalenmarken(pfad),
                         {("C", "CON", "2025-06-30"): "skaliert"})
        Path(pfad).unlink()

    def test_a_missing_file_marks_nothing(self):
        """Fehlt scale_flags.csv, verhaelt sich die Auswertung wie vor #83 —
        statt stillschweigend jeden Report zu verdaechtigen."""
        self.assertEqual(fp.lade_skalenmarken(ROOT / "gibt_es_nicht.csv"), {})

    def test_the_scale_flags_are_built_before_the_footprint(self):
        """Laeuft build_footprint.py zuerst, findet es keine scale_flags.csv,
        markiert nichts — und SCHEITERT NICHT. Genau der Zustand, den #83
        beanstandet hat, waere damit zurueck."""
        pl = (ROOT / ".github" / "workflows" / "pipeline.yml").read_text(
            encoding="utf-8")
        self.assertLess(pl.index("scripts/build_report_scale.py"),
                        pl.index("scripts/build_footprint.py"))


class UnterTreaTest(unittest.TestCase):
    """Die vierte Pruefung (#83 Punkt 3) — und warum sie die dritte NICHT
    ersetzt.

    `scale_flags.csv` beurteilt den Report als GANZES. Ist er durchgehend
    skaliert, sind Zaehler und Nenner gleichermassen zu klein, und das
    Verhaeltnis CCyB1/TREA ist unauffaellig — gemessen liegen 20 der 22
    verdaechtigen Zeilen bei rund 0,0.

    Genau deshalb entkam dem Skalendetektor ein Fall: Bank GPB International
    meldet in CCyB1 215,30 EUR, waehrend KM1 im selben Report 1,52 Mrd traegt.
    Das ist ein TEMPLATE-lokaler Fehler, und nur der Vergleich innerhalb des
    Reports sieht ihn.
    """

    def test_a_template_local_scale_error_is_caught(self):
        """Der Fall, der die Pruefung erzwungen hat: −6,39 Groessenordnungen."""
        self.assertTrue(fp.unter_eigenem_trea(215.30, 1_521_014_423.27))

    def test_a_normal_report_passes(self):
        """CCyB1 liegt ueblicherweise UEBER dem TREA (Median +0,21) — die
        Pruefung darf dort nie anschlagen."""
        self.assertFalse(fp.unter_eigenem_trea(1.6e9, 1.0e9))
        self.assertFalse(fp.unter_eigenem_trea(5.0e7, 4.4e10))   # −2,9: knapp

    def test_a_uniformly_scaled_report_is_NOT_caught_here(self):
        """Der Beleg, dass die beiden Pruefungen komplementaer sind. Sind
        BEIDE Seiten um 10^6 zu klein, ist das Verhaeltnis normal — dafuer ist
        `skalenbefund` da, nicht diese Pruefung."""
        self.assertFalse(fp.unter_eigenem_trea(215.30, 1521.01))

    def test_a_missing_trea_claims_nothing(self):
        """Ohne Vergleichswert wird nichts behauptet (Arbeitsprinzip 3). Ein
        `True` hiesse, jeder Report ohne KM1 waere verdaechtig."""
        self.assertFalse(fp.unter_eigenem_trea(215.30, None))
        self.assertFalse(fp.unter_eigenem_trea(215.30, 0))
        self.assertFalse(fp.unter_eigenem_trea(0, 1e9))

    def test_the_threshold_is_actually_used(self):
        # 10^-5 unter dem TREA: bei 4 Ordnungen ein Treffer, bei 6 nicht.
        self.assertTrue(fp.unter_eigenem_trea(1e4, 1e9, ordnungen=4))
        self.assertFalse(fp.unter_eigenem_trea(1e4, 1e9, ordnungen=6))

    def test_the_reservation_is_its_own_name(self):
        """Nicht `skala`: dort ist der ganze Report verschoben und die QUOTEN
        bleiben gueltig. Hier ist nur dieses Template verschoben — dann stimmen
        auch die Quoten nicht mehr gegen den Rest des Reports."""
        f = fp.footprint([("Germany", 100.0), ("France", 115.3)], "Germany",
                         trea=1.5e9)
        self.assertIn("unter_trea", f["vorbehalt"])
        self.assertNotIn("skala", f["vorbehalt"])
        self.assertFalse(f["reliable"])

    def test_without_the_check_the_row_would_pass(self):
        """Die Gegenprobe: dieselben Zahlen ohne TREA sind unauffaellig. Ohne
        die vierte Pruefung stuende hier `reliable=true` — der Zustand, den
        #83 beanstandet."""
        f = fp.footprint([("Germany", 100.0), ("France", 115.3)], "Germany")
        self.assertTrue(f["reliable"])
        self.assertEqual(f["vorbehalt"], "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
