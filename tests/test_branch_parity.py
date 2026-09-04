"""Tests für scripts/check_branch_parity.py.

Die Prüfung ersetzt den dekommissionierten CSV-Viewer. Der war als
„unabhängige Gegenprobe" begründet, lief aber seit dem Voll-Load nicht mehr
(der Browser-Tab stirbt beim Parsen der 413-MB-Long-Form am Speicher) und war
13 Commits hinterher — er kannte weder die offene Zeilenachse (#56) noch den
Zell-Diskriminator (#52) noch die Coverage-Zustände. Eine Gegenprobe, die
planmäßig abweicht, ist keine.

Die README-Zusage „Werte byte-identisch verifiziert" war damit ungedeckt.
Diese Tests decken die Prüfung ab, die sie jetzt einlöst — mit eigener
Fixture, damit sie auch ohne gebauten Bestand laufen.
"""

from pathlib import Path
import csv
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_branch_parity as bp  # noqa: E402

HEADER = ["entityID", "refPeriod", "framework_version", "template_id",
          "template_reported", "datapoint_code", "cell_row", "cell_col",
          "open_axis_dims", "fact_value", "baseCurrency", "decimalsMonetary",
          "source_file"]


def _row(eid, rp, tid, row, col, val, dp="dp1"):
    return [eid, rp, "4.1", tid, "True", dp, row, col, "", val,
            "iso4217:EUR", "-6", "x.zip"]


class ParityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self._orig = (bp.LONG_FORM, bp.SHARDS)
        bp.LONG_FORM = root / "long_form_raw.csv"
        bp.SHARDS = root / "reports"
        bp.SHARDS.mkdir()

        self.eid, self.rp = "rs:LEI00000000000000001.CON", "2025-12-31"
        self.rows = [
            _row(self.eid, self.rp, "61.00", "0010", "0010", "100.0"),
            _row(self.eid, self.rp, "61.00", "0050", "0010", "0.184"),
            # Dieselbe Koordinate ZWEIMAL mit verschiedenen Werten (#52) —
            # der Fall, an dem ein Mengenvergleich blind wäre.
            _row(self.eid, self.rp, "67.01.A", "NL", "0060", "5.0", "dpA"),
            _row(self.eid, self.rp, "67.01.A", "NL", "0060", "7.0", "dpB"),
            # ohne cell_row: gehört in keinen Shard, muss beidseitig raus
            _row(self.eid, self.rp, "99.00", "", "0010", "42.0"),
        ]
        self._write_long_form(self.rows)
        self._write_shard(self.eid, self.rp, {
            "61.00": [["0010", "0010", "100.0"], ["0050", "0010", "0.184"]],
            "67.01.A": [["NL", "0060", "5.0", "dpA"], ["NL", "0060", "7.0", "dpB"]],
        })

    def tearDown(self):
        bp.LONG_FORM, bp.SHARDS = self._orig
        self.tmp.cleanup()

    def _write_long_form(self, rows):
        with open(bp.LONG_FORM, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(HEADER)
            w.writerows(rows)

    def _write_shard(self, eid, rp, tpl, coverage=None):
        name = eid.replace(":", "_") + "__" + rp + ".json"
        (bp.SHARDS / name).write_text(
            json.dumps({"tpl": tpl, "coverage": coverage or {}}), encoding="utf-8")

    def _run(self):
        """-> Exit-Code. 0 heißt Parität."""
        argv = sys.argv
        sys.argv = ["check_branch_parity.py"]
        try:
            bp.main()
            return 0
        except SystemExit as e:
            return e.code or 0
        finally:
            sys.argv = argv

    # ---- der gute Fall -----------------------------------------------------

    def test_matching_shard_passes(self):
        self.assertEqual(self._run(), 0)

    def test_cells_without_a_row_are_excluded_on_both_sides(self):
        """`99.00` steht in der Long-Form ohne `cell_row` und in keinem Shard.
        Das ist so gebaut und darf nicht als Abweichung gelten — sonst wäre die
        Prüfung ab dem ersten Lauf rot und damit wertlos."""
        self.assertEqual(self._run(), 0)

    # ---- Drift, die sie fangen muss ---------------------------------------

    def test_a_changed_value_is_caught(self):
        self._write_shard(self.eid, self.rp, {
            "61.00": [["0010", "0010", "999.0"], ["0050", "0010", "0.184"]],
            "67.01.A": [["NL", "0060", "5.0", "dpA"], ["NL", "0060", "7.0", "dpB"]],
        })
        self.assertEqual(self._run(), 1)

    def test_a_lost_duplicate_is_caught(self):
        """Der Grund für die Multimenge: 88.155 Koordinaten tragen je Report
        mehr als einen Fakt. Fällt einer davon weg, sieht die Zellmenge
        unverändert aus — der Wert ist trotzdem verschwunden."""
        self._write_shard(self.eid, self.rp, {
            "61.00": [["0010", "0010", "100.0"], ["0050", "0010", "0.184"]],
            "67.01.A": [["NL", "0060", "5.0", "dpA"]],
        })
        self.assertEqual(self._run(), 1)

    def test_a_string_reformat_is_caught(self):
        """Verglichen wird als Zeichenkette, nicht über float(). '100' statt
        '100.0' ist numerisch dasselbe und trotzdem ein Drift — der Shard soll
        die Meldung tragen, nicht unsere Formatierung davon."""
        self._write_shard(self.eid, self.rp, {
            "61.00": [["0010", "0010", "100"], ["0050", "0010", "0.184"]],
            "67.01.A": [["NL", "0060", "5.0", "dpA"], ["NL", "0060", "7.0", "dpB"]],
        })
        self.assertEqual(self._run(), 1)

    def test_a_cell_invented_by_the_shard_is_caught(self):
        self._write_shard(self.eid, self.rp, {
            "61.00": [["0010", "0010", "100.0"], ["0050", "0010", "0.184"],
                      ["0070", "0010", "0.23"]],
            "67.01.A": [["NL", "0060", "5.0", "dpA"], ["NL", "0060", "7.0", "dpB"]],
        })
        self.assertEqual(self._run(), 1)

    def test_a_shard_without_any_long_form_facts_is_an_error(self):
        """Ein Shard ohne Gegenstück behauptet Daten, die es nicht gibt — die
        gefährlichere Richtung, weil sie im Viewer sichtbar wird."""
        self._write_shard("rs:LEI00000000000000009.CON", self.rp,
                          {"61.00": [["0010", "0010", "1.0"]]})
        self.assertEqual(self._run(), 1)

    # ---- die erlaubte Abweichung ------------------------------------------

    def test_a_report_without_placeable_cells_is_not_an_error(self):
        """#28: ein Institut kann für einen Stichtag deklarieren und nichts
        offenlegen. Dann gibt es keinen Shard — und das ist richtig so."""
        self.rows.append(_row("rs:LEI00000000000000002.CON", self.rp,
                              "30.01", "", "0010", "5.0"))
        self._write_long_form(self.rows)
        self.assertEqual(self._run(), 0)


class ShardKeyTest(unittest.TestCase):
    """Der Dateiname ist der einzige Weg vom Shard zurück zum Report."""

    def test_round_trip(self):
        self.assertEqual(
            bp.shard_key(Path("rs_LEI00000000000000001.CON__2025-12-31.json")),
            "rs:LEI00000000000000001.CON|2025-12-31")

    def test_only_the_first_underscore_becomes_a_colon(self):
        """entityID trägt genau einen Doppelpunkt ('rs:'). Ein Unterstrich
        weiter hinten gehört zum Namen und darf nicht zurückgedreht werden."""
        self.assertEqual(
            bp.shard_key(Path("rs_ABC_DEF__2025-06-30.json")),
            "rs:ABC_DEF|2025-06-30")

    def test_a_name_without_the_separator_is_rejected(self):
        self.assertIsNone(bp.shard_key(Path("kaputt.json")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
