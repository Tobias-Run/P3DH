"""In welcher Sprache berichten die Institute? (#38)

#38 macht die Sprachverteilung zur Vorbedingung jeder inhaltlichen Aussage:

> ⚠️ Eine Schlagwortsuche auf Deutsch oder Englisch erfasst einen verzerrten
> Ausschnitt und würde systematisch die Institute treffen, die auf Englisch
> berichten.

`probe_disdocs.py` konnte sie nicht beantworten — kein PDF gibt ein `/Lang` an.
Erkannt wird deshalb über Funktionswörter, und diese Tests halten die Stellen
fest, an denen ein Spracherkenner gefährlich wird:

1. **Ein knapper Sieg als Erkenntnis.** Tschechisch gegen Slowakisch und
   Dänisch gegen Norwegisch trennen sich über Funktionswörter nur knapp. Ohne
   Mindestabstand meldet der Erkenner eine Sprache, wo ein Münzwurf steht.
2. **Zu wenig Text.** Aus vierzig Wörtern folgt nichts.
3. **Eine Zufallsziehung als Gegenprobe.** Die Selbstkonsistenz braucht
   Institute mit mehreren Berichten; zufällig gezogen enthielt die Stichprobe
   genau eines, und aus n=1 folgt nichts.
"""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

DE = ("Der Bericht beschreibt die Eigenmittel und das Risikoprofil der Bank. "
      "Die Angaben in diesem Dokument beziehen sich auf den Stichtag und "
      "wurden von dem Vorstand der Gesellschaft freigegeben. Mit dieser "
      "Offenlegung erfüllt das Institut die Anforderungen aus der Verordnung. "
      "Die nachfolgenden Abschnitte enthalten auch eine Beschreibung der "
      "Verfahren, die für das Management von Risiken eingesetzt werden. ") * 4
EN = ("This report describes the own funds and the risk profile of the bank. "
      "The information in this document refers to the reference date and is "
      "approved by the management board of the company. With this disclosure "
      "the institution meets the requirements set out in the regulation. The "
      "following sections also contain a description of the processes that "
      "are used for the management of risks. ") * 4


class ErkennungTest(unittest.TestCase):
    def setUp(self):
        import probe_disdocs_language as p
        self.p = p

    def test_german_is_recognised(self):
        sprache, abstand, n = self.p.erkenne(DE)
        self.assertEqual(sprache, "de")
        self.assertGreater(abstand, 0)
        self.assertGreater(n, 100)

    def test_english_is_recognised(self):
        self.assertEqual(self.p.erkenne(EN)[0], "en")

    def test_too_little_text_yields_no_verdict(self):
        """Aus vierzig Wörtern folgt nichts — und ein Erkenner, der trotzdem
        etwas meldet, ist an genau den kurzen Dokumenten am unzuverlässigsten."""
        sprache, _, n = self.p.erkenne("Der Bericht beschreibt die Eigenmittel.")
        self.assertEqual(sprache, "")
        self.assertLess(n, self.p.MIN_WOERTER)

    def test_a_narrow_win_is_reported_as_unsure(self):
        """Der Fall, für den der Mindestabstand da ist. Zwei künstliche
        Sprachen mit fast identischem Wortschatz: ohne die Schranke gewönne
        eine von beiden, und niemand sähe, wie knapp."""
        saetze = {"xx": {"der", "die", "das", "und"},
                  "yy": {"der", "die", "das", "von"}}
        sprache, abstand, _ = self.p.erkenne(DE, saetze=saetze)
        self.assertEqual(sprache, "", f"knapper Sieg gemeldet, Abstand {abstand}")

    def test_a_clear_win_survives_the_threshold(self):
        """Die Gegenprobe: die Schranke darf nicht ALLES verwerfen, sonst
        meldete der Erkenner nie etwas und wäre trivial „korrekt"."""
        saetze = {"xx": {"der", "die", "das", "und", "von", "mit"},
                  "yy": {"zzz", "qqq"}}
        self.assertEqual(self.p.erkenne(DE, saetze=saetze)[0], "xx")

    def test_empty_text_does_not_raise(self):
        self.assertEqual(self.p.erkenne("")[0], "")


class UrteilTest(unittest.TestCase):
    def setUp(self):
        import probe_disdocs_language as p
        self.p = p

    def test_the_official_language_is_expected(self):
        self.assertEqual(self.p.urteil_von("de", "DE"), "landessprache")

    def test_english_is_its_own_category_not_a_deviation(self):
        """Auf Englisch zu berichten ist üblich und zulässig. Als `abweichend`
        geführt läse sich die Zahl wie ein Befund."""
        self.assertEqual(self.p.urteil_von("en", "DE"), "englisch")

    def test_neither_is_flagged(self):
        self.assertEqual(self.p.urteil_von("fi", "DE"), "abweichend")

    def test_an_unknown_country_is_named_as_such(self):
        """Nicht `abweichend`: ohne Amtssprache im Verzeichnis ist gar nichts
        zu erwarten, und ein Befund wäre eine Aussage über unsere Lücke."""
        self.assertEqual(self.p.urteil_von("de", "XX"), "land unbekannt")

    def test_no_language_is_unsure_not_deviating(self):
        self.assertEqual(self.p.urteil_von("", "DE"), "unsicher")


class PaarstichprobeTest(unittest.TestCase):
    """Die Gegenprobe braucht Institute mit mehreren Berichten. Zufällig
    gezogen enthielt die Stichprobe genau eines — aus n=1 folgt nichts."""

    def setUp(self):
        import probe_disdocs_language as p
        self.p = p
        self.zeilen = (
            [{"lei": "A", "refdate": "2025-06-30"},
             {"lei": "A", "refdate": "2025-12-31"},
             {"lei": "B", "refdate": "2025-12-31"},
             {"lei": "C", "refdate": "2025-06-30"},
             {"lei": "C", "refdate": "2025-12-31"},
             {"lei": "C", "refdate": "2026-03-31"}])

    def test_only_institutions_with_several_reports_are_drawn(self):
        aus = self.p.paarstichprobe(self.zeilen, 10, 1)
        self.assertEqual({z["lei"] for z in aus}, {"A", "C"})

    def test_exactly_two_reports_per_institution(self):
        aus = self.p.paarstichprobe(self.zeilen, 10, 1)
        self.assertEqual(len(aus), 4)

    def test_the_draw_is_reproducible(self):
        a = self.p.paarstichprobe(self.zeilen, 1, 7)
        b = self.p.paarstichprobe(self.zeilen, 1, 7)
        self.assertEqual(a, b)


class KonsistenzTest(unittest.TestCase):
    def setUp(self):
        import probe_disdocs_language as p
        self.p = p

    def _z(self, lei, sprache, status="ok"):
        return {"lei": lei, "sprache": sprache, "status": status}

    def test_a_consistent_institution_counts_as_such(self):
        self.assertEqual(self.p.konsistenz(
            [self._z("A", "de"), self._z("A", "de")]), (1, 1))

    def test_a_language_switch_is_counted_as_inconsistent(self):
        """Entweder ein Erkennungsfehler oder ein echter Sprachwechsel —
        beides gehört in den Bericht, und beides darf nicht als Bestätigung
        durchgehen."""
        self.assertEqual(self.p.konsistenz(
            [self._z("A", "de"), self._z("A", "en")]), (1, 0))

    def test_a_single_report_is_no_evidence_either_way(self):
        self.assertEqual(self.p.konsistenz([self._z("A", "de")]), (0, 0))

    def test_unreadable_reports_do_not_count(self):
        self.assertEqual(self.p.konsistenz(
            [self._z("A", "de"), self._z("A", "", status="Fehler")]), (0, 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
