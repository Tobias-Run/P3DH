"""Nicht eindeutig platzierte Koordinaten (#54).

## Was der Fall ist

Das DPM führt je Templatecode **mehrere `TableVersion`s** (463 von 549 Codes),
und zwischen ihnen verschieben sich die Zeilennummern. `build_codebook.py`
dedupliziert über `(dp, template, row, col)` — dieser Schlüssel fasst zusammen,
was zwei Versionen auf *dieselbe* Zelle legen, aber er fängt nicht den Fall,
dass sie den Datenpunkt auf *verschiedene* Zellen legen. Dann überleben beide
Zeilen.

`xbrl_csv_parser._load_codebook()` schlüsselt nur nach `(dp, template)` und
überschreibt:

    codebook[key] = {...}      # die letzte Zeile der Datei gewinnt

Für **eine** der beiden Meldeversionen ist die gewählte Platzierung damit
falsch — und zwar für alle Reports gleich, weil die Framework-Version im
Schlüssel gar nicht vorkommt.

## Die Größenordnung

Gemessen: **73** `(dp, Template)`-Paare, daraus **31** Koordinaten mit zwei
konkurrierenden Zeilenlabels, und **13.027** betroffene Fakten im Bestand —
9.559 davon in OV1 unter RF 4.1, 1.398 unter 4.2, 1.199 in CR6-A.

In OV1 fällt „20. Position, foreign exchange and commodities risks" mit
„15. Settlement risk" zusammen. Das sind keine Label-Varianten derselben
Zeile, sondern verschiedene Risikoarten.

## Was diese Tests halten

Die Behebung braucht eine framework-bewusste Auflösung über
`TableVersion.StartReleaseID`, einen Codebook-Neubau (755-MB-DPM) und einen
vollen Reparse — das ist Sache der Pipeline. Bis dahin gilt:

1. Die Zahl darf nicht **wachsen**, ohne dass es auffällt.
2. Der Viewer muss die betroffenen Zellen **markieren** statt eine der beiden
   Zeilen zu behaupten.
3. Kennzahlen, die wir ausliefern, dürfen **nicht** auf so einer Koordinate
   liegen.
"""

from pathlib import Path
import collections
import csv
import json
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import metrics as mx  # noqa: E402

CODEBOOK_CSV = ROOT / "codebook" / "dpm_codebook.csv"
CODEBOOK_JSON = ROOT / "processed" / "zweig_a" / "data" / "codebook.json"
VIEWER = ROOT / "processed" / "zweig_a" / "viewer_json.html"

# Beobachteter Stand 2026-09-04. Eine Obergrenze, kein Ziel: sie darf sinken,
# und wenn sie das tut, gehört sie nachgezogen.
MAX_AMBIGUOUS_PAIRS = 73
MAX_AMBIGUOUS_CELLS = 31


def rows():
    with CODEBOOK_CSV.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def ambiguous_pairs(rs):
    placed = collections.defaultdict(set)
    for r in rs:
        if r["template"]:
            placed[(r["datapoint_code"], r["template"])].add((r["row"], r["col"]))
    return {k: v for k, v in placed.items() if len(v) > 1}


def ambiguous_cells(rs):
    seen = collections.defaultdict(set)
    for r in rs:
        if r["row"]:
            seen[(r["template"], r["row"], r["col"])].add((r["row_label"], r["col_label"]))
    return {k: v for k, v in seen.items()
            if len({a for a, _ in v}) > 1 or len({b for _, b in v}) > 1}


class ScopeTest(unittest.TestCase):
    def setUp(self):
        if not CODEBOOK_CSV.exists():
            self.skipTest("dpm_codebook.csv fehlt")
        self.rows = rows()

    def test_the_ambiguity_does_not_grow(self):
        n = len(ambiguous_pairs(self.rows))
        self.assertLessEqual(
            n, MAX_AMBIGUOUS_PAIRS,
            f"{n} mehrdeutige (dp, Template)-Paare — mehr als die {MAX_AMBIGUOUS_PAIRS}, "
            "gegen die zuletzt geprüft wurde. Jede zusätzliche bedeutet Fakten in "
            "einer willkürlich gewählten Zeile (#54).")

    def test_the_affected_cells_do_not_grow(self):
        n = len(ambiguous_cells(self.rows))
        self.assertLessEqual(n, MAX_AMBIGUOUS_CELLS,
                             f"{n} Koordinaten mit konkurrierenden Labels (#54)")

    def test_it_is_still_a_real_problem(self):
        """Sinkt die Zahl auf null, prüfen die Obergrenzen oben nichts mehr —
        dann sollen sie nachgezogen und dieser Test entfernt werden, statt
        still grün zu bleiben."""
        self.assertGreater(len(ambiguous_pairs(self.rows)), 0,
                           "keine Mehrdeutigkeit mehr — Obergrenzen nachziehen und "
                           "#54 schließen")


class ShippedMetricsTest(unittest.TestCase):
    """Die Kennzahlen, die wir selbst ausliefern, dürfen nicht auf einer
    unsicheren Koordinate stehen. Bei CQ3 ist die Mehrdeutigkeit an r0060 —
    die NPL-Quote liegt auf r0020 und ist nicht betroffen. Das soll so
    bleiben."""

    def setUp(self):
        if not CODEBOOK_CSV.exists():
            self.skipTest("dpm_codebook.csv fehlt")
        self.cells = ambiguous_cells(rows())

    def test_no_overview_metric_sits_on_an_ambiguous_cell(self):
        def dpm(tid):
            p = tid.split(".")
            if p and len(p[-1]) == 1 and p[-1].isalpha() and p[-1].isupper():
                p[-1] = p[-1].lower()
            return "K_" + ".".join(p)

        hits = []
        for m in mx.METRICS:
            coords = list(m["cells"]) + ([m["own_req"] + ["own"]] if m.get("own_req") else [])
            for tid, r, c, *_ in coords:
                if (dpm(tid), r, c) in self.cells:
                    hits.append(f"{m['id']}: {tid} r{r} c{c}")
        self.assertEqual(hits, [], f"Kennzahl auf mehrdeutiger Koordinate: {hits}")


class ViewerMarkTest(unittest.TestCase):
    """Der Viewer soll die Unsicherheit zeigen, nicht eine der beiden Zeilen
    behaupten."""

    def test_the_codebook_json_ships_the_ambiguous_cells(self):
        if not CODEBOOK_JSON.exists():
            self.skipTest("codebook.json nicht gebaut")
        payload = json.loads(CODEBOOK_JSON.read_text(encoding="utf-8")).get("ambig")
        self.assertIsNotNone(payload, "codebook.json trägt die Mehrdeutigkeiten nicht")
        self.assertEqual(sum(len(v) for v in payload.values()),
                         len(ambiguous_cells(rows())))

    def test_each_entry_names_the_competing_rows(self):
        """Ein Marker ohne die konkurrierenden Labels sagt „unsicher" und lässt
        den Leser damit allein."""
        if not CODEBOOK_JSON.exists():
            self.skipTest("codebook.json nicht gebaut")
        payload = json.loads(CODEBOOK_JSON.read_text(encoding="utf-8"))["ambig"]
        for tid, cells in payload.items():
            for coord, labels in cells.items():
                self.assertGreaterEqual(len(labels), 2,
                                        f"{tid} {coord}: weniger als zwei Labels")

    def test_the_viewer_marks_row_labels_and_cells(self):
        src = VIEWER.read_text(encoding="utf-8")
        self.assertIn("const ambigAt=", src)
        self.assertIn("rowAmbig", src, "Zeilenlabel ohne Marker")
        self.assertIn("ambigNote", src, "Template ohne Hinweis")

    def test_the_build_reports_the_ambiguity_instead_of_swallowing_it(self):
        """Derselbe Fehlermodus wie #56: erzeugt wurde die Mehrdeutigkeit schon
        immer, gemeldet nie."""
        src = (ROOT / "scripts" / "build_codebook.py").read_text(encoding="utf-8")
        self.assertIn("Nicht eindeutig platziert", src)
        self.assertIsNotNone(re.search(r"multi\s*=\s*\{k: v for k, v in placed", src))


if __name__ == "__main__":
    unittest.main(verbosity=2)
