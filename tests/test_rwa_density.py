"""RWA-Dichte über die volle Population (#45).

## Was diese Auswertung der EBA-Übung voraus hat

Die EBA-Benchmarking-Übung deckt IRB-Institute ab und veröffentlicht nicht auf
Institutsebene. Der Vergleich, den sie strukturell nicht liefern kann, faellt
hier unmittelbar heraus:

    Standardansatz   n=379   Median 0,425
    gemischt         n=316   Median 0,339
    IRB (rein)       n= 11   Median 0,205

## Die Falle: unplausibel ist nicht dasselbe wie falsch

    Kommuninvest - Grupp     0,031 · 0,033 · 0,039 · 0,059   ECHT
    National Bank of Greece  475.095,78                      kaputt

Beide sehen aus wie Ausreisser. Kommuninvest finanziert schwedische Kommunen
zum Risikogewicht 0 % und meldet ueber vier Stichtage stabil um 0,03 — das ist
die interessanteste Beobachtung des Datensatzes, und ein pauschaler
Ausreisserfilter haette sie geloescht.

Deshalb belegt die Markierung den Defekt **am Nenner**, nicht an der Dichte:
gegen das Maximum der eigenen Zeitreihe, plus eine Schranke fuer Dichten, die
keine Portfolioeigenschaft mehr sein koennen.
"""

from pathlib import Path
import collections
import csv
import statistics as st
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "rwa_density.csv"


def zeilen():
    if not OUT.exists():
        return []
    with OUT.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class MarkierungTest(unittest.TestCase):
    def setUp(self):
        import build_rwa_density as b
        self.b = b

    def test_the_broken_side_of_a_jump_is_flagged_not_both(self):
        """Der erste Entwurf prueft gegen den MEDIAN der uebrigen Stichtage.
        Bei vier Werten, von denen zwei kaputt sind, liegt der Median zwischen
        den Welten — und die Regel markierte alle vier. Sie erkannte, dass das
        Institut inkonsistent ist, aber nicht, welcher Wert es ist.

        Der Skalenfehler macht den Nenner immer zu KLEIN, also entscheidet das
        Maximum."""
        werte = {"A": 4.1e4, "B": 4.2e4, "C": 3.72e10, "D": 3.74e10}
        v = self.b.skalenverdacht({"x": werte})["x"]
        self.assertEqual(v["A"], "true")
        self.assertEqual(v["B"], "true")
        self.assertEqual(v["C"], "false", "korrekter Stichtag mitmarkiert")
        self.assertEqual(v["D"], "false", "korrekter Stichtag mitmarkiert")

    def test_a_single_reference_date_with_an_absurd_density_is_still_caught(self):
        """Banque Banorient France hat nur einen Stichtag und meldet eine
        Dichte von 410 — durch die Zeitreihen-Regel faellt sie glatt hindurch."""
        v = self.b.skalenverdacht({"x": {"A": 2.55e6}}, {("x", "A"): 410.0})["x"]
        self.assertEqual(v["A"], "true")

    def test_a_high_but_conceivable_density_is_left_alone(self):
        """FMO meldet 1,16 und Brown Brothers Harriman 2,31. Hohe Werte fuer
        Haeuser mit hohen Risikogewichten — sie als Fehler zu markieren waere
        dieselbe Anmassung wie ein Filter, der Kommuninvest loescht."""
        for d in (1.16, 2.31, 9.9):
            with self.subTest(dichte=d):
                v = self.b.skalenverdacht({"x": {"A": 1.0e8}}, {("x", "A"): d})["x"]
                self.assertEqual(v["A"], "unbekannt")

    def test_one_reference_date_alone_is_not_evidence_of_health(self):
        """„Fehlt ≠ Null": ohne zweiten Stichtag gibt es keine
        Vergleichsgrundlage — dann `unbekannt`, nicht `false`."""
        v = self.b.skalenverdacht({"x": {"A": 1.0e9}})["x"]
        self.assertEqual(v["A"], "unbekannt")

    def test_the_approach_is_read_from_ov1_not_guessed(self):
        """OV1 fuehrt „davon Standardansatz" und „davon IRB" als eigene
        Zeilen. Aus den gemeldeten Templates zu schliessen waere eine
        Vermutung."""
        self.assertEqual(self.b.ansatz_von(0.95, 0.05), "SA")
        self.assertEqual(self.b.ansatz_von(0.02, 0.98), "IRB")
        self.assertEqual(self.b.ansatz_von(0.40, 0.60), "gemischt")
        self.assertEqual(self.b.ansatz_von("", ""), "unbekannt")

    def test_the_density_threshold_leaves_room_above_one(self):
        """Bei 1 abzuschneiden haette FMO und BBH getroffen."""
        self.assertGreater(self.b.DICHTE_ABSURD, 2.5)


class TabelleTest(unittest.TestCase):
    def setUp(self):
        self.rows = zeilen()
        if not self.rows:
            self.skipTest("rwa_density.csv nicht gebaut")

    def test_the_denominator_is_the_leverage_exposure_not_total_assets(self):
        """Der Name „RWA-Dichte" verleitet zu TREA/Bilanzsumme. Die
        LR-Messgroesse enthaelt ausserbilanzielle Positionen — wer die Zahl
        gegen Literatur haelt, die anders rechnet, vergleicht Verschiedenes."""
        src = (ROOT / "scripts" / "build_rwa_density.py").read_text(encoding="utf-8")
        self.assertIn("0210", src)
        self.assertIn("nicht** TREA/Bilanzsumme", src)

    def test_the_density_matches_its_parts(self):
        for r in self.rows:
            with self.subTest(lei=r["lei"], d=r["refPeriod"]):
                self.assertAlmostEqual(
                    float(r["rwa_density"]),
                    float(r["trea_eur"]) / float(r["lr_exposure_eur"]), places=3)

    def test_ov1_confirms_km1(self):
        """Zwei unabhaengig gemeldete Templates tragen dieselbe Gesamtsumme.
        Die Uebereinstimmung validiert die Kette vom Parser bis zur
        EUR-Normierung besser als jeder interne Guard — gemessen liegt der
        Median der Abweichung bei 0,0000 %."""
        abw = [float(r["ov1_abweichung"]) for r in self.rows if r["ov1_abweichung"]]
        self.assertGreater(len(abw), 500, "kaum Gegenproben — Join pruefen")
        self.assertLess(st.median(abw), 0.001,
                        "OV1 und KM1 laufen auseinander")

    def test_kommuninvest_survives(self):
        """Die schaerfste Probe auf die Markierung: eine ECHTE Dichte von 0,03
        darf nicht als Defekt gelten, waehrend 475.095 es muss."""
        k = [r for r in self.rows if "Kommuninvest" in r["bank_name"]]
        self.assertTrue(k, "Kommuninvest nicht im Datensatz")
        for r in k:
            with self.subTest(d=r["refPeriod"]):
                self.assertLess(float(r["rwa_density"]), 0.1)
                self.assertNotEqual(r["skalenverdacht"], "true",
                                    "echte niedrige Dichte als Defekt markiert")

    def test_the_scale_defects_are_caught(self):
        markiert = {r["bank_name"] for r in self.rows if r["skalenverdacht"] == "true"}
        for nm in ("National Bank of Greece", "Deutsche Pfandbriefbank",
                   "Banque Banorient"):
            with self.subTest(nm=nm):
                self.assertTrue(any(nm in m for m in markiert),
                                f"{nm} nicht als Skalenverdacht markiert")

    def test_only_the_broken_dates_of_an_institution_are_flagged(self):
        """Bei der Deutschen Pfandbriefbank sind zwei von vier Stichtagen
        kaputt. Alle vier zu markieren waere die alte, falsche Regel."""
        pbb = [r for r in self.rows if "Pfandbriefbank" in r["bank_name"]]
        self.assertGreaterEqual(len(pbb), 3)
        markiert = [r for r in pbb if r["skalenverdacht"] == "true"]
        self.assertTrue(0 < len(markiert) < len(pbb),
                        "entweder alle oder keiner markiert — Regel greift nicht")

    def test_a_share_above_one_only_where_the_report_itself_disagrees(self):
        """Ein Anteil ueber 100 % hiesse normalerweise, dass wir eine
        „davon"-Zeile fuer eine eigenstaendige gehalten haben. Es gibt aber
        einen echten Fall: Československá obchodná banka meldet Kreditrisiko
        7.177 + CCR 28 + operationell 558 = 7.763 bei einer Gesamtzeile von
        6.993 — die Teile uebersteigen das Ganze.

        Das ist ein Befund ueber die Meldung, kein Rechenfehler bei uns. Er
        darf sichtbar bleiben, muss aber als Inkonsistenz markiert sein."""
        for r in self.rows:
            for k in ("anteil_kredit", "anteil_ccr", "anteil_markt",
                      "anteil_operationell"):
                if r[k] == "" or float(r[k]) <= 1.02:
                    continue
                with self.subTest(lei=r["lei"], feld=k):
                    self.assertEqual(
                        r["ov1_teile_stimmt"], "false",
                        f"{k} über 100 %, ohne dass der Report als inkonsistent gilt")

    def test_the_ov1_addends_were_measured_not_assumed(self):
        """`r0340` ist eine NACHRICHTENZEILE und steckt schon im Kreditrisiko.
        Nimmt man sie als Summanden, stimmen nur 196 von 746 Reports statt
        646 — die Pruefung waere damit Rauschen statt Signal."""
        import build_rwa_density as b
        self.assertNotIn("0340", b.OV1_SUMMANDEN)
        for z in ("0010", "0070", "0260", "0320"):
            self.assertIn(z, b.OV1_SUMMANDEN)
        stimmt = [r for r in self.rows if r["ov1_teile_stimmt"] == "true"]
        gesamt = [r for r in self.rows if r["ov1_teile_stimmt"] != ""]
        self.assertGreater(len(stimmt) / len(gesamt), 0.85,
                           "die Summandenmenge trifft nicht mehr")

    def test_the_standardised_approach_carries_the_higher_density(self):
        """Der Kernbefund. Wuerde er kippen, waere entweder die
        Ansatz-Zuordnung kaputt oder die Population eine andere — beides
        gehoert bemerkt, nicht stillschweigend ueberschrieben."""
        gut = [r for r in self.rows if r["plausibel"] == "true"]
        je = collections.defaultdict(list)
        for r in gut:
            je[r["ansatz"]].append(float(r["rwa_density"]))
        self.assertGreaterEqual(len(je["SA"]), 100)
        self.assertGreaterEqual(len(je["gemischt"]), 100)
        self.assertGreater(st.median(je["SA"]), st.median(je["gemischt"]))

    def test_the_order_is_stable(self):
        k = [(r["lei"], r["scope"], r["refPeriod"]) for r in self.rows]
        self.assertEqual(k, sorted(k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
