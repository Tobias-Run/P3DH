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


class JoinFanOutTest(unittest.TestCase):
    """Der Label-Join in build_zweig_b.py lautet seit #56

        AND (cb.row = b.cell_row OR cb.row = '*') AND cb.col = b.cell_col

    Das ist nur dann kein Fan-out, wenn KEIN (datapoint, template, col) sowohl
    eine offene als auch eine feste Zeile trägt — sonst träfe ein Fakt zwei
    Codebook-Zeilen und würde verdoppelt. Still, versteht sich.

    Heute gilt das (0 von 14.292 Einträgen). Es ist aber eine Eigenschaft des
    DPM, keine Zusage — deshalb hier festgehalten statt im Kopf behalten.
    """

    def test_no_datapoint_has_both_an_open_and_a_fixed_row(self):
        import collections
        import csv
        path = (Path(__file__).resolve().parent.parent
                / "codebook" / "dpm_codebook.csv")
        if not path.exists():
            self.skipTest("Codebook nicht vorhanden")
        seen = collections.defaultdict(set)
        with path.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                seen[(r["datapoint_code"], r["template"], r["col"])].add(r["row"])
        both = [k for k, v in seen.items() if bc.OPEN_AXIS in v and len(v) > 1]
        self.assertEqual(both, [], f"Join würde Fakten verdoppeln: {both[:5]}")


class AxisLabelMapTest(unittest.TestCase):
    """codebook.json trägt seit dem Viewer-Fix eine `axis`-Map: {template:
    {Achsenwert: Klartext}}. Sie leistet zweierlei — sie löst 'NL' zu
    'Netherlands' auf, UND ihr Vorhandensein sagt dem Viewer, dass die
    Zeilenreihenfolge dieses Templates keine Modellordnung ist (dort wird nach
    Betrag sortiert statt alphabetisch).

    Der Test läuft gegen die gebauten Daten, wenn sie da sind — die Map entsteht
    aus dem Parquet, nicht aus einer reinen Funktion.
    """

    def _codebook(self):
        import json
        p = (Path(__file__).resolve().parent.parent
             / "processed" / "zweig_a" / "data" / "codebook.json")
        if not p.exists():
            self.skipTest("codebook.json nicht gebaut")
        return json.loads(p.read_text(encoding="utf-8"))

    def test_axis_map_exists_and_resolves_ccyb1(self):
        axis = self._codebook().get("axis", {})
        self.assertIn("K_67.01.a", axis, "CCyB1 braucht die Länderauflösung")
        self.assertEqual(axis["K_67.01.a"].get("NL"), "Netherlands")
        self.assertEqual(axis["K_67.01.a"].get("DE"), "Germany")

    def test_non_country_rows_stay_unresolved(self):
        """'x1' (Summenzeile) und 'x28' (übrige Länder) sind keine Staaten. Sie
        bekommen KEINEN erfundenen Klartext — der Viewer zeigt den Code und
        sortiert sie ans Ende, statt sie oben wie ein Land aussehen zu lassen."""
        axis = self._codebook().get("axis", {}).get("K_67.01.a", {})
        self.assertNotIn("x1", axis)
        self.assertNotIn("x28", axis)

    def test_fixed_axis_templates_have_no_entry(self):
        """Templates mit fester DPM-Zeile dürfen NICHT in der Map stehen —
        sonst würde der Viewer ihre Modellordnung (Zwischensummen, Gliederung)
        gegen eine Betragssortierung tauschen."""
        axis = self._codebook().get("axis", {})
        self.assertNotIn("K_61.00", axis, "KM1 hat feste Zeilen")
        self.assertNotIn("K_60.00.a", axis, "OV1 hat feste Zeilen")


class CodebookMarkerTest(unittest.TestCase):
    def test_open_axis_marker_is_the_star(self):
        """Parser und Codebook müssen sich auf dasselbe Zeichen einigen —
        sonst greift die Zeilenbildung stillschweigend nie."""
        self.assertEqual(bc.OPEN_AXIS, xp.OPEN_AXIS)
        self.assertEqual(bc.OPEN_AXIS, "*")


if __name__ == "__main__":
    unittest.main(verbosity=2)
