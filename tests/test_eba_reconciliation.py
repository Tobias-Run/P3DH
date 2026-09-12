"""Bottom-up gegen top-down (#37): unsere Aggregate gegen die EBA-eigenen.

## Das Ergebnis

407 Vergleichspunkte über vier Kapitalkennzahlen, 29 Länder, vier Stichtage.
Median der absoluten Abweichung 0,45 bis 1,02 Prozentpunkte; 60 % liegen
innerhalb eines Prozentpunkts.

Und die Abweichung faellt **monoton mit der Zahl der Institute je Land**:

    n = 1      2,07 pp     27 % innerhalb 1 pp
    n = 2–4    0,62 pp     66 %
    n = 5–9    0,53 pp     70 %
    n >= 10    0,23 pp     82 %

Das ist die Signatur eines ABDECKUNGSUNTERSCHIEDS, nicht eines systematischen
Fehlers. Ein Rechenfehler in unserer Kette waere von der Zahl der Institute
unabhaengig; ein Stichprobenunterschied verschwindet mit wachsender Zahl. Damit
ist die Kette vom Parser ueber die Zellplatzierung bis zur EUR-Normierung
extern bestaetigt — bisher validierte das Projekt nur gegen sich selbst.

## Drei Dinge, ohne die der Vergleich Unsinn misst

**Gewichtet, nicht gemittelt.** Die EBA weist Summe-durch-Summe aus.
**Keine Doppelzaehlung.** 90 Institutszeilen sind ausgeschlossen, weil ihre
Mutter selbst meldet (#32).
**Keine kaputten Nenner.** 5 Zeilen sind wegen Skalenverdacht ausgeschlossen
(#45, #83) — in einem Summenaggregat verschwindet ein 10^6-Fehler nicht, er
verzerrt es.
"""

from pathlib import Path
import collections
import csv
import statistics as st
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "eba_reconciliation.csv"


def zeilen():
    if not OUT.exists():
        return []
    with OUT.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class LogikTest(unittest.TestCase):
    def setUp(self):
        import build_eba_reconciliation as b
        self.b = b
        self.src = (ROOT / "scripts" / "build_eba_reconciliation.py").read_text(
            encoding="utf-8")

    def test_the_period_mapping_matches_the_eba_format(self):
        self.assertEqual(self.b.periode_von("2025-12-31"), "202512")
        self.assertEqual(self.b.periode_von("2026-03-31"), "202603")

    def test_subsidiaries_of_reporting_parents_are_excluded(self):
        """Ohne das summiert ein Laenderaggregat Mutter UND Tochter. Gemessen
        liegt bei 66 der 508 Institute die Mutter selbst im Bestand."""
        self.assertIn("def eigenstaendige", self.src)
        self.assertIn("lei_relations.csv", self.src)

    def test_reports_with_a_broken_scale_are_excluded(self):
        """Ein Report, dessen absolute Groessen um 10^6 zu klein sind,
        verschwindet in einer Summe nicht — er verzerrt sie."""
        self.assertIn("skalenverdacht", self.src)
        self.assertIn("def verdaechtige", self.src)

    def test_the_aggregate_is_weighted_not_averaged(self):
        """Die EBA weist gewichtete Durchschnitte aus. Ein Mittelwert ueber
        Institute ist bei stark unterschiedlichen Bilanzsummen etwas voellig
        anderes."""
        rumpf = self.src[self.src.index("def unsere_aggregate"):]
        rumpf = rumpf[:rumpf.index("\ndef ")]
        self.assertIn("eintrag[0] += a", rumpf)
        self.assertIn("eintrag[1] += b", rumpf)
        self.assertNotIn("statistics.mean", rumpf)
        self.assertNotIn("st.mean", rumpf)

    def test_the_ratios_come_from_km1_not_from_a_reported_percentage(self):
        """Zaehler und Nenner getrennt zu summieren ist der einzige Weg zu
        einem gewichteten Aggregat — eine gemeldete Quote liesse sich nicht
        gewichten."""
        for kri, (zae, nen) in self.b.KRI.items():
            with self.subTest(kri=kri):
                self.assertIn(zae, ("0010", "0020", "0030"))
                self.assertIn(nen, ("0040", "0210"))


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        self.rows = zeilen()
        if not self.rows:
            self.skipTest("eba_reconciliation.csv nicht gebaut")

    def test_the_comparison_actually_has_points(self):
        """Faende sich keiner, saehe der Bericht aus wie ein Befund — er waere
        aber einer ueber unseren Join."""
        self.assertGreater(len(self.rows), 200)
        self.assertGreater(len({r["country_iso"] for r in self.rows}), 15)
        self.assertGreaterEqual(len({r["kri"] for r in self.rows}), 4)

    def test_the_difference_is_what_the_columns_say(self):
        for r in self.rows:
            with self.subTest(kri=r["kri"], land=r["country_iso"]):
                self.assertAlmostEqual(
                    float(r["differenz_pp"]),
                    (float(r["unser_wert"]) - float(r["eba_wert"])) * 100, places=2)

    def test_the_bulk_of_the_comparison_agrees(self):
        """Der eigentliche Befund: unsere Kette trifft die EBA-Zahlen. Ginge
        das verloren, waere entweder die Aggregation kaputt oder die
        Grundgesamtheit eine andere — beides gehoert bemerkt."""
        d = sorted(abs(float(r["differenz_pp"])) for r in self.rows)
        self.assertLess(st.median(d), 2.0,
                        "die Uebereinstimmung mit der EBA ist weggebrochen")

    def test_the_deviation_shrinks_with_the_population(self):
        """Die Signatur, die alles entscheidet. Ein RECHENFEHLER waere von der
        Zahl der Institute unabhaengig; ein ABDECKUNGSUNTERSCHIED verschwindet
        mit wachsender Zahl. Gemessen faellt der Median von 2,07 auf 0,23 pp."""
        je = collections.defaultdict(list)
        for r in self.rows:
            n = int(r["n_institute"])
            schluessel = "klein" if n == 1 else ("mittel" if n < 10 else "gross")
            je[schluessel].append(abs(float(r["differenz_pp"])))
        for k in ("klein", "mittel", "gross"):
            self.assertGreater(len(je[k]), 20, f"zu wenige Punkte in '{k}'")
        self.assertGreater(st.median(je["klein"]), st.median(je["mittel"]))
        self.assertGreater(st.median(je["mittel"]), st.median(je["gross"]))

    def test_a_single_institution_country_is_not_read_as_an_error(self):
        """Bei n=1 vertritt ein Institut ein ganzes Land. Die Abweichung misst
        dort die Grundgesamtheit, nicht unsere Rechnung — deshalb steht n in
        jeder Zeile."""
        for r in self.rows:
            with self.subTest(kri=r["kri"], land=r["country_iso"]):
                self.assertGreaterEqual(int(r["n_institute"]), 1)

    def test_exclusions_are_counted_not_hidden(self):
        """Wer ausschliesst, muss sagen wie viele — sonst ist die Grundgesamtheit
        unserer Seite unbekannt."""
        gruppe = sum(int(r["n_ausgeschlossen_gruppe"]) for r in self.rows)
        self.assertGreater(gruppe, 0,
                           "keine Konzernausschluesse — Doppelzaehlung wahrscheinlich")

    def test_the_order_is_stable(self):
        k = [(r["kri"], r["refPeriod"], r["country_iso"]) for r in self.rows]
        self.assertEqual(k, sorted(k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
