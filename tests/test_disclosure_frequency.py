"""Offenlegungsfrequenz je Template (#34).

Die Frequenz steht in Art. 433a–c CRR. Sie zu kodieren wäre möglich; gemessen
wird stattdessen, was Institute TUN — dann sind Abweichungen selbst ein Befund.

## Die Konstruktion, und warum die naheliegende nicht geht

Der Anteil der Melder je (Template, Stichtag) ist unbrauchbar: **ein Drittel der
Quoten liegt zwischen 20 und 80 %**, und eine Schwelle darauf erfände eine
Trennung, die die Zahlen nicht hergeben — derselbe Fehler, gegen den #43 die
drei Bänder hat.

Gemessen wird deshalb das MUSTER eines einzelnen Instituts über vier Stichtage,
als Vierer-Kette `06-30 · 09-30 · 12-31 · 03-31`. Das ist scharf: 96,5 % der
4.407 vollständigen Paare fallen in genau vier Muster.

## Die Gegenprobe, die den Ausschlag gibt

Drei Templates, deren Frequenz aus #43 unabhängig bekannt ist, müssen
herauskommen — sonst misst das Modell etwas anderes als die Frequenz:

    61.00  KM1     vierteljährlich
    74.00  LIQ2    halbjährlich
    19.03  OR3     jährlich
"""

from pathlib import Path
import collections
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "disclosure_frequency.csv"


def zeilen():
    if not OUT.exists():
        return []
    with OUT.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class MusterTest(unittest.TestCase):
    def setUp(self):
        import build_disclosure_frequency as b
        self.b = b

    def test_the_pattern_follows_the_calendar_order(self):
        """Die Reihenfolge IST das Muster. Vertauscht man zwei Stichtage, wird
        aus `halbjährlich` etwas anderes, ohne dass eine Zahl sich ändert."""
        self.assertEqual(self.b.STICHTAGE,
                         ("2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31"))
        belegung = {"2025-06-30": True, "2025-09-30": False,
                    "2025-12-31": True, "2026-03-31": False}
        self.assertEqual(self.b.muster_von(belegung), "1010")

    def test_an_incomplete_pattern_is_none_not_a_short_one(self):
        """Der Normalfall, nicht der Randfall: nur 4.407 von 38.616 Paaren haben
        alle vier Stichtage. Ein Muster aus zweien zu bilden hiesse, `10` als
        halbjährlich zu lesen — es könnte ein vierteljährliches Template sein,
        dessen andere Stichtage schlicht fehlen."""
        self.assertIsNone(self.b.muster_von({"2025-06-30": True,
                                             "2025-12-31": True}))

    def test_only_four_patterns_carry_a_frequency(self):
        self.assertEqual(self.b.frequenz_von("1111"), "vierteljaehrlich")
        self.assertEqual(self.b.frequenz_von("1010"), "halbjaehrlich")
        self.assertEqual(self.b.frequenz_von("0010"), "jaehrlich")
        self.assertEqual(self.b.frequenz_von("0000"), "nie")

    def test_an_unknown_pattern_is_not_forced_into_one(self):
        """`1110` und `1011` machen zusammen 2 % aus. Sie einer der vier
        Frequenzen zuzuschlagen wäre bequem und falsch — sie sind
        uneinheitlich, und das ist eine Aussage."""
        for m in ("1110", "1011", "0001", "0101"):
            with self.subTest(muster=m):
                self.assertEqual(self.b.frequenz_von(m), "uneinheitlich")

    def test_a_narrow_majority_is_not_a_frequency(self):
        """Eine Koordinate, in der sich die Institute nicht einig sind, trägt
        keine Frequenz. Ein Modalmuster von 40 % als Regel auszugeben wäre
        genau die erfundene Trennung, die dieses Modell vermeiden soll."""
        knapp = ["1010"] * 4 + ["1111"] * 3 + ["0010"] * 3
        freq, modal, anteil, eindeutig = self.b.koordinate(knapp)
        self.assertEqual(modal, "1010")
        self.assertLess(anteil, self.b.MODAL_ANTEIL)
        self.assertFalse(eindeutig)
        self.assertEqual(freq, "uneinheitlich")

    def test_a_clear_majority_carries_the_frequency(self):
        klar = ["1010"] * 9 + ["1111"]
        freq, modal, anteil, eindeutig = self.b.koordinate(klar)
        self.assertTrue(eindeutig)
        self.assertEqual(freq, "halbjaehrlich")
        self.assertAlmostEqual(anteil, 0.9)

    def test_too_few_institutions_carry_nothing(self):
        """Ein einziges Institut, das ein Template jährlich meldet, ist kein
        Frequenzmodell — auch wenn sein Modalanteil 100 % beträgt."""
        freq, modal, anteil, eindeutig = self.b.koordinate(["0010"])
        self.assertEqual(anteil, 1.0)
        self.assertFalse(eindeutig)
        self.assertEqual(freq, "uneinheitlich")

    def test_the_special_reference_date_is_excluded(self):
        """2025-10-31 trägt drei Reports und passt in kein Quartalsraster.
        Mitgenommen zerstörte er jedes Muster, weil ihn fast niemand hat."""
        self.assertNotIn("2025-10-31", self.b.STICHTAGE)


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        self.rows = zeilen()
        if not self.rows:
            self.skipTest("disclosure_frequency.csv nicht gebaut")

    def _finde(self, tid, klasse="Large highest EEA"):
        for r in self.rows:
            if r["template_id"] == tid and r["institution_type"] == klasse:
                return r
        return None

    def test_the_three_known_templates_come_out_right(self):
        """Die Gegenprobe. Diese drei Frequenzen sind bei #43 unabhängig aus
        den Populationsquoten abgelesen worden; kommen sie hier nicht heraus,
        misst das Modell etwas anderes."""
        for tid, erwartet in (("61.00", "vierteljaehrlich"),
                              ("74.00", "halbjaehrlich"),
                              ("19.03", "jaehrlich")):
            with self.subTest(template=tid):
                r = self._finde(tid)
                self.assertIsNotNone(r, f"{tid} fehlt")
                self.assertEqual(r["frequenz"], erwartet)
                self.assertEqual(r["eindeutig"], "ja")
                self.assertGreater(float(r["anteil_modal"]), 0.85)

    def test_the_known_patterns_dominate(self):
        """96,5 % über alle Paare. Bricht das ein, ist entweder der Kalender
        ein anderer geworden oder die Messung kaputt."""
        gesamt = sum(int(r["n_institute"]) for r in self.rows)
        bekannt = sum(int(r[f"n_{k}"]) for r in self.rows
                      for k in ("vierteljaehrlich", "halbjaehrlich",
                                "jaehrlich", "nie"))
        self.assertGreater(bekannt / gesamt, 0.9)

    def test_a_coordinate_without_agreement_says_so(self):
        """Nicht jede Koordinate trägt eine Frequenz — 96 von 184 nicht. Stünde
        überall eine, wäre die Schwelle wirkungslos."""
        u = [r for r in self.rows if r["eindeutig"] == "nein"]
        self.assertGreater(len(u), 20)
        for r in u:
            self.assertEqual(r["frequenz"], "uneinheitlich")

    def test_the_proportionality_effect_is_visible(self):
        """Der inhaltliche Befund: dieselbe Angabe hat je nach Grössenklasse
        eine andere Frequenz. `19.03` (OR3) ist für grosse EEA-Institute
        jährlich und für Tochtergesellschaften `nie` — Art. 433a gegen 433b/c,
        gemessen statt abgeschrieben."""
        gross = self._finde("19.03", "Large highest EEA")
        tochter = self._finde("19.03", "Large subsidiaries")
        self.assertIsNotNone(gross)
        self.assertIsNotNone(tochter)
        self.assertNotEqual(gross["frequenz"], tochter["frequenz"])

    def test_the_counts_add_up_to_the_institutions(self):
        for r in self.rows:
            with self.subTest(t=r["template_id"], k=r["institution_type"]):
                summe = sum(int(r[f"n_{k}"]) for k in
                            ("vierteljaehrlich", "halbjaehrlich", "jaehrlich",
                             "nie", "uneinheitlich"))
                self.assertEqual(summe, int(r["n_institute"]))

    def test_the_order_is_stable(self):
        k = [(r["institution_type"], r["template_id"]) for r in self.rows]
        self.assertEqual(k, sorted(k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
