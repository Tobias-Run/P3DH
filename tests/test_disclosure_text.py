"""Berichtsumfang gegen Offenlegungsumfang (#38, zweite Auswertung).

Vier Dinge halten die Tests fest:

1. **Kein Textlayer ist nicht null Zeichen.** Ein gescannter 200-Seiten-Bericht
   mit 0 extrahierten Zeichen wäre sonst der knappste Bericht im Bestand.
2. **Kein PDF ist wieder etwas anderes als ein Scan.** Beide liefern keinen
   Text, aber aus verschiedenen Gründen — und „Fehlt ≠ Null" verlangt, das
   auseinanderzuhalten.
3. **Zeichen sind sprachabhängig.** Ein roher Vergleich über den Korpus misst
   zur Hälfte die Sprachverteilung; die Auswertung ist deshalb geschichtet.
4. **Beides wächst mit der Grösse** — oder eben nicht, und genau das ist zu
   messen statt anzunehmen. Ohne r² gegen die Bilanzsumme wäre „viel Text"
   eine Aussage über grosse Banken.
"""

from pathlib import Path
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "disclosure_text.csv"


class TextebeneTest(unittest.TestCase):
    def setUp(self):
        import build_disclosure_text as b
        self.b = b

    def test_a_dense_report_has_a_text_layer(self):
        self.assertEqual(self.b.textebene_von(123352, 40), "ja")

    def test_a_scan_is_recognised_as_one(self):
        """97 % der PDFs tragen eine Textebene — die übrigen 3 % dürfen nicht
        als besonders knappe Berichte in die Auswertung."""
        self.assertEqual(self.b.textebene_von(120, 200), "nein")

    def test_without_pages_there_is_no_statement(self):
        """Ein Paket ohne PDF ist kein Scan. Ein leeres Urteil ist hier die
        ehrliche Antwort, `nein` wäre eine erfundene."""
        self.assertEqual(self.b.textebene_von(0, 0), "")

    def test_the_threshold_is_actually_used(self):
        self.assertEqual(self.b.textebene_von(5000, 10), "ja")
        self.assertEqual(
            self.b.textebene_von(5000, 10, min_zeichen_je_seite=1000), "nein")


class GroesseTest(unittest.TestCase):
    def setUp(self):
        import build_disclosure_text as b
        self.b = b

    def test_the_bounds_are_the_terciles_of_the_population(self):
        """Eine runde Zahl träfe hier nichts: die Verteilung läuft über fünf
        Grössenordnungen."""
        self.assertEqual(self.b.groessenklassen([1, 2, 3, 4, 5, 6, 7, 8, 9]),
                         (4, 7))

    def test_too_few_values_yield_no_bounds(self):
        self.assertEqual(self.b.groessenklassen([5]), (0.0, 0.0))

    def test_the_classes_split_where_they_claim_to(self):
        g = (1e10, 1e11)
        self.assertEqual(self.b.groessenklasse(5e9, g), "klein")
        self.assertEqual(self.b.groessenklasse(5e10, g), "mittel")
        self.assertEqual(self.b.groessenklasse(5e11, g), "gross")

    def test_a_missing_size_is_not_a_small_bank(self):
        self.assertEqual(self.b.groessenklasse(None, (1e10, 1e11)), "unbekannt")
        self.assertEqual(self.b.groessenklasse(0, (1e10, 1e11)), "unbekannt")


class SteigungTest(unittest.TestCase):
    def setUp(self):
        import build_disclosure_text as b
        self.b = b

    def test_a_perfect_line_is_recognised(self):
        a, b_, r2 = self.b.steigung([(1.0, 2.0), (2.0, 4.0), (3.0, 6.0)])
        self.assertAlmostEqual(a, 2.0)
        self.assertAlmostEqual(r2, 1.0)

    def test_no_relationship_yields_a_vanishing_r2(self):
        _, _, r2 = self.b.steigung([(1.0, 5.0), (2.0, 5.0), (3.0, 5.0)])
        self.assertIsNone(r2, "konstantes y hat keine erklärte Varianz")

    def test_too_few_points_yield_nothing(self):
        self.assertEqual(self.b.steigung([(1.0, 2.0), (2.0, 4.0)]),
                         (None, None, None))

    def test_a_constant_x_yields_nothing(self):
        self.assertEqual(self.b.steigung([(1.0, 2.0), (1.0, 4.0), (1.0, 6.0)]),
                         (None, None, None))


class PaketTest(unittest.TestCase):
    def setUp(self):
        import build_disclosure_text as b
        self.b = b

    def test_a_package_without_a_pdf_is_not_an_error(self):
        import io
        import zipfile
        puffer = io.BytesIO()
        with zipfile.ZipFile(puffer, "w") as z:
            z.writestr("liesmich.txt", "kein PDF")
        n_pdf, seiten, zeichen, anfang = self.b.lies_paket(puffer.getvalue())
        self.assertEqual((n_pdf, seiten, zeichen, anfang), (0, 0, 0, ""))


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        if not OUT.exists():
            self.skipTest("disclosure_text.csv nicht gebaut")
        with OUT.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))

    def test_the_corpus_is_covered(self):
        self.assertGreater(len(self.rows), 500)

    def test_every_row_carries_a_text_layer_verdict(self):
        for r in self.rows:
            if not r["fehler"]:
                with self.subTest(lei=r["lei"]):
                    self.assertIn(r["textebene"], ("ja", "nein", ""))

    def test_most_documents_carry_a_text_layer(self):
        """Der Extraktionstest aus #38 Punkt 2 sagte 97 %. Fiele das deutlich
        ab, wäre entweder der Korpus ein anderer oder die Extraktion kaputt."""
        mit = [r for r in self.rows if not r["fehler"] and r["textebene"]]
        ja = [r for r in mit if r["textebene"] == "ja"]
        self.assertGreater(len(ja) / len(mit), 0.85)

    def test_a_document_without_a_text_layer_has_no_ratio(self):
        """Die Falle: ein Scan mit 0 Zeichen und 30 Templates ergäbe 0 Zeichen
        je Template und wäre der sparsamste Bericht im Bestand."""
        for r in self.rows:
            if r["textebene"] == "nein" and r["zeichen_je_template"]:
                with self.subTest(lei=r["lei"]):
                    self.assertGreater(int(r["zeichen_je_template"]), 0,
                                       "eine Null hier wäre eine Aussage")

    def test_english_is_the_largest_but_not_the_majority_language(self):
        """Die Randbedingung des Issues, am vollen Korpus statt an n=58:
        eine einsprachige Auswertung liesse einen grossen Teil aus."""
        from collections import Counter
        c = Counter(r["sprache"] for r in self.rows
                    if r["sprache"] and not r["fehler"])
        self.assertEqual(c.most_common(1)[0][0], "en")
        gesamt = sum(c.values())
        self.assertLess(c["en"] / gesamt, 0.75)

    def test_the_order_is_stable(self):
        k = [(r["lei"], r["scope"], r["refPeriod"], r["submission_ts"])
             for r in self.rows]
        self.assertEqual(k, sorted(k))

    def test_every_document_is_identified_by_its_submission(self):
        """Ohne den Zeitstempel im Schlüssel bliebe eine korrigierte Fassung
        für immer ungemessen — lautlos, weil nichts fehlschlüge."""
        import build_disclosure_text as b
        k = [b.schluessel_von(r) for r in self.rows]
        self.assertEqual(len(k), len(set(k)))


class BestandTest(unittest.TestCase):
    """Der Zwischenstand (inkrementeller Lauf)."""

    def setUp(self):
        import build_disclosure_text as b
        import tempfile
        self.b = b
        self.d = Path(tempfile.mkdtemp())
        self.p = self.d / "stand.csv"

    def _schreib(self, zeilen):
        with self.p.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=self.b.FELDER)
            w.writeheader()
            for z in zeilen:
                w.writerow({f: z.get(f, "") for f in self.b.FELDER})

    def test_a_measured_document_is_reused(self):
        self._schreib([{"lei": "A", "scope": "CON", "refPeriod": "2025-06-30",
                        "submission_ts": "2026", "n_zeichen": "500",
                        "textebene": "ja"}])
        stand = self.b.lade_bestand(self.p)
        self.assertEqual(stand[("A", "CON", "2025-06-30", "2026")]["n_zeichen"],
                         "500")

    def test_a_failed_row_is_retried_not_cached(self):
        """Ein zwischengespeicherter Netzwerkfehler sähe aus wie ein
        gemessenes Ergebnis — und bliebe es für immer."""
        self._schreib([{"lei": "A", "scope": "CON", "refPeriod": "2025-06-30",
                        "submission_ts": "2026", "fehler": "timeout"}])
        self.assertEqual(self.b.lade_bestand(self.p), {})

    def test_a_new_version_is_a_new_document(self):
        """Dieselbe Meldung, andere Einreichung: muss neu gemessen werden."""
        self._schreib([{"lei": "A", "scope": "CON", "refPeriod": "2025-06-30",
                        "submission_ts": "2026010100", "n_zeichen": "500"}])
        stand = self.b.lade_bestand(self.p)
        self.assertNotIn(("A", "CON", "2025-06-30", "2026060100"), stand)

    def test_only_the_measurement_is_cached_not_the_joins(self):
        """`n_offengelegt` und `trea_eur` haengen am Bestand und wuerden
        eingefroren stillschweigend veralten."""
        for feld in ("n_offengelegt", "trea_eur", "groessenklasse",
                     "quote_gegen_erwartung", "zeichen_je_template"):
            with self.subTest(feld=feld):
                self.assertNotIn(feld, self.b.GEMESSEN)

    def test_a_missing_cache_is_not_an_error(self):
        self.assertEqual(self.b.lade_bestand(self.d / "weg.csv"), {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
