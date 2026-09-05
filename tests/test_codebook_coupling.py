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


class WiringTest(unittest.TestCase):
    """Der Abdruck nützt nur, wenn er den Lauf überlebt."""

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
