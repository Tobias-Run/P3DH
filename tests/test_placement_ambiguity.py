"""Nicht eindeutig platzierte Koordinaten (#54).

## Was der Fall war

Das DPM-Dictionary ist **kumulativ**: es führt jede Tabellenfassung mit, die es
je gab, über fünf Releases. `build_codebook.py` löste jeden Datenpunkt gegen
*alle* Fassungen auf. Damit standen Zeilenbeschriftungen und Platzierungen aus
Fassungen im Codebook, die unser Korpus nie meldet — und
`xbrl_csv_parser._load_codebook()` schlüsselt nur nach `(dp, template)` und
nimmt die letzte Zeile der Datei.

Gemessen waren das **31** Koordinaten mit zwei konkurrierenden Zeilenlabels
(7.994 Fakten) und **73** `(dp, Template)`-Paare mit zwei Platzierungen.

## Was der Release-Filter geleistet hat

Welche Release zu welcher Framework-Version gehört, ist gemessen: für jede
Version wurde gezählt, welcher Anteil ihrer Fakten in welcher Release einen
Eintrag findet. RF 4.1 wird zu 100 % von Release 4 gedeckt (95,9 % von 5),
RF 4.2 zu 100 % von Release 5 (97,6 % von 4). Jede Version hat genau eine
Release, die sie vollständig trägt.

`MIN_RELEASE = 4` verwirft alles davor:

    Koordinaten mit zwei Zeilenlabels     31  ->   0
    mehrdeutige (dp, Template)-Paare      73  ->  38
    aufgelöste Datenpunkte                     9.775 / 9.775 (100 %)

Kein Paar kam hinzu; 35 fielen weg.

## Was übrig bleibt, und warum es zwei verschiedene Dinge sind

**26 Paare sind auflösbar, aber nicht so.** Der Filter behält die Vereinigung
der Releases 4 und 5, weil unser Bestand beide Framework-Versionen enthält. Ein
Datenpunkt, der in Release 4 auf einer anderen Zeile sitzt als in Release 5, ist
in jeder Release für sich eindeutig — in der Vereinigung nicht. Das ist der
Framework-Bruch aus #26, und dagegen hülfe ein Schlüssel
`(dp, template, framework_version)`.

**12 Paare sind es nicht.** Dort liegt dieselbe Variablenfassung in derselben
Tabellenfassung auf zwei verschiedenen Zellen — in OV1 „21. Of which the
Alternative standardised approach (A-SA)" gegen „22. Of which the Alternative
Internal Models Approach (A-IMA)". Zwei Ansätze, nicht zwei Schreibweisen. Die
Meldung hilft nicht: OV1 trägt **keine einzige** Dimension. Sichtbar ist die
Fehlplatzierung an der Struktur — die gewählte Zeile trägt sechs Datenpunkte,
wo jede Nachbarzeile drei trägt, und die andere bleibt fast leer.

Fünf der 12 betreffen Templates, die unser Korpus gar nicht meldet (`C_76.00.a`,
`D_07.00.b`: 0 Fakten). Von den übrigen sieben sind 2.413 Fakten betroffen, alle
unter RF 4.1.

## Was diese Tests halten

1. Die Zahlen dürfen nicht **wachsen**, ohne dass es auffällt.
2. Die Label-Mehrdeutigkeit muss bei **null** bleiben — der Filter ist die
   Zusage, nicht ein glücklicher Zufall.
3. Kennzahlen, die wir ausliefern, dürfen nicht auf so einer Koordinate liegen.
4. Der Viewer behält seine Markierung, obwohl sie heute nichts zu markieren
   findet: sie ist der Auffangmechanismus, falls die Mehrdeutigkeit zurückkommt.
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
import build_codebook as mx_bc  # noqa: E402

CODEBOOK_CSV = ROOT / "codebook" / "dpm_codebook.csv"
CODEBOOK_JSON = ROOT / "processed" / "zweig_a" / "data" / "codebook.json"
VIEWER = ROOT / "processed" / "zweig_a" / "viewer_json.html"

# Beobachteter Stand 2026-09-06, nach Release-Filter UND Vorzugsregel. Eine
# Obergrenze, kein Ziel: sie darf sinken, und wenn sie das tut, gehört sie
# nachgezogen. 73 -> 38 (Filter) -> 12 (Vorzug).
MAX_AMBIGUOUS_PAIRS = 12
# Bei den Labels ist es keine Obergrenze mehr, sondern eine Zusage.
MAX_AMBIGUOUS_CELLS = 0


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

    def test_no_coordinate_carries_two_row_labels(self):
        """Der Release-Filter beseitigt die Label-Mehrdeutigkeit vollständig.
        Kommt sie zurück, ist entweder MIN_RELEASE falsch oder das DPM hat eine
        neue Release gebracht, die wir noch nicht kennen — beides gehört
        angesehen und nicht als „nur ein paar" durchgewinkt."""
        cells = ambiguous_cells(self.rows)
        self.assertEqual(len(cells), MAX_AMBIGUOUS_CELLS,
                         f"{len(cells)} Koordinaten mit konkurrierenden Labels, "
                         f"z. B. {sorted(cells)[:3]} (#54)")

    def test_it_is_still_a_real_problem(self):
        """Sinkt auch die Paarzahl auf null, prüft die Obergrenze oben nichts
        mehr — dann sollen sie nachgezogen und dieser Test entfernt werden,
        statt still grün zu bleiben."""
        self.assertGreater(len(ambiguous_pairs(self.rows)), 0,
                           "keine Mehrdeutigkeit mehr — Obergrenze nachziehen und "
                           "#54 schließen")


class ReleaseFilterTest(unittest.TestCase):
    """Die beiden Annahmen, auf denen der Filter ruht.

    Beide sind gemessen, nicht dokumentiert — das DPM sagt nirgends, wie
    `EndReleaseID` zu lesen ist, und die Release-Nummern tragen keine Namen.
    Genau deshalb gehören sie in einen Test: eine falsch geratene Konvention
    verschöbe 2,3 Mio. Fakten, ohne dass irgendetwas rot würde.
    """

    def test_the_end_release_is_exclusive(self):
        """Unter der inklusiven Lesart überlappten alle 31 mehrdeutigen
        Koordinaten in genau einer Release, unter der exklusiven sind alle 31
        disjunkt. Eine Konvention, die 31 von 31 Fällen trennt, ist die
        richtige."""
        self.assertFalse(mx_bc.alive_from((1, 4), 4),
                         "eine Fassung, die mit Release 4 endet, gilt IN 4 nicht mehr")
        self.assertTrue(mx_bc.alive_from((1, 5), 4))
        self.assertTrue(mx_bc.alive_from((5, None), 4), "offenes Ende gilt weiter")
        self.assertTrue(mx_bc.alive_from((4, 0), 4), "0 steht im DPM für „offen\"")

    def test_the_cutoff_covers_both_framework_versions(self):
        """RF 4.1 ist Release 4, RF 4.2 ist Release 5 — gemessen über die
        Deckung (100 % gegen 95,9 % bzw. 97,6 %). Ein Schnitt bei 5 würde
        4,1 % der 4.1-Datenpunkte unplatzierbar machen, rund 91.500 Fakten."""
        self.assertEqual(mx_bc.MIN_RELEASE, 4)
        self.assertTrue(mx_bc.alive_from((4, 5), mx_bc.MIN_RELEASE),
                        "die RF-4.1-Fassung fiele heraus")
        self.assertTrue(mx_bc.alive_from((5, None), mx_bc.MIN_RELEASE),
                        "die RF-4.2-Fassung fiele heraus")
        self.assertFalse(mx_bc.alive_from((1, 3), mx_bc.MIN_RELEASE),
                         "Altbestand bliebe drin — das war der Fehler")


class PreferenceRuleTest(unittest.TestCase):
    """Die Vorzugsregel bei konkurrierenden Platzierungen (#54).

    Der Filter allein liess 38 Paare uebrig. 26 davon waren Koordinaten, die
    zwischen Release 4 und 5 umgebunden wurden — in jeder Release fuer sich
    eindeutig, nur in der Vereinigung nicht. `_load_codebook()` nimmt dort die
    letzte CSV-Zeile, also die hoechste (Zeile, Spalte). Gemessen trifft das
    bei 14 von 26 Paaren die falsche Zelle; in K_26.01 landen Werte durchweg
    in c0050, waehrend c0040 leer bleibt.

    Die Alternative waere ein Schluessel (dp, template, framework_version)
    gewesen — sechs Skripte, fuenf Testdateien, der Kern-Lookup des Parsers und
    eine neue Art, Fakten zu verlieren. Fuer 1.465 Fakten, 0,06 % des Bestands.
    Die Vorzugsregel leistet dasselbe in einer Funktion.
    """

    def _row(self, dp, tmpl, row, col, tvid):
        return {"datapoint_code": dp, "template": tmpl, "row": row, "col": col,
                "_tvid": tvid}

    def test_the_stale_placement_loses(self):
        rows = [self._row("dp1", "K_26.01", "0020", "0040", 6261),   # gilt
                self._row("dp1", "K_26.01", "0020", "0050", 2329)]   # abgeloest
        out, dropped = mx_bc.prefer_live_placement(rows, live={6261})
        self.assertEqual(dropped, 1)
        self.assertEqual([(r["row"], r["col"]) for r in out], [("0020", "0040")])

    def test_a_real_ambiguity_survives(self):
        """Zwei Zellen AUS DERSELBEN geltenden Fassung — OV1 A-SA gegen A-IMA.
        Die Regel darf hier nicht eine Seite waehlen; sie soll gemeldet werden.
        Waehlte sie doch, waere aus einer sichtbaren Unsicherheit eine
        unsichtbare Behauptung geworden."""
        rows = [self._row("dp3529408", "K_60.00.a", "0270", "0030", 6280),
                self._row("dp3529408", "K_60.00.a", "0290", "0030", 6280)]
        out, dropped = mx_bc.prefer_live_placement(rows, live={6280})
        self.assertEqual(dropped, 0)
        self.assertEqual(len(out), 2)

    def test_an_unambiguous_datapoint_is_untouched(self):
        rows = [self._row("dp1", "K_61.00", "0050", "0010", 999)]
        out, dropped = mx_bc.prefer_live_placement(rows, live=set())
        self.assertEqual((out, dropped), (rows, 0))

    def test_nothing_is_dropped_when_no_placement_is_live(self):
        """Sonst bliebe der Datenpunkt ganz ohne Koordinate — unplatzierbar,
        und das ist der stille Verlust, gegen den der Placement-Guard steht."""
        rows = [self._row("dp1", "K_26.01", "0020", "0040", 1),
                self._row("dp1", "K_26.01", "0020", "0050", 2)]
        out, dropped = mx_bc.prefer_live_placement(rows, live={999})
        self.assertEqual(dropped, 0)
        self.assertEqual(len(out), 2)

    def test_the_rule_rests_on_an_assumption_that_holds_today(self):
        """Die Regel waehlt die Fassung aus MIN_RELEASE. Das ist richtig, weil
        auf den betroffenen Paaren KEIN einziger RF-4.2-Fakt liegt — es gibt
        also nichts zu unterscheiden. Meldet ein spaeterer Bestand dasselbe
        Template unter beiden Versionen mit gewechselter Koordinate, greift sie
        zu kurz, und der Schluessel waere faellig.

        Dieser Test haelt die Annahme fest, damit sie auffaellt statt vergessen
        zu werden: er prueft, dass die Begruendung im Code steht."""
        src = (ROOT / "scripts" / "build_codebook.py").read_text(encoding="utf-8")
        self.assertIn("KEIN einziger RF-4.2-Fakt", src,
                      "Die Annahme der Vorzugsregel ist nicht mehr dokumentiert")


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
