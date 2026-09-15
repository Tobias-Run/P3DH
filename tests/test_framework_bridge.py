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

    def test_the_same_multiple_dps_in_both_versions_are_not_ambiguous(self):
        """Der Befund aus #70. Bis dahin kam die Mehrfach-Prüfung VOR dem
        Gleichheitstest — und damit bekam eine Koordinate mit identischem
        dp-Satz das Etikett `ambiguous`, obwohl die Zuordnung feststeht: sie
        ist die Identität.

        Gemessen betraf das ALLE 123 vermeintlich mehrdeutigen Zellen des
        Bestands; nach der Korrektur bleiben null übrig. Der Unterschied ist
        nicht kosmetisch — `ambiguous` sagt dem Leser „hier ist nichts zu
        holen", und das war falsch."""
        bridge = build_bridge([
            obs("4.1", "60.00.A", "0120", "0020", "dpA"),
            obs("4.1", "60.00.A", "0120", "0020", "dpB"),
            obs("4.2", "60.00.A", "0120", "0020", "dpA"),
            obs("4.2", "60.00.A", "0120", "0020", "dpB"),
        ])
        self.assertEqual(bridge[0]["status"], "mehrfach")
        # deterministisch sortiert serialisiert
        self.assertEqual(bridge[0]["dp_41"], "dpA|dpB")
        self.assertEqual(bridge[0]["dp_41"], bridge[0]["dp_42"])

    def test_differing_multiple_dps_stay_ambiguous(self):
        """Erst wenn die Sätze AUSEINANDERGEHEN, kann die Brücke nichts
        sagen. Fiele diese Einstufung weg, verschwände die einzige Klasse, für
        die sie gedacht war."""
        bridge = build_bridge([
            obs("4.1", "60.00.A", "0120", "0020", "dpA"),
            obs("4.1", "60.00.A", "0120", "0020", "dpB"),
            obs("4.2", "60.00.A", "0120", "0020", "dpA"),
            obs("4.2", "60.00.A", "0120", "0020", "dpC"),
        ])
        self.assertEqual(bridge[0]["status"], "ambiguous")

    def test_a_single_dp_pair_never_becomes_mehrfach(self):
        """`mehrfach` heisst „mehrere Werte auf einer Koordinate". Bei genau
        einem dp-Code je Version wäre das eine Falschaussage."""
        bridge = build_bridge([
            obs("4.1", "61.00", "0010", "0010", "dp1"),
            obs("4.2", "61.00", "0010", "0010", "dp1"),
        ])
        self.assertEqual(bridge[0]["status"], "stable")

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
