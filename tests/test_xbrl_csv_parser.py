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


if __name__ == "__main__":
    unittest.main(verbosity=2)
