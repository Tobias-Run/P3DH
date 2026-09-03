"""Tests für die offene Zeilenachse (#56).

Der Befund: 409.057 Fakten (18 % des Bestands) lagen im Parquet ohne Zeile und
waren damit weder im Viewer noch in einer Auswertung sichtbar. Ursache war
NICHT eine fehlende Quelle — das DPM führt diese Zellen als

    {K_67.01.a, r*, c0010}

Die Spalte ist fest, nur die Zeile offen: bei CCyB1 ist sie das Land, und der
Wert dazu steht in der Quelldatei (`RIO=eba_GA:AL`). Das alte Muster verlangte
`r(\\w+)`, traf `*` nicht, und `if not parsed: continue` verwarf den ganzen
Eintrag — samt der bekannten Spalte, ohne eine Spur zu hinterlassen.

Gemessene Formen in DPM 2.0 v4.2 (alle CellCodes der geladenen dp-Codes):

    r#,c#      35.011   Normalfall
    r#,c#,s*    2.853   feste Zelle, offenes Blatt
    r#,c#,s#    1.513
    r*,c#         199   offene Zeile
    r*,c#,s*      129   offene Zeile + offenes Blatt

`c*` kommt nicht vor — die Spalte ist immer fest. Deshalb behandelt der Parser
nur die Zeile; ein `c*` würde als unparsbare Form gezählt und gemeldet, nicht
still verworfen.
"""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_codebook as bc  # noqa: E402
import xbrl_csv_parser as xp  # noqa: E402


class ParseCellcodeTest(unittest.TestCase):
    def test_plain_coordinate(self):
        self.assertEqual(bc.parse_cellcode("{K_61.00, r0010, c0010}"),
                         ("K_61.00", "0010", "0010"))

    def test_open_row_axis_is_recognised(self):
        """Der Fall, der 409.057 Fakten gekostet hat."""
        self.assertEqual(bc.parse_cellcode("{K_67.01.a, r*, c0010}"),
                         ("K_67.01.a", "*", "0010"))

    def test_open_row_and_open_sheet(self):
        """Form `r*,c#,s*` — das offene Blatt steht hinter der Spalte und darf
        die Erkennung nicht stören."""
        self.assertEqual(bc.parse_cellcode("{K_29.01.a, r*, c0010, s*}"),
                         ("K_29.01.a", "*", "0010"))

    def test_fixed_cell_with_open_sheet_still_parses(self):
        self.assertEqual(bc.parse_cellcode("{K_20.00, r0040, c0020, s*}"),
                         ("K_20.00", "0040", "0020"))

    def test_the_column_survives_an_open_row(self):
        """Der Kern des Fehlers: die SPALTE steht im CellCode und ging mit
        verloren, obwohl sie bekannt ist."""
        self.assertEqual(bc.parse_cellcode("{K_66.02.a, r*, c0020}")[2], "0020")

    def test_garbage_yields_none_so_the_caller_can_count_it(self):
        self.assertIsNone(bc.parse_cellcode("völlig anderes Format"))
        self.assertIsNone(bc.parse_cellcode(""))


class AxisMemberTest(unittest.TestCase):
    def test_geographic_member_becomes_iso_code(self):
        """`eba_GA:AL` -> `AL`, der Schlüssel, den geo_names.csv auflöst."""
        self.assertEqual(xp.axis_member({"RIO": "eba_GA:AL"}), "AL")

    def test_non_geographic_axis_keeps_its_member(self):
        self.assertEqual(xp.axis_member({"qEEA": "eba_qAE:qx2071"}), "qx2071")

    def test_value_without_colon_passes_through(self):
        self.assertEqual(xp.axis_member({"qADP": "Freitext"}), "Freitext")

    def test_freetext_ending_in_colon_keeps_the_whole_value(self):
        """CC2 (66.02) und LI2/LI3 (64.01) führen als Zeile den Bilanzposten
        des Instituts — Freitext, oft mit Doppelpunkt am Ende. Blind hinter dem
        letzten ':' abzuschneiden lieferte einen leeren Schlüssel und liess
        192 Fakten ohne Zeile zurück."""
        self.assertEqual(
            xp.axis_member({"qADQ": "100. Provisions for risks and charges:"}),
            "100. Provisions for risks and charges:")
        self.assertEqual(xp.axis_member({"qADQ": "l. Fondi per rischi e oneri:"}),
                         "l. Fondi per rischi e oneri:")

    def test_colon_inside_freetext_still_splits_only_at_the_end(self):
        """Ein Doppelpunkt MITTEN im Text bleibt ein Trenner — das ist der
        Normalfall 'domain:member' und darf nicht verloren gehen."""
        self.assertEqual(xp.axis_member({"RIO": "eba_GA:DE"}), "DE")

    def test_several_dimensions_are_combined_not_guessed(self):
        """Form `r*,c#,s*`: welche Achse fachlich die Zeile ist, sagt das DPM
        hier nicht. Statt zu raten geht die Kombination ein."""
        self.assertEqual(
            xp.axis_member({"RIO": "eba_GA:DE", "qEEA": "eba_qAE:qx1"}), "DE|qx1")

    def test_no_dimension_yields_no_row(self):
        """Ohne Achsenwert gibt es keine Zeile — und es wird keine erfunden
        (Arbeitsprinzip 3, 'Fehlt != Null')."""
        self.assertEqual(xp.axis_member({}), "")

    def test_empty_values_are_skipped(self):
        self.assertEqual(xp.axis_member({"RIO": "", "qX": "eba_q:v"}), "v")

    def test_order_follows_the_source_columns(self):
        """Reproduzierbarkeit: die Reihenfolge stammt aus der Spaltenfolge der
        Quelldatei, nicht aus einer Hash-Ordnung."""
        d = {"b": "x:2", "a": "x:1"}
        self.assertEqual(xp.axis_member(d), "2|1")


class CodebookMarkerTest(unittest.TestCase):
    def test_open_axis_marker_is_the_star(self):
        """Parser und Codebook müssen sich auf dasselbe Zeichen einigen —
        sonst greift die Zeilenbildung stillschweigend nie."""
        self.assertEqual(bc.OPEN_AXIS, xp.OPEN_AXIS)
        self.assertEqual(bc.OPEN_AXIS, "*")


if __name__ == "__main__":
    unittest.main(verbosity=2)
