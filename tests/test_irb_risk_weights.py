"""IRB-Risikogewichte je PD-Band (#45, Punkt 3).

CR6 (`26.00.A`) trägt, was die EBA-Benchmarking-Übung misst, aber nicht
institutsgenau veröffentlicht. Drei Eigenschaften des Templates machen jede
naive Auswertung falsch, und alle drei sind hier als Test festgehalten:

1. **Die PD-Spalte heisst „(%)" und ist meistens keine.** 15.638 von 15.997
   Werten liegen bei <= 1. Geraten werden muss nichts: die Zeilenbeschriftung
   nennt das Band, und daran lässt sich die Einheit MESSEN.
2. **Die Bänder überlappen sich.** `r0010` enthält `r0020` und `r0030`. Wer
   alle 18 Zeilen summiert, zählt das Exposure doppelt.
3. **Das Gitter ist dünn besetzt.** 2.736 Zellen tragen PD = 0 und Exposure = 0
   — sie sind keine Meldung, sondern eine Leerstelle.

Dazu eine vierte, die erst beim Nachrechnen auffiel: ein Risikogewicht von
0,008 bei 20 % Ausfallwahrscheinlichkeit ist intern konsistent (die gemeldete
Dichte bestätigt es) und trotzdem keine Aussage über Modellierung — es steht
auf einem Exposure von 87.671 EUR und misst Rundung auf ganze Euro.
"""

from pathlib import Path
import collections
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "irb_risk_weights.csv"


def zeilen():
    if not OUT.exists():
        return []
    with OUT.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class EinheitTest(unittest.TestCase):
    """Die Einheit wird gemessen, nicht angenommen."""

    def setUp(self):
        import build_irb_risk_weights as b
        self.b = b

    def test_the_band_label_decides_the_unit(self):
        """0,22 in Band 20–30 kann nur ein Bruch sein; 22,0 nur Prozent. Genau
        diese Entscheidbarkeit macht die Auswertung möglich."""
        self.assertEqual(self.b.lesart(0.228, "0150"), "bruch")
        self.assertEqual(self.b.lesart(22.8, "0150"), "prozent")

    def test_an_ambiguous_value_is_named_as_such(self):
        """0,12 passt in Band 0,10–0,15 als Prozent UND als Bruch in 10–20.
        Aber innerhalb EINER Zeile kann beides gelten — dann entscheidet nicht
        die Zelle, sondern die Mehrheit des Reports."""
        self.assertEqual(self.b.lesart(0.12, "0030"), "prozent")
        self.assertIn(self.b.lesart(0.5, "0060"), ("prozent", "beides"))

    def test_the_default_band_is_a_point_not_an_interval(self):
        """r0170 heisst „100 (Default)" — von 100 bis 100. Ein halboffenes
        Intervall wäre dort leer, und jede Defaultzeile fiele durch."""
        self.assertEqual(self.b.lesart(1.0, "0170"), "bruch")
        self.assertEqual(self.b.lesart(100.0, "0170"), "prozent")

    def test_the_unit_belongs_to_the_report_not_the_cell(self):
        """Nordea meldet 82 eindeutige Bruch-Zellen gegen 2 Prozent-Zellen. Das
        ist kein Einheitenwechsel mitten im Meldebogen, das sind zwei
        auffällige Zellen — eine Regel ohne Übergewicht verlöre den Report."""
        z = ([{"lei": "A", "scope": "CON", "refPeriod": "2025-12-31",
               "pd": 0.228, "cell_row": "0150"}] * 82
             + [{"lei": "A", "scope": "CON", "refPeriod": "2025-12-31",
                 "pd": 22.8, "cell_row": "0150"}] * 2)
        self.assertEqual(self.b.einheit_je_report(z),
                         {("A", "CON", "2025-12-31"): "bruch"})

    def test_a_narrow_majority_is_not_a_majority(self):
        """Die Konstante `EINHEIT_UEBERGEWICHT` definiert genau diesen Fall, und
        nur er unterscheidet die Regel von einem schlichten „mehr als".
        Fünf gegen drei ist keine Mehrheit, die eine Einheit für den ganzen
        Report trägt — es ist ein Report, über den die Daten nichts sagen."""
        def z(pd, n):
            return [{"lei": "C", "scope": "CON", "refPeriod": "2025-12-31",
                     "pd": pd, "cell_row": "0150"}] * n
        self.assertEqual(self.b.einheit_je_report(z(0.228, 5) + z(22.8, 3)),
                         {("C", "CON", "2025-12-31"): "unklar"})

    def test_a_genuinely_split_report_stays_unclear(self):
        """DNB meldet 4 Bruch- gegen 5 Prozent-Zellen. Dort eine Einheit zu
        wählen hiesse raten — und ein normierter Wert aus einer unbekannten
        Einheit sieht aus wie ein gemessener."""
        z = ([{"lei": "B", "scope": "CON", "refPeriod": "2025-12-31",
               "pd": 0.228, "cell_row": "0150"}] * 4
             + [{"lei": "B", "scope": "CON", "refPeriod": "2025-12-31",
                 "pd": 22.8, "cell_row": "0150"}] * 5)
        self.assertEqual(self.b.einheit_je_report(z),
                         {("B", "CON", "2025-12-31"): "unklar"})

    def test_nothing_is_normalised_without_a_known_unit(self):
        self.assertIsNone(self.b.pd_in_prozent(0.228, "unklar"))
        self.assertAlmostEqual(self.b.pd_in_prozent(0.228, "bruch"), 22.8)
        self.assertAlmostEqual(self.b.pd_in_prozent(22.8, "prozent"), 22.8)

    def test_the_band_hierarchy_is_declared_not_guessed(self):
        """Acht grobe Bänder summieren zum Subtotal, dreizehn feine decken
        dieselbe Skala. Über Ebenen hinweg zu aggregieren verdoppelt das
        Exposure."""
        grob = {k for k, v in self.b.BAND.items() if v[2] in ("grob", "beide")}
        fein = {k for k, v in self.b.BAND.items() if v[2] in ("fein", "beide")}
        self.assertEqual(len(grob), 8)
        self.assertEqual(len(fein), 13)
        self.assertNotIn(self.b.SUMME, self.b.BAND)


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        self.rows = zeilen()
        if not self.rows:
            self.skipTest("irb_risk_weights.csv nicht gebaut")

    def test_the_reported_density_confirms_the_computed_one(self):
        """Die Gegenprobe, die der Datensatz sich selbst gibt: `c0100` ist
        unabhängig gemeldet und muss `c0090 / c0040` sein. Bricht das weg, ist
        entweder die EUR-Normierung oder die Zellplatzierung kaputt."""
        d = collections.Counter(r["dichte_stimmt"] for r in self.rows if r["dichte_stimmt"])
        self.assertGreater(d["ja"], 10 * d["nein"],
                           "die beiden Spalten stimmen nicht mehr überein")

    def test_an_empty_cell_makes_no_statement(self):
        """CR6 ist ein volles Gitter aus Forderungsklasse x Band, und die
        meisten Institute besetzen nur einen Teil. Eine erste Fassung wertete
        jede leere Zelle als „PD unterhalb ihres Bandes" und meldete 3.016
        Verstösse statt 230 — sie mass die Belegung, nicht die Meldung."""
        leer = [r for r in self.rows
                if not float(r["exposure_eur"] or 0) and not float(r["pd_pct"] or 0)]
        self.assertGreater(len(leer), 1000, "unerwartet dicht besetzt")
        for r in leer:
            self.assertEqual(r["pd_im_band"], "",
                             "eine unbesetzte Zelle wird als Befund geführt")

    def test_the_pd_lands_in_its_own_band(self):
        """Der Beleg, dass die Einheitenbestimmung trägt. `c0050` ist die
        exposure-gewichtete PD INNERHALB des Bandes — sie muss dort liegen.
        Täte sie es reihenweise nicht, wäre die Normierung falsch."""
        gewertet = [r for r in self.rows if r["pd_im_band"]]
        self.assertGreater(len(gewertet), 5000)
        drin = sum(1 for r in gewertet if r["pd_im_band"] == "ja")
        self.assertGreater(drin / len(gewertet), 0.95)

    def test_immaterial_cells_are_marked_not_dropped(self):
        """Markieren statt filtern — dieselbe Linie wie überall im Projekt. Die
        Zeilen bleiben, die Statistik nimmt sie nicht."""
        self.assertIn("wesentlich", self.rows[0])
        klein = [r for r in self.rows if r["wesentlich"] == "nein"]
        self.assertGreater(len(klein), 100)

    def test_the_materiality_threshold_costs_almost_no_substance(self):
        """Die Schwelle muss sich rechtfertigen: Zellen unter 10 Mio EUR sind
        rund ein Fünftel der besetzten Zellen und tragen 0,017 % des
        Exposures. Wäre der Anteil gross, wäre die Schwelle eine Auswahl."""
        import build_irb_risk_weights as b
        besetzt = [float(r["exposure_eur"]) for r in self.rows
                   if r["exposure_eur"] and float(r["exposure_eur"]) > 0
                   and r["ebene"] in ("fein", "beide")]
        klein = [v for v in besetzt if v < b.MIN_EXPOSURE]
        self.assertLess(sum(klein) / sum(besetzt), 0.01,
                        "die Schwelle schneidet spürbares Exposure weg")

    def test_defaulted_exposures_still_disperse(self):
        """Der sauberste Befund der Datei: im Defaultband ist die PD auf 100 %
        FIXIERT, sie kann die Streuung also nicht erklären. Was übrig bleibt,
        sind LGD-Schätzung und Wertberichtigungen."""
        d = [float(r["risikogewicht"]) for r in self.rows
             if r["cell_row"] == "0170" and r["wesentlich"] == "ja"
             and r["risikogewicht"]]
        self.assertGreater(len(d), 50)
        d.sort()
        p10, p90 = d[int(0.1 * (len(d) - 1))], d[int(0.9 * (len(d) - 1))]
        self.assertGreater(p90 / max(p10, 1e-9), 2.0)

    def test_levels_are_never_mixed_in_one_row(self):
        for r in self.rows:
            self.assertIn(r["ebene"], ("grob", "fein", "beide", "summe"))

    def test_the_order_is_stable(self):
        k = [(r["lei"], r["scope"], r["refPeriod"], r["klasse_code"], r["cell_row"])
             for r in self.rows]
        self.assertEqual(k, sorted(k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
