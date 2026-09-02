"""Tests für scripts/determinism.py — die Zusage, dass gleiche Eingaben
gleiche Ausgaben liefern.

Warum es diese Datei gibt: dieselbe Fehlerklasse hat dreimal zugeschlagen, und
alle 107 bestehenden Tests waren dafür STRUKTURELL BLIND. Sie prüfen reine
Funktionen (collapse_cells, resolve_coverage, base_tid) — die sind
deterministisch per Konstruktion. Der Nichtdeterminismus lebt exakt an der Naht
SQL -> Python, die kein Test berührte. Mehr Tests derselben Art hätten nicht
geholfen; es brauchte eine andere ART von Test.

Zwei Ebenen:
  1. der Guard selbst (assert_total_order) — schnell, deckt die SQL-Klasse ab
  2. ein echter Doppellauf des Shard-Builds auf Mini-Daten mit VARIIERTEM
     PYTHONHASHSEED — deckt ab, was SQL nicht sieht: Set-Iteration in Python
"""

from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import determinism as d  # noqa: E402


class MaskNestedTest(unittest.TestCase):
    """Die Maske entscheidet, WELCHE Query der Guard beurteilt."""

    def test_cte_projection_is_hidden(self):
        """Ohne Maskierung prüfte der Guard die Projektion der CTE statt die
        der äußeren Query — er urteilte über die falsche Query."""
        mask = d.mask_nested("WITH n AS (SELECT a, b FROM t) SELECT x FROM n ORDER BY x")
        self.assertNotIn("SELECT a", mask)
        self.assertIn("SELECT x", mask)

    def test_mask_is_position_preserving(self):
        sql = "SELECT max(a), b FROM t"
        self.assertEqual(len(d.mask_nested(sql)), len(sql))

    def test_fill_is_not_whitespace(self):
        """Mit Leerzeichen als Füller matcht `(.*?)\\s+FROM` schon nach 'max'
        und schneidet die letzte Projektionsspalte ab."""
        self.assertFalse(d.FILL.isspace())
        proj, _, _ = d.parse_select("SELECT a, max(b) FROM t GROUP BY a ORDER BY a")
        self.assertEqual([p[0] for p in proj], ["a", "max(b)"])

    def test_string_literals_are_masked(self):
        self.assertNotIn("order by", d.mask_nested("SELECT a FROM t WHERE x='order by'").lower())


class ParseSelectTest(unittest.TestCase):
    def test_ordinals_resolve_against_projection(self):
        proj, order, group = d.parse_select(
            "SELECT template_id, cell_row, count(*) FROM p GROUP BY 1, 2 ORDER BY 1, 2")
        self.assertEqual(order, ["template_id", "cell_row"])
        self.assertEqual(group, ["template_id", "cell_row"])

    def test_direction_and_alias_are_stripped(self):
        _, order, _ = d.parse_select("SELECT a FROM t ORDER BY a DESC NULLS LAST")
        self.assertEqual(order, ["a"])

    def test_table_prefix_is_dropped(self):
        _, order, _ = d.parse_select("SELECT num.lei FROM num ORDER BY num.lei")
        self.assertEqual(order, ["lei"])

    def test_comments_do_not_confuse_the_parser(self):
        proj, order, _ = d.parse_select("SELECT a,  -- ORDER BY b\n b FROM t ORDER BY a, b")
        self.assertEqual([p[0] for p in proj], ["a", "b"])
        self.assertEqual(order, ["a", "b"])


class AssertTotalOrderTest(unittest.TestCase):
    def test_fully_sorted_projection_passes(self):
        self.assertTrue(d.assert_total_order("SELECT a, b FROM t ORDER BY a, b"))

    def test_unsorted_projection_column_is_caught(self):
        """Der reale Fall: `currency` stand in der Projektion, nicht im ORDER BY,
        und wurde je Report aus der ERSTEN Zeile gezogen — bei 12 Reports mit
        zwei Währungen entschied damit die Zufallsreihenfolge."""
        with self.assertRaises(d.NonDeterministic) as cm:
            d.assert_total_order("SELECT a, currency FROM t ORDER BY a")
        self.assertIn("currency", str(cm.exception))

    def test_missing_order_by_is_caught(self):
        with self.assertRaises(d.NonDeterministic):
            d.assert_total_order("SELECT a, b FROM t")

    def test_ties_are_allowed_when_they_are_invisible(self):
        """Die Invariante ist NICHT 'der Schlüssel muss eindeutig sein', sondern
        'er muss alles abdecken, was sichtbar wird'. Im Shard-Build bleiben 3.695
        Tie-Gruppen übrig — sie sind genau deshalb unschädlich."""
        self.assertTrue(d.assert_total_order("SELECT a FROM t ORDER BY a"))

    def test_deterministic_aggregate_with_group_by_passes(self):
        self.assertTrue(d.assert_total_order(
            "SELECT a, max(b) FROM t GROUP BY a ORDER BY a"))

    def test_any_value_is_rejected(self):
        """any_value() greift sich ein beliebiges Element. In der Zellstatistik
        hat es zwei row_labels gegeneinander wandern lassen."""
        with self.assertRaises(d.NonDeterministic) as cm:
            d.assert_total_order("SELECT a, any_value(b) FROM t GROUP BY a ORDER BY a")
        self.assertIn("any_value", str(cm.exception))

    def test_list_without_own_order_by_is_rejected(self):
        with self.assertRaises(d.NonDeterministic):
            d.assert_total_order("SELECT a, LIST(v) FROM t GROUP BY a ORDER BY a")

    def test_list_with_own_order_by_passes(self):
        self.assertTrue(d.assert_total_order(
            "SELECT a, LIST(v ORDER BY v) FROM t GROUP BY a ORDER BY a"))

    def test_unsorted_group_by_key_is_caught(self):
        with self.assertRaises(d.NonDeterministic):
            d.assert_total_order("SELECT a, b, max(c) FROM t GROUP BY a, b ORDER BY a")

    def test_aggregate_beside_plain_column_without_group_by_is_caught(self):
        """`SELECT a, max(b) ... ORDER BY a` ohne GROUP BY: welche Zeile das
        Aggregat begleitet, ist offen. (Eine reine Aggregatquery ohne GROUP BY
        liefert dagegen genau eine Zeile und ist zulässig.)"""
        with self.assertRaises(d.NonDeterministic):
            d.assert_total_order("SELECT a, max(b) FROM t ORDER BY a")
        self.assertTrue(d.assert_total_order("SELECT max(a) FROM t ORDER BY 1"))

    def test_set_operations_are_refused_not_waved_through(self):
        """Fail closed: was der Guard nicht sicher beurteilen kann, lehnt er ab.
        Ein Guard, der im Zweifel 'ok' sagt, ist schlimmer als keiner."""
        with self.assertRaises(d.NonDeterministic):
            d.assert_total_order("SELECT a FROM t UNION SELECT a FROM u ORDER BY a")

    def test_cte_outer_query_is_the_one_judged(self):
        with self.assertRaises(d.NonDeterministic) as cm:
            d.assert_total_order(
                "WITH n AS (SELECT a, b FROM t ORDER BY a, b) "
                "SELECT n.a, n.b FROM n ORDER BY n.a")
        self.assertIn("b", str(cm.exception))


class PipelineQueriesTest(unittest.TestCase):
    """Regression: die echten Queries der Pipeline halten die Zusage.

    Diese Fälle sind der eigentliche Wert der Datei — sie hätten alle drei
    Vorfälle vor dem Commit gefangen.
    """

    def test_shard_build_queries_are_guarded(self):
        src = (Path(__file__).resolve().parent.parent
               / "scripts" / "build_zweig_a_shards.py").read_text(encoding="utf-8")
        self.assertNotIn("con.execute(\"\"\"", src,
                         "Query am Guard vorbei — bitte ordered() verwenden")

    def test_plausibility_queries_are_guarded(self):
        src = (Path(__file__).resolve().parent.parent
               / "scripts" / "check_plausibility.py").read_text(encoding="utf-8")
        self.assertNotIn("con.execute(f\"\"\"", src,
                         "Query am Guard vorbei — bitte ordered_query() verwenden")


class ShardBuildIsReproducibleTest(unittest.TestCase):
    """Doppellauf auf Mini-Daten mit VARIIERTEM PYTHONHASHSEED.

    Der Guard deckt die SQL-Seite ab. Diese Klasse deckt ab, was er nicht sieht:
    Set- und Dict-Iteration in Python. PYTHONHASHSEED zu variieren macht die
    Klasse ZUVERLÄSSIG sichtbar — sonst hinge der Test davon ab, dass zwei
    zufällige Seeds zufällig verschieden ausfallen.
    """

    @classmethod
    def setUpClass(cls):
        try:
            import duckdb  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("duckdb nicht installiert")

    def _build(self, root, seed):
        """Shard-Build in einem eigenen Prozess mit gesetztem Hash-Seed."""
        env = {**os.environ, "PYTHONHASHSEED": seed}
        script = Path(__file__).resolve().parent.parent / "scripts" / "build_zweig_a_shards.py"
        r = subprocess.run(
            [sys.executable, "-c",
             f"import sys; sys.path.insert(0, {str(script.parent)!r});\n"
             "import build_zweig_a_shards as z; from pathlib import Path;\n"
             f"z.ROOT = Path({str(root)!r});\n"
             "z.PARQUET = z.ROOT/'processed'/'long'/'p3dh_long.parquet';\n"
             "z.OUT = z.ROOT/'processed'/'zweig_a'/'data'; z.SHARDS = z.OUT/'reports';\n"
             "z.OUT.mkdir(parents=True, exist_ok=True); z.main()"],
            env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        return {p.name: p.read_bytes()
                for p in sorted((Path(root) / "processed/zweig_a/data").rglob("*.json"))}

    def _fixture(self, root):
        """Mini-Parquet, das die bekannten Fallen ENTHÄLT: mehrfach belegte
        Koordinaten, zwei Währungen je Report, VIELE Templates plus
        Filing-Indicators (sonst ist die Coverage-Map ein- oder nullelementig
        und die Set-Iteration, die den ersten Vorfall verursacht hat, ist gar
        nicht auslösbar — ein Test, der die Falle nicht enthält, ist grün ohne
        etwas zu beweisen).
        """
        import duckdb
        (Path(root) / "processed" / "long").mkdir(parents=True, exist_ok=True)
        (Path(root) / "processed" / "zweig_a" / "data" / "reports").mkdir(
            parents=True, exist_ok=True)
        templates = ["%02d.00" % t for t in range(10, 40)]
        rows = []
        for i in range(60):
            tid = templates[i % len(templates)]
            # zwei Fakten auf DERSELBEN Koordinate, unterschieden nur durch dp
            for dp, val in (("dpA", "11.5"), ("dpB", "22.5")):
                rows.append(("rs:LEI%016d.CON" % (i % 4), "2025-12-31",
                             "EUR" if i % 7 else "PLN", "4.1", tid,
                             "%04d" % i, "0010", val, None, None, dp,
                             "LEI%016d" % (i % 4), "CON", "Bank %d" % (i % 4),
                             "DE", "Large", False, "T " + tid, "Zeile", "Spalte",
                             "monetary", 1.0))
        # Filing-Indicators: erst dadurch hat resolve_coverage() eine Map mit
        # vielen Schlüsseln, deren Iterationsordnung vom Hash-Seed abhängt.
        cov = Path(root) / "processed" / "filing_indicators.csv"
        cov.write_text(
            "entityID,refPeriod,framework_version,template_id,reported,source_file\n"
            + "".join("rs:LEI%016d.CON,2025-12-31,4.1,%s,%s,x.zip\n" % (e, t, bool(j % 3))
                      for e in range(4) for j, t in enumerate(templates)),
            encoding="utf-8")
        con = duckdb.connect()
        con.execute("""CREATE TABLE t (entityID VARCHAR, refPeriod VARCHAR,
            currency VARCHAR, framework_version VARCHAR, template_id VARCHAR,
            cell_row VARCHAR, cell_col VARCHAR, fact_value_raw VARCHAR,
            open_axis_country VARCHAR, open_axis_dims VARCHAR, datapoint_code VARCHAR,
            lei VARCHAR, scope VARCHAR, bank_name VARCHAR, country VARCHAR,
            institution_type VARCHAR, files_gsii_module BOOLEAN, template_title VARCHAR,
            row_label VARCHAR, col_label VARCHAR, data_type VARCHAR, fx_rate DOUBLE)""")
        con.executemany("INSERT INTO t VALUES (" + ",".join("?" * 22) + ")", rows)
        con.execute(f"COPY t TO '{root}/processed/long/p3dh_long.parquet' (FORMAT PARQUET)")
        con.close()

    def test_two_runs_with_different_hash_seeds_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as root:
            self._fixture(root)
            a = self._build(root, "1")
            b = self._build(root, "97531")
        self.assertEqual(sorted(a), sorted(b), "andere Dateien geschrieben")
        differing = [n for n in a if a[n] != b[n]]
        self.assertEqual(differing, [],
                         f"nicht reproduzierbar bei anderem PYTHONHASHSEED: {differing}")

    def test_fixture_actually_contains_colliding_cells(self):
        """Ein Test, der nur grün ist, weil er den Fall nicht enthält, ist
        schlimmer als keiner — hier wird geprüft, dass die Falle drinsteckt."""
        with tempfile.TemporaryDirectory() as root:
            self._fixture(root)
            self._build(root, "1")
            shard = next((Path(root) / "processed/zweig_a/data/reports").glob("*.json"))
            doc = json.loads(shard.read_text())
        cells = [c for cs in doc["tpl"].values() for c in cs]
        self.assertTrue(any(len(c) == 4 for c in cells),
                        "Fixture enthält keine mehrfach belegte Koordinate")
        self.assertGreater(len(doc["coverage"]), 5,
                           "Fixture erzeugt keine Coverage-Map — die Set-Iteration, "
                           "die den ersten Vorfall verursacht hat, wäre nicht auslösbar")


if __name__ == "__main__":
    unittest.main(verbosity=2)
