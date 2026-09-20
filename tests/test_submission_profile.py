"""Korrekturverhalten als Qualitätssignal (#31).

Drei Dinge halten die Tests fest:

1. **Die Definition entscheidet über die Kernzahl.** Drei plausible Schlüssel
   geben 472, 2.539 und 3.353 Korrekturen — Faktor sieben. Deshalb rechnet
   dieses Skript nicht selbst, sondern benutzt `submissions.identitaet` (#88).
2. **Die Schichtung ist nicht optional.** Ohne sie steht in der Kreuztabelle
   Meldeumfang statt Verhalten — der wiederkehrende Fehler aus #43, #45, #11
   und #44.
3. **„Nie korrigiert" ist nicht „keine Befunde".** Die persistente Liste ist
   die Schnittmenge aus `hoch`-Befund UND null Korrekturen; wer eine der
   beiden Seiten verliert, bekommt eine ganz andere Liste.
"""

from pathlib import Path
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PROFIL = ROOT / "processed" / "submission_profile.csv"
PERSISTENT = ROOT / "processed" / "persistent_findings.csv"


class UmfangsklasseTest(unittest.TestCase):
    def setUp(self):
        import build_submission_profile as b
        self.b = b

    def test_the_boundaries_are_inclusive(self):
        self.assertEqual(self.b.umfangsklasse(3), "1-3")
        self.assertEqual(self.b.umfangsklasse(4), "4-8")
        self.assertEqual(self.b.umfangsklasse(8), "4-8")
        self.assertEqual(self.b.umfangsklasse(9), "9+")

    def test_a_filer_without_submissions_has_no_class(self):
        """Null Einreichungen sind keine Klasse. `1-3` zu liefern stellte ein
        Institut neben Melder, die tatsächlich gemeldet haben."""
        self.assertEqual(self.b.umfangsklasse(0), "")

    def test_a_very_large_filer_still_lands_somewhere(self):
        self.assertEqual(self.b.umfangsklasse(500), "9+")


class ZaehlTest(unittest.TestCase):
    def setUp(self):
        import build_submission_profile as b
        self.b = b

    def _z(self, lei, refdate, url, cons="CON", modul="020000"):
        return {"lei": lei, "consolidation": cons, "module": modul,
                "refdate": refdate, "url": url, "country": "DE",
                "submission_ts": "2026-01-01"}

    def test_one_submission_is_no_correction(self):
        e, m, k, mx = self.b.zaehle(
            [self._z("A", "2025-12-31", "x/CON_DE_PILLAR3020000_CODIS_1.zip")])["A"]
        self.assertEqual((e, m, k, mx), (1, 1, 0, 1))

    def test_a_resubmission_is_a_correction(self):
        e, m, k, mx = self.b.zaehle([
            self._z("A", "2025-12-31", "x/CON_DE_PILLAR3020000_CODIS_1.zip"),
            self._z("A", "2025-12-31", "x/CON_DE_PILLAR3020000_CODIS_2.zip"),
        ])["A"]
        self.assertEqual((e, m, k, mx), (2, 1, 1, 2))

    def test_two_modules_are_not_corrections_of_each_other(self):
        """Der Fehler, der die Kernzahl um Faktor sieben verschiebt. Die Spalte
        `module` trägt nur den PILLAR3-Code; CODIS und ESGDIS liegen darunter
        als eigenständige Meldungen."""
        e, m, k, mx = self.b.zaehle([
            self._z("A", "2025-12-31", "x/CON_DE_PILLAR3020000_CODIS_1.zip"),
            self._z("A", "2025-12-31", "x/CON_DE_PILLAR3020000_ESGDIS_1.zip"),
        ])["A"]
        self.assertEqual(k, 0)
        self.assertEqual(m, 2)

    def test_two_reference_dates_are_not_corrections_either(self):
        k = self.b.zaehle([
            self._z("A", "2025-06-30", "x/CON_DE_PILLAR3020000_CODIS_1.zip"),
            self._z("A", "2025-12-31", "x/CON_DE_PILLAR3020000_CODIS_1.zip"),
        ])["A"][2]
        self.assertEqual(k, 0)

    def test_filers_are_counted_separately(self):
        aus = self.b.zaehle([
            self._z("A", "2025-12-31", "x/CON_DE_PILLAR3020000_CODIS_1.zip"),
            self._z("B", "2025-12-31", "x/CON_DE_PILLAR3020000_CODIS_1.zip"),
        ])
        self.assertEqual(set(aus), {"A", "B"})
        self.assertEqual(aus["A"][2], 0)


class KreuztabelleTest(unittest.TestCase):
    def setUp(self):
        import build_submission_profile as b
        self.b = b

    def _p(self, klasse, befund, rate):
        return {"umfangsklasse": klasse, "hat_befund": befund,
                "korrekturen_je_einreichung": str(rate)}

    def test_the_two_sides_are_kept_apart(self):
        kt = self.b.kreuztabelle([self._p("4-8", "ja", 0.2),
                                  self._p("4-8", "nein", 0.1)])
        self.assertAlmostEqual(kt["4-8"]["mit"][1], 0.2)
        self.assertAlmostEqual(kt["4-8"]["ohne"][1], 0.1)

    def test_the_classes_are_kept_apart(self):
        """Ohne Schichtung stünde in der Tabelle Meldeumfang statt Verhalten —
        genau der Fehler, vor dem das Issue warnt."""
        kt = self.b.kreuztabelle([self._p("1-3", "ja", 0.9),
                                  self._p("9+", "ja", 0.1)])
        self.assertAlmostEqual(kt["1-3"]["mit"][1], 0.9)
        self.assertAlmostEqual(kt["9+"]["mit"][1], 0.1)

    def test_a_filer_without_a_class_is_left_out(self):
        self.assertEqual(self.b.kreuztabelle([self._p("", "ja", 0.5)]), {})


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        if not PROFIL.exists():
            self.skipTest("submission_profile.csv nicht gebaut")
        with PROFIL.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))

    def test_the_artefact_covers_the_population(self):
        self.assertGreater(len(self.rows), 400)

    def test_corrections_never_exceed_submissions(self):
        for r in self.rows:
            with self.subTest(lei=r["lei"]):
                self.assertLessEqual(int(r["n_korrekturen"]),
                                     int(r["n_einreichungen"]))
                self.assertEqual(int(r["n_einreichungen"]),
                                 int(r["n_meldungen"]) + int(r["n_korrekturen"]))

    def test_the_total_matches_the_known_count(self):
        """472 ist die Zahl aus `submissions.py` (#88) und deckt sich mit
        `docs/analysen_nach_vollload.md`. Weicht sie ab, ist der Schlüssel
        gewechselt — und die Kernzahl dieses Issues mit ihr."""
        self.assertEqual(sum(int(r["n_korrekturen"]) for r in self.rows), 472)

    def test_the_flags_agree_with_the_counts(self):
        for r in self.rows:
            with self.subTest(lei=r["lei"]):
                self.assertEqual(r["hat_korrigiert"] == "ja",
                                 int(r["n_korrekturen"]) > 0)
                self.assertEqual(r["hat_befund"] == "ja",
                                 int(r["n_findings"]) > 0)

    def test_the_order_is_stable(self):
        k = [r["lei"] for r in self.rows]
        self.assertEqual(k, sorted(k))


class PersistentTest(unittest.TestCase):
    def setUp(self):
        if not PERSISTENT.exists() or not PROFIL.exists():
            self.skipTest("Artefakte nicht gebaut")
        with PERSISTENT.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))
        with PROFIL.open(encoding="utf-8") as fh:
            self.profil = {r["lei"]: r for r in csv.DictReader(fh)}

    def test_the_list_is_not_empty(self):
        """Eine leere Liste wäre kein Erfolg, sondern ein Hinweis, dass eine
        der beiden Seiten nicht mehr gelesen wird."""
        self.assertTrue(self.rows)

    def test_every_entry_really_never_corrected(self):
        for r in self.rows:
            with self.subTest(bank=r["bank_name"]):
                self.assertEqual(
                    int(self.profil[r["lei"]]["n_korrekturen"]), 0)

    def test_every_entry_really_has_a_high_finding(self):
        for r in self.rows:
            with self.subTest(bank=r["bank_name"]):
                self.assertGreater(int(r["n_hoch"]), 0)

    def test_it_is_a_strict_subset_of_the_profile(self):
        for r in self.rows:
            self.assertIn(r["lei"], self.profil)

    def test_the_worst_case_comes_first(self):
        n = [int(r["n_hoch"]) for r in self.rows]
        self.assertEqual(n, sorted(n, reverse=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
