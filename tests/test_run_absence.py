"""Der Wächter gegen den Zeitplan, der still stirbt (#8, blinder Fleck).

Vier Dinge halten die Tests fest:

1. **Kein Lauf ist der Alarm, nicht die Ruhe.** Der Streckenwächter zählt rote
   Läufe und hängt damit daran, dass einer stattgefunden hat. Feuert der Cron
   nie, ist er für ihn unsichtbar — dieser hier meldet genau das.
2. **Ein roter Lauf ist hier ein Lebenszeichen.** Er beweist, dass der
   Zeitplan feuert. Ob er gelingt, ist die andere Frage.
3. **Unbekannt ist nicht leer.** Ist die Historie nicht abrufbar, wird
   gemeldet — eine stumme Überwachung ist schlimmer als ein überflüssiger
   Alarm.
4. **Titel und Wiedererkennungsmarke kommen aus einer Quelle.** Liefen sie
   auseinander, entstünde kein Fehler, sondern täglich ein neues Issue.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

JETZT = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


def _lauf(vor_tagen, event="schedule", conclusion="success"):
    return {"event": event, "conclusion": conclusion,
            "created_at": (JETZT - timedelta(days=vor_tagen)).isoformat()}


class ZeitTest(unittest.TestCase):
    def setUp(self):
        import check_run_absence as a
        self.a = a

    def test_the_github_format_is_understood(self):
        self.assertEqual(self.a.zeit("2026-09-21T04:00:00Z").hour, 4)

    def test_an_unreadable_stamp_is_not_a_date(self):
        """Ein geratener Zeitpunkt wäre schlimmer als keiner: er erzeugte ein
        Alter und damit eine Aussage."""
        self.assertIsNone(self.a.zeit("neulich"))
        self.assertIsNone(self.a.zeit(""))
        self.assertIsNone(self.a.zeit(None))


class JuengsterTest(unittest.TestCase):
    def setUp(self):
        import check_run_absence as a
        self.a = a

    def test_the_most_recent_scheduled_run_wins(self):
        j = self.a.juengster_geplanter([_lauf(30), _lauf(2), _lauf(9)])
        self.assertEqual(self.a.alter_tage(j, JETZT), 2)

    def test_a_manual_run_is_no_sign_of_life(self):
        """Der Kern: ein Lauf, den jemand von Hand gestartet hat, beweist
        nichts über den Zeitplan. Zählte er mit, hielte ein einziger
        Handstart den Wächter monatelang ruhig."""
        self.assertIsNone(self.a.juengster_geplanter(
            [_lauf(1, event="workflow_dispatch"),
             _lauf(2, event="push")]))

    def test_a_failed_scheduled_run_is_a_sign_of_life(self):
        """Rot heisst: der Zeitplan feuert. Ob er gelingt, beantwortet
        check_run_streak.py."""
        j = self.a.juengster_geplanter([_lauf(1, conclusion="failure")])
        self.assertIsNotNone(j)

    def test_no_runs_at_all_yield_nothing(self):
        self.assertIsNone(self.a.juengster_geplanter([]))


class EntscheidungTest(unittest.TestCase):
    def setUp(self):
        import check_run_absence as a
        self.a = a

    def test_a_recent_run_is_no_alarm(self):
        melden, _ = self.a.soll_melden([_lauf(2)], None, JETZT)
        self.assertFalse(melden)

    def test_a_missed_week_is_an_alarm(self):
        """Wöchentlicher Cron: ein ausgefallener Montag plus zwei Tage
        Nachsicht. Am Mittwoch darauf wird gemeldet."""
        melden, grund = self.a.soll_melden([_lauf(9.5)], None, JETZT)
        self.assertTrue(melden)
        self.assertIn("9.5", grund)

    def test_the_grace_period_really_grants_grace(self):
        """Am 2026-09-21 kam der Lauf 5 h 21 zu spät. Eine Schwelle von
        genau 7 Tagen hätte deshalb Fehlalarme erzeugt."""
        melden, _ = self.a.soll_melden([_lauf(7.3)], None, JETZT)
        self.assertFalse(melden)

    def test_no_scheduled_run_at_all_is_the_whole_point(self):
        """Der Fall, den der Streckenwächter konstruktiv nicht sehen kann."""
        melden, grund = self.a.soll_melden(
            [_lauf(1, event="workflow_dispatch")], None, JETZT)
        self.assertTrue(melden)
        self.assertIn("keinen einzigen", grund)

    def test_an_unknown_history_reports(self):
        """Unbekannt ist nicht leer. Ein `except: return False` hiesse: die
        Überwachung fällt aus und meldet „alles in Ordnung"."""
        melden, grund = self.a.soll_melden([], None, JETZT,
                                           historie_bekannt=False)
        self.assertTrue(melden)
        self.assertIn("nicht abrufbar", grund)

    def test_an_open_report_prevents_a_second(self):
        """Sonst stünde nach einer Woche siebenmal dasselbe im Tracker — der
        Wächter läuft täglich."""
        melden, grund = self.a.soll_melden([_lauf(30)], 42, JETZT)
        self.assertFalse(melden)
        self.assertIn("#42", grund)

    def test_an_open_report_wins_over_an_unknown_history(self):
        melden, _ = self.a.soll_melden([], 42, JETZT, historie_bekannt=False)
        self.assertFalse(melden)

    def test_the_threshold_is_actually_used(self):
        melden, _ = self.a.soll_melden([_lauf(9.5)], None, JETZT, schwelle=30)
        self.assertFalse(melden)


class MeldungTest(unittest.TestCase):
    def setUp(self):
        import check_run_absence as a
        self.a = a

    def test_the_title_is_the_marker(self):
        """Liefen Titel und Marke auseinander, entstünde kein Fehler, sondern
        täglich ein neues Issue."""
        titel, _ = self.a.meldung("Befund")
        self.assertEqual(titel, self.a.MARKE)

    def test_an_unconfirmed_report_does_not_claim_the_finding(self):
        """Eine Meldung, die mehr weiss als ihre Grundlage hergibt, schickt
        jemanden auf Basis einer Behauptung los."""
        _, text = self.a.meldung("Befund", bestaetigt=False)
        self.assertIn("nicht feststellen", text)
        self.assertNotIn("hat **nicht stattgefunden**", text)

    def test_a_confirmed_report_says_so_plainly(self):
        _, text = self.a.meldung("Befund", bestaetigt=True)
        self.assertIn("nicht stattgefunden", text)

    def test_the_report_names_the_sixty_day_rule(self):
        """Die wahrscheinlichste Ursache gehört in die Meldung, sonst sucht
        der Leser sie selbst: GitHub deaktiviert geplante Workflows in
        stillen Repositories nach 60 Tagen."""
        _, text = self.a.meldung("Befund")
        self.assertIn("60", text)

    def test_the_two_watchers_do_not_share_a_marker(self):
        """Gleiche Marke hiesse: die eine Meldung unterdrückt die andere,
        und der seltenere Fall verschwände hinter dem häufigeren."""
        import check_run_streak as s
        self.assertNotEqual(self.a.MARKE, s.MARKE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
