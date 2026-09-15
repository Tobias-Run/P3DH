"""Hängen Bankattribute am Heimatland? (#11) — ein negatives Ergebnis absichern.

Ein negatives Ergebnis braucht mehr Tests als ein positives, nicht weniger.
„Kein Zusammenhang gefunden" ist von „falsch gemessen" nur durch die
Gegenproben zu unterscheiden, und ein kaputtes Skript liefert dieselbe Aussage
wie ein funktionierendes.

## Die Konstruktion, auf die es ankommt

Zuerst die **Obergrenze**, dann der Regressor. Eine Kennzahl des Heimatlands ist
für alle Institute desselben Landes identisch und kann deshalb nur den Teil der
Streuung erklären, der ZWISCHEN Ländern liegt. Gemessen sind das 31,8 % — also
R² <= 0,318 für jede denkbare Länderkennzahl, auch für noch nicht erhobene.

Das BIP erreicht r² = 0,0013, also **0,4 % des Erreichbaren.** Ohne die
Obergrenze wäre diese Zahl nicht einzuordnen.

## Die vier Fallen

1. **Pseudoreplikation.** `footprint.csv` führt 335 Zeilen über 243 Institute.
   Ein Institut mit vier Stichtagen zählte viermal, mit fast identischem Wert.
2. **Der Rettungsversuch.** „Dann ist eben nicht das BIP die richtige Kennzahl,
   sondern die Finanzplatzintensität" — auch das ist geprüft und scheitert:
   Irland liegt bei Exposure/BIP am unteren Ende und bei der Domestizität
   trotzdem ganz unten.
3. **Konstante Regressoren.** EURIBOR hat zu einem Stichtag für alle Banken
   denselben Wert. Die Korrelation darauf ist nicht klein, sie ist undefiniert
   — und darf nicht als 0,0 durchgehen.
4. **„Kein Makroeffekt" heisst nicht „kein Ländereffekt".** Die Mediane reichen
   von 0,061 (Irland) bis 0,993 (Norwegen). Wer das zusammenwirft, zieht aus
   einem widerlegten Regressor den falschen Schluss.
"""

from pathlib import Path
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "country_effect.csv"


class VarianzzerlegungTest(unittest.TestCase):
    def setUp(self):
        import check_country_effect as c
        self.c = c

    def test_all_variance_between_groups(self):
        """Gruppen ohne Binnenstreuung: eine Gruppenkennzahl könnte alles
        erklären, die Obergrenze ist 1,0."""
        g = {"A": [1.0, 1.0, 1.0], "B": [2.0, 2.0, 2.0]}
        _, _, anteil = self.c.varianzzerlegung(g)
        self.assertAlmostEqual(anteil, 1.0)

    def test_no_variance_between_groups(self):
        """Der Gegenpol, und er ist der Kern des Issues: haben alle Gruppen
        denselben Mittelwert, kann KEINE Gruppenkennzahl etwas erklären — egal
        welche. Obergrenze 0."""
        g = {"A": [1.0, 3.0], "B": [3.0, 1.0]}
        _, _, anteil = self.c.varianzzerlegung(g)
        self.assertAlmostEqual(anteil, 0.0)

    def test_the_parts_add_up(self):
        """Die Zerlegung ist eine Identität, keine Schätzung. Stimmt sie nicht,
        ist die Obergrenze frei erfunden."""
        g = {"A": [0.1, 0.5, 0.9], "B": [0.2, 0.4], "C": [0.8, 0.85, 0.9, 0.95]}
        gesamt, zwischen, _ = self.c.varianzzerlegung(g)
        alle = [w for v in g.values() for w in v]
        import statistics as st
        innerhalb = sum(sum((a - st.mean(v)) ** 2 for a in v)
                        for v in g.values()) / len(alle)
        self.assertAlmostEqual(gesamt, zwischen + innerhalb, places=10)

    def test_a_constant_attribute_has_no_decomposition(self):
        self.assertIsNone(self.c.varianzzerlegung({"A": [1.0, 1.0], "B": [1.0]}))


class KorrelationTest(unittest.TestCase):
    def setUp(self):
        import check_country_effect as c
        self.c = c

    def test_perfect_positive(self):
        self.assertAlmostEqual(self.c.korrelation([(1, 2), (2, 4), (3, 6)]), 1.0)

    def test_perfect_negative(self):
        self.assertAlmostEqual(self.c.korrelation([(1, 6), (2, 4), (3, 2)]), -1.0)

    def test_a_constant_regressor_is_undefined_not_zero(self):
        """Die EURIBOR-Falle aus #15, hier als Funktion. Ein Regressor ohne
        Varianz liefert KEINE Korrelation. Als 0,0 durchgereicht sähe er aus
        wie ein gemessener Nicht-Zusammenhang statt wie eine unmögliche
        Messung."""
        self.assertIsNone(self.c.korrelation([(5, 1), (5, 2), (5, 3)]))

    def test_a_constant_target_is_undefined_too(self):
        self.assertIsNone(self.c.korrelation([(1, 5), (2, 5), (3, 5)]))

    def test_too_few_pairs(self):
        self.assertIsNone(self.c.korrelation([(1, 2), (2, 4)]))


class PseudoreplikationTest(unittest.TestCase):
    def setUp(self):
        import check_country_effect as c
        self.c = c

    def test_one_row_per_institution(self):
        """335 Zeilen über 243 Institute. Ein Institut mit vier Stichtagen
        zählte sonst viermal — das bläht n auf, ohne Information hinzuzufügen,
        und lässt jede Korrelation belastbarer aussehen als sie ist."""
        z = [{"lei": "A", "scope": "CON", "refPeriod": "2025-12-31"},
             {"lei": "A", "scope": "CON", "refPeriod": "2025-06-30"},
             {"lei": "B", "scope": "CON", "refPeriod": "2025-12-31"}]
        self.assertEqual([r["lei"] for r in self.c.ein_institut_je_lei(z)], ["A", "B"])

    def test_the_choice_is_deterministic_and_not_by_value(self):
        """Genommen wird die erste Zeile in stabiler Sortierung. Eine Auswahl
        nach dem Wert wäre eine Vorentscheidung über das Ergebnis."""
        z = [{"lei": "A", "scope": "CON", "refPeriod": "2025-12-31"},
             {"lei": "A", "scope": "CON", "refPeriod": "2025-06-30"}]
        a = self.c.ein_institut_je_lei(z)[0]["refPeriod"]
        b = self.c.ein_institut_je_lei(list(reversed(z)))[0]["refPeriod"]
        self.assertEqual(a, b)
        self.assertEqual(a, "2025-06-30")


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        if not OUT.exists():
            self.skipTest("country_effect.csv nicht gebaut")
        with OUT.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))

    def test_several_attributes_are_tested(self):
        """Ein negatives Ergebnis an einer einzelnen Kennzahl wäre ein Zufall.
        Geprüft werden Domestizität, HHI und Länderzahl."""
        self.assertGreaterEqual(len({r["attribut"] for r in self.rows}), 3)

    def test_several_regressors_are_tested(self):
        """Auch der naheliegende Rettungsversuch (Exposure/BIP) steht drin —
        ohne ihn läse sich das Ergebnis als „BIP war die falsche Kennzahl"."""
        self.assertIn("log10_exposure_je_bip", {r["regressor"] for r in self.rows})

    def test_the_ceiling_is_computed_before_the_correlation(self):
        """Ohne die Obergrenze ist ein r² nicht einzuordnen."""
        for r in self.rows:
            with self.subTest(attr=r["attribut"], reg=r["regressor"]):
                self.assertTrue(r["anteil_zwischen"])
                self.assertGreater(float(r["anteil_zwischen"]), 0)

    def test_the_population_is_exactly_one_reliable_row_per_institution(self):
        """Beide Entscheidungen über die Grundgesamtheit, unabhängig
        nachgerechnet — sie sind dokumentiert und wären sonst ungeschützt:

        * nur `reliable = true` (kein Heimatland, zu hoher Residualanteil oder
          ein Skalenbefund aus #83 machen die Quote unbrauchbar)
        * eine Zeile je LEI, nicht je Report

        Fällt eine davon weg, steigt n — und jede Korrelation sieht
        belastbarer aus, ohne dass eine Schwelle anschlägt."""
        fp = ROOT / "processed" / "footprint.csv"
        if not fp.exists():
            self.skipTest("footprint.csv nicht vorhanden")
        gdp = ROOT / "codebook" / "country_gdp.csv"
        with gdp.open(encoding="utf-8") as fh:
            laender = {z["country"] for z in csv.DictReader(fh) if z.get("gdp_usd")}
        with fp.open(encoding="utf-8") as fh:
            zeilen = list(csv.DictReader(fh))
        erwartet = len({z["lei"] for z in zeilen if z["reliable"] == "true"
                        and z["domestic_share"] and z["home_country"] in laender})
        alle_zeilen = sum(1 for z in zeilen if z["domestic_share"])
        self.assertGreater(alle_zeilen, erwartet,
                           "footprint.csv hat keine Mehrfachzeilen mehr — dann "
                           "prüft dieser Test die Entdopplung nicht")
        dom = [r for r in self.rows if r["attribut"] == "domestic_share"][0]
        self.assertEqual(int(dom["n_institute"]), erwartet)

    def test_the_measurement_actually_ran(self):
        """Gegenprobe gegen ein Skript, das stillschweigend nichts misst: ein
        leerer Bestand lieferte dieselbe Aussage („kein Zusammenhang")."""
        self.assertGreater(min(int(r["n_institute"]) for r in self.rows), 100)
        self.assertGreater(min(int(r["n_laender"]) for r in self.rows), 10)

    def test_gdp_explains_almost_nothing_of_what_is_attainable(self):
        """Das Ergebnis des Issues. Das BIP erreicht unter 5 % dessen, was ein
        Länderindikator überhaupt erklären könnte — bei der Domestizität sind
        es 0,4 %."""
        bip = [r for r in self.rows if r["regressor"] == "log10_bip"
               and r["attribut"] == "domestic_share"]
        self.assertEqual(len(bip), 1)
        self.assertLess(float(bip[0]["anteil_des_erreichbaren"]), 0.05)

    def test_no_regressor_comes_close_to_the_ceiling(self):
        """Die Aussage gilt für ALLE geprüften Länderkennzahlen, nicht nur für
        das BIP. Käme eine über die Hälfte des Erreichbaren, wäre die These
        nicht widerlegt, sondern nur der erste Versuch."""
        for r in self.rows:
            with self.subTest(attr=r["attribut"], reg=r["regressor"]):
                self.assertLess(float(r["anteil_des_erreichbaren"] or 0), 0.5)

    def test_most_variance_sits_inside_the_countries(self):
        """Der strukturelle Grund, und er ist der eigentliche Befund: zwei
        Drittel der Streuung liegen INNERHALB der Länder. Kein Länderindikator
        kommt dort hin, gleich welcher."""
        dom = [r for r in self.rows if r["attribut"] == "domestic_share"][0]
        self.assertLess(float(dom["anteil_zwischen"]), 0.5)

    def test_the_country_effect_is_not_denied(self):
        """„Kein Makroeffekt" heisst nicht „kein Ländereffekt". Ein Drittel der
        Streuung liegt sehr wohl zwischen den Ländern — das Ergebnis ist, dass
        die Makrokennzahl es nicht einfängt, nicht dass es das Muster nicht
        gäbe."""
        dom = [r for r in self.rows if r["attribut"] == "domestic_share"][0]
        self.assertGreater(float(dom["anteil_zwischen"]), 0.15)

    def test_the_order_is_stable(self):
        k = [(r["attribut"], r["regressor"]) for r in self.rows]
        self.assertEqual(k, sorted(k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
