"""Zeilenlabels haengen an der Zelle, nicht an der ersten gemeldeten Spalte.

## Der Fund

Bei Adyen N.V. (82.00.A, 2025-12-31) war die Tabelle im Viewer praktisch
unbeschriftet: von acht Zeilen trug genau eine ein Label. Es sah aus, als
fehlten Daten — die Daten waren vollstaendig da, es fehlte der Schluessel.

Der Viewer holte das Zeilenlabel ueber die ERSTE Spalte, die der Report meldet:

    const e = CB.get(tcode+'|'+r+'|'+(cols[0]||''));  return e ? e.rl : '';

`cols` entsteht aus den gemeldeten Zellen und wird sortiert. Adyen meldet in
82.00.A eine Zelle in Spalte `00`, und `'00' < '0010'`. Das Codebook kennt diese
Spalte genau einmal, `K_82.00.a|0060|00` — also traf der Lookup fuer Zeile 0060
und ging fuer jede andere Zeile ins Leere.

Welche Spalten ein Report meldet, entscheidet der MELDER. Ein Label an dieser
Auswahl aufzuhaengen macht die Beschriftung von einer Eigenschaft der Einreichung
abhaengig, die mit ihr nichts zu tun hat.

## Warum es niemandem auffiel

Es gibt kein Fehlerbild. Eine leere Beschriftung sieht aus wie eine Zeile ohne
Label — und die gibt es legitim (offene Achsen mit Freitext). Dieselbe Klasse wie
#55 und #57: kein Fehler, nur eine stille Luecke.

Gemessen ueber den Bestand: 53.045 Zeilen ohne Label, davon **15.350 in 744
Reports allein durch die falsche Spaltenwahl** — und kein einziger mehrdeutiger
Fall. Die restlichen 37.695 kennt das Codebook wirklich nicht; das sind die
Freitext-Zeilenachsen (64.02, 66.02.*), wo der Zeilencode selbst der Text ist.
"""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent
VIEWER = ROOT / "processed" / "zweig_a" / "viewer_json.html"


def _fn(src, name):
    """Den Rumpf einer `const <name>=` Pfeilfunktion herausschneiden."""
    start = src.index(f"const {name}=")
    return src[start:start + 400]


class RowLabelLookupTest(unittest.TestCase):
    def setUp(self):
        self.src = VIEWER.read_text(encoding="utf-8")

    def test_the_row_label_does_not_hang_on_the_first_reported_column(self):
        """Der eigentliche Defekt. `cols[0]` ist eine Eigenschaft der
        Einreichung, keine des Modells."""
        body = _fn(self.src, "rowLbl")
        self.assertNotIn("cols[0]", body,
                         "rowLbl haengt wieder an der ersten gemeldeten Spalte — "
                         "faellt die im Codebook aus, verschwindet das Label "
                         "JEDER Zeile")

    def test_the_row_label_scans_the_columns(self):
        body = _fn(self.src, "rowLbl")
        self.assertIn("for(const c of cols)", body,
                      "rowLbl sucht nicht ueber die Spalten")
        self.assertIn("e.rl", body)

    def test_an_empty_label_does_not_end_the_search(self):
        """K_82.00.a|0060|00 existiert, traegt aber ein LEERES Spaltenlabel.
        Beim ersten Treffer stehenzubleiben liefert dort '' statt zu suchen."""
        for name in ("rowLbl", "colLbl"):
            with self.subTest(fn=name):
                body = _fn(self.src, name)
                attr = "rl" if name == "rowLbl" else "cl"
                self.assertRegex(
                    body, rf"if\(e\s*&&\s*e\.{attr}\)",
                    f"{name} bricht beim ersten Codebook-Treffer ab, statt auf "
                    f"ein nicht leeres Label zu pruefen")

    def test_the_open_axis_still_wins(self):
        """Bei offener Achse IST der Achsenwert das Label (#56) — der
        Codebook-Lookup darf ihn nicht ueberstimmen."""
        body = _fn(self.src, "rowLbl")
        axis = body.index("axisMap")
        scan = body.index("for(const c of cols)")
        self.assertLess(axis, scan,
                        "Die Achsenkarte wird erst nach dem Codebook gefragt")


class AdyenRegressionTest(unittest.TestCase):
    """Die konkrete Konstellation, an der es aufgefallen ist — als Tabelle
    nachgestellt, damit der Test ohne Bestand laeuft."""

    # (Zeile, Spalte) -> Zeilenlabel, wie im echten Codebook fuer K_82.00.a
    CODEBOOK = {("0010", "0010"): "005 Cash balances at central banks",
                ("0010", "0020"): "005 Cash balances at central banks",
                ("0020", "0010"): "010 Loans and advances",
                ("0020", "0020"): "010 Loans and advances",
                ("0060", "00"):   "050 Other financial corporations",
                ("0060", "0010"): "050 Other financial corporations"}

    REPORTED_COLS = ["00", "0010", "0020"]      # sortiert, wie im Viewer

    def _alt(self, row):
        """Das alte Verhalten: nur ueber cols[0]."""
        return self.CODEBOOK.get((row, self.REPORTED_COLS[0]), "")

    def _neu(self, row):
        """Das neue Verhalten: ueber alle Spalten, bis ein Label steht."""
        for c in self.REPORTED_COLS:
            lab = self.CODEBOOK.get((row, c))
            if lab:
                return lab
        return ""

    def test_the_old_lookup_loses_every_row_but_one(self):
        verloren = [r for r in ("0010", "0020", "0060") if not self._alt(r)]
        self.assertEqual(verloren, ["0010", "0020"],
                         "Ohne den Defekt braucht dieser Test keinen Beleg mehr")
        self.assertEqual(self._alt("0060"), "050 Other financial corporations")

    def test_the_new_lookup_finds_them_all(self):
        for row, want in (("0010", "005 Cash balances at central banks"),
                          ("0020", "010 Loans and advances"),
                          ("0060", "050 Other financial corporations")):
            with self.subTest(row=row):
                self.assertEqual(self._neu(row), want)

    def test_a_row_the_codebook_does_not_know_stays_empty(self):
        """Nicht raten: fehlt die Zeile wirklich, bleibt das Label leer
        (Arbeitsprinzip 3)."""
        self.assertEqual(self._neu("9999"), "")



class MangledLabelTest(unittest.TestCase):
    """≤ und ≥ überlebten die DPM-Dekodierung als 'd"' und 'e"'.

    Dasselbe UTF-16LE-Byte-Paar-Problem, das `_repair_mangled_punct` für den
    Block General Punctuation schon behandelt: U+2264 hat low byte 0x64 ('d'),
    high byte 0x22 ('"'). Bei Adyens 82.00.A las der Spaltenkopf deshalb
    „Past due > 30 days d" 90 days".
    """

    def setUp(self):
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_codebook as bc
        self.repair = bc._repair_mangled_punct

    def test_the_two_measured_pairs_are_repaired(self):
        self.assertEqual(self.repair('Past due > 30 days d" 90 days'),
                         "Past due > 30 days ≤ 90 days")
        self.assertEqual(self.repair('Past due e" 90 days'),
                         "Past due ≥ 90 days")

    def test_the_general_punctuation_repair_still_works(self):
        """Die ältere Reparatur darf nicht verlorengehen. Ihr Muster ist
        ‹Steuerzeichen 0x10–0x1F› + 0x20 — das Leerzeichen gehört dazu, es ist
        das high byte, nicht Beiwerk."""
        self.assertEqual(self.repair("Tier\x13 1 capital"), "Tier–1 capital")

    def test_it_is_a_table_not_a_blanket_rule(self):
        """Eine Regel `(.)" -> chr(0x2200|ord(.))` träfe auch legitime Labels.
        Gemessen kommen genau zwei Paare vor — mehr wird nicht geraten."""
        import build_codebook as bc
        self.assertEqual(set(bc._MATH_MANGLED), {'d"', 'e"'})
        self.assertEqual(self.repair('a size of 5" diameter'), 'a size of 5" diameter')

    def test_an_unmangled_label_is_left_alone(self):
        for s in ("Not past due or past due ≤ 30 days", "Performing exposures", ""):
            with self.subTest(s=s):
                self.assertEqual(self.repair(s), s)

if __name__ == "__main__":
    unittest.main(verbosity=2)
