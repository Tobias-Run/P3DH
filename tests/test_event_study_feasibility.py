"""Trägt der Bestand eine Ereignisstudie? (#39)

Das Issue setzt die Machbarkeit an den Anfang und nennt den Abbruch
ausdrücklich als legitimen Ausgang. Diese Tests halten die drei Stellen fest,
an denen die Antwort zu gross ausfallen würde:

1. **Einreichungen statt Ereignisse zählen.** Ein Institut reicht mehrere
   Module am selben Tag ein; gemessen verdichten sich 4.278 Einreichungen auf
   1.964 Tage. Wer sie einzeln zählt, hält die Stichprobe für doppelt so gross.
2. **Isolation nicht prüfen.** Eine Einreichung mit der nächsten zwei Tage
   daneben trägt kein sauberes Ereignisfenster.
3. **Unbekannt als „nicht notiert" lesen.** 257 der 489 Institute haben keinen
   Wikidata-Eintrag. Sie als nicht börsennotiert zu führen machte die
   Selektionsverzerrung unsichtbar, statt sie zu beziffern.
"""

from datetime import date
from pathlib import Path
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "event_study_feasibility.csv"


class EreignisTest(unittest.TestCase):
    def setUp(self):
        import check_event_study_feasibility as c
        self.c = c

    def test_several_modules_on_one_day_are_one_event(self):
        """Der Unterschied zwischen 4.278 und 1.964."""
        zeilen = [{"lei": "A", "submission_ts": "20260415103000000"},
                  {"lei": "A", "submission_ts": "20260415170000000"},
                  {"lei": "A", "submission_ts": "20260416090000000"}]
        self.assertEqual(self.c.ereignisse_je_institut(zeilen),
                         {"A": {date(2026, 4, 15), date(2026, 4, 16)}})

    def test_an_unreadable_timestamp_is_dropped_not_guessed(self):
        zeilen = [{"lei": "A", "submission_ts": "kaputt"},
                  {"lei": "A", "submission_ts": "20260415103000000"}]
        self.assertEqual(self.c.ereignisse_je_institut(zeilen),
                         {"A": {date(2026, 4, 15)}})

    def test_a_row_without_a_lei_is_dropped(self):
        self.assertEqual(self.c.ereignisse_je_institut(
            [{"lei": "", "submission_ts": "20260415103000000"}]), {})


class IsolationTest(unittest.TestCase):
    def setUp(self):
        import check_event_study_feasibility as c
        self.c = c

    def test_a_lone_event_is_isolated(self):
        self.assertEqual(self.c.isolierte({date(2026, 4, 15)}, 3),
                         [date(2026, 4, 15)])

    def test_two_events_inside_the_window_are_both_dropped(self):
        """Nicht nur das zweite: bei beiden ist das Fenster verunreinigt, und
        eines davon zu behalten hiesse, sich das bessere auszusuchen."""
        self.assertEqual(self.c.isolierte(
            {date(2026, 4, 15), date(2026, 4, 17)}, 3), [])

    def test_the_window_edge_still_counts_as_near(self):
        self.assertEqual(self.c.isolierte(
            {date(2026, 4, 15), date(2026, 4, 18)}, 3), [])

    def test_just_outside_the_window_is_isolated(self):
        self.assertEqual(len(self.c.isolierte(
            {date(2026, 4, 15), date(2026, 4, 19)}, 3)), 2)

    def test_a_wider_window_never_finds_more(self):
        """Monotonie: ein strengeres Fenster darf die Stichprobe nur
        verkleinern. Bräche das, wäre die Zählung falsch."""
        tage = {date(2026, 4, d) for d in (1, 4, 5, 12, 20, 21, 30)}
        n = [len(self.c.isolierte(tage, f)) for f in (3, 5, 10, 21)]
        self.assertEqual(n, sorted(n, reverse=True), n)


class NotierungTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        import check_event_study_feasibility as c
        self.c = c
        self.d = Path(tempfile.mkdtemp()) / "wd.csv"
        self.d.write_text(
            "lei,wikidata_id,name,mitarbeiter,mitarbeiter_stand,gruendung,"
            "rechtsform,boersennotiert\n"
            "A,Q1,Alpha,100,,,,ja\n"
            "B,Q2,Beta,200,,,,nein\n", encoding="utf-8")

    def test_only_a_positive_entry_counts_as_listed(self):
        notiert, bekannt = self.c.boersennotierte(self.d)
        self.assertEqual(notiert, {"A"})
        self.assertEqual(bekannt, {"A", "B"})

    def test_an_absent_institution_is_unknown_not_unlisted(self):
        """Arbeitsprinzip 3. `bekannt` trennt die beiden — ohne diese Trennung
        verschwände die Selektionsverzerrung, die #39 ausdrücklich nennt."""
        notiert, bekannt = self.c.boersennotierte(self.d)
        self.assertNotIn("C", bekannt)
        self.assertNotIn("C", notiert)

    def test_a_missing_file_yields_nothing_rather_than_everything(self):
        notiert, bekannt = self.c.boersennotierte(Path("/gibt/es/nicht.csv"))
        self.assertEqual((notiert, bekannt), (set(), set()))


class UrteilTest(unittest.TestCase):
    """Die Entscheidung hängt an der Schnittmenge aus isoliert UND notiert —
    nicht an der Zahl der Ereignisse. Vier von fünf Instituten dieses Bestands
    haben keine handelbare Aktie."""

    def setUp(self):
        import check_event_study_feasibility as c
        self.c = c

    def test_a_large_sample_carries(self):
        self.assertEqual(self.c.urteil_von(243), "tragfaehig")

    def test_a_tiny_sample_is_named_as_such(self):
        """Das Issue nennt 20 Ereignisse als Beispiel für zu klein und den
        Abbruch als legitimen Ausgang."""
        self.assertEqual(self.c.urteil_von(20), "zu klein")

    def test_the_middle_is_not_rounded_up(self):
        self.assertEqual(self.c.urteil_von(75), "grenzwertig")

    def test_the_threshold_is_actually_used(self):
        self.assertEqual(self.c.urteil_von(50, schwelle=40), "tragfaehig")
        self.assertEqual(self.c.urteil_von(50, schwelle=1000), "zu klein")


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        if not OUT.exists():
            self.skipTest("event_study_feasibility.csv nicht gebaut")
        with OUT.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))

    def test_the_listed_sample_is_far_smaller_than_the_isolated_one(self):
        """Der Befund, der die Machbarkeit bestimmt. Wäre er verschwunden,
        hiesse das, dass plötzlich fast alle Institute notiert sind — dann
        stimmt die Notierungsquelle nicht mehr."""
        for r in self.rows:
            with self.subTest(fenster=r["fenster_tage"]):
                self.assertLess(int(r["isoliert_boersennotiert"]),
                                int(r["isoliert"]) / 2)

    def test_a_stricter_window_never_yields_more_events(self):
        n = [int(r["isoliert"]) for r in
             sorted(self.rows, key=lambda r: int(r["fenster_tage"]))]
        self.assertEqual(n, sorted(n, reverse=True), n)

    def test_the_treatment_group_is_a_subset_of_the_sample(self):
        """`+Befund` zählt Ereignisse, die BEIDES sind: notiert und mit
        `hoch`-Befund. Grösser als die Stichprobe kann das nicht sein."""
        for r in self.rows:
            with self.subTest(fenster=r["fenster_tage"]):
                self.assertLessEqual(int(r["isoliert_mit_hoch_befund"]),
                                     int(r["isoliert_boersennotiert"]))

    def test_every_window_carries_a_verdict(self):
        for r in self.rows:
            self.assertIn(r["urteil"], {"tragfaehig", "grenzwertig", "zu klein"})

    def test_the_verdict_follows_the_listed_sample_not_the_total(self):
        """Die Kopplung selbst, nicht ihr heutiges Ergebnis. An der Gesamtzahl
        gemessen fiele jedes Fenster „tragfaehig" aus — auch ±21d, wo die
        verwertbare Stichprobe auf 75 Ereignisse schrumpft. Der Unterschied
        ist die ganze Aussage dieses Blattes: vier von fünf Instituten haben
        keine handelbare Aktie."""
        import check_event_study_feasibility as c
        for r in self.rows:
            with self.subTest(fenster=r["fenster_tage"]):
                self.assertEqual(r["urteil"],
                                 c.urteil_von(int(r["isoliert_boersennotiert"])))


if __name__ == "__main__":
    unittest.main(verbosity=2)
