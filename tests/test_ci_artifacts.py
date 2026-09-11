"""Die Tests, die Zweig A gegen seine Quelle pruefen, laufen auch in CI (#69).

## Die Luecke

24 Tests pruefen, ob die Zweig-A-Artefakte (`index.json`, `codebook.json`,
`benchmark.json`) tragen, was das Repo verspricht: die Framework-Bruecke, die
Kennzahlen-Registry, die Achsenkarte, die Waehrungsausnahmen, die
Mehrdeutigkeitsmarker.

Diese Dateien sind gitignored — sie leben auf dem `data`-Branch. In CI wird
frisch geklont, also fehlten sie dort IMMER, und die Tests riefen `skipTest`.
Gemessen an einem frischen Checkout: 411 Tests, davon **24 uebersprungen**, und
unittest meldete `OK`.

Eine Pruefung, die sich bei Abwesenheit fuer erfuellt erklaert, ist genau der
Fehlermodus, den dieses Projekt sonst jagt — dieselbe Klasse wie #55, #57 und
der Codebook-Wechsel.

## Warum gebaut und nicht heruntergeladen

Der naheliegende Weg waere, die publizierten Artefakte zu ziehen. Der geht
nicht: sie stammen vom letzten Pipeline-Lauf, ein Pull Request aendert die
Repo-Seite davor. `test_payload_matches_the_source` vergleicht
`codebook.json` gegen `codebook/framework_bridge.csv` — mit heruntergeladenen
Artefakten waere der Test rot, obwohl beide Seiten fuer sich richtig sind.
Genau dieser Fehlalarm ist lokal mehrfach aufgetreten.

Deshalb baut der Job die Artefakte aus dem AKTUELLEN Code. Dann vergleichen die
Tests Repo und Artefakt desselben Standes.
"""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"


def _job(text, name):
    """Einen Job aus tests.yml herausschneiden, bis zur naechsten Jobgrenze."""
    start = text.index(f"\n  {name}:\n")
    nxt = text.find("\n  ", text.index("steps:", start))
    # Jobgrenzen sind Zeilen mit genau zwei Leerzeichen Einrueckung und Doppelpunkt
    import re
    m = re.search(r"\n  [a-z][a-z0-9_-]*:\n", text[start + 1:])
    return text[start:start + 1 + m.start()] if m else text[start:]


def _ohne_kommentare(block):
    """Nur die ausfuehrbaren Zeilen.

    Ein Test, der den ganzen Block durchsucht, wird von der Begruendung erfuellt
    statt vom Mechanismus: der Kommentar nennt `fetch_state.sh`, um zu erklaeren,
    warum es NICHT benutzt wird.
    """
    return "\n".join(z for z in block.splitlines()
                     if not z.lstrip().startswith("#"))


class ArtefaktJobTest(unittest.TestCase):
    def setUp(self):
        self.wf = WORKFLOW.read_text(encoding="utf-8")

    def test_there_is_a_job_that_builds_the_artifacts(self):
        self.assertIn("\n  artifacts:\n", self.wf,
                      "Ohne diesen Job ueberspringen sich die 24 Tests wieder — "
                      "und der Lauf meldet weiter OK")

    def test_the_artifacts_are_built_not_downloaded(self):
        """Heruntergeladene Artefakte stammen vom letzten Pipeline-Lauf und
        widersprechen der Repo-Seite eines Pull Requests."""
        job = _ohne_kommentare(_job(self.wf, "artifacts"))
        self.assertIn("python scripts/build_zweig_a_shards.py", job)
        for gebaut in ("index.json", "codebook.json", "benchmark.json"):
            self.assertNotIn(f"/{gebaut}", job,
                             f"{gebaut} wird heruntergeladen statt gebaut")

    def test_only_the_gitignored_state_is_fetched(self):
        """Parquet und Coverage-Matrix sind gitignored und muessen kommen.
        fetch_state.sh zoege zusaetzlich long_form_raw.csv (~300 MB) — die liest
        hier niemand."""
        job = _ohne_kommentare(_job(self.wf, "artifacts"))
        self.assertIn("p3dh_long.parquet", job)
        self.assertIn("filing_indicators.csv.gz", job)
        self.assertNotIn("fetch_state.sh", job)

    def test_a_skipped_test_fails_the_job(self):
        """Der Kern von #69. Mit gebauten Artefakten laeuft alles; jede
        Auslassung waere die Rueckkehr der Luecke."""
        job = _job(self.wf, "artifacts")
        self.assertIn("skipped", job)
        self.assertIn("exit 1", job,
                      "Auslassungen werden gezaehlt, aber nicht geahndet")

    def test_the_pipe_does_not_swallow_the_exit_code(self):
        """`python … | tee` liefert den Status von tee. Ohne pipefail waere ein
        roter Testlauf gruen — die Lueckenschliessung haette ein Loch."""
        job = _job(self.wf, "artifacts")
        self.assertIn("set -o pipefail", job)

    def test_the_fast_job_survives(self):
        """Die schnelle Rueckmeldung am Pull Request soll bleiben: der
        Artefakt-Job braucht Netz und ~30 s Bauzeit."""
        self.assertIn("\n  unittest:\n", self.wf)

    def test_the_workflow_no_longer_claims_every_test_builds_its_fixture(self):
        """Der alte Kommentar behauptete, jeder datenabhaengige Test baue sich
        seine eigene Fixture. Fuer diese 24 stimmte das nie."""
        self.assertNotIn("baut sich seine eigene Fixture", self.wf)

    def test_the_workflow_stays_read_only(self):
        """Ein Pull Request darf nichts schreiben — schon gar nicht aus einem
        Fork. Der neue Job aendert daran nichts."""
        self.assertIn("contents: read", self.wf)
        self.assertNotIn("contents: write", self.wf)


if __name__ == "__main__":
    unittest.main(verbosity=2)
