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
        die Zellen nicht führen, stünde in der Formel und nirgends sonst."""
        for m in mx.METRICS:
            if not m.get("formula"):
                continue
            roles = {c[3] for c in m["cells"]}
            used = set(re.findall(r"[A-Za-zÄÖÜäöüß_]+", m["formula"]))
            self.assertEqual(used - roles, set(),
                             f"{m['id']}: Formel nennt unbekannte Rollen")


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


class WiringTest(unittest.TestCase):
    """Registry, Shard und Viewer müssen dieselben Kennzahlen kennen."""

    def test_the_codebook_ships_the_registry(self):
        if not CODEBOOK.exists():
            self.skipTest("codebook.json nicht gebaut")
        payload = json.loads(CODEBOOK.read_text(encoding="utf-8")).get("metrics")
        self.assertEqual(payload, mx.metric_payload(),
                         "codebook.json ist gegenüber scripts/metrics.py veraltet")

    def test_viewer_and_registry_cover_the_same_metrics(self):
        """Die Rechenvorschrift bleibt im Viewer, die Beschreibung in der
        Registry — verbunden über `id`. Fällt eine Seite auseinander, zeigt der
        Viewer eine Karte ohne Erklärung oder umgekehrt."""
        src = VIEWER.read_text(encoding="utf-8")
        block = re.search(r"const OV_METRICS=\[(.*?)\n\];", src, re.S)
        self.assertIsNotNone(block, "OV_METRICS nicht gefunden")
        ids = re.findall(r"\{id:'([a-z0-9]+)'", block.group(1))
        self.assertEqual(ids, mx.METRIC_IDS,
                         "OV_METRICS und scripts/metrics.py führen verschiedene Kennzahlen")

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
