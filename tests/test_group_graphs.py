"""Zwei Konzerngraphen gegeneinander (#32, #42).

Im Repo liegen zwei Graphen, die nie gegeneinander geprüft wurden: GLEIF
Level-2 und die EZB-Hierarchie. `build_eba_reconciliation.py` schliesst über den
ersten 90 Institutszeilen aus, damit ein Länderaggregat Mutter und Tochter nicht
doppelt zählt — wäre er falsch, wären es die Aggregate auch.

## Die Falle, gegen die diese Tests geschrieben sind

Die beiden Graphen beantworten **verschiedene Fragen**:

    EZB     wer führt die beaufsichtigte Gruppe im SSM?
    GLEIF   wem gehört das Institut?

Wer nur auf Gleichheit prüft, liest 31 % Abweichung als 31 % Fehler. Tatsächlich
ist jede einzelne davon die Perimetergrenze: der GLEIF-Kopf liegt ausserhalb der
EZB-Liste, weil der Konzern über den SSM hinausreicht (Bank of America, HSBC
Holdings, SEB AB).

## Und die Falle dahinter

Die Kategorie `konflikt` — beide Quellen führen den Kopf, nennen aber
verschiedene — ist **leer**. Eine Prüfung, deren interessante Kategorie leer
ist, sieht aus wie eine, die nichts tut. Der Unterschied ist die Gegenprobe:
97 Paare, davon 30 mit abweichendem Kopf. Der Vergleich greift, er findet nur
keinen Widerspruch.
"""

from pathlib import Path
import collections
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "group_graph_check.csv"


class UrteilTest(unittest.TestCase):
    def setUp(self):
        import check_group_graphs as g
        self.g = g

    def test_the_same_head_is_agreement(self):
        self.assertEqual(self.g.urteil_von("A", "P", "P", True), "identisch")

    def test_a_head_outside_the_supervised_list_is_not_a_conflict(self):
        """Der Kern. BofA Securities Europe hat als EZB-Kopf sich selbst und
        als GLEIF-Kopf Bank of America — beide Angaben stimmen, sie beantworten
        verschiedene Fragen. Das als Widerspruch zu zählen hiesse, 30 Fehler zu
        melden, wo keine sind."""
        self.assertEqual(self.g.urteil_von("A", "A", "US-MUTTER", False),
                         "ssm_schnitt")

    def test_two_different_heads_inside_the_list_are_a_conflict(self):
        """Die Kategorie, auf die es ankommt: beide Quellen führen den Kopf und
        nennen verschiedene. Dann irrt eine von beiden."""
        self.assertEqual(self.g.urteil_von("A", "P1", "P2", True), "konflikt")

    def test_a_missing_head_yields_no_verdict(self):
        """Ohne Angabe auf einer Seite gibt es nichts zu vergleichen — und ein
        Urteil wäre eine Aussage über Daten, die nicht vorliegen."""
        self.assertEqual(self.g.urteil_von("A", "", "P", True), "")
        self.assertEqual(self.g.urteil_von("A", "P", "", True), "")


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        if not OUT.exists():
            self.skipTest("group_graph_check.csv nicht gebaut")
        with OUT.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))

    def test_the_comparison_actually_has_pairs(self):
        """Ohne diese Zahl wäre „0 Konflikte" bedeutungslos — es könnte
        heissen, dass gar nichts verglichen wurde."""
        self.assertGreater(len(self.rows), 50)

    def test_the_two_graphs_do_not_contradict_each_other(self):
        """Das Ergebnis. Bricht es, ist einer der beiden Graphen kaputt — und
        mit ihm die Konzernausschlüsse in den Länderaggregaten (#37)."""
        k = [r for r in self.rows if r["urteil"] == "konflikt"]
        self.assertEqual(k, [], f"echte Widersprüche: "
                                f"{[(r['name'], r['ezb_kopf_name'], r['gleif_kopf_name']) for r in k]}")

    def test_the_deviations_are_all_perimeter_cuts(self):
        """Jede Abweichung muss sich erklären. Läge auch nur eine davon
        INNERHALB der EZB-Liste, wäre sie ein Konflikt — und die Erklärung
        „Perimetergrenze" träfe nicht mehr auf alle zu."""
        for r in self.rows:
            if r["urteil"] == "ssm_schnitt":
                with self.subTest(bank=r["name"]):
                    self.assertEqual(r["gleif_kopf_in_ezb_liste"], "nein")

    def test_agreement_always_lies_inside_the_supervised_list(self):
        """Die Gegenprobe zur vorigen: wo beide denselben Kopf nennen, ist er
        auch beaufsichtigt. Zusammen ergeben die beiden Tests die Aussage, dass
        die Perimetergrenze die EINZIGE Ursache der Abweichungen ist."""
        for r in self.rows:
            if r["urteil"] == "identisch":
                with self.subTest(bank=r["name"]):
                    self.assertEqual(r["gleif_kopf_in_ezb_liste"], "ja")

    def test_the_comparison_finds_deviations_at_all(self):
        """Der Test, der verhindert, dass ein kaputter Vergleich als Erfolg
        durchgeht: fände er nirgends eine Abweichung, wäre „kein Konflikt"
        keine Aussage, sondern ein Symptom."""
        u = collections.Counter(r["urteil"] for r in self.rows)
        self.assertGreater(u["ssm_schnitt"], 10)
        self.assertGreater(u["identisch"], 10)

    def test_most_perimeter_cases_are_their_own_group_head(self):
        """27 von 30: das Institut IST die Spitze seiner beaufsichtigten
        Gruppe. Genau das erwartet man, wenn die Ursache der Perimeterschnitt
        ist — und nicht ein Datenfehler, der keinen Grund hätte, sich so zu
        häufen."""
        s = [r for r in self.rows if r["urteil"] == "ssm_schnitt"]
        selbst = sum(1 for r in s if r["ezb_kopf_ist_selbst"] == "ja")
        self.assertGreater(selbst / max(len(s), 1), 0.7)

    def test_the_order_is_stable(self):
        k = [r["lei"] for r in self.rows]
        self.assertEqual(k, sorted(k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
