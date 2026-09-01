"""Tests für scripts/build_zweig_a_shards.py — Schwerpunkt Coverage-Auflösung
("Fehlt != Null", Issue #21).

Der Kern ist resolve_coverage(): eine reine Funktion, die die Filing-Indicator-
Deklarationen eines Reports auf die Template-IDs abbildet, die der Viewer
tatsächlich rendert. Genau hier lag der Fehler der ersten Fassung — die
Deklarationen kommen auf Basis-IDs ('60.00'), die Daten tragen Sub-Buchstaben
('60.00.A'), und ein reiner Exact-Match verfehlt damit 60 % des Bestands.
"""

from pathlib import Path
import tempfile
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_zweig_a_shards as z  # noqa: E402


class BaseTidTest(unittest.TestCase):
    def test_strips_single_uppercase_subletter(self):
        self.assertEqual(z.base_tid("60.00.A"), "60.00")
        self.assertEqual(z.base_tid("83.01.D"), "83.01")

    def test_leaves_plain_ids_alone(self):
        self.assertEqual(z.base_tid("61.00"), "61.00")
        self.assertEqual(z.base_tid("00.01"), "00.01")


class CellDiscriminatorTest(unittest.TestCase):
    """#52: was unterscheidet zwei Fakten auf derselben (template,row,col)?"""

    def test_country_wins(self):
        self.assertEqual(z.cell_discriminator("Niederlande", "RIO=eba_GA:NL", "dp1"),
                         "Niederlande")

    def test_raw_dimension_when_no_country(self):
        self.assertEqual(z.cell_discriminator(None, "qEEA=eba_qAE:qx2071", "dp1"),
                         "qEEA=eba_qAE:qx2071")

    def test_datapoint_as_last_resort(self):
        """LIQ1 (74.00.C) hat vier dp-Codes auf r0150/c0050 mit identischen
        Labels — unser Codebook kennt die unterscheidende Achse nicht."""
        self.assertEqual(z.cell_discriminator(None, None, "dp3525361"), "dp3525361")

    def test_nothing_yields_empty(self):
        self.assertEqual(z.cell_discriminator(None, None, None), "")


class CollapseCellsTest(unittest.TestCase):
    def test_unique_cells_keep_three_elements(self):
        """94 % der Zellen sind eindeutig — dort waere der Diskriminator nur
        Ballast im Shard."""
        out = z.collapse_cells([("0010", "0010", "5", "dpA"),
                                ("0020", "0010", "7", "dpB")])
        self.assertEqual(out, [["0010", "0010", "5"], ["0020", "0010", "7"]])

    def test_colliding_cells_keep_discriminator(self):
        out = z.collapse_cells([("0010", "0010", "5", "NL"),
                                ("0010", "0010", "7", "DE")])
        self.assertEqual(out, [["0010", "0010", "5", "NL"],
                               ["0010", "0010", "7", "DE"]])

    def test_collision_is_per_coordinate_not_per_template(self):
        """Eine kollidierende Koordinate darf die uebrigen Zellen desselben
        Templates nicht mit aufblaehen."""
        out = z.collapse_cells([("0010", "0010", "5", "NL"),
                                ("0010", "0010", "7", "DE"),
                                ("0020", "0010", "9", "dpX")])
        self.assertEqual(len(out[0]), 4)
        self.assertEqual(len(out[2]), 3)

    def test_input_order_is_preserved(self):
        """Die Sortierung kommt aus SQL und traegt die Determiniertheit —
        collapse_cells darf sie nicht antasten."""
        rows = [("0010", "0010", str(i), f"d{i}") for i in range(5)]
        self.assertEqual([c[2] for c in z.collapse_cells(rows)],
                         ["0", "1", "2", "3", "4"])

    def test_same_value_twice_still_counts_as_collision(self):
        out = z.collapse_cells([("0010", "0010", "5", "NL"),
                                ("0010", "0010", "5", "DE")])
        self.assertTrue(all(len(c) == 4 for c in out))


class LoadCoverageMapTest(unittest.TestCase):
    def _write(self, rows):
        root = Path(tempfile.mkdtemp())
        cov = root / "processed" / "filing_indicators.csv"
        cov.parent.mkdir(parents=True, exist_ok=True)
        cov.write_text(
            "entityID,refPeriod,framework_version,template_id,reported,source_file\n"
            + "".join(rows), encoding="utf-8")
        return root

    def test_tracks_true_false_and_missing(self):
        root = self._write([
            "rs:LEI00000000000000001.CON,2025-12-31,4.1,61.00,True,x.zip\n",
            "rs:LEI00000000000000001.CON,2025-12-31,4.1,99.00,False,x.zip\n",
        ])
        cov = z.load_coverage_map(root)["rs:LEI00000000000000001.CON|2025-12-31"]
        self.assertTrue(cov["61.00"])
        self.assertFalse(cov["99.00"])
        self.assertNotIn("67.01", cov)

    def test_missing_file_yields_empty_map(self):
        self.assertEqual(z.load_coverage_map(Path(tempfile.mkdtemp())), {})

    def test_rows_with_empty_keys_are_skipped(self):
        root = self._write([",2025-12-31,4.1,61.00,True,x.zip\n",
                            "rs:LEI00000000000000001.CON,2025-12-31,4.1,,True,x.zip\n"])
        self.assertEqual(z.load_coverage_map(root), {})


class ResolveCoverageTest(unittest.TestCase):
    def test_exact_match(self):
        cov = z.resolve_coverage({"61.00": True}, {"61.00"})
        self.assertEqual(cov, {"61.00": "reported"})

    def test_subletter_resolves_via_base_id(self):
        """Der Fall, der die erste Fassung gerissen hat: deklariert wird '60.00',
        gemeldet werden '60.00.A' und '60.00.B'."""
        cov = z.resolve_coverage({"60.00": True}, {"60.00.A", "60.00.B"})
        self.assertEqual(cov, {"60.00.A": "reported", "60.00.B": "reported"})

    def test_subletter_base_id_produces_no_phantom(self):
        """Die Basis-ID darf NICHT zusätzlich als eigener (leerer) Eintrag
        auftauchen — das waren die 54 Phantom-Sektionen."""
        cov = z.resolve_coverage({"01.00": True}, {"01.00.A", "01.00.B"})
        self.assertNotIn("01.00", cov)
        self.assertEqual(len(cov), 2)

    def test_exact_match_wins_over_base(self):
        """14 der 114 deklarierten IDs tragen selbst einen Sub-Buchstaben —
        deren eigene Deklaration muss die der Basis-ID schlagen."""
        cov = z.resolve_coverage({"63.01": False, "63.01.C": True}, {"63.01.C"})
        self.assertEqual(cov["63.01.C"], "reported")

    def test_declared_false_without_data_is_an_omission(self):
        cov = z.resolve_coverage({"47.00": False}, set())
        self.assertEqual(cov, {"47.00": "not-reported"})

    def test_declared_false_with_data_stays_not_reported(self):
        """Widersprüchliche Meldung: als nicht offengelegt deklariert, aber
        Fakten vorhanden. Die Deklaration ist die Aussage des Instituts und
        wird nicht stillschweigend überschrieben."""
        cov = z.resolve_coverage({"61.00": False}, {"61.00"})
        self.assertEqual(cov["61.00"], "not-reported")

    def test_declared_true_without_data_is_our_gap_not_an_omission(self):
        cov = z.resolve_coverage({"83.01": True}, set())
        self.assertEqual(cov, {"83.01": "reported-empty"})

    def test_undeclared_template_is_absent_not_guessed(self):
        """Kern von Arbeitsprinzip 3: ohne Deklaration KEINE Aussage. Die erste
        Fassung hat hier 'not-applicable' behauptet — die stärkste mögliche
        Aussage aus der dünnsten Datenlage."""
        cov = z.resolve_coverage({}, {"99.00"})
        self.assertEqual(cov, {})
        cov = z.resolve_coverage({"61.00": True}, {"61.00", "99.00"})
        self.assertNotIn("99.00", cov)

    def test_no_data_template_left_unresolved_in_a_mixed_report(self):
        declared = {"60.00": True, "61.00": True, "47.00": False}
        data = {"60.00.A", "60.00.B", "61.00"}
        cov = z.resolve_coverage(declared, data)
        for tid in data:
            self.assertIn(tid, cov, f"{tid} ohne Coverage-Eintrag")
        self.assertEqual(cov["47.00"], "not-reported")

    def test_declarations_are_not_mutated(self):
        """resolve_coverage darf die geteilte Deklarations-Map nicht anfassen
        (die erste Fassung hat via setdefault in sie hineingeschrieben)."""
        declared = {"60.00": True}
        before = dict(declared)
        z.resolve_coverage(declared, {"60.00.A"})
        self.assertEqual(declared, before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
