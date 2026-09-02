"""Tests für scripts/build_parse_manifest.py — die "latest wins"-Reduktion.

Der Schlüssel dieser Tests ist der Berichtstyp. Ein erster Anlauf gruppierte
nur nach (lei, consolidation, module, refdate) — das sah plausibel aus und
hätte 1.091 von 1.946 Quelldateien als vermeintlich überholte Resubmissions
verworfen, weil unter EINEM Modulcode mehrere fachlich verschiedene Meldungen
liegen (CODIS, FINDIS, ESGDIS, ...). Der Fehler ist teuer und unauffällig:
das Manifest sieht danach sauber aus, der Bestand schrumpft still.
"""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_parse_manifest as m  # noqa: E402

BASE = "https://errp.eba.europa.eu/public-documents/CODIS/input/"


def row(lei="LEI1", cons="CON", country="DE", module="020000",
        refdate="2025-12-31", rtype="CODIS", ts="20260101000000000"):
    url = f"{BASE}{lei}.{cons}_{country}_PILLAR3{module}_{rtype}_{refdate}_{ts}.zip"
    return {"url": url, "lei": lei, "consolidation": cons, "country": country,
            "module": module, "refdate": refdate, "submission_ts": ts}


class ReportTypeTest(unittest.TestCase):
    def test_extracts_type_from_filename(self):
        self.assertEqual(m.report_type(row(rtype="ESGDIS")["url"]), "ESGDIS")
        self.assertEqual(m.report_type(row(rtype="MRELTLACDIS")["url"]), "MRELTLACDIS")

    def test_malformed_name_yields_empty(self):
        self.assertEqual(m.report_type("https://x/kaputt.zip"), "")


class LatestWinsTest(unittest.TestCase):
    def test_newer_submission_supersedes_older(self):
        old = row(ts="20260101000000000")
        new = row(ts="20260202000000000")
        kept = m.latest_wins([old, new])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["submission_ts"], "20260202000000000")

    def test_input_order_does_not_matter(self):
        old, new = row(ts="20260101000000000"), row(ts="20260202000000000")
        self.assertEqual(m.latest_wins([old, new]), m.latest_wins([new, old]))

    def test_report_types_under_one_module_all_survive(self):
        """Der Fehler, der fast passiert wäre. (LEI, CON, 020000, 2025-06-30)
        traegt im echten Katalog CODIS, ESGDIS UND FINDIS — drei eigenstaendige
        Meldungen, keine Resubmissions voneinander."""
        rows = [row(rtype="CODIS", ts="20260211154609543"),
                row(rtype="ESGDIS", ts="20260520145947261"),
                row(rtype="FINDIS", ts="20260317103532962")]
        kept = m.latest_wins(rows)
        self.assertEqual(len(kept), 3)
        self.assertEqual({m.report_type(r["url"]) for r in kept},
                         {"CODIS", "ESGDIS", "FINDIS"})

    def test_resubmission_within_one_report_type_is_reduced(self):
        rows = [row(rtype="CODIS", ts="1"), row(rtype="CODIS", ts="2"),
                row(rtype="FINDIS", ts="1")]
        kept = m.latest_wins(rows)
        self.assertEqual(len(kept), 2)
        codis = [r for r in kept if m.report_type(r["url"]) == "CODIS"]
        self.assertEqual(codis[0]["submission_ts"], "2")

    def test_dimensions_are_kept_apart(self):
        """Stichtag, Konsolidierungskreis und Modulcode (4.1 vs 4.2) sind
        eigene Achsen — nichts davon darf zusammenfallen."""
        rows = [row(refdate="2025-06-30"), row(refdate="2025-12-31"),
                row(cons="IND"), row(module="020100")]
        self.assertEqual(len(m.latest_wins(rows)), 4)

    def test_result_is_sorted_by_url(self):
        rows = [row(lei="LEI9"), row(lei="LEI1")]
        self.assertEqual([r["lei"] for r in m.latest_wins(rows)], ["LEI1", "LEI9"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
