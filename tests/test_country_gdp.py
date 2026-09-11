"""BIP je Land als deskriptive Kontextspalte (#14).

## Die Abgrenzung ist der Kern des Issues

BIP **nicht** als Korrelations-Regressor: der Regressor waere auf Laenderebene
konstant, die effektive Stichprobe also ~30 statt ~450, und Laender mit hohem BIP
haben strukturell andere Bankensysteme. Ein Befund „hohes BIP ↔ hoehere
Kapitalquote" waere vermutlich ein Groessenklassen-Effekt.

Sondern zur **Normierung**: ein Laenderexposure von 5 Mrd EUR bedeutet in Malta
etwas anderes als in Deutschland.

## Join ueber ISO-Code, nicht ueber den Namen

Das Issue warnt vor der Alias-Falle („Czech" vs „Czechia"). Gemessen waere sie
teuer gewesen: von 216 gemeinsamen Codes tragen **32** bei der Weltbank einen
anderen Namen als bei uns — „Korea, Rep." gegen „Korea, Republic of", „Lao PDR"
gegen „Lao People's Democratic Republic". Ein Namensabgleich haette sie verloren.

## Abdeckung

    Laender in geo_names.csv      250
      davon mit BIP-Wert          212
    Exposure mit Host-Staat   172,0 Bio EUR
      davon mit BIP-Wert       99,68 %

Die Luecken sind Offshore-Plaetze (Britische Jungferninseln, Jersey, Guernsey)
und Taiwan — fuer die veroeffentlicht die Weltbank kein BIP. Bezeichnenderweise
sind das genau die Orte, an denen ein Verhaeltnis Exposure/BIP ohnehin nichts
aussagte.
"""

from pathlib import Path
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

GDP = ROOT / "codebook" / "country_gdp.csv"
GEO = ROOT / "codebook" / "geo_names.csv"


def zeilen():
    if not GDP.exists():
        return []
    with GDP.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class TabelleTest(unittest.TestCase):
    def setUp(self):
        self.rows = zeilen()
        if not self.rows:
            self.skipTest("country_gdp.csv fehlt")

    def test_every_code_is_one_we_actually_use(self):
        """Ein BIP fuer ein Land, das der Bestand nicht kennt, ist tote Pflege —
        und ein Hinweis darauf, dass ein Aggregat durchgerutscht ist."""
        with GEO.open(encoding="utf-8") as fh:
            geo = {r["code"].upper() for r in csv.DictReader(fh)}
        fremd = sorted({r["iso2"] for r in self.rows} - geo)
        self.assertEqual(fremd, [], f"Codes ausserhalb geo_names.csv: {fremd}")

    def test_no_world_bank_aggregate_slipped_through(self):
        """'Arab World', 'Euro area' und Co. tragen Pseudo-Codes wie 1A oder Z4.
        Stuende so etwas drin, waere ein 'Land' die Summe anderer."""
        for r in self.rows:
            with self.subTest(code=r["iso2"]):
                self.assertRegex(r["iso2"], r"^[A-Z]{2}$")

    def test_the_name_is_ours_not_the_world_banks(self):
        """Der Join in die Auswertung laeuft ueber unseren Laendernamen. Stuende
        hier 'Korea, Rep.', traefe er nichts."""
        with GEO.open(encoding="utf-8") as fh:
            geo = {r["code"].upper(): r["name"] for r in csv.DictReader(fh)}
        for r in self.rows[:50]:
            with self.subTest(code=r["iso2"]):
                self.assertEqual(r["country"], geo[r["iso2"]])

    def test_the_year_travels_with_the_value(self):
        """Je Land der juengste verfuegbare Wert — ohne das Jahr waere nicht
        erkennbar, worauf sich die Zahl bezieht."""
        for r in self.rows:
            with self.subTest(code=r["iso2"]):
                self.assertTrue(2015 <= int(r["year"]) <= 2030)
                self.assertGreater(float(r["gdp_usd"]), 0)

    def test_the_big_economies_are_there(self):
        """Ohne sie waere die Normierung fuer den Grossteil des Exposures
        wertlos."""
        drin = {r["country"] for r in self.rows}
        for land in ("Germany", "France", "United States", "United Kingdom",
                     "Netherlands", "Spain", "Italy", "Sweden"):
            with self.subTest(land=land):
                self.assertIn(land, drin)

    def test_the_order_is_stable(self):
        """Sortiert nach Code, damit ein Neuabruf keinen Rausch-Diff erzeugt."""
        codes = [r["iso2"] for r in self.rows]
        self.assertEqual(codes, sorted(codes))


class SkriptTest(unittest.TestCase):
    def setUp(self):
        import fetch_country_gdp as f
        self.f = f
        self.src = (ROOT / "scripts" / "fetch_country_gdp.py").read_text(encoding="utf-8")

    def test_aggregates_are_excluded_by_the_join_not_by_a_region_field(self):
        """Der erste Versuch filterte ueber ein Regionsfeld — das liefert dieser
        Endpunkt gar nicht, und der Filter warf ALLES weg (0 von 250)."""
        self.assertNotIn('"region"', self.src)
        self.assertIn("code not in erlaubt", self.src)

    def test_it_keeps_the_newest_year_per_country(self):
        rows = [
            {"country": {"id": "DE", "value": "Germany"}, "date": "2020", "value": 1.0},
            {"country": {"id": "DE", "value": "Germany"}, "date": "2024", "value": 2.0},
            {"country": {"id": "XX", "value": "Nirgendwo"}, "date": "2024", "value": 9.0},
        ]
        best = self.f.juengste_werte(rows, {"DE"})
        self.assertEqual(best["DE"][0], 2024)
        self.assertEqual(best["DE"][1], 2.0)
        self.assertNotIn("XX", best, "Land ausserhalb geo_names.csv aufgenommen")

    def test_a_missing_value_is_not_a_zero(self):
        """`None` heisst 'nicht veroeffentlicht'. Als 0 gelesen erzeugte es ein
        Land ohne Wirtschaft — und eine Division durch null."""
        rows = [{"country": {"id": "DE", "value": "Germany"}, "date": "2024",
                 "value": None}]
        self.assertEqual(self.f.juengste_werte(rows, {"DE"}), {})

    def test_a_paginated_answer_is_refused(self):
        """Ueber mehrere Seiten verteilt fehlten stillschweigend Laender."""
        self.assertIn("pages", self.src)
        self.assertIn("raise SystemExit", self.src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
