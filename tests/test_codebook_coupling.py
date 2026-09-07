"""Codebook-Wechsel erzwingt den vollen Reparse (#57).

## Die Falle

`pipeline.yml` koppelte Codebook-Refresh und Voll-Reparse — richtig begründet,
aber am **Input**:

    if [ "$full_reparse" = true ] || [ "$refresh_codebook" = true ]; then --full

`codebook/dpm_codebook.csv` ist versioniert. Wer es per Commit ändert und einen
normalen Lauf auslöst, bekommt einen Mischzustand: neue Einreichungen mit den
neuen Koordinaten, der Altbestand mit den alten.

Und es gibt kein Fehlerbild. Der Placement-Guard prüft `unplaceable > baseline`
und schweigt, weil nichts unplatzierbar wird — die alten Fakten tragen *eine*
Koordinate, nur die falsche. Dieselbe Klasse wie #55 und #6: kein Fehler, nur
eine stille Inkonsistenz.

## Die Zusage gehört in den Ausführungspfad

Neben dem Bestand liegt jetzt der Fingerabdruck des Codebooks, mit dem er
entstanden ist. Weicht er ab, schaltet der Parser selbst auf `--full` — egal,
wie das Codebook dorthin kam. Der Workflow-Input bleibt als bequeme Abkürzung
bestehen, trägt die Zusage aber nicht mehr.

## Nachtrag: die Zusage kam beim Download nicht an

Der Fingerabdruck erreichte nur den PARSER. Der Download entschied weiter nach
`inputs.full_reparse` und holte sonst bloss das Delta. Da `raw/` auf jedem
Runner leer beginnt, baut ein voller Parse danach den Bestand aus einem
Bruchteil der Quellen neu.

Zwei Wege führten hinein, und der zweite lag schon vor #57 offen:

    Codebook per Commit geändert, kein Input   → Delta geladen, voll geparst
    refresh_codebook ohne full_reparse         → Delta geladen, voll geparst

Der erste wäre am Sanity-Gate gestorben, der zweite nicht: das Gate übersprang
sich ausgerechnet bei `refresh_codebook` selbst und hätte den geschrumpften
Bestand publiziert.

Jetzt fällt die Entscheidung EINMAL, vor dem Download, und Download, Parse und
Gate lesen dieselbe Antwort. Der Parser prüft den Abdruck weiterhin selbst —
die Zusage gehört in den Ausführungspfad, nicht allein in den Workflow.
"""

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import xbrl_csv_parser as xp  # noqa: E402

WORKFLOW = ROOT / ".github" / "workflows" / "pipeline.yml"
FETCH = ROOT / "scripts" / "fetch_state.sh"
PUBLISH = ROOT / "scripts" / "publish_data_branch.sh"


class FingerprintTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.cb = self.d / "dpm_codebook.csv"
        self.out = self.d / "long_form_raw.csv"
        self.cb.write_text("datapoint_code,template,row,col\ndp1,K_61.00,0010,0010\n",
                           encoding="utf-8")
        self.out.write_text("entityID\nrs:x\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_fingerprint_follows_the_content_not_the_file_date(self):
        a = xp.codebook_fingerprint(self.cb)
        self.cb.touch()
        self.assertEqual(xp.codebook_fingerprint(self.cb), a)

    def test_a_changed_coordinate_changes_the_fingerprint(self):
        """Der Fall, um den es geht: gleiche Zeilenzahl, andere Koordinate.
        Eine Prüfung über die Zeilenzahl ginge hier durch."""
        a = xp.codebook_fingerprint(self.cb)
        self.cb.write_text("datapoint_code,template,row,col\ndp1,K_61.00,0020,0010\n",
                           encoding="utf-8")
        self.assertNotEqual(xp.codebook_fingerprint(self.cb), a)

    def test_an_unchanged_codebook_keeps_the_incremental_run(self):
        xp._stamp_codebook(self.cb, self.out)
        changed, why = xp.codebook_changed(self.cb, self.out)
        self.assertFalse(changed)
        self.assertEqual(why, "", "unauffälliger Fall soll nichts sagen")

    def test_a_changed_codebook_forces_the_full_reparse(self):
        xp._stamp_codebook(self.cb, self.out)
        self.cb.write_text("datapoint_code,template,row,col\ndp1,K_61.00,0020,0010\n",
                           encoding="utf-8")
        changed, why = xp.codebook_changed(self.cb, self.out)
        self.assertTrue(changed)
        self.assertIn("Mischzustand", why,
                      "Der Grund gehört in die Ausgabe — sonst sieht der volle "
                      "Reparse aus wie ein Zufall")

    def test_a_missing_fingerprint_is_said_out_loud(self):
        """„Nicht geprüft" darf nicht wie „geprüft und in Ordnung" aussehen.
        Genau so ist der Fehler entstanden."""
        changed, why = xp.codebook_changed(self.cb, self.out)
        self.assertFalse(changed, "ohne Abdruck keinen vollen Reparse erzwingen")
        self.assertTrue(why, "ein fehlender Abdruck bleibt unerwähnt")
        self.assertIn("#57", why)

    def test_no_corpus_means_nothing_to_protect(self):
        self.out.unlink()
        changed, why = xp.codebook_changed(self.cb, self.out)
        self.assertFalse(changed)

    def test_the_stamp_sits_next_to_the_corpus(self):
        """Nicht neben dem Codebook: die Frage ist „womit ist DIESER Bestand
        entstanden", und der Bestand wandert als Zustand mit."""
        xp._stamp_codebook(self.cb, self.out)
        self.assertEqual(xp.fingerprint_path(self.out).parent, self.out.parent)
        self.assertTrue(xp.fingerprint_path(self.out).exists())


def _step(workflow_text, name):
    """Genau EIN Schritt aus pipeline.yml, bis zur nächsten Schrittgrenze.

    Grob bis zum nächsten interessanten Schritt zu schneiden zieht Nachbarn
    herein — etwa `Refresh DPM codebook`, der `inputs.refresh_codebook` zu Recht
    liest, weil er den Refresh selbst ausführt.
    """
    head = f"- name: {name}\n"
    start = workflow_text.index(head)
    nxt = workflow_text.find("\n      - name: ", start + len(head))
    return workflow_text[start:nxt if nxt != -1 else len(workflow_text)]


class ReparseModeTest(unittest.TestCase):
    """Die Entscheidung muss VOR dem Download fallen, sonst nützt sie nichts.

    Der Fingerabdruck schaltete den Parser auf --full, der Download fragte
    weiter den Workflow-Input. `raw/` beginnt auf jedem Runner leer — ein voller
    Parse über ein Delta-`raw/` baut den Bestand aus einem Bruchteil der Quellen
    neu.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.cb = self.d / "dpm_codebook.csv"
        self.out = self.d / "long_form_raw.csv"
        self.cb.write_text("datapoint_code,template,row,col\ndp1,K_61.00,0010,0010\n",
                           encoding="utf-8")
        self.out.write_text("entityID\nrs:x\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_unchanged_codebook_stays_incremental(self):
        xp._stamp_codebook(self.cb, self.out)
        mode, _ = xp.reparse_mode(self.cb, self.out)
        self.assertEqual(mode, "incremental")

    def test_changed_codebook_decides_full_before_anything_is_downloaded(self):
        xp._stamp_codebook(self.cb, self.out)
        self.cb.write_text("datapoint_code,template,row,col\ndp1,K_61.00,0020,0010\n",
                           encoding="utf-8")
        mode, why = xp.reparse_mode(self.cb, self.out)
        self.assertEqual(mode, "full")
        self.assertIn("Mischzustand", why)

    def test_forced_short_circuits_the_fingerprint(self):
        """`refresh_codebook` baut das Codebook erst NACH dem Download neu — der
        Abdruck kann zum Entscheidungszeitpunkt noch gar nichts davon wissen."""
        xp._stamp_codebook(self.cb, self.out)
        mode, why = xp.reparse_mode(self.cb, self.out, forced=True)
        self.assertEqual(mode, "full")
        self.assertTrue(why)

    def test_the_decision_is_the_same_one_the_parser_would_make(self):
        """Zwei Implementierungen derselben Zusage wären genau der Bruch, den
        dieser Fix schliesst."""
        for changed in (False, True):
            with self.subTest(changed=changed):
                self.cb.write_text("datapoint_code,template,row,col\n"
                                   f"dp1,K_61.00,00{'2' if changed else '1'}0,0010\n",
                                   encoding="utf-8")
                xp._stamp_codebook(self.cb, self.out)
                if changed:
                    self.cb.write_text("datapoint_code,template,row,col\n"
                                       "dp1,K_61.00,0030,0010\n", encoding="utf-8")
                mode, _ = xp.reparse_mode(self.cb, self.out)
                parser_says, _ = xp.codebook_changed(self.cb, self.out)
                self.assertEqual(mode == "full", parser_says)


class WiringTest(unittest.TestCase):
    """Der Abdruck nützt nur, wenn er den Lauf überlebt."""

    def test_download_and_parse_read_the_same_decision(self):
        """Der eigentliche Fehler: der Download entschied nach `inputs`, der
        Parse nach `inputs` PLUS Fingerabdruck. Wo sie auseinanderliefen, wurde
        das Delta geladen und der Bestand voll neu gebaut."""
        wf = WORKFLOW.read_text(encoding="utf-8")
        self.assertLess(wf.index("- name: Reparse-Modus bestimmen"),
                        wf.index("- name: Download new submissions"),
                        "Die Entscheidung steht hinter dem Download — dann lädt "
                        "er wieder auf eigene Rechnung")
        for name in ("Download new submissions", "Parse", "Sanity gate"):
            block = _step(wf, name)
            self.assertIn("steps.mode.outputs.full", block,
                          f"{name} liest die gemeinsame Entscheidung nicht")
            self.assertNotIn("inputs.full_reparse", block,
                             f"{name} fragt wieder direkt den Workflow-Input")
            self.assertNotIn("inputs.refresh_codebook", block,
                             f"{name} fragt wieder direkt den Workflow-Input")

    def test_the_inputs_still_reach_the_decision(self):
        """Die Abkürzung bleibt — sie hängt jetzt nur an einer Stelle."""
        wf = WORKFLOW.read_text(encoding="utf-8")
        block = wf[wf.index("- name: Reparse-Modus bestimmen"):
                   wf.index("- name: Download new submissions")]
        self.assertIn("inputs.full_reparse", block)
        self.assertIn("inputs.refresh_codebook", block)
        self.assertIn("--forced", block)

    def test_the_sanity_gate_reports_in_every_mode(self):
        """Seit der Fingerabdruck den vollen Reparse selbst auslösen kann, wären
        mit einem `if:` am Schritt Läufe ganz ohne Zahlenvergleich
        durchgelaufen, die niemand angefordert hat."""
        wf = WORKFLOW.read_text(encoding="utf-8")
        block = _step(wf, "Sanity gate")
        self.assertNotIn("if:", block,
                         "Das Gate überspringt sich selbst — dann bleibt ein "
                         "Schrumpfen unerwähnt statt gemeldet")
        self.assertIn("::warning::", block, "voller Reparse: melden statt abbrechen")
        self.assertIn("::error::", block, "inkrementell: abbrechen")

    def test_the_parser_checks_before_it_merges(self):
        src = (ROOT / "scripts" / "xbrl_csv_parser.py").read_text(encoding="utf-8")
        marker = "codebook_changed(codebook_path, output_path)"
        self.assertIn(marker, src,
                      "Der Parser fragt gar nicht mehr nach dem Codebook — die "
                      "Kopplung hängt wieder allein am Workflow-Input")
        check = src.index(marker)
        merge = src.index("existing_rows, dropped, parsed_sources = _load_existing")
        self.assertLess(check, merge,
                        "Die Prüfung steht hinter dem inkrementellen Merge — "
                        "dann ist der Mischzustand schon gebaut")

    def test_the_state_scripts_carry_the_fingerprint(self):
        """Ohne Mitnahme beginnt jeder frische Runner ohne Gedächtnis, und die
        Kopplung greift nie — die Pipeline ist stateless by design."""
        self.assertIn("codebook_fingerprint.txt", FETCH.read_text(encoding="utf-8"))
        self.assertIn("codebook_fingerprint.txt", PUBLISH.read_text(encoding="utf-8"))

    def test_a_missing_fingerprint_does_not_fail_the_restore(self):
        """Zustände von vor #57 tragen ihn nicht. Ein `rc=1` dort machte jeden
        Lauf rot, bis jemand einmal von Hand publiziert."""
        line = next(l for l in FETCH.read_text(encoding="utf-8").splitlines()
                    if "codebook_fingerprint.txt" in l and l.startswith("fetch"))
        self.assertIn("|| true", line)

    def test_the_fingerprint_stays_off_main(self):
        """Er gehört zum Zustand, nicht ins Repo — sonst stünde im Repo eine
        Behauptung über einen Bestand, den das Repo gar nicht enthält."""
        self.assertIn("processed/codebook_fingerprint.txt",
                      (ROOT / ".gitignore").read_text(encoding="utf-8"))

    def test_the_workflow_no_longer_claims_to_carry_the_coupling(self):
        """Der Input bleibt als Abkürzung — aber der Kommentar darf nicht
        weiter behaupten, er sei der Mechanismus."""
        wf = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("#57", wf)
        self.assertIn("Fingerabdruck", wf)


if __name__ == "__main__":
    unittest.main(verbosity=2)
