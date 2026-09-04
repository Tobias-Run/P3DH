"""Tests zur Darstellung des Framework-Bruchs 4.1→4.2 (#26).

Der Viewer verbindet Zellen über die **Koordinate** `(row, col)`, nicht über den
dp-Code. Wo RF 4.2 eine Zelle auf einen neuen Datenpunkt umgebunden hat, wird
der Wert deshalb weiter gefunden — **es bricht nicht sichtbar, es bricht still.**
Ein Sprung an dieser Stelle sah aus wie Geschäftsentwicklung.

Zwei Zusagen dieser Umsetzung sind prüfenswert, weil man sie der Oberfläche
nicht ansieht:

1. **Es wird nur behauptet, was belegt ist.** Die Brücke ist
   beobachtungsbasiert: Zellen, die nur in einer Version vorkommen, stehen
   bewusst nicht drin, denn Abwesenheit ist bei Offenlegungsdaten kein Beleg
   für eine Taxonomie-Änderung (Arbeitsprinzip 3). Der Viewer darf über sie
   also nichts sagen — und markiert deshalb nur `rebound` und `ambiguous`.
2. **Der Marker sitzt an den richtigen Zellen.** Wenn KM1 r0190 eines Tages
   nicht mehr umgebunden ist, verschwindet der Marker still — und niemand
   merkt, dass der Test seither nichts mehr prüft.
"""

from pathlib import Path
import csv
import json
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent
BRIDGE_CSV = ROOT / "codebook" / "framework_bridge.csv"
CODEBOOK = ROOT / "processed" / "zweig_a" / "data" / "codebook.json"
VIEWER = ROOT / "processed" / "zweig_a" / "viewer_json.html"


def bridge_rows():
    with BRIDGE_CSV.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class BridgePayloadTest(unittest.TestCase):
    """Was aus der Brücke in den Viewer geht — und was bewusst nicht."""

    def setUp(self):
        if not CODEBOOK.exists():
            self.skipTest("codebook.json nicht gebaut")
        self.payload = json.loads(CODEBOOK.read_text(encoding="utf-8")).get("bridge")

    def test_the_codebook_ships_the_bridge(self):
        self.assertIsNotNone(self.payload, "codebook.json trägt keine Brücke")

    def test_only_unstable_cells_are_shipped(self):
        """Die 5.087 stabilen Zellen wären 40× so viel Nutzlast für eine
        Aussage, die der Viewer nicht braucht."""
        states = {s for cells in self.payload.values() for s in cells.values()}
        self.assertEqual(states, {"rebound", "ambiguous"},
                         f"unerwartete Zustände in der Brücke: {sorted(states)}")

    def test_payload_matches_the_source(self):
        want = {}
        for r in bridge_rows():
            if r["status"] in ("rebound", "ambiguous"):
                want.setdefault(r["template_id"], {})[
                    r["cell_row"] + "|" + r["cell_col"]] = r["status"]
        self.assertEqual(self.payload, want,
                         "codebook.json ist gegenüber framework_bridge.csv veraltet")

    def test_the_payload_stays_small(self):
        """Sie fährt in codebook.json mit, das der Viewer beim Start lädt."""
        self.assertLess(len(json.dumps(self.payload, separators=(",", ":"))), 30_000)


class MarkedCellsTest(unittest.TestCase):
    """Die Zellen, an denen der Marker tatsächlich hängt."""

    def setUp(self):
        if not BRIDGE_CSV.exists():
            self.skipTest("framework_bridge.csv fehlt")
        self.rows = bridge_rows()

    def _status(self, tid, row, col):
        for r in self.rows:
            if (r["template_id"], r["cell_row"], r["cell_col"]) == (tid, row, col):
                return r["status"]
        return None

    def test_the_metric_that_carries_the_marker_really_is_rebound(self):
        """KM1 r0190 „Overall capital requirements" ist die einzige umgebundene
        Zelle, auf der eine ausgelieferte Kennzahl steht: die Überblickskarte
        „Headroom TC−OCR" und die Benchmark-Spalte „Gesamtanforderung (OCR)".
        Fällt der Rebound weg, prüft der Rest dieses Tests nichts mehr — dann
        soll er auffallen, statt still grün zu bleiben."""
        self.assertEqual(self._status("61.00", "0190", "0010"), "rebound")

    def test_the_time_series_metrics_are_deliberately_unmarked(self):
        """Die sieben Kennzahlen der KM1-Zeitreihe liegen auf stabilen Zellen.
        Ein Marker dort wäre eine Behauptung ohne Beleg."""
        marked = [row for row in ("0050", "0070", "0220", "0320", "0350", "0040", "0010")
                  if self._status("61.00", row, "0010") in ("rebound", "ambiguous")]
        self.assertEqual(marked, [],
                         f"KM1-Zeitreihenzellen gelten plötzlich als instabil: {marked} "
                         "— dann gehört der Marker auch dorthin")


class ViewerContractTest(unittest.TestCase):
    """Verhalten, das ohne JS-Laufzeit nur am Quelltext prüfbar ist. Die
    Darstellung selbst ist am gerenderten Zustand in Chromium abgenommen."""

    def setUp(self):
        self.src = VIEWER.read_text(encoding="utf-8")

    def test_unknown_cells_yield_no_claim(self):
        """`bridgeAt` muss für alles Unbekannte leer liefern — das ist die
        Stelle, an der Arbeitsprinzip 3 im Code steht."""
        m = re.search(r"const bridgeAt=\(tid,row,col\)=>\{(.*?)\};", self.src)
        self.assertIsNotNone(m, "bridgeAt nicht gefunden")
        self.assertIn("m?(m[row+'|'+col]||''):''", m.group(1).replace(" ", ""))

    def test_the_break_is_derived_from_the_reports_own_framework(self):
        """Nicht aus einer Datumsgrenze geraten: welcher Stichtag unter welcher
        Version gemeldet wurde, steht am Report."""
        self.assertIn("series[i-1].framework!==s.framework", self.src)
        self.assertIn("reps[i-1].framework!==r.framework", self.src,
                      "Benchmark-Sparkline ohne Bruchberechnung")

    def test_the_sparkline_dashes_across_the_break(self):
        """Gestrichelt, nicht unterbrochen. Eine Lücke behauptete „nicht
        vergleichbar", und das wäre für die meisten Zellen falsch — der
        KM1-Trend läuft auf r0050, das die Brücke als `stable` führt."""
        self.assertIn("function sparkline(vals,w,h,breaks)", self.src)
        self.assertIn("if(breaks&&breaks[i]) dash+=seg; else d+=seg;", self.src)
        self.assertIn('stroke-dasharray="2.5 2"', self.src)

    def test_an_isolated_point_is_still_drawn(self):
        """Ein Stichtag ohne beide Nachbarn hängt an keinem Verbindungsstück
        und wäre unsichtbar — er verschwände aus der Grafik."""
        self.assertIn("} else if(!pts[i+1]){", self.src)
        self.assertIn("<circle", self.src)

    def test_the_break_marker_is_not_the_accent_colour(self):
        """Der Bruch ist eine Eigenschaft der Taxonomie — kein Fokus und keine
        Wertung. Der Akzent ist für Fokus reserviert (#61)."""
        m = re.search(r"\.fwbreak\{([^}]*)\}", self.src)
        self.assertIsNotNone(m)
        self.assertNotIn("--accent", m.group(1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
