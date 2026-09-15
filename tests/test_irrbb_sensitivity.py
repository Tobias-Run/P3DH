"""Zinssensitivität aus dem IRRBB-Modul (#15).

Das Modul war im ganzen Projekt ungenutzt, obwohl es genau die Grösse enthält,
die #11 über eine EURIBOR-Korrelation schätzen wollte — was konstruktionsbedingt
nicht geht, weil EURIBOR zu einem Stichtag für alle Banken denselben Wert hat.

## Die vier Fallen, gegen die diese Tests geschrieben sind

1. **Der Nenner kann kaputt sein.** Die Deutsche Pfandbriefbank meldet ein
   Tier-1-Kapital von 2.998 EUR — ihr ganzer Report liegt um 10^6 daneben
   (#83). Ungefiltert ergibt das eine Quote von −42.028 und damit 126 Zeilen
   scheinbarer SOT-Überschreitungen aus EINEM Skalenfehler.

2. **Der Zähler auch.** Citibank Europe meldet ΔEVE = −298 Mrd. EUR gegen
   14,4 Mrd. Kernkapital. Ein Verlust über dem gesamten Kernkapital ist kein
   Zinsrisiko, sondern ein Artefakt.

3. **Der Test ist einseitig.** Der Supervisory Outlier Test fragt nach dem
   VERLUST. Symmetrisch geprüft stünden Institute mit Zinsgewinnen in derselben
   Liste wie solche am aufsichtlichen Schwellenwert.

4. **„Fehlt ≠ Null".** ΔNII wird nur für die beiden Parallelverschiebungen
   gemeldet — so sieht es die Meldevorschrift vor. Für Steepener und Flattener
   ist die Spalte leer, nicht null.

## Und die Falle dahinter: die EVE-Kategorie ist LEER

Null Überschreitungen der 15-%-Schwelle. Eine leere Kategorie sieht aus wie
eine Prüfung, die nicht greift. Der Unterschied ist die Randverteilung: der
grösste Verlust liegt bei **−14,84 %**, und fünf Institute drängen sich im
letzten Prozentpunkt vor der Grenze. Die Verteilung bricht unmittelbar davor
ab — das ist die Schwelle als bindende Nebenbedingung, nicht ein Test, der
nichts findet. Ohne diese Zahl wäre „0 Überschreitungen" bedeutungslos.
"""

from pathlib import Path
import collections
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "irrbb_sensitivity.csv"


class QuoteTest(unittest.TestCase):
    def setUp(self):
        import build_irrbb_sensitivity as b
        self.b = b

    def test_the_ratio_is_against_tier_one(self):
        self.assertAlmostEqual(self.b.quote(-15.0, 100.0), -0.15)

    def test_without_capital_there_is_no_ratio(self):
        """None heisst „nicht berechenbar", nicht „null". Ohne Kernkapital gibt
        es keinen aufsichtlichen Bezug — und eine 0 dort läse sich als
        „unauffällig"."""
        self.assertIsNone(self.b.quote(-15.0, None))
        self.assertIsNone(self.b.quote(-15.0, 0))
        self.assertIsNone(self.b.quote(-15.0, -100.0))
        self.assertIsNone(self.b.quote(None, 100.0))


class SotTest(unittest.TestCase):
    def setUp(self):
        import build_irrbb_sensitivity as b
        self.b = b

    def test_a_loss_beyond_the_threshold_is_flagged(self):
        self.assertEqual(self.b.sot_urteil(-0.16, self.b.SOT_EVE), "ja")

    def test_a_loss_inside_the_threshold_is_not(self):
        """−14,84 % ist der grösste gemessene Verlust im Bestand und liegt
        INNERHALB. Wer hier `ja` liefert, meldet die ganze Randverteilung als
        Verletzung."""
        self.assertEqual(self.b.sot_urteil(-0.1484, self.b.SOT_EVE), "nein")

    def test_a_gain_is_never_a_breach(self):
        """Der einseitige Test. Ein ΔEVE von +20 % ist ein Zinsgewinn; ihn
        neben eine SOT-Überschreitung zu stellen wäre zwei Sachverhalte unter
        einem Etikett."""
        self.assertEqual(self.b.sot_urteil(+0.90, self.b.SOT_EVE), "nein")

    def test_the_nii_threshold_is_stricter(self):
        """5 % statt 15 % — EBA/GL/2022/14 gegen CRD Art. 98(5). Dieselbe
        Quote urteilt bei ΔNII anders als bei ΔEVE."""
        self.assertEqual(self.b.sot_urteil(-0.08, self.b.SOT_NII), "ja")
        self.assertEqual(self.b.sot_urteil(-0.08, self.b.SOT_EVE), "nein")

    def test_a_missing_ratio_yields_no_verdict(self):
        self.assertEqual(self.b.sot_urteil(None, self.b.SOT_EVE), "")


class VorbehaltTest(unittest.TestCase):
    def setUp(self):
        import build_irrbb_sensitivity as b
        self.b = b

    def test_a_scaled_report_is_marked_as_such(self):
        """Und zwar als `skala`, nicht als `unplausibel`: ein skalierter Report
        erzeugt AUCH einen unplausiblen Quotienten. Wer die Reihenfolge
        vertauscht, schreibt den Skalenfehler dem Zähler zu und verliert die
        Spur zu #83."""
        self.assertEqual(self.b.vorbehalt_von(True, -42028.0, None), "skala")

    def test_a_loss_beyond_the_whole_capital_is_an_artefact(self):
        """Citibank Europe: −298 Mrd. gegen 14,4 Mrd. Kernkapital. Ein solches
        Institut wäre zwanzigfach insolvent."""
        self.assertEqual(self.b.vorbehalt_von(False, -20.6, None), "unplausibel")

    def test_a_plausible_row_carries_no_caveat(self):
        self.assertEqual(self.b.vorbehalt_von(False, -0.1484, -0.02), "")

    def test_the_caveat_also_sees_the_income_side(self):
        """Beide Quotienten zählen. Prüfte nur ΔEVE, käme ein Artefakt in der
        ΔNII-Spalte ungefiltert durch."""
        self.assertEqual(self.b.vorbehalt_von(False, -0.05, 12.0), "unplausibel")

    def test_a_missing_scale_file_marks_nothing(self):
        self.assertEqual(self.b.lade_skalenmarken(ROOT / "gibt-es-nicht.csv"), set())


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        if not OUT.exists():
            self.skipTest("irrbb_sensitivity.csv nicht gebaut")
        with OUT.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))

    def test_the_module_is_actually_evaluated(self):
        """Es war im ganzen Projekt ungenutzt — das ist der Punkt des Issues."""
        self.assertGreater(len({r["lei"] for r in self.rows}), 150)

    def test_all_six_scenarios_appear(self):
        import build_irrbb_sensitivity as b
        s = collections.Counter(r["szenario"] for r in self.rows)
        for k in b.SZENARIEN:
            with self.subTest(szenario=k):
                self.assertGreater(s[k], 100)

    def test_income_change_is_reported_only_for_parallel_shocks(self):
        """„Fehlt ≠ Null": ΔNII gibt es nur für Parallel hoch/runter, so sieht
        es die Meldevorschrift vor. Eine 0 in den übrigen vier Szenarien wäre
        eine Angabe, die niemand gemacht hat."""
        import build_irrbb_sensitivity as b
        for r in self.rows:
            if r["szenario"] not in b.NII_SZENARIEN:
                with self.subTest(bank=r["bank_name"], szenario=r["szenario"]):
                    self.assertEqual(r["delta_nii_eur"], "")

    def test_a_caveat_suppresses_the_verdict_instead_of_passing_it(self):
        """Der gefährlichste Fall. Stünde an einer skalierten Zeile `nein`,
        läse sich ein Skalenfehler als bestandener Test — 138 Zeilen, die als
        unauffällig durchgingen."""
        for r in self.rows:
            if r["vorbehalt"]:
                with self.subTest(bank=r["bank_name"], vb=r["vorbehalt"]):
                    self.assertEqual((r["sot_eve"], r["sot_nii"]), ("", ""))

    def test_the_scale_error_is_caught_before_it_becomes_a_finding(self):
        """Die Pfandbriefbank namentlich: ihr Tier-1 von 2.998 EUR ergäbe eine
        Quote von −42.028. Ohne den Filter wäre sie die Spitze jeder
        Zinsrisiko-Rangliste — mit einem Kapitalfehler als Ursache."""
        pbb = [r for r in self.rows if "Pfandbriefbank" in r["bank_name"]]
        self.assertTrue(pbb, "Pfandbriefbank meldet 68.00 nicht mehr — Test neu eichen")
        for r in pbb:
            if r["refPeriod"] in ("2025-06-30", "2025-09-30"):
                with self.subTest(rp=r["refPeriod"]):
                    self.assertEqual(r["vorbehalt"], "skala")

    def test_no_clean_row_breaches_the_eve_test(self):
        """Das Ergebnis. Bricht es, hat entweder ein Institut die
        aufsichtliche Schwelle gerissen — dann ist das ein Befund — oder ein
        Filter greift nicht mehr."""
        treffer = [r for r in self.rows if r["sot_eve"] == "ja"]
        self.assertEqual([(r["bank_name"], r["quote_eve"]) for r in treffer], [])

    def test_the_eve_distribution_stops_right_before_the_threshold(self):
        """Die Gegenprobe, ohne die „0 Überschreitungen" bedeutungslos wäre.
        Der grösste Verlust liegt bei −14,84 % gegen eine Schwelle von −15 %,
        und mehrere Institute drängen sich im letzten Prozentpunkt davor. Die
        Prüfung MISST also — sie findet nur keine Überschreitung."""
        import build_irrbb_sensitivity as b
        q = sorted(float(r["quote_eve"]) for r in self.rows
                   if r["quote_eve"] and not r["vorbehalt"])
        self.assertGreater(len(q), 1000)
        self.assertLess(q[0], -0.8 * b.SOT_EVE,
                        "keine Zeile kommt der Schwelle nahe — dann prüft der "
                        "Test nicht die Schwelle, sondern eine leere Menge")
        self.assertGreaterEqual(q[0], -b.SOT_EVE)

    def test_the_income_test_does_find_breaches(self):
        """Die zweite Gegenprobe: derselbe Mechanismus, andere Schwelle, und
        dort ist die Kategorie NICHT leer. Wäre auch sie leer, läge der
        Verdacht auf dem Verfahren statt auf den Daten."""
        treffer = [r for r in self.rows if r["sot_nii"] == "ja"]
        self.assertGreater(len(treffer), 10)

    def test_the_income_breaches_concentrate_in_falling_rates(self):
        """Der fachliche Plausibilitätsbeleg: Broker und Neobanken verdienen am
        Zinsspread auf Kundengelder und verlieren, wenn die Zinsen FALLEN. Läge
        die Mehrheit bei „Parallel hoch", wäre entweder das Vorzeichen gedreht
        oder die Szenarienzuordnung vertauscht."""
        treffer = [r for r in self.rows if r["sot_nii"] == "ja"]
        runter = sum(1 for r in treffer if r["szenario"] == "0020")
        self.assertGreater(runter / max(len(treffer), 1), 0.5)

    def test_every_verdict_rests_on_a_ratio(self):
        for r in self.rows:
            if r["sot_eve"] in ("ja", "nein"):
                with self.subTest(bank=r["bank_name"]):
                    self.assertTrue(r["quote_eve"])

    def test_the_order_is_stable(self):
        k = [(r["lei"], r["scope"], r["refPeriod"], r["szenario"]) for r in self.rows]
        self.assertEqual(k, sorted(k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
