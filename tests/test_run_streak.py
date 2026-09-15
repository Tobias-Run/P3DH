"""Wann meldet die unbeaufsichtigte Pipeline sich selbst? (#8)

Seit der Zeitplan scharf ist, sieht niemand mehr zu. Diese Regel entscheidet,
wann ein roter Lauf einen Menschen erreicht — und sie ist genau dann falsch
gebaut, wenn sie im Zweifel schweigt.

## Die drei Fallen, gegen die diese Tests geschrieben sind

1. **Stille als Entspannung lesen.** Ist die Lauf-Historie nicht abrufbar, ist
   die Strecke *unbekannt*, nicht null. Ein `except: return False` liesse die
   Überwachung ausfallen und sich dabei als „alles in Ordnung" melden.
2. **Manuelle Läufe mitzählen.** Wer selbst startet, sieht das Ergebnis. Zählte
   ein Experiment am Freitag mit, löste es eine Meldung aus, die niemand
   braucht — und die echte ginge im Rauschen unter.
3. **Jede Woche dieselbe Meldung.** Nach einem Monat stünde viermal dasselbe im
   Tracker, und die Meldung verlöre die Dringlichkeit, für die sie da ist.

Der Ernstfall selbst lässt sich nicht proben: dafür müssten zwei geplante Läufe
in echt scheitern. Prüfbar ist die Entscheidungsregel — und die ist der Teil,
der falsch sein kann.
"""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def lauf(conclusion, event="schedule"):
    return {"event": event, "conclusion": conclusion}


class StreckeTest(unittest.TestCase):
    def setUp(self):
        import check_run_streak as c
        self.c = c

    def test_a_green_run_ends_the_streak(self):
        self.assertEqual(self.c.strecke(
            [lauf("failure"), lauf("success"), lauf("failure")]), 1)

    def test_two_in_a_row_are_counted(self):
        self.assertEqual(self.c.strecke([lauf("failure"), lauf("failure")]), 2)

    def test_a_manual_failure_does_not_extend_the_streak(self):
        """Wer selbst startet, sieht das Ergebnis — das ist kein unbemerkter
        Ausfall. Zählte er mit, meldete ein Experiment am Freitag einen
        Pipeline-Schaden."""
        self.assertEqual(self.c.strecke(
            [lauf("failure"), lauf("failure", event="workflow_dispatch")]), 1)

    def test_a_manual_run_between_two_failures_does_not_break_it(self):
        """Umgekehrt darf ein manueller GRÜNER Lauf die Strecke nicht
        beenden — er sagt nichts darüber, ob der Zeitplan funktioniert."""
        self.assertEqual(self.c.strecke(
            [lauf("failure"), lauf("success", event="workflow_dispatch"),
             lauf("failure")]), 2)

    def test_a_cancelled_run_is_not_a_failure(self):
        """Jemand hat abgebrochen. Das ist eine Entscheidung, kein Schaden."""
        self.assertEqual(self.c.strecke(
            [lauf("failure"), lauf("cancelled"), lauf("failure")]), 1)

    def test_a_timeout_is_a_failure(self):
        self.assertEqual(self.c.strecke(
            [lauf("failure"), lauf("timed_out")]), 2)

    def test_a_run_without_a_result_ends_the_count(self):
        """Ein Lauf ohne `conclusion` ist kein Beleg — weder dafür noch
        dagegen."""
        self.assertEqual(self.c.strecke(
            [lauf("failure"), lauf(None), lauf("failure")]), 1)

    def test_no_history_is_no_streak(self):
        self.assertEqual(self.c.strecke([]), 0)


class EntscheidungTest(unittest.TestCase):
    def setUp(self):
        import check_run_streak as c
        self.c = c

    def test_one_failure_stays_quiet(self):
        """EDAP ist zeitweise weg, ein Runner fällt aus, Wikidata drosselt.
        Solche Läufe heilen sich in der Woche darauf."""
        melden, grund = self.c.soll_melden([lauf("failure")], None)
        self.assertFalse(melden)
        self.assertIn("Schwelle", grund)

    def test_two_failures_raise_the_alarm(self):
        melden, _ = self.c.soll_melden([lauf("failure"), lauf("failure")], None)
        self.assertTrue(melden)

    def test_an_open_report_prevents_a_second(self):
        melden, grund = self.c.soll_melden(
            [lauf("failure"), lauf("failure")], offene_meldung=42)
        self.assertFalse(melden)
        self.assertIn("42", grund)

    def test_an_unreachable_history_reports_rather_than_stays_silent(self):
        """Die wichtigste Zeile dieser Datei. Unbekannt ist nicht null: sonst
        fiele die Überwachung aus und meldete sich als „alles in Ordnung"."""
        melden, grund = self.c.soll_melden([], None, historie_bekannt=False)
        self.assertTrue(melden)
        self.assertIn("nicht abrufbar", grund)

    def test_even_then_an_open_report_still_prevents_a_second(self):
        """Sonst entstünde bei einer längeren API-Störung jede Woche ein
        neues Issue."""
        melden, _ = self.c.soll_melden([], offene_meldung=42,
                                       historie_bekannt=False)
        self.assertFalse(melden)

    def test_the_threshold_is_configurable_and_actually_used(self):
        drei = [lauf("failure")] * 2
        self.assertFalse(self.c.soll_melden(drei, None, schwelle=3)[0])
        self.assertTrue(self.c.soll_melden(drei, None, schwelle=2)[0])

    def test_the_reason_is_always_filled(self):
        for args in (([lauf("failure")], None),
                     ([lauf("failure"), lauf("failure")], None),
                     ([], 7),
                     ([], None)):
            with self.subTest(args=args):
                self.assertTrue(self.c.soll_melden(*args)[1])


class MeldungTest(unittest.TestCase):
    """Die Wiedererkennung läuft über den Titel, nicht über ein Label: ein
    Label muss im Repository existieren, sonst schlägt das Anlegen genau an
    der Stelle fehl, die gerade melden soll."""

    def setUp(self):
        import check_run_streak as c
        self.c = c

    def test_the_title_is_the_marker_itself(self):
        """Titel und Suchmarke kommen aus derselben Quelle. Liefen sie
        auseinander, fände die Suche die offene Meldung nie — und das Ergebnis
        wäre kein Fehler, sondern jede Woche ein neues Issue."""
        titel, _ = self.c.meldung("egal")
        self.assertTrue(titel.startswith(self.c.MARKE))

    def test_the_marker_is_a_plain_title_prefix(self):
        self.assertTrue(self.c.MARKE)
        for zeichen in ("[", "]", "\n"):
            self.assertNotIn(zeichen, self.c.MARKE)

    def test_the_body_tags_the_owner(self):
        """Ohne Erwähnung ist beim Lesen nicht klar, an wen die Meldung
        gerichtet ist."""
        _, text = self.c.meldung("egal")
        self.assertIn("@Tobias-Run", text)

    def test_the_body_carries_the_reason_and_the_links(self):
        _, text = self.c.meldung("2 geplante Läufe hintereinander",
                                 lauf_url="https://x/run/1",
                                 workflow_url="https://x/wf")
        self.assertIn("2 geplante Läufe hintereinander", text)
        self.assertIn("https://x/run/1", text)
        self.assertIn("https://x/wf", text)

    def test_the_body_says_why_a_single_failure_stays_quiet(self):
        """Sonst liest sich die Meldung wie ein Alarm bei jedem roten Lauf,
        und der Empfänger stellt die Überwachung ab."""
        _, text = self.c.meldung("egal")
        self.assertIn("einzelner", text.lower())

    def test_an_unconfirmed_report_does_not_claim_the_streak(self):
        """Wird gemeldet, weil die Historie fehlte, ist die Strecke unbekannt.
        Der Text darf sie dann nicht behaupten — eine Meldung, die mehr weiss
        als ihre Grundlage hergibt, schickt jemanden auf eine falsche Fährte."""
        _, text = self.c.meldung("Historie weg", bestaetigt=False)
        self.assertNotIn("ist **zweimal hintereinander** fehlgeschlagen", text)
        self.assertIn("nicht feststellen", text.replace("liess sich nicht "
                                                        "feststellen",
                                                        "nicht feststellen"))

    def test_a_confirmed_report_states_the_streak_plainly(self):
        _, text = self.c.meldung("2 Läufe", bestaetigt=True)
        self.assertIn("zweimal hintereinander", text)


def job_block(text, name):
    """Die Zeilen EINES Jobs aus pipeline.yml — ohne PyYAML.

    Das Projekt liest diese Datei auch sonst textuell
    (`check_pipeline_order.py`) und verzichtet bewusst auf die Abhängigkeit;
    PyYAML steht nicht in `requirements.txt`, und eine projektweite Dependency
    für einen einzigen Test wäre unverhältnismässig. Genau daran ist der erste
    Anlauf in CI gescheitert — lokal war PyYAML da, auf dem Runner nicht.

    Abgegrenzt wird über die Einrückung: ein Job beginnt bei zwei Leerzeichen
    und endet beim nächsten Geschwister auf derselben Ebene.
    """
    aus, drin = [], False
    for z in text.splitlines():
        if z.startswith(f"  {name}:"):
            drin = True
            continue
        if drin:
            if z.startswith("  ") and not z.startswith("   ") and z[2:3].strip():
                break                      # naechster Job
            if z and not z.startswith(" "):
                break                      # naechster Abschnitt
            aus.append(z)
    return aus


class WorkflowTest(unittest.TestCase):
    """Der Workflow muss halten, was das Skript voraussetzt."""

    def setUp(self):
        self.wf = (ROOT / ".github" / "workflows" / "pipeline.yml").read_text(
            encoding="utf-8")

    def test_the_workflow_may_write_issues(self):
        """Ohne `issues: write` scheitert das Anlegen mit 403 — und der
        Ausfall der Meldung wäre selbst wieder ein stiller Ausfall."""
        self.assertIn("issues: write", self.wf)

    def test_the_report_is_its_own_job(self):
        """Als Schritt mit `if: failure()` innerhalb des Pipeline-Jobs würde
        die Meldung übersprungen, wenn der Lauf früh abbricht — beim Checkout
        oder bei `pip install`. Gerade dann braucht es sie."""
        text = "\n".join(job_block(self.wf, "melden"))
        self.assertTrue(text, "Job `melden` fehlt in pipeline.yml")
        self.assertIn("needs: pipeline", text,
                      "ohne `needs: pipeline` haengt die Meldung an nichts")
        self.assertIn("failure()", text)
        self.assertIn("schedule", text)

    def test_the_job_uses_the_files_the_script_writes(self):
        self.assertIn("interim/meldung_titel.txt", self.wf)
        self.assertIn("interim/meldung.md", self.wf)

    def test_the_issue_is_assigned_not_only_mentioned(self):
        """Eine Erwähnung im Text erzeugt keine verlässliche Benachrichtigung,
        eine Zuweisung schon."""
        self.assertIn("--assignee Tobias-Run", self.wf)

    def test_the_extractor_finds_the_job_in_the_real_file(self):
        block = "\n".join(job_block(self.wf, "melden"))
        self.assertIn("Strecke pruefen", block)
        self.assertEqual(job_block(self.wf, "gibtsnicht"), [])


class BlockTest(unittest.TestCase):
    """Der Extraktor selbst, an einem KÜNSTLICHEN Beispiel.

    Gegen `pipeline.yml` geprüft wäre die Abgrenzung nicht prüfbar: `melden` ist
    dort der letzte Job, es gibt also gar nichts, worüber der Extraktor hinaus
    laufen könnte. Ein Test, der ihn dort misst, läuft über nichts und meldet
    Erfolg — dieselbe Falle, gegen die diese ganze Datei geschrieben ist.
    """

    BEISPIEL = (
        "jobs:\n"
        "  erster:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - name: A\n"
        "  melden:\n"
        "    needs: erster\n"
        "    steps:\n"
        "      - name: B\n"
        "  dritter:\n"
        "    steps:\n"
        "      - name: C\n"
        "\n"
        "footer: x\n"
    )

    def test_it_stops_at_the_next_job(self):
        block = "\n".join(job_block(self.BEISPIEL, "melden"))
        self.assertIn("name: B", block)
        self.assertNotIn("name: C", block, "läuft in den nächsten Job hinein")
        self.assertNotIn("name: A", block, "greift den vorigen Job mit")

    def test_it_stops_at_the_end_of_the_jobs_section(self):
        block = "\n".join(job_block(self.BEISPIEL, "dritter"))
        self.assertIn("name: C", block)
        self.assertNotIn("footer", block)

    def test_an_unknown_job_yields_nothing(self):
        self.assertEqual(job_block(self.BEISPIEL, "gibtsnicht"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
