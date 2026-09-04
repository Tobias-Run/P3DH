"""Tests der Kennzahlen-Registry (#63, erster Teil von #25).

Der Überblick zeigte acht Zahlen ohne Erklärung. Seit `scripts/metrics.py`
trägt jede Kennzahl Definition, Zweck, Schwelle und Herkunft — und auf Klick
die Herleitung aus dem Meldetemplate des Instituts.

Die Schwellen sind der Teil, der schiefgehen kann, und sie sind hier auch
schiefgegangen: die erste Fassung stellte die gemeldete Gesamtanforderung
(KM1 r0190) neben die **CET1**-Quote. Bei BNP Paribas las sich das als
12,6 % gegen 14,7 % — eine Unterdeckung, die es nicht gibt: r0190 ist die
Anforderung an die **Gesamtkapital**quote. Genau davor warnt der eigene
Modul-Docstring, und genau das ist trotzdem passiert. Deshalb steht es jetzt
in einem Test.
"""

from pathlib import Path
import json
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import metrics as mx  # noqa: E402

CODEBOOK = ROOT / "processed" / "zweig_a" / "data" / "codebook.json"
VIEWER = ROOT / "processed" / "zweig_a" / "viewer_json.html"


class RegistryShapeTest(unittest.TestCase):
    def test_ids_are_unique(self):
        self.assertEqual(len(mx.METRIC_IDS), len(set(mx.METRIC_IDS)))

    def test_every_metric_explains_itself(self):
        """Definition und Zweck sind der ganze Sinn der Übung — eine Kennzahl
        ohne beides wäre wieder eine nackte Zahl."""
        for m in mx.METRICS:
            self.assertTrue(m.get("definition"), f"{m['id']}: keine Definition")
            self.assertTrue(m.get("purpose"), f"{m['id']}: kein Zweck")
            self.assertTrue(m.get("cells"), f"{m['id']}: keine Herkunft")

    def test_every_floor_names_its_source(self):
        """Eine Schwelle ohne Fundstelle ist eine Behauptung."""
        for m in mx.METRICS:
            if m.get("floor") is not None:
                self.assertTrue(m.get("floor_src"), f"{m['id']}: Schwelle ohne Fundstelle")

    def test_metrics_without_a_threshold_say_so(self):
        """Wo es keine Schwelle gibt, steht keine — aber das Fehlen wird
        benannt, statt es dem Leser zu überlassen. NPL und TREA sind die
        beiden Fälle."""
        for m in mx.METRICS:
            if m.get("floor") is None:
                self.assertTrue(m.get("note"),
                                f"{m['id']}: keine Schwelle und kein Hinweis darauf")

    def test_a_formula_only_where_something_is_computed(self):
        """Bei einer direkten Zelle wird nichts gerechnet. Eine Formel
        vorzugeben wäre eine Erfindung; mehr als eine Quellzelle ohne Formel
        wäre eine Lücke."""
        for m in mx.METRICS:
            if len(m["cells"]) > 1:
                self.assertTrue(m.get("formula"),
                                f"{m['id']}: mehrere Quellzellen, aber keine Formel")
            else:
                self.assertIsNone(m.get("formula"),
                                  f"{m['id']}: eine Zelle, aber eine Formel behauptet")

    def test_formula_only_uses_declared_roles(self):
        """Die Formel beschriftet die Herleitungstabelle. Ein Rollenname, den
        die Zellen nicht führen, stünde in der Formel und nirgends sonst — und
        eine Rolle, die in der Formel fehlt, wäre eine Quellzelle, die
        offenbar in nichts eingeht."""
        for m in mx.METRICS:
            if not m.get("formula"):
                continue
            roles = {c[3] for c in m["cells"]}
            rest = m["formula"]
            for r in sorted(roles, key=len, reverse=True):
                if r not in rest:
                    self.fail(f"{m['id']}: Rolle „{r}“ kommt in der Formel nicht vor")
                rest = rest.replace(r, " ")
            self.assertEqual(
                set(re.findall(r"[A-Za-zÄÖÜäöüß_]+", rest)), set(),
                f"{m['id']}: Formel nennt Namen, die keine Rolle sind")


class ThresholdSemanticsTest(unittest.TestCase):
    """Die Verwechslung, die schon einmal passiert ist."""

    def _by_id(self, mid):
        return next(m for m in mx.METRICS if m["id"] == mid)

    def test_the_overall_requirement_sits_only_on_the_total_capital_ratio(self):
        """KM1 r0190 „Overall capital requirements" bezieht sich auf die
        GESAMTkapitalquote. Neben der CET1-Quote gelesen suggeriert sie eine
        Unterdeckung, wo keine ist."""
        with_own = [m["id"] for m in mx.METRICS if m.get("own_req")]
        self.assertEqual(with_own, ["tc"],
                         "own_req darf nur an der Gesamtkapitalquote hängen — "
                         f"steht aber an: {with_own}")

    def test_cet1_says_why_it_has_no_institution_specific_line(self):
        """Weglassen genügt nicht: der Leser soll erfahren, dass die bindende
        CET1-Anforderung existiert und nur nicht als eine Zahl gemeldet wird."""
        note = self._by_id("cet1").get("note", "")
        self.assertIn("nicht", note)
        self.assertIn("Gesamtkapitalquote", note)

    def test_the_own_requirement_points_at_the_reported_cell(self):
        self.assertEqual(self._by_id("tc")["own_req"], ["61.00", "0190", "0010"])

    def test_the_npl_note_calls_the_five_percent_a_trigger_not_a_limit(self):
        note = self._by_id("npl").get("note", "")
        self.assertIn("Auslöser", note)
        self.assertIn("keine Grenze", note)


class ProfileTest(unittest.TestCase):
    """Die Benchmark-Profile sind seit #25 nur noch eine Reihenfolge von IDs.
    Das macht sie billig zu ändern — und leise falsch, wenn eine ID nicht
    existiert: der Viewer filtert unbekannte Spalten weg, die Tabelle wäre
    einfach eine Spalte schmaler."""

    def test_every_profile_column_exists(self):
        known = set(mx.METRIC_IDS)
        for p in mx.PROFILES:
            unknown = [i for i in p["metrics"] if i not in known]
            self.assertEqual(unknown, [], f"{p['id']}: unbekannte Kennzahlen {unknown}")

    def test_the_default_sort_column_is_in_the_profile(self):
        """Nach einer Spalte zu sortieren, die nicht angezeigt wird, ergäbe
        eine Reihenfolge ohne sichtbaren Grund."""
        for p in mx.PROFILES:
            self.assertIn(p["sort"][0], p["metrics"],
                          f"{p['id']}: sortiert nach einer Spalte, die es nicht zeigt")
            self.assertIn(p["sort"][1], (1, -1), f"{p['id']}: Sortierrichtung")

    def test_profile_ids_and_labels_are_unique(self):
        ids = [p["id"] for p in mx.PROFILES]
        self.assertEqual(len(ids), len(set(ids)))
        labels = [p["label"] for p in mx.PROFILES]
        self.assertEqual(len(labels), len(set(labels)))

    def test_every_metric_is_reachable(self):
        """Eine Kennzahl, die weder im Überblick noch in einem Profil steht,
        wäre nur über die Suche zu finden — gepflegt würde sie nicht."""
        used = set(mx.OVERVIEW_IDS)
        for p in mx.PROFILES:
            used |= set(p["metrics"])
        self.assertEqual(set(mx.METRIC_IDS) - used, set(),
                         "Kennzahlen, die nirgends angezeigt werden")

    def test_the_columns_of_a_profile_come_from_its_own_template(self):
        """Sonst steht in der Tabelle eine Spalte, die für die meisten Zeilen
        leer bleibt: die Zeilenmenge kommt aus `tpl`. Ausnahme sind die beiden
        Bezugsgrößen aus KM1 — TREA und der Anteil daran —, die der Viewer
        bewusst dazuholt und in der Kopfzeile auch ausweist."""
        for p in mx.PROFILES:
            for mid in p["metrics"]:
                m = next(x for x in mx.METRICS if x["id"] == mid)
                tpls = {c[0] for c in m["cells"]}
                extra = tpls - {p["tpl"], "61.00"}
                self.assertEqual(extra, set(),
                                 f"{p['id']}/{mid}: Spalte aus {extra} statt {p['tpl']}")


class SearchTest(unittest.TestCase):
    """Die Suche (#25) soll die Kennzahl finden, ohne dass man ihre Koordinate
    kennt. Sie greift auf Bezeichnung, englischen Namen, ID und Synonyme zu —
    fehlt eines davon, findet sie nur, wer die deutsche Bezeichnung schon weiß."""

    def test_every_metric_is_searchable_in_both_languages(self):
        for m in mx.METRICS:
            self.assertTrue(m.get("en"), f"{m['id']}: kein englischer Name")
            self.assertTrue(m.get("syn"), f"{m['id']}: keine Synonyme")

    def test_labels_are_unique(self):
        """Zwei Kennzahlen mit derselben Bezeichnung wären in der Trefferliste
        nicht auseinanderzuhalten."""
        labels = [m["label"] for m in mx.METRICS]
        dupes = {l for l in labels if labels.count(l) > 1}
        self.assertEqual(dupes, set(), f"doppelte Bezeichnungen: {dupes}")

    def test_the_viewer_searches_all_of_those_fields(self):
        src = VIEWER.read_text(encoding="utf-8")
        m = re.search(r"const metricMatches=\(m,q\)=>\[(.*?)\]", src, re.S)
        self.assertIsNotNone(m, "metricMatches nicht gefunden")
        for field in ("m.label", "m.en", "m.id", "m.syn"):
            self.assertIn(field, m.group(1), f"Suche ignoriert {field}")


class WiringTest(unittest.TestCase):
    """Registry, Shard und Viewer müssen dieselben Kennzahlen kennen."""

    def test_the_codebook_ships_the_registry(self):
        if not CODEBOOK.exists():
            self.skipTest("codebook.json nicht gebaut")
        payload = json.loads(CODEBOOK.read_text(encoding="utf-8")).get("metrics")
        self.assertEqual(payload, mx.metric_payload(),
                         "codebook.json ist gegenüber scripts/metrics.py veraltet")

    def test_the_viewer_keeps_no_second_list_of_metrics(self):
        """Der Kern von #25. Vorher stand dieselbe Kennzahl bis zu dreimal:
        in `OV_METRICS`, in `BM_PROFILES` und in der Registry — die NPL-Quote
        war der Fall, an dem es auffiel. Jetzt leitet der Viewer beides aus
        `METRICDOC` ab. Eine wiederauferstandene Literal-Liste wäre genau der
        Zustand, den dieses Issue beseitigt hat, und niemandem fiele es auf,
        solange beide Listen zufällig übereinstimmen."""
        src = VIEWER.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"^\s*const (OV_METRICS|BM_PROFILES)\s*=\s*[\[{]",
                                    src, re.M),
                          "Der Viewer führt wieder eine eigene Kennzahlenliste")
        self.assertIn("const OV_METRICS=()=>[...METRICDOC.values()]", src,
                      "Überblick leitet die Kennzahlen nicht aus der Registry ab")
        self.assertIn("for(const p of PROFILES)", src,
                      "Benchmark-Profile kommen nicht aus der Registry")

    def test_the_viewer_can_evaluate_every_declared_op(self):
        """`op` ist eine Rechenvorschrift ohne Code — sie funktioniert nur,
        solange der generische Auswerter im Viewer jede Form kennt. Eine neue
        Form in der Registry ergäbe sonst still eine leere Karte."""
        src = VIEWER.read_text(encoding="utf-8")
        body = re.search(r"function metricValue\(rep, m\)\{(.*?)\n\}", src, re.S)
        self.assertIsNotNone(body, "metricValue nicht gefunden")
        handled = set(re.findall(r"case '(\w+)':", body.group(1)))
        declared = {m["op"] for m in mx.METRICS}
        self.assertEqual(declared - handled, set(),
                         f"Rechenformen ohne Auswertung im Viewer: {declared - handled}")
        self.assertEqual(handled - declared, set(),
                         f"Auswertung für Rechenformen, die niemand nutzt: {handled - declared}")

    def test_every_cell_exists_in_the_codebook(self):
        """Ein Tippfehler in einer Koordinate fällt sonst nie auf: eine
        Herleitung, die nichts findet, sieht aus wie eine, für die es keine
        Daten gibt."""
        if not CODEBOOK.exists():
            self.skipTest("codebook.json nicht gebaut")
        cb = json.loads(CODEBOOK.read_text(encoding="utf-8"))["cb"]

        def dpm(tid):                      # Spiegel von dpmCode() im Viewer
            p = tid.split(".")
            if p and len(p[-1]) == 1 and p[-1].isalpha() and p[-1].isupper():
                p[-1] = p[-1].lower()
            return "K_" + ".".join(p)

        missing = []
        for m in mx.METRICS:
            coords = list(m["cells"]) + ([m["own_req"] + ["own"]] if m.get("own_req") else [])
            for tid, r, c, *_ in coords:
                if dpm(tid) + "|" + r + "|" + c not in cb:
                    missing.append(f"{m['id']}: {tid} r{r} c{c}")
        self.assertEqual(missing, [], f"Koordinaten ohne Eintrag im Codebook: {missing}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
