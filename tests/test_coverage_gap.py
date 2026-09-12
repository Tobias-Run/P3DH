"""Die Negativmenge (#42): welche beaufsichtigten Institute fehlen im Hub?

## Der Weg von der rohen Differenz zum belastbaren Rest

    2.479   rohe Differenz EZB-Liste gegen unseren Bestand
      126   nur signifikante, Gruppenabdeckung über die EZB-Hierarchie
       19   nach Abgleich über den 18-stelligen LEI-Kern
       12   nach Anerkennung teilweise meldender Gruppen

Jeder dieser Schritte entfernt Scheinbefunde, keine echten. Das ist der Kern
dieses Issues: die rohe Zahl ist nicht bloss ungenau, sie misst etwas anderes —
naemlich Proportionalitaet und Schreibweisen.

## Die drei Fallen, die gemessen zugeschlagen haben

**Proportionalitaet.** 1.093 deutsche und 363 oesterreichische Einheiten der
rohen Differenz sind Sparkassen und Genossenschaftsbanken, die nach CRR
Art. 433b/c gar nicht einzeln quartalsweise offenlegen.

**Konzernstruktur.** 593 signifikante Einheiten sind Toechter, deren Kopf
meldet. Ohne die Hierarchie zaehlte jede davon als fehlend.

**Schreibweise des Kennzeichens.** Drei Eintraege unseres Bestands sind keine
LEIs, sondern Laenderpraefix plus abgeschnittener LEI:

    EZB             9695005MSX1OYEMGDF46   BPCE S.A.
    unser Bestand   FR9695005MSX1OYEMGDF   Groupe BPCE

Diese drei Zeilen erklaerten 104 der 126 vermeintlich fehlenden Institute —
52 Caisses régionales, 43 Caisses d'Épargne, 9 Volksbanken.
"""

from pathlib import Path
import collections
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "coverage_gap.csv"
META = ROOT / "processed" / "entity_meta.csv"


def zeilen():
    if not OUT.exists():
        return []
    with OUT.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class LogikTest(unittest.TestCase):
    def setUp(self):
        import build_coverage_gap as b
        self.b = b

    def test_a_truncated_identifier_still_finds_its_entity(self):
        """Der teuerste Einzelfehler: 104 Institute galten als fehlend, weil
        unser Bestand `FR9695005MSX1OYEMGDF` fuehrt und die EZB
        `9695005MSX1OYEMGDF46`. Derselbe 18-stellige Kern, zwei
        Schreibweisen."""
        exakt, kern = self.b.bestand_index({"FR9695005MSX1OYEMGDF"})
        self.assertTrue(self.b._drin("9695005MSX1OYEMGDF46", exakt, kern))

    def test_an_exact_lei_still_matches(self):
        exakt, kern = self.b.bestand_index({"549300DYPOFMXOR7XM56"})
        self.assertTrue(self.b._drin("549300DYPOFMXOR7XM56", exakt, kern))
        self.assertFalse(self.b._drin("A5GWLFH3KM7YV2SFQL84", exakt, kern))

    def test_a_subsidiary_is_covered_by_its_head(self):
        """Ohne das zaehlte jede Tochter als fehlend, die korrekt ueber die
        Mutter konsolidiert offenlegt — die Voraussetzung aus #32."""
        zeilen = [
            {"lei": "K" * 20, "gruppenkopf_lei": "K" * 20},
            {"lei": "T" * 20, "gruppenkopf_lei": "K" * 20},
        ]
        self.b.einordnen(zeilen, self.b.bestand_index({"K" * 20}))
        self.assertEqual(zeilen[0]["einordnung"], "meldet_selbst")
        self.assertEqual(zeilen[1]["einordnung"], "ueber_gruppe")

    def test_a_group_that_reports_only_in_the_middle_is_marked_as_such(self):
        """Die EZB-Hierarchie ist FLACH. Bei Novo Banco ist der Kopf ein
        Private-Equity-Halter, der nicht meldet, waehrend die Bank in der Mitte
        sehr wohl meldet. Weder „abgedeckt" noch „Luecke" waere richtig."""
        zeilen = [
            {"lei": "H" * 20, "gruppenkopf_lei": "H" * 20},   # Kopf, meldet nicht
            {"lei": "M" * 20, "gruppenkopf_lei": "H" * 20},   # Mitte, meldet
            {"lei": "U" * 20, "gruppenkopf_lei": "H" * 20},   # Tochter darunter
        ]
        self.b.einordnen(zeilen, self.b.bestand_index({"M" * 20}))
        self.assertEqual(zeilen[0]["einordnung"], "gruppe_meldet_teilweise")
        self.assertEqual(zeilen[1]["einordnung"], "meldet_selbst")
        self.assertEqual(zeilen[2]["einordnung"], "gruppe_meldet_teilweise")

    def test_an_entity_without_a_head_is_not_called_missing(self):
        """Das LSI-Blatt fuehrt keine Gruppenstruktur. Eine Gruppe zu erfinden
        oder das Fehlen als Luecke zu lesen waere beides falsch."""
        zeilen = [{"lei": "X" * 20, "gruppenkopf_lei": ""}]
        self.b.einordnen(zeilen, self.b.bestand_index(set()))
        self.assertEqual(zeilen[0]["einordnung"], "keine_gruppe_bekannt")

    def test_the_columns_are_found_by_header_not_by_position(self):
        """Die beiden Blaetter haben verschiedene Layouts. Fest verdrahtete
        Indizes lieferten fuer LSIs null Zeilen — und zwar lautlos."""
        src = (ROOT / "scripts" / "build_coverage_gap.py").read_text(encoding="utf-8")
        self.assertIn("def spalten_von", src)
        self.assertIn("KOPF", src)

    def test_the_wording_never_accuses(self):
        """„Ein fehlendes Institut ist kein Vorwurf." Die ueberwiegende
        Mehrheit hat eine legitime Erklaerung."""
        src = (ROOT / "scripts" / "build_coverage_gap.py").read_text(encoding="utf-8")
        felder = src[src.index("FELDER = ["):]
        felder = felder[:felder.index("]")]
        for wort in ("verstoss", "verstoß", "versaeumnis", "pflichtverletzung"):
            self.assertNotIn(wort, felder.lower())


class TabelleTest(unittest.TestCase):
    def setUp(self):
        self.rows = zeilen()
        if not self.rows:
            self.skipTest("coverage_gap.csv nicht gebaut")

    def test_both_sheets_were_read(self):
        """Das LSI-Blatt lieferte zuerst null Zeilen, ohne dass irgendetwas
        fehlschlug — die stillste Art, eine halbe Quelle zu verlieren."""
        sig = collections.Counter(r["signifikanz"] for r in self.rows)
        self.assertGreater(sig["SI"], 500)
        self.assertGreater(sig["LSI"], 1000)

    def test_the_group_hierarchy_actually_carries(self):
        """Die Abdeckung ueber die Gruppe ist der wichtigste Einzelbeitrag:
        ohne sie waeren hunderte Toechter faelschlich „fehlend"."""
        ueber = [r for r in self.rows if r["einordnung"] == "ueber_gruppe"]
        self.assertGreater(len(ueber), 300,
                           "kaum Gruppenabdeckung — Hierarchie nicht gelesen?")

    def test_the_residual_is_small_and_significant_only(self):
        """Bleibt die Restmenge gross, misst die Auswertung wieder
        Proportionalitaet statt einer Luecke."""
        rest = [r for r in self.rows
                if r["signifikanz"] == "SI" and r["einordnung"] == "nicht_abgedeckt"]
        self.assertLess(len(rest), 40, f"Restmenge auf {len(rest)} gewachsen")

    def test_our_own_institutions_outside_the_ssm_are_not_counted_as_missing(self):
        """Die SSM-Liste deckt den Euroraum ab, unser Bestand 31 Laender.
        Daenemark, Schweden und Norwegen duerfen dabei nicht als Fehler der
        einen oder anderen Seite erscheinen."""
        with META.open(encoding="utf-8") as fh:
            meta = list(csv.DictReader(fh))
        ssm_kern = {r["lei"][:18] for r in self.rows}
        nur_bei_uns = [m for m in meta
                       if m["lei"][:18] not in ssm_kern
                       and (m["lei"][2:] if len(m["lei"]) == 20 else m["lei"])[:18]
                       not in ssm_kern]
        laender = {m["country"] for m in nur_bei_uns}
        for l in ("Denmark", "Sweden", "Norway"):
            self.assertIn(l, laender, f"{l} fehlt in der Gegenrichtung")

    def test_every_row_has_a_verdict(self):
        erlaubt = {"meldet_selbst", "ueber_gruppe", "gruppe_meldet_teilweise",
                   "keine_gruppe_bekannt", "nicht_abgedeckt"}
        for r in self.rows:
            with self.subTest(lei=r["lei"]):
                self.assertIn(r["einordnung"], erlaubt)

    def test_the_order_is_stable(self):
        k = [(r["signifikanz"], r["land"], r["lei"]) for r in self.rows]
        self.assertEqual(k, sorted(k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
