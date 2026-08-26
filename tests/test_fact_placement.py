"""Tests für den Placement-Guard (scripts/check_fact_placement.py).

Synthetische Zeilen + Mini-CSVs im Temp-Verzeichnis — läuft ohne die
gitignorierten Rohdaten (frischer Clone, CI, Remote-Session).
"""

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_fact_placement as g  # noqa: E402


def fact(fw="4.1", tid="61.00", row="0010", col="0010", dims="", dp="dp1"):
    return {"framework_version": fw, "template_id": tid, "cell_row": row,
            "cell_col": col, "open_axis_dims": dims, "datapoint_code": dp}


class ClassifyTest(unittest.TestCase):
    def test_placed(self):
        s = g.classify([fact()], {"dp1"})
        self.assertEqual(s["by_framework"]["4.1"]["placed"], 1)
        self.assertEqual(s["unplaceable_total"], 0)

    def test_open_axis_is_not_an_alarm(self):
        # Offene Achse hat im DPM keine statische (row, col) — erwartet, kein Verlust.
        s = g.classify([fact(row="", col="", dims="RIO=eba_GA:NL")], {"dp1"})
        self.assertEqual(s["by_framework"]["4.1"]["open_axis"], 1)
        self.assertEqual(s["unplaceable_total"], 0)

    def test_unplaceable_counted_and_attributed(self):
        s = g.classify([fact(tid="47.00.A", row="", col="", dims="", dp="dpX")], {"dp1"})
        self.assertEqual(s["unplaceable_total"], 1)
        self.assertEqual(s["unplaceable_by_template"]["47.00.A"], 1)

    def test_half_coordinate_counts_as_unplaceable(self):
        # Nur row, keine col -> nicht platzierbar
        s = g.classify([fact(col="")], {"dp1"})
        self.assertEqual(s["unplaceable_total"], 1)

    def test_unknown_dp_detected_even_when_placed(self):
        s = g.classify([fact(dp="dpNEU")], {"dp1"})
        self.assertEqual(s["unknown_dps"], ["dpNEU"])

    def test_frameworks_are_separated(self):
        s = g.classify([fact(fw="4.1"), fact(fw="4.2", row="", col="")], {"dp1"})
        self.assertEqual(s["by_framework"]["4.1"]["placed"], 1)
        self.assertEqual(s["by_framework"]["4.2"]["unplaceable"], 1)


class BridgeDpTest(unittest.TestCase):
    def test_rebound_cell_with_missing_dp_flagged(self):
        rows = [{"template_id": "61.00", "cell_row": "0260", "cell_col": "0010",
                 "dp_41": "dp457441", "dp_42": "dp5490147", "status": "rebound"}]
        broken = g.check_bridge_dps(rows, {"dp457441"})  # dp_42 fehlt
        self.assertEqual(len(broken), 1)
        self.assertEqual(broken[0]["missing"], ["dp5490147"])

    def test_stable_cells_ignored(self):
        rows = [{"template_id": "61.00", "cell_row": "0010", "cell_col": "0010",
                 "dp_41": "dpA", "dp_42": "dpA", "status": "stable"}]
        self.assertEqual(g.check_bridge_dps(rows, set()), [])

    def test_all_dps_known_is_clean(self):
        rows = [{"template_id": "61.00", "cell_row": "0260", "cell_col": "0010",
                 "dp_41": "dpA", "dp_42": "dpB", "status": "rebound"}]
        self.assertEqual(g.check_bridge_dps(rows, {"dpA", "dpB"}), [])


class BaselineGateTest(unittest.TestCase):
    """End-to-end über main(): Baseline anlegen, dann Verschlechterung erzwingen."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.long = d / "long_form_raw.csv"
        self.cb = d / "dpm_codebook.csv"
        self.baseline = d / "placement_baseline.json"
        self.report = d / "placement_report.csv"

        self.cb.write_text("datapoint_code\ndp1\n", encoding="utf-8")
        self._write_long([fact()])

        self._orig = (g.LONG_FORM, g.CODEBOOK, g.BRIDGE, g.BASELINE, g.REPORT, sys.argv)
        g.LONG_FORM, g.CODEBOOK = self.long, self.cb
        g.BRIDGE = d / "no_bridge.csv"          # bewusst nicht vorhanden
        g.BASELINE, g.REPORT = self.baseline, self.report
        sys.argv = ["check_fact_placement.py"]

    def tearDown(self):
        (g.LONG_FORM, g.CODEBOOK, g.BRIDGE, g.BASELINE, g.REPORT, sys.argv) = self._orig
        self.tmp.cleanup()

    def _write_long(self, rows):
        with open(self.long, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    def test_first_run_creates_baseline_then_stays_green(self):
        self.assertEqual(g.main(), 0)
        self.assertTrue(self.baseline.exists())
        self.assertEqual(g.main(), 0)

    def test_new_unplaceable_fact_fails(self):
        self.assertEqual(g.main(), 0)
        self._write_long([fact(), fact(tid="47.00.A", row="", col="", dp="dp1")])
        self.assertEqual(g.main(), 1, "wachsender Fact-Verlust muss den Guard röten")

    def test_new_unknown_dp_fails(self):
        self.assertEqual(g.main(), 0)
        self._write_long([fact(dp="dpNEU")])
        self.assertEqual(g.main(), 1, "neuer unbekannter dp-Code muss anschlagen")

    def test_accepted_loss_stays_green(self):
        # Verlust existiert schon beim Anlegen der Baseline -> darf nicht röten
        self._write_long([fact(tid="47.00.A", row="", col="", dp="dp1")])
        self.assertEqual(g.main(), 0)
        self.assertEqual(g.main(), 0)

    def test_update_baseline_accepts_new_state(self):
        self.assertEqual(g.main(), 0)
        self._write_long([fact(), fact(tid="47.00.A", row="", col="", dp="dp1")])
        self.assertEqual(g.main(), 1)
        sys.argv = ["check_fact_placement.py", "--update-baseline"]
        self.assertEqual(g.main(), 0)
        sys.argv = ["check_fact_placement.py"]
        self.assertEqual(g.main(), 0)
        base = json.loads(self.baseline.read_text(encoding="utf-8"))
        self.assertEqual(base["unplaceable_by_framework"]["4.1"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
