"""Ist die Stichtagswelle geladen? (#7)

## Die Falle, gegen die diese Tests geschrieben sind

Katalogzeilen minus geladene Reports ergibt 43 — und das ist eine falsche Zahl,
weil sie vier verschiedene Dinge in einen Topf wirft:

    nur DISDOCS (PDF, kein XBRL-CSV)                  40
    geparst, aber keine platzierbaren Fakten (#28)     1
    tote EDAP-Links (404)                              2
    offen und ladbar                                   0

Nur die letzte Zeile beschreibt eine Aufgabe. Die 40 PDF-Institute als
Rückstand zu führen hiesse, eine Eigenschaft der Quelle als eigenes Versäumnis
zu buchen — und die eine Zahl, die zählt, in 42 Zeilen Rauschen zu begraben.

Die Einstufung läuft deshalb über eine reine Funktion, und die Tests prüfen
jeden der vier Fälle einzeln. Über die Ausgabe geprüft wäre `offen` heute leer
und der Test liefe über nichts.
"""

from pathlib import Path
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "catalogue_coverage.csv"


class EinstufungTest(unittest.TestCase):
    def setUp(self):
        import check_catalogue_coverage as c
        self.c = c

    def _kat(self, lei, url):
        return {"lei": lei, "consolidation": "CON", "refdate": "2025-12-31",
                "url": url}

    def _stufe(self, kat, parse=(), todo=(), geladen=(), verarbeitet=()):
        u = self.c.einstufen(list(kat), list(parse), set(todo), set(geladen),
                             set(verarbeitet))
        return list(u.values())[0]

    def test_a_report_with_facts_is_loaded(self):
        self.assertEqual(
            self._stufe([self._kat("A", "http://x/a.zip")],
                        geladen=[("A", "CON", "2025-12-31")]),
            self.c.GELADEN)

    def test_a_pdf_only_institution_is_not_a_backlog(self):
        """40 der 43 Fehlstellen. Sie veröffentlichen ihren Pillar-3-Bericht
        ausschliesslich als PDF; build_parse_manifest schliesst DISDOCS
        bewusst aus. Sie als Rückstand zu zählen buchte eine Eigenschaft der
        Quelle als eigenes Versäumnis."""
        self.assertEqual(
            self._stufe([self._kat("A", "http://x/a_DISDOCS.zip")], parse=[]),
            self.c.NUR_PDF)

    def test_a_submission_that_parsed_but_placed_nothing_is_its_own_case(self):
        """Der heikelste Fall (#28): heruntergeladen, geparst, in der
        Coverage-Matrix — und ohne einen platzierbaren Fakt. Sichtbar nur,
        wenn man die Matrix gegen das Parquet hält."""
        self.assertEqual(
            self._stufe([self._kat("A", "http://x/a.zip")],
                        parse=[self._kat("A", "http://x/a.zip")],
                        verarbeitet=["a.zip"]),
            self.c.OHNE_FAKTEN)

    def test_a_catalogue_row_without_a_published_file_is_dead(self):
        self.assertEqual(
            self._stufe([self._kat("A", "http://x/a.zip")],
                        parse=[self._kat("A", "http://x/a.zip")],
                        todo=["http://x/a.zip"]),
            self.c.TOTER_LINK)

    def test_only_a_fetchable_unfetched_report_counts_as_open(self):
        """Die einzige Einstufung, die eine Aufgabe beschreibt."""
        self.assertEqual(
            self._stufe([self._kat("A", "http://x/a.zip")],
                        parse=[self._kat("A", "http://x/a.zip")]),
            self.c.OFFEN)

    def test_being_loaded_beats_every_other_reason(self):
        """Ein Report mit Fakten im Parquet ist geladen — auch wenn eine
        ältere Fassung derselben Einreichung noch in `todo` steht. Sonst
        meldete ein toter Resubmission-Link ein geladenes Haus als Lücke."""
        self.assertEqual(
            self._stufe([self._kat("A", "http://x/a.zip")],
                        parse=[self._kat("A", "http://x/a.zip")],
                        todo=["http://x/a.zip"],
                        geladen=[("A", "CON", "2025-12-31")]),
            self.c.GELADEN)

    def test_every_catalogue_report_gets_exactly_one_verdict(self):
        kat = [self._kat("A", "http://x/a.zip"), self._kat("B", "http://x/b.zip")]
        u = self.c.einstufen(kat, [], set(), set(), set())
        self.assertEqual(len(u), 2)
        self.assertTrue(all(s in self.c.GRUND for s in u.values()))


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        if not OUT.exists():
            self.skipTest("catalogue_coverage.csv nicht gebaut")
        with OUT.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))

    def test_the_wave_is_substantially_loaded(self):
        """#7 fragt nach der nächsten Welle. Gemessen sind 95,4 % des Katalogs
        geladen — fällt das deutlich, ist etwas in der Kette gerissen."""
        geladen = [r for r in self.rows if r["status"] == "geladen"]
        self.assertGreater(len(self.rows), 500)
        self.assertGreater(len(geladen) / len(self.rows), 0.90)

    def test_the_backlog_is_reported_separately_from_the_source_properties(self):
        """Die Zahl, die eine Aufgabe beschreibt, darf nicht mit denen
        verrechnet werden, die keine beschreiben."""
        import collections
        z = collections.Counter(r["status"] for r in self.rows)
        self.assertGreater(z["nur_pdf"], z["offen"],
                           "die PDF-Faelle sind verschwunden — dann zaehlt "
                           "diese Trennung nichts mehr")

    def test_every_row_says_why(self):
        for r in self.rows:
            with self.subTest(lei=r["lei"]):
                self.assertTrue(r["grund"])

    def test_the_order_is_stable(self):
        k = [(r["lei"], r["consolidation"], r["refdate"]) for r in self.rows]
        self.assertEqual(k, sorted(k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
