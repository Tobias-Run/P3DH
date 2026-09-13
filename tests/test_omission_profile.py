"""Ermessensausübung nach Art. 432 (#43) — und die drei Arten, sie zu verfehlen.

Die Auswertung selbst ist einfach: zähle, was ein Institut als „nicht
offengelegt" deklariert. Schwer ist, dass diese Zahl **dreimal etwas anderes
misst als Verhalten**, und jedes Mal überzeugend aussieht:

1. **Den Meldekalender.** Roh gemittelt liegt die Offenlegungsquote bei 45,1 %
   am 2025-12-31 und 11,9 % am 2025-09-30. Das ist die Frequenz nach Art. 433a
   bis c, kein Ermessen.
2. **Die Institutsgrösse.** Ein kleines Haus lässt mehr weg, weil es weniger
   hat — kein Handelsbuch, keine internen Modelle.
3. **Eine gemeinsame Regel.** Sechs Institute in vier Ländern lassen EXAKT
   dieselben elf Templates weg. Unabhängige Einzelentscheidungen sehen anders
   aus.

Dazu kommt ein vierter Fall, der die Rangliste anführen würde: acht Reports
deklarieren jedes Template als „nicht offengelegt" und liefern trotzdem Daten.
Das ist ein Deklarationsfehler, kein Ermessen.

Die Tests unten prüfen für jeden dieser vier Fälle, dass er NICHT als Verhalten
gezählt wird.
"""

from pathlib import Path
import collections
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "omission_profile.csv"
OUT_TPL = ROOT / "processed" / "omission_templates.csv"


def lies(pfad):
    if not pfad.exists():
        return []
    with pfad.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class LogikTest(unittest.TestCase):
    def setUp(self):
        import build_omission_profile as b
        self.b = b

    def test_the_three_bands_are_not_a_single_threshold(self):
        """Ein Template, das 45 % einer Klasse offenlegen, ist weder erwartbar
        noch untypisch. Es an einer 50-%-Grenze in eines von beiden zu zwingen
        hiesse, eine Erwartung zu erfinden, die die Daten nicht hergeben —
        gemessen träfe das 254 der 745 Koordinaten."""
        self.assertEqual(self.b.band_von(0.95), "erwartbar")
        self.assertEqual(self.b.band_von(0.45), "uneinheitlich")
        self.assertEqual(self.b.band_von(0.05), "untypisch")
        self.assertLess(self.b.UNTYPISCH, self.b.ERWARTUNG - 0.3,
                        "die Bänder liegen zu eng — der Mittelbau verschwindet")

    def test_only_the_expected_band_counts_as_a_deviation(self):
        """Gezählt wird nur, wo die klare Mehrheit der direkten Peers am selben
        Stichtag offenlegt. Alles andere trägt keine Erwartung."""
        self.assertGreaterEqual(self.b.ERWARTUNG, 0.75)

    def test_a_declaration_that_contradicts_its_own_delivery_is_unusable(self):
        """Der Fall, der jede Rangliste anführen würde. PPF Financial Holdings
        deklariert am 2025-12-31 JEDES Template als nicht offengelegt und
        liefert Daten für 46. Mit Quote 1,0 stünde es an der Spitze einer Liste,
        die „Ermessensausübung" heisst."""
        self.assertEqual(self.b.deklaration_von(0, 12), "unbrauchbar")
        self.assertEqual(self.b.deklaration_von(40, 2), "widersprüchlich")
        self.assertEqual(self.b.deklaration_von(40, 0), "stimmig")

    def test_an_empty_report_without_contradiction_is_not_called_unusable(self):
        """Wer nichts deklariert offenlegt und auch nichts liefert, ist
        konsistent — möglicherweise ein Institut mit minimaler Pflicht. Es als
        `unbrauchbar` zu führen wäre eine Unterstellung."""
        self.assertEqual(self.b.deklaration_von(0, 0), "stimmig")

    def test_the_base_template_id_bridges_the_two_sources(self):
        """Die Filing-Indicators führen `66.02`, das Parquet `66.02.A` bis
        `66.02.F`. Ohne diese Abbildung liefe die Gegenprobe ins Leere und
        meldete jede Deklaration als stimmig — ein Vergleich, der immer
        zustimmt, ist keiner."""
        self.assertEqual(self.b.basis_id("66.02.A"), "66.02")
        self.assertEqual(self.b.basis_id("61.00"), "61.00")
        self.assertEqual(self.b.basis_id("30.05.B"), "30.05")

    def test_article_432_2_exempts_own_funds_and_remuneration(self):
        """Art. 432(2) nimmt Art. 437 (Eigenmittel) und Art. 450 (Vergütung)
        von der Proprietäts-Ausnahme aus. Eine Auslassung dort kann sich nicht
        auf Vertraulichkeit stützen."""
        self.assertIn("66.01", self.b.ART_432_2)     # CC1
        self.assertIn("66.02", self.b.ART_432_2)     # CC2
        for rem in ("30.01", "30.02", "30.03", "30.04", "30.05"):
            self.assertIn(rem, self.b.ART_432_2)
        self.assertNotIn("61.00", self.b.ART_432_2, "KM1 ist keine Art.-437-Angabe")

    def test_a_peer_group_below_the_minimum_yields_no_expectation(self):
        """Bei zwei Instituten in einer Klasse ist der Anteil kein Massstab.
        Dann steht dort NICHTS — nicht „unauffällig"."""
        zeilen = [{"institution_type": "X", "refPeriod": "2025-06-30",
                   "template_id": "61.00", "reported": True} for _ in range(3)]
        self.assertEqual(self.b.peer_quoten(zeilen), {})
        viele = [{"institution_type": "X", "refPeriod": "2025-06-30",
                  "template_id": "61.00", "reported": True}
                 for _ in range(self.b.MIN_PEER)]
        self.assertIn(("X", "2025-06-30", "61.00"), self.b.peer_quoten(viele))

    def test_reports_without_a_size_class_never_enter_the_expectation(self):
        """Ohne Schichtung wäre der Vergleich eine Grössenmessung mit einem
        Verhaltensetikett."""
        zeilen = [{"institution_type": "", "refPeriod": "2025-06-30",
                   "template_id": "61.00", "reported": True}
                  for _ in range(self.b.MIN_PEER * 2)]
        self.assertEqual(self.b.peer_quoten(zeilen), {})


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        self.rows = lies(OUT)
        self.tpl = lies(OUT_TPL)
        if not self.rows:
            self.skipTest("omission_profile.csv nicht gebaut")
        self.pruefbar = [r for r in self.rows
                         if r["deklaration"] != "unbrauchbar" and int(r["n_erwartbar"])]

    def test_every_report_appears_even_without_a_checkable_coordinate(self):
        """Auch „nicht prüfbar" ist ein Ergebnis. Nur die auffälligen zu
        schreiben machte „nicht geprüft" und „geprüft und in Ordnung"
        ununterscheidbar."""
        self.assertGreater(len(self.rows), 850)
        self.assertTrue(any(not int(r["n_erwartbar"]) for r in self.rows))

    def test_the_unmeasurable_rate_is_empty_not_zero(self):
        """Eine 0 bei fehlender Peer-Gruppe läse sich als „nichts ausgelassen"
        statt als „nicht prüfbar"."""
        for r in self.rows:
            with self.subTest(bank=r["bank_name"], rp=r["refPeriod"]):
                if int(r["n_erwartbar"]) == 0:
                    self.assertEqual(r["quote_gegen_erwartung"], "")
                else:
                    self.assertNotEqual(r["quote_gegen_erwartung"], "")

    def test_the_measure_is_conservative(self):
        """Der Median liegt bei 0: die grosse Mehrheit folgt ihren Peers. Ein
        Mass, das bei der Hälfte der Population anschlägt, misst die Regel und
        nicht die Abweichung."""
        q = sorted(float(r["quote_gegen_erwartung"]) for r in self.pruefbar)
        self.assertEqual(q[len(q) // 2], 0.0)
        ohne = sum(1 for x in q if x == 0)
        self.assertGreater(ohne / len(q), 0.5)

    def test_the_declaration_defect_is_excluded_from_the_ranking(self):
        """PPF Financial Holdings und OTP Luxembourg — Quote 1,0 aus einem
        Deklarationsfehler. Stünden sie in der Auswertung, führten sie sie an."""
        unbrauchbar = [r for r in self.rows if r["deklaration"] == "unbrauchbar"]
        self.assertGreaterEqual(len(unbrauchbar), 5,
                                "die Gegenprobe gegen die Lieferung greift nicht mehr")
        for r in unbrauchbar:
            self.assertEqual(r["n_offengelegt"], "0")
            self.assertGreater(int(r["n_false_mit_daten"]), 0)
            self.assertNotIn(r, self.pruefbar)

    def test_both_directions_of_the_cross_check_are_kept_apart(self):
        """Die beiden Widersprüche sind unterschiedlich belastbar: „False trotz
        Daten" ist zuschreibbar, „True ohne Fakt" kann auch eine Lücke in
        unserer Platzierung sein. In einer Spalte addiert wären 175 belastbare
        Zeilen unter 2.001 unzuschreibbaren verschwunden."""
        self.assertIn("n_false_mit_daten", self.rows[0])
        self.assertIn("n_true_ohne_daten", self.rows[0])
        self.assertGreater(sum(int(r["n_false_mit_daten"]) for r in self.rows), 0)
        self.assertGreater(sum(int(r["n_true_ohne_daten"]) for r in self.rows),
                           sum(int(r["n_false_mit_daten"]) for r in self.rows))

    def test_a_shared_omission_pattern_is_visible_as_such(self):
        """Der wichtigste Vorbehalt, und er steht in einer Spalte statt nur im
        Fliesstext: sechs Institute in vier Ländern lassen exakt dieselben elf
        Templates weg. Wer `n_signatur_geteilt` ignoriert, liest eine gemeinsame
        Regel als individuelle Entscheidung."""
        mit = [r for r in self.pruefbar if r["templates_gegen_erwartung"]]
        self.assertTrue(mit)
        geteilt = [r for r in mit if int(r["n_signatur_geteilt"]) >= 2]
        self.assertGreater(len(geteilt) / len(mit), 0.25,
                           "kein wiederholtes Muster gefunden — unerwartet")
        lang = [r for r in geteilt
                if r["templates_gegen_erwartung"].count("|") + 1 >= 10]
        self.assertTrue(lang, "die lange gemeinsame Auslassungsmenge fehlt")
        self.assertGreater(len({r["country"] for r in lang}), 2,
                           "dasselbe Muster müsste über Ländergrenzen laufen")

    def test_the_shared_count_excludes_the_report_itself(self):
        """`n_signatur_geteilt` zählt die ANDEREN. Eine 1 bei einem einzigartigen
        Muster wäre eine erfundene Gemeinsamkeit."""
        sig = collections.Counter(r["templates_gegen_erwartung"] for r in self.rows
                                  if r["templates_gegen_erwartung"]
                                  and r["deklaration"] != "unbrauchbar")
        einzel = [s for s, c in sig.items() if c == 1]
        self.assertTrue(einzel)
        for r in self.rows:
            if r["templates_gegen_erwartung"] in einzel:
                self.assertEqual(r["n_signatur_geteilt"], "0")

    def test_the_template_file_carries_all_three_bands(self):
        """Die Koordinatendatei ist der Beleg für die Erwartung. Stünde dort nur
        `erwartbar`, liesse sich nicht nachprüfen, wogegen gemessen wurde."""
        self.assertGreater(len(self.tpl), 500)
        self.assertEqual({t["band"] for t in self.tpl},
                         {"erwartbar", "uneinheitlich", "untypisch"})

    def test_the_calendar_is_visible_in_the_coordinates(self):
        """Die Begründung für die Koordinate (Klasse × STICHTAG × Template):
        dasselbe Template liegt an verschiedenen Stichtagen in verschiedenen
        Bändern. Ohne den Stichtag im Schlüssel wäre die Frequenz in die
        Verhaltenszahl eingerechnet."""
        je = collections.defaultdict(set)
        for t in self.tpl:
            je[(t["institution_type"], t["template_id"])].add(t["band"])
        wechselnd = [k for k, v in je.items() if len(v) > 1]
        self.assertGreater(len(wechselnd), 10,
                           "kein Template wechselt das Band über die Stichtage — "
                           "dann wäre der Stichtag im Schlüssel überflüssig")

    def test_the_order_is_stable(self):
        k = [(r["entityID"], r["refPeriod"]) for r in self.rows]
        self.assertEqual(k, sorted(k))
        t = [(r["institution_type"], r["refPeriod"], r["template_id"]) for r in self.tpl]
        self.assertEqual(t, sorted(t))


if __name__ == "__main__":
    unittest.main(verbosity=2)
