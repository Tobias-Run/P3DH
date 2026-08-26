"""Tests für die Brücken-Logik in scripts/build_framework_bridge.py.

Synthetische Zell-Beobachtungen — kein Parquet nötig, läuft auf frischem Clone.
"""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from build_framework_bridge import build_bridge  # noqa: E402


def obs(fw, tmpl, r, c, dp, rl="rowlbl", cl="collbl"):
    return (fw, tmpl, r, c, dp, rl, cl)


class BuildBridgeTest(unittest.TestCase):
    def test_stable_cell(self):
        bridge = build_bridge([
            obs("4.1", "61.00", "0010", "0010", "dp1"),
            obs("4.2", "61.00", "0010", "0010", "dp1"),
        ])
        self.assertEqual(len(bridge), 1)
        self.assertEqual(bridge[0]["status"], "stable")
        self.assertEqual(bridge[0]["dp_41"], "dp1")
        self.assertEqual(bridge[0]["dp_42"], "dp1")

    def test_rebound_cell(self):
        bridge = build_bridge([
            obs("4.1", "61.00", "0260", "0010", "dp457441"),
            obs("4.2", "61.00", "0260", "0010", "dp5490147"),
        ])
        self.assertEqual(bridge[0]["status"], "rebound")
        self.assertEqual(bridge[0]["dp_41"], "dp457441")
        self.assertEqual(bridge[0]["dp_42"], "dp5490147")

    def test_single_version_cell_excluded(self):
        # Nur in 4.1 beobachtet -> keine Brücken-Aussage (Frequenz/Anwendbarkeit!)
        bridge = build_bridge([
            obs("4.1", "66.01.A", "0010", "0010", "dp9"),
        ])
        self.assertEqual(bridge, [])

    def test_ambiguous_multiple_dps_per_version(self):
        bridge = build_bridge([
            obs("4.1", "60.00.A", "0120", "0020", "dpA"),
            obs("4.1", "60.00.A", "0120", "0020", "dpB"),
            obs("4.2", "60.00.A", "0120", "0020", "dpA"),
            obs("4.2", "60.00.A", "0120", "0020", "dpB"),
        ])
        self.assertEqual(bridge[0]["status"], "ambiguous")
        # deterministisch sortiert serialisiert
        self.assertEqual(bridge[0]["dp_41"], "dpA|dpB")

    def test_output_sorted_deterministically(self):
        bridge = build_bridge([
            obs("4.1", "71.00", "0210", "0010", "dp1"),
            obs("4.2", "71.00", "0210", "0010", "dp1"),
            obs("4.1", "61.00", "0010", "0010", "dp2"),
            obs("4.2", "61.00", "0010", "0010", "dp2"),
        ])
        self.assertEqual([b["template_id"] for b in bridge], ["61.00", "71.00"])

    def test_first_nonempty_label_kept(self):
        bridge = build_bridge([
            obs("4.1", "61.00", "0010", "0010", "dp1", rl="", cl=""),
            obs("4.2", "61.00", "0010", "0010", "dp1", rl="Own funds", cl="Amount"),
        ])
        self.assertEqual(bridge[0]["row_label"], "Own funds")
        self.assertEqual(bridge[0]["col_label"], "Amount")


if __name__ == "__main__":
    unittest.main(verbosity=2)
