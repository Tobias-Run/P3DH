"""Regressionstests für scripts/xbrl_csv_parser.py.

Selbst-erzeugtes Fixture-ZIP (in-memory), damit die Tests ohne die gitignorierten
Rohdaten überall laufen (frischer Clone, CI, Remote-Session). Decken die Defekte
ab, die hier real aufgetreten sind:
  - Filing-Indicator-Bug (BOM + K_-Präfix-/Key-Mismatch → alles False)
  - Phase 2.5: Templates mit offener Achse (typisierte Dimensionsspalte) dürfen
    die Dimension nicht verwerfen.

Lauf: python3 -m unittest tests/test_xbrl_csv_parser.py
"""

import io
import json
import zipfile
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from xbrl_csv_parser import XBRLCSVParser  # noqa: E402

BOM = "﻿"


def _build_fixture_zip(path: Path):
    """Minimales, aber repräsentatives XBRL-CSV-Paket schreiben.

    Enthält bewusst:
      - parameters.csv und FilingIndicators.csv MIT BOM (utf-8-sig-Pflicht)
      - FilingIndicators mit K_-Präfix, einem true und einem false
      - eine closed-axis k-Datei (nur datapoint/factValue) → Codebook-Join
      - eine open-axis k-Datei (zusätzliche Spalte RIO) → Dimension erfassen
    """
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("reports/report.json", json.dumps({
            "documentInfo": {
                "extends": ["http://www.eba.europa.eu/eu/fr/xbrl/crr/fws/pillar3/4.1/mod/codis.json"]
            }
        }))
        # BOM vorangestellt — Parser muss utf-8-sig nutzen, sonst wird der erste
        # Spaltenname zu "﻿name" bzw. "﻿reported".
        z.writestr("reports/parameters.csv",
                   BOM + "name,value\n"
                   "entityID,rs:TESTLEI123.CON\n"
                   "refPeriod,2025-06-30\n"
                   "baseCurrency,iso4217:EUR\n"
                   "decimalsMonetary,-6\n")
        z.writestr("reports/FilingIndicators.csv",
                   BOM + "templateID,reported\n"
                   "K_61.00,true\n"
                   "K_67.01,true\n"
                   "K_99.00,false\n")
        # closed axis: fixe Zelle, im Codebook gemappt
        z.writestr("reports/k_61.00.csv",
                   "datapoint,factValue\n"
                   "dp100,16064153276.03\n")
        # open axis: dritte Spalte RIO (Land) — pro Land eine Zeile, gleicher dp
        z.writestr("reports/k_67.01.a.csv",
                   "datapoint,factValue,RIO\n"
                   "dp200,1688919250.04,eba_GA:NL\n"
                   "dp200,991946358.7,eba_GA:LU\n")


def _build_codebook(path: Path):
    """Codebook nur für die closed-axis-Zelle; open axis bewusst NICHT enthalten."""
    path.write_text(
        "datapoint_code,template,row,col,cell_code\n"
        "dp100,K_61.00,0010,0010,r0010c0010\n",
        encoding="utf-8",
    )


class XBRLParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        cls.zip_path = d / "fixture.zip"
        cls.codebook_path = d / "codebook.csv"
        _build_fixture_zip(cls.zip_path)
        _build_codebook(cls.codebook_path)
        parser = XBRLCSVParser(cls.zip_path, cls.codebook_path)
        cls.metadata, cls.records = parser.parse()
        cls.filing = parser.filing_indicators

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    # --- Metadaten / BOM ---
    def test_metadata_bom_safe(self):
        self.assertEqual(self.metadata["entityID"], "rs:TESTLEI123.CON")
        self.assertEqual(self.metadata["baseCurrency"], "iso4217:EUR")
        self.assertEqual(self.metadata["decimalsMonetary"], "-6")

    def test_framework_version_from_report_json(self):
        self.assertEqual(self.metadata["framework_version"], "4.1")

    # --- Filing-Indicator-Regression (der Bug, der alles False machte) ---
    def test_filing_indicators_not_all_false(self):
        self.assertTrue(any(self.filing.values()),
                        "Regression: Filing-Indicators sind alle False (BOM/Key-Bug)")

    def test_filing_indicators_key_normalized_and_values(self):
        # K_-Präfix gestrippt, true/false korrekt geparst
        self.assertEqual(self.filing.get("61.00"), True)
        self.assertEqual(self.filing.get("67.01"), True)
        self.assertEqual(self.filing.get("99.00"), False)

    def test_template_reported_propagated_to_records(self):
        rec = next(r for r in self.records if r["template_id"] == "61.00")
        self.assertTrue(rec["template_reported"])

    # --- Closed axis: Codebook-Koordinate gejoint ---
    def test_closed_axis_coordinate_joined(self):
        rec = next(r for r in self.records if r["datapoint_code"] == "dp100")
        self.assertEqual(rec["cell_row"], "0010")
        self.assertEqual(rec["cell_col"], "0010")
        self.assertEqual(rec["open_axis_dims"], "")

    # --- Phase 2.5: open axis Dimension erfasst statt verworfen ---
    def test_open_axis_dimension_captured(self):
        open_recs = [r for r in self.records if r["template_id"] == "67.01.A"]
        self.assertEqual(len(open_recs), 2, "beide Länder-Zeilen müssen erhalten bleiben")
        dims = sorted(r["open_axis_dims"] for r in open_recs)
        self.assertEqual(dims, ["RIO=eba_GA:LU", "RIO=eba_GA:NL"])

    def test_open_axis_rows_not_collapsed(self):
        # gleicher datapoint, aber zwei unterscheidbare Fakten über die Dimension
        vals = {r["open_axis_dims"]: r["fact_value"]
                for r in self.records if r["datapoint_code"] == "dp200"}
        self.assertEqual(vals["RIO=eba_GA:NL"], "1688919250.04")
        self.assertEqual(vals["RIO=eba_GA:LU"], "991946358.7")


class IncrementalMergeTest(unittest.TestCase):
    """Der inkrementelle Merge muss zustandslos laufen können.

    Auf einem frischen Runner ist `raw/` leer und es wird nur das Neue geladen.
    Der Altbestand kommt aus dem wiederhergestellten Zustand — er darf dabei
    nicht als 'überholt' eingestuft und weggeworfen werden. Genau das passierte,
    solange die Menge der gültigen Quellen aus den Dateien auf der Platte statt
    aus dem Manifest abgeleitet wurde.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.raw = self.d / "raw"
        self.raw.mkdir()
        self.codebook = self.d / "codebook.csv"
        _build_codebook(self.codebook)
        self.out = self.d / "long_form_raw.csv"

        # Nur die NEUE Einreichung liegt auf der Platte (CI-Fall).
        self.new_zip = self.raw / "NEW.CON_DE_PILLAR3020000_CODIS_2025-12-31_1.zip"
        _build_fixture_zip(self.new_zip)

        # Manifest kennt beide: die alte (nicht auf Platte) und die neue.
        self.manifest = self.d / "manifest.csv"
        self.manifest.write_text(
            "url\n"
            "https://example.org/OLD.CON_DE_PILLAR3020000_CODIS_2025-06-30_1.zip\n"
            f"https://example.org/{self.new_zip.name}\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _write_existing(self, rows, path=None, fields=None):
        path = path or self.out
        fields = fields or ["entityID", "template_id", "fact_value", "source_file"]
        import csv as _csv
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = _csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    def _read(self, path=None):
        import csv as _csv
        path = path or self.out
        with open(path, encoding="utf-8") as f:
            return list(_csv.DictReader(f))

    def test_existing_rows_survive_when_their_zip_is_absent(self):
        """Regression: Bestand darf nicht verschwinden, nur weil das ZIP fehlt."""
        from xbrl_csv_parser import parse_all_reports
        self._write_existing([{
            "entityID": "rs:OLDLEI.CON", "template_id": "61.00",
            "fact_value": "42", "source_file": "OLD.CON_DE_PILLAR3020000_CODIS_2025-06-30_1.zip",
        }])
        parse_all_reports(self.raw, self.codebook, self.out,
                          manifest_path=self.manifest, incremental=True)
        sources = {r["source_file"] for r in self._read()}
        self.assertIn("OLD.CON_DE_PILLAR3020000_CODIS_2025-06-30_1.zip", sources,
                      "Altbestand wurde verworfen, obwohl er im Manifest steht")
        self.assertIn(self.new_zip.name, sources, "neue Einreichung fehlt")

    def test_source_dropped_when_it_leaves_the_manifest(self):
        """Gegenprobe: überholte Resubmissions sollen sehr wohl rausfallen."""
        from xbrl_csv_parser import parse_all_reports
        self._write_existing([{
            "entityID": "rs:GONE.CON", "template_id": "61.00",
            "fact_value": "1", "source_file": "SUPERSEDED.zip",
        }])
        parse_all_reports(self.raw, self.codebook, self.out,
                          manifest_path=self.manifest, incremental=True)
        sources = {r["source_file"] for r in self._read()}
        self.assertNotIn("SUPERSEDED.zip", sources)

    def test_zero_fact_submission_is_not_reparsed(self):
        """Eine Einreichung ohne platzierbare Fakten steht nur in der Coverage-Matrix.

        Ohne die Coverage als Ledger würde sie bei jedem Lauf erneut geparst.
        """
        from xbrl_csv_parser import parse_all_reports
        self._write_existing([], fields=["entityID", "template_id", "fact_value", "source_file"])
        cov = self.out.parent / "filing_indicators.csv"
        self._write_existing(
            [{"entityID": "rs:TESTLEI123.CON", "refPeriod": "2025-12-31",
              "framework_version": "4.1", "template_id": "99.00",
              "reported": "False", "source_file": self.new_zip.name}],
            path=cov,
            fields=["entityID", "refPeriod", "framework_version", "template_id",
                    "reported", "source_file"],
        )
        import io as _io
        from contextlib import redirect_stdout
        buf = _io.StringIO()
        with redirect_stdout(buf):
            parse_all_reports(self.raw, self.codebook, self.out,
                              manifest_path=self.manifest, incremental=True)
        self.assertIn("0 neu zu parsen", buf.getvalue(),
                      "bereits verarbeitete Einreichung wurde erneut geparst")


if __name__ == "__main__":
    unittest.main(verbosity=2)
