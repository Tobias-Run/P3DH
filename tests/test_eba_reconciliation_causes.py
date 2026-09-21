"""Bottom-up gegen top-down: die Ursachentrennung (#37 Punkt 3).

Vier Dinge halten die Tests fest:

1. **Entdopplung braucht BEIDE Wege.** Die direkte Mutter allein lässt
   Enkelinnen durch; der Konzernkopf allein macht den umgekehrten Fehler —
   Bank Handlowy hat als GLEIF-Kopf die Citigroup (meldet nicht), ihre direkte
   Mutter Citibank Europe aber sehr wohl.
2. **„Abgedeckt" heisst nicht „zählt hier mit".** In Luxemburg melden 7 von 30
   signifikanten Instituten selbst; die übrigen 21 sind Töchter ausländischer
   Gruppen, deren Kapital im Land der Mutter steht. Wer sie mitzählt, gibt
   Luxemburg eine Abdeckung von 1,0 bei 10 Prozentpunkten Abweichung.
3. **Eine Ursache, die man nicht misst, gehört nicht in die Spalte.** Der
   Stichtagsversatz ist geprüft und widerlegt und steht deshalb nicht drin.
4. **Die Abweichung ist kein Gütemass.** Die korrekte Entdopplung vergrössert
   sie — wer darauf hin optimiert, passt die eigene Methode an eine fremde
   Grundgesamtheit an.
"""

from pathlib import Path
import csv
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "eba_reconciliation.csv"


class EigenstaendigTest(unittest.TestCase):
    def setUp(self):
        import build_eba_reconciliation as b
        self.b = b
        self.d = Path(tempfile.mkdtemp())
        self.rel = self.d / "rel.csv"

    def _rel(self, zeilen):
        self.rel.write_text("lei,direct_parent_lei\n" + "".join(zeilen),
                            encoding="utf-8")
        self.b.RELATIONS = self.rel

    def test_a_reporting_direct_parent_excludes_the_daughter(self):
        self._rel(["T,M\n", "M,\n"])
        aus = self.b.eigenstaendige({"T", "M"}, {"T": "", "M": ""})
        self.assertNotIn("T", aus)
        self.assertIn("M", aus)

    def test_a_reporting_group_head_excludes_the_granddaughter(self):
        """Der Fall, den die alte Regel durchliess: die direkte Mutter meldet
        nicht, der Konzernkopf aber schon."""
        self._rel(["E,M\n"])
        aus = self.b.eigenstaendige({"E", "K"}, {"E": "K", "K": "K"})
        self.assertNotIn("E", aus)

    def test_the_head_alone_would_let_bank_handlowy_through(self):
        """Bank Handlowy: GLEIF-Kopf ist die Citigroup und meldet nicht, die
        direkte Mutter Citibank Europe meldet. Auf dem Kopf allein geprüft
        stünde ihr Kapital zweimal im polnischen Aggregat."""
        self._rel(["BH,CITIEU\n"])
        koepfe = {"BH": "CITIGROUP", "CITIEU": "CITIGROUP"}
        aus = self.b.eigenstaendige({"BH", "CITIEU"}, koepfe)
        self.assertNotIn("BH", aus, "über die direkte Mutter auszuschliessen")
        self.assertIn("CITIEU", aus)

    def test_an_institution_being_its_own_head_is_not_excluded(self):
        self._rel(["A,\n"])
        self.assertIn("A", self.b.eigenstaendige({"A"}, {"A": "A"}))

    def test_a_parent_outside_the_population_does_not_exclude(self):
        """Meldet die Mutter nicht, ist das Kapital der Tochter nirgends
        sonst erfasst — sie wegzulassen verlöre es ganz."""
        self._rel(["T,AUSSEN\n"])
        self.assertIn("T", self.b.eigenstaendige({"T"}, {"T": ""}))


class SiJeLandTest(unittest.TestCase):
    def setUp(self):
        import build_eba_reconciliation as b
        self.b = b
        self.p = Path(tempfile.mkdtemp()) / "cov.csv"

    def _schreib(self, zeilen):
        self.p.write_text("lei,land,signifikanz,einordnung\n" + "".join(zeilen),
                          encoding="utf-8")

    def test_only_self_filers_count(self):
        """Der Fehler, den Luxemburg aufgedeckt hat. `ueber_gruppe` heisst:
        das Kapital steht im Aggregat der MUTTER, nicht hier."""
        self._schreib(["A,Luxembourg,SI,meldet_selbst\n",
                       "B,Luxembourg,SI,ueber_gruppe\n",
                       "C,Luxembourg,SI,ueber_gruppe\n"])
        self.assertEqual(self.b.si_je_land(self.p)["Luxembourg"], (3, 1))

    def test_non_significant_entities_are_ignored(self):
        self._schreib(["A,Malta,SI,meldet_selbst\n",
                       "B,Malta,LSI,meldet_selbst\n"])
        self.assertEqual(self.b.si_je_land(self.p)["Malta"], (1, 1))

    def test_a_missing_file_is_not_an_error(self):
        self.assertEqual(self.b.si_je_land(self.p.parent / "weg.csv"), {})


class UrsacheTest(unittest.TestCase):
    def setUp(self):
        import build_eba_reconciliation as b
        self.b = b

    def test_a_small_deviation_needs_no_explanation(self):
        self.assertEqual(self.b.ursache_von(0.4, 20, 1.0), "stimmig")

    def test_a_single_institution_is_a_thin_basis(self):
        """Zypern mit einem Institut weicht um 13 pp ab. Das als Fehler zu
        führen wäre falsch — ein gewichtetes Landesaggregat aus einem Haus
        ist mit dem der EBA nicht vergleichbar."""
        self.assertEqual(self.b.ursache_von(-12.97, 1, 1.0), "duenne_basis")

    def test_foreign_parents_explain_the_luxembourg_gap(self):
        self.assertEqual(self.b.ursache_von(-10.17, 4, 0.233),
                         "konsolidierung")

    def test_a_broad_well_covered_country_stays_unexplained(self):
        """Die Teilmenge, die eine Erklärung verdient — und sie als
        `konsolidierung` zu etikettieren wäre eine Erklärung, die nicht
        gemessen ist."""
        self.assertEqual(self.b.ursache_von(-3.21, 10, 0.95), "unerklaert")

    def test_the_thin_basis_wins_over_the_coverage(self):
        """Bei einem Institut ist die Selbstmelderquote gleichgültig — die
        Basis trägt ohnehin nicht."""
        self.assertEqual(self.b.ursache_von(-10.0, 1, 0.1), "duenne_basis")

    def test_an_unknown_coverage_does_not_become_an_explanation(self):
        """„Fehlt ≠ Null": ohne Quote ist die Konsolidierung nicht belegt."""
        self.assertEqual(self.b.ursache_von(-5.0, 10, None), "unerklaert")

    def test_the_thresholds_are_actually_used(self):
        self.assertEqual(self.b.ursache_von(-5.0, 20, 1.0, schwelle=10.0),
                         "stimmig")
        self.assertEqual(self.b.ursache_von(-5.0, 5, 1.0, duenn=10),
                         "duenne_basis")


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        if not OUT.exists():
            self.skipTest("eba_reconciliation.csv nicht gebaut")
        with OUT.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))

    def test_the_comparison_has_content(self):
        self.assertGreater(len(self.rows), 200)

    def test_every_row_carries_a_cause(self):
        for r in self.rows:
            with self.subTest(kri=r["kri"], land=r["country_iso"]):
                self.assertIn(r["ursache"], ("stimmig", "duenne_basis",
                                             "konsolidierung", "unerklaert"))

    def test_a_small_deviation_is_always_stimmig(self):
        import build_eba_reconciliation as b
        for r in self.rows:
            if abs(float(r["differenz_pp"])) <= b.NAH_PP:
                with self.subTest(land=r["country_iso"]):
                    self.assertEqual(r["ursache"], "stimmig")

    def test_the_largest_deviations_are_all_explained(self):
        """Die Gegenprobe: bliebe der grösste Ausreisser `unerklaert`, hätte
        die Ursachentrennung ihren Zweck verfehlt."""
        weit = sorted(self.rows,
                      key=lambda r: -abs(float(r["differenz_pp"])))[:5]
        for r in weit:
            with self.subTest(land=r["country_iso"]):
                self.assertNotEqual(r["ursache"], "unerklaert")

    def test_the_self_filer_quota_is_a_quota(self):
        for r in self.rows:
            if r["quote_selbstmelder"]:
                with self.subTest(land=r["country_iso"]):
                    q = float(r["quote_selbstmelder"])
                    self.assertGreaterEqual(q, 0.0)
                    self.assertLessEqual(q, 1.0)
                    self.assertLessEqual(int(r["n_si_selbstmelder"]),
                                         int(r["n_si_land"]))

    def test_the_deviation_matches_its_own_inputs(self):
        for r in self.rows:
            with self.subTest(land=r["country_iso"]):
                self.assertAlmostEqual(
                    float(r["differenz_pp"]),
                    (float(r["unser_wert"]) - float(r["eba_wert"])) * 100,
                    places=2)

    def test_the_order_is_stable(self):
        k = [(r["kri"], r["refPeriod"], r["country_iso"]) for r in self.rows]
        self.assertEqual(k, sorted(k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
