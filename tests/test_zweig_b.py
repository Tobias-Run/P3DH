"""Integrationstest für scripts/build_zweig_b.py — v. a. den Codebook-
Fallback für offene Achsen (Issue #10).

build_zweig_b.py ist ein SQL-Join-Skript ohne extrahierbare reine Funktionen;
getestet wird deshalb end-to-end gegen ein Mini-Repo in einem Temp-Verzeichnis
(gleiches Muster wie tests/test_fact_placement.py — Modul-Pfadkonstanten
umbiegen, Skript laufen lassen, Ergebnis mit DuckDB direkt prüfen).
"""

from pathlib import Path
import csv
import os
import sys
import tempfile
import unittest

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_zweig_b as z  # noqa: E402


def _write_csv(path: Path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


class ZweigBFallbackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self._orig = (z.ROOT, z.OUT_DIR, z.OUT)
        z.ROOT = self.root
        z.OUT_DIR = self.root / "processed" / "long"
        z.OUT = z.OUT_DIR / "p3dh_long.parquet"

        # build_zweig_b.py löst seine read_csv_auto()-Pfade relativ zu
        # `SET file_search_path` auf — das ist nur ein FALLBACK, der nicht
        # greift, wenn derselbe relative Pfad schon übers CWD auflöst (hier:
        # der echte Repo-Bestand liegt an genau denselben relativen Pfaden).
        # In Produktion läuft das Skript immer mit CWD=Repo-Root, wo CWD und
        # file_search_path identisch sind — für den Test muss CWD deshalb
        # explizit auf die Fixture zeigen, sonst liest DuckDB den echten Bestand.
        self._orig_cwd = os.getcwd()
        os.chdir(self.root)

        # long_form_raw.csv: eine closed-axis Zeile (61.00, echte Koordinate)
        # und eine open-axis Zeile (67.01.A, cell_row/cell_col leer, RIO-Dim).
        _write_csv(self.root / "processed" / "long_form_raw.csv",
                   ["entityID", "refPeriod", "framework_version", "template_id",
                    "template_reported", "datapoint_code", "cell_row", "cell_col",
                    "open_axis_dims", "fact_value", "baseCurrency",
                    "decimalsMonetary", "source_file"],
                   [
                       ["rs:LEI00000000000000001.CON", "2025-12-31", "4.1", "61.00",
                        "True", "dpCLOSED", "0010", "0010", "", "100.0",
                        "iso4217:EUR", "-6", "x.zip"],
                       ["rs:LEI00000000000000001.CON", "2025-12-31", "4.1", "67.01.A",
                        "True", "dpOPEN", "", "", "RIO=eba_GA:NL", "50.0",
                        "iso4217:EUR", "-6", "x.zip"],
                       # ambiger dp: taucht im Codebook unter zwei verschiedenen
                       # (template,row,col) auf -> Fallback darf NICHT greifen
                       ["rs:LEI00000000000000001.CON", "2025-12-31", "4.1", "67.01.A",
                        "True", "dpAMBIG", "", "", "RIO=eba_GA:DE", "9.0",
                        "iso4217:EUR", "-6", "x.zip"],
                       # #56: offene ZEILENachse. Der Parser hat die Zeile aus der
                       # Dimension gebildet ('NL'), das Codebook führt sie als '*'
                       # und kennt die Spalte. Der primäre Join muss das treffen.
                       ["rs:LEI00000000000000001.CON", "2025-12-31", "4.1", "67.01.A",
                        "True", "dpSTAR", "NL", "0060", "RIO=eba_GA:NL", "7.0",
                        "iso4217:EUR", "-6", "x.zip"],
                   ])

        # dpm_codebook.csv: dpCLOSED nur unter K_61.00 (normaler Fall),
        # dpOPEN nur unter dem generischen C_09.04 (der eigentliche Fallback-
        # Fall), dpAMBIG unter zwei verschiedenen Templates (mehrdeutig).
        _write_csv(self.root / "codebook" / "dpm_codebook.csv",
                   ["datapoint_code", "template", "row", "col",
                    "row_label", "col_label", "data_type", "template_title"],
                   [
                       ["dpCLOSED", "K_61.00", "0010", "0010",
                        "CET1", "Amount", "monetary", "KM1"],
                       ["dpOPEN", "C_09.04", "0010", "0010",
                        "Exposure SA", "Amount", "monetary", "generic"],
                       ["dpAMBIG", "K_60.00.A", "0010", "0010", "A-Label", "Amount",
                        "monetary", "OV1"],
                       ["dpAMBIG", "K_71.00", "0020", "0030", "B-Label", "Amount",
                        "monetary", "LR2"],
                       # offene Zeilenachse: Spalte bekannt, Zeile '*' (#56)
                       ["dpSTAR", "K_67.01.a", "*", "0060", "", "Total exposure value",
                        "monetary", "CCyB1"],
                   ])

        _write_csv(self.root / "processed" / "entity_meta.csv",
                   ["lei", "name", "country", "entity_type", "institution_type",
                    "is_gsii", "modules"],
                   [["LEI00000000000000001", "Testbank", "Germany", "Bank",
                     "Other highest EEA", "false", "Common disclosures"]])

        _write_csv(self.root / "processed" / "fx_rates.csv",
                   ["currency", "refdate", "rate_to_eur"],
                   [["EUR", "2025-12-31", "1.0"]])

        _write_csv(self.root / "codebook" / "geo_names.csv",
                   ["code", "name"], [["NL", "Netherlands"]])

    def tearDown(self):
        os.chdir(self._orig_cwd)
        z.ROOT, z.OUT_DIR, z.OUT = self._orig
        self.tmp.cleanup()

    def _rows(self):
        con = duckdb.connect()
        return {r[0]: r for r in con.execute(
            f"SELECT datapoint_code, row_label, col_label, data_type, "
            f"fact_value_eur, open_axis_country FROM '{z.OUT}'").fetchall()}

    def test_closed_axis_untouched_by_fallback(self):
        z.main()
        rows = self._rows()
        self.assertEqual(rows["dpCLOSED"][1], "CET1")
        self.assertEqual(rows["dpCLOSED"][4], 100.0)

    def test_open_axis_resolved_via_generic_template(self):
        z.main()
        rows = self._rows()
        r = rows["dpOPEN"]
        self.assertEqual(r[1], "Exposure SA", "row_label muss aus C_09.04 fallen")
        self.assertEqual(r[3], "monetary")
        self.assertEqual(r[4], 50.0, "fact_value_eur muss ueber den Fallback-data_type berechnet werden")
        self.assertEqual(r[5], "Netherlands")

    def test_open_row_axis_keeps_its_column_label(self):
        """#56: das Codebook führt die Zeile als '*', der Parser hat sie aus der
        Dimension gebildet ('NL'). Der Join `cb.row = b.cell_row` konnte das nie
        treffen — 227.373 Fakten verloren dadurch Spaltenlabel UND data_type,
        und ohne data_type auch die EUR-Normalisierung.
        """
        z.main()
        r = self._rows()["dpSTAR"]
        self.assertEqual(r[2], "Total exposure value",
                         "col_label muss aus dem EIGENEN Template kommen")
        self.assertEqual(r[3], "monetary", "ohne data_type keine EUR-Normalisierung")
        self.assertEqual(r[4], 7.0, "fact_value_eur muss berechnet sein")
        self.assertEqual(r[5], "Netherlands")

    def test_open_row_axis_does_not_duplicate_facts(self):
        """Der Join lautet `(cb.row = b.cell_row OR cb.row = '*')`. Träfe ein
        Fakt zwei Codebook-Zeilen, würde er verdoppelt — still."""
        z.main()
        con = duckdb.connect()
        n = con.execute(
            f"SELECT count(*) FROM '{z.OUT}' WHERE datapoint_code = 'dpSTAR'").fetchone()[0]
        self.assertEqual(n, 1, "Fakt darf durch den OR-Zweig nicht vervielfacht werden")

    def test_ambiguous_dp_not_resolved(self):
        z.main()
        rows = self._rows()
        r = rows["dpAMBIG"]
        self.assertIsNone(r[1], "mehrdeutiger dp darf NICHT ueber den Fallback aufgeloest werden")
        self.assertIsNone(r[4], "ohne data_type darf kein fact_value_eur entstehen")

    def test_row_count_parity(self):
        """Der Join darf weder Zeilen verlieren noch welche erfinden — gegen die
        Long-Form gezählt statt gegen eine feste Zahl, damit die Fixture wachsen
        kann, ohne den Test zu einer Zahlenpflege zu machen."""
        z.main()
        con = duckdb.connect()
        n = con.execute(f"SELECT count(*) FROM '{z.OUT}'").fetchone()[0]
        with open(self.root / "processed" / "long_form_raw.csv", encoding="utf-8") as f:
            expected = sum(1 for _ in f) - 1
        self.assertEqual(n, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
