"""Der Harvest-Diff und sein Schrumpf-Gate (#6).

## Die Prämisse des Issues stimmte nicht — der Defekt war ein anderer

Das Issue sagte, der Vergleich sei „nicht scharf geschaltet". Gerechnet wurde er
seit `9a198be` bei jedem Lauf. Was fehlte, war beides drumherum:

* `harvest_log.csv` und `manifest_delta.csv` standen **nicht** in der
  Commit-Liste des Workflows. Ein append-only-Log, das auf einem Wegwerf-Runner
  entsteht, hat nach jedem CI-Harvest genau eine Zeile.
* Gelesen hat den Diff niemand.

Und beim Nachrechnen kam ein dritter Punkt dazu, den das Issue nicht kannte:
`manifest_full.csv` wurde **überschrieben, bevor** irgendetwas den Umfang
prüfen konnte. Ein Gate danach ist wirkungslos — die Vergleichsgrundlage ist
dann schon weg. Genau dieser Reihenfolgefehler ist es, der einen abgebrochenen
Harvest lautlos zum neuen Katalog macht.

## Was hier geprüft wird

Die Rechenlogik als reine Funktion über Strings — ohne Playwright, ohne Netz.
Dazu die beiden Zusagen, die man dem Code nicht ansieht: dass das Gate vor dem
Schreiben steht und dass der Workflow die beiden Dateien wirklich committet.
"""

from pathlib import Path
import csv
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import harvest_delta as hd  # noqa: E402

HARVESTER = ROOT / "scripts" / "harvest_catalog_query.py"
WORKFLOW = ROOT / ".github" / "workflows" / "pipeline.yml"

BASE = "https://errp.eba.europa.eu/x/"


def u(slot, ts):
    return f"{BASE}{slot}_{ts}.zip"


SLOT_A = "LEI1.CON_DE_PILLAR3020000_CODIS_2025-12-31"
SLOT_B = "LEI1.CON_DE_PILLAR3020000_ESGDIS_2025-12-31"
SLOT_C = "LEI2.IND_FR_PILLAR3020000_CODIS_2025-12-31"


class SlotTest(unittest.TestCase):
    def test_the_timestamp_is_what_separates_two_versions_of_a_slot(self):
        self.assertEqual(hd.slot_of(u(SLOT_A, "20260101120000000")), SLOT_A)
        self.assertEqual(hd.slot_of(u(SLOT_A, "1")), SLOT_A)

    def test_the_report_type_stays_part_of_the_slot(self):
        """Ohne den Typ fielen CODIS und ESGDIS desselben Instituts, Moduls und
        Stichtags zusammen — dann sähe eine zweite Meldung wie eine
        Neufassung der ersten aus. `build_parse_manifest.report_type()` warnt
        vor genau dieser Verwechslung; sie hat dort einmal 1.091 von 1.946
        Quelldateien gekostet."""
        self.assertNotEqual(hd.slot_of(u(SLOT_A, "1")), hd.slot_of(u(SLOT_B, "1")))


class ClassifyTest(unittest.TestCase):
    def test_a_first_entry_for_a_slot_is_new(self):
        rows = hd.classify(set(), {u(SLOT_A, "1")})
        self.assertEqual([r["change"] for r in rows], ["neu"])

    def test_a_second_version_of_a_known_slot_is_a_resubmission(self):
        rows = hd.classify({u(SLOT_A, "1")}, {u(SLOT_A, "1"), u(SLOT_A, "2")})
        self.assertEqual([(r["change"], r["url"]) for r in rows],
                         [("resubmission", u(SLOT_A, "2"))])

    def test_a_disappeared_row_whose_slot_survives_is_only_superseded(self):
        rows = hd.classify({u(SLOT_A, "1")}, {u(SLOT_A, "2")})
        self.assertEqual(hd.counts(rows),
                         {"neu": 0, "resubmission": 1, "ueberholt": 1,
                          "zurueckgezogen": 0})

    def test_only_an_empty_slot_counts_as_withdrawn(self):
        """Das ist die Klasse, in der die belegten toten EDAP-Links sichtbar
        werden — und die einzige, die einen echten Verlust bedeutet."""
        rows = hd.classify({u(SLOT_A, "1"), u(SLOT_C, "1")}, {u(SLOT_A, "1")})
        self.assertEqual([(r["change"], r["slot"]) for r in rows],
                         [("zurueckgezogen", SLOT_C)])

    def test_an_unchanged_catalog_produces_no_rows(self):
        cur = {u(SLOT_A, "1"), u(SLOT_B, "2")}
        self.assertEqual(hd.classify(cur, cur), [])

    def test_the_output_is_deterministic(self):
        """`manifest_delta.csv` wird committet. Eine unsortierte Ausgabe würde
        bei jedem Lauf einen Diff erzeugen, der nichts bedeutet."""
        prev = {u(SLOT_A, "1"), u(SLOT_C, "1")}
        cur = {u(SLOT_A, "2"), u(SLOT_B, "1")}
        first = hd.classify(prev, cur)
        for _ in range(5):
            self.assertEqual(hd.classify(set(prev), set(cur)), first)
        self.assertEqual(first, sorted(first, key=lambda r: (r["change"], r["url"])))

    def test_counts_always_names_all_four_classes(self):
        """Eine fehlende Null im Log wäre eine Lücke, keine Null."""
        self.assertEqual(sorted(hd.counts([])), sorted(hd.LOG_FIELDS[3:]))


class ShrinkGateTest(unittest.TestCase):
    """Der Harvest ist der fragilste Teil der Kette. Bricht die DSR-Pagination
    ab, liefert er weniger Zeilen — und die sähen aus wie ein Katalog."""

    def test_a_growing_catalog_passes(self):
        self.assertIsNone(hd.shrink_verdict(4278, 4290))

    def test_the_documented_dead_links_stay_within_tolerance(self):
        """17 tote Links auf 4.278 Zeilen sind 0,4 % — legitimer Abgang, kein
        Fehlschlag. Eine Toleranz, die diesen Fall fängt, wäre unbrauchbar."""
        self.assertIsNone(hd.shrink_verdict(4278, 4278 - 17))

    def test_a_truncated_pagination_is_caught(self):
        v = hd.shrink_verdict(4278, 2000)
        self.assertIsNotNone(v)
        self.assertIn("Pagination", v)

    def test_an_empty_harvest_is_caught_even_on_the_first_run(self):
        self.assertIsNotNone(hd.shrink_verdict(0, 0))

    def test_the_first_run_has_nothing_to_protect(self):
        self.assertIsNone(hd.shrink_verdict(0, 4278))

    def test_the_gate_runs_before_the_catalog_is_overwritten(self):
        """Der Punkt, den das Issue nicht kannte. Ein Gate nach dem Schreiben
        vergleicht gegen den bereits beschädigten Katalog und kann nie wieder
        auslösen."""
        src = HARVESTER.read_text(encoding="utf-8")
        gate = src.index("shrink_verdict")
        write = src.index('with open(out, "w"')
        self.assertLess(gate, write,
                        "Das Schrumpf-Gate steht hinter dem Überschreiben von "
                        "manifest_full.csv — dort ist die Vergleichsgrundlage weg.")

    def test_the_harvester_reports_the_refusal_as_a_failure(self):
        """Ein abgelehnter Harvest, der mit 0 endet, lässt die Pipeline auf dem
        alten Katalog weiterlaufen, als wäre nichts gewesen."""
        src = HARVESTER.read_text(encoding="utf-8")
        self.assertIn("raise SystemExit(main())", src)
        self.assertRegex(src, r"verdict and .--allow-shrink. not in sys\.argv[\s\S]{0,400}return 1")


class PersistenceTest(unittest.TestCase):
    """Der eigentliche Defekt: berechnet, gedruckt, verworfen."""

    def test_the_workflow_commits_both_delta_files(self):
        wf = WORKFLOW.read_text(encoding="utf-8")
        for name in ("harvest_log.csv", "manifest_delta.csv"):
            self.assertIn(f"interim/edap_recon/{name}", wf,
                          f"{name} steht nicht in der Commit-Liste — die "
                          "Historie stirbt mit dem Runner")

    def test_the_delta_files_are_not_gitignored(self):
        """Committen kann der Workflow nur, was nicht ignoriert ist."""
        ign = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for name in ("harvest_log.csv", "manifest_delta.csv"):
            self.assertNotIn(name, ign)

    def test_the_diff_has_a_reader(self):
        wf = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("scripts/harvest_delta.py", wf,
                      "Der Diff wird nirgends gelesen — genau der Zustand, den "
                      "#6 beseitigen sollte")
        self.assertIn("GITHUB_STEP_SUMMARY", wf)

    def test_the_log_is_append_only_across_runs(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "harvest_log.csv"
            hd.append_log("2026-01-01T00:00:00Z", 4278, 489,
                          hd.classify(set(), {u(SLOT_A, "1")}), path=log)
            hd.append_log("2026-01-08T00:00:00Z", 4279, 489,
                          hd.classify({u(SLOT_A, "1")},
                                      {u(SLOT_A, "1"), u(SLOT_C, "1")}), path=log)
            with log.open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 2, "zweiter Lauf hat den Log überschrieben")
        self.assertEqual([r["neu"] for r in rows], ["1", "1"])
        self.assertEqual(rows[1]["total"], "4279")

    def test_a_log_with_a_different_header_is_refused_instead_of_misaligned(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "harvest_log.csv"
            log.write_text("harvested_at,total,institutions,new,gone\n"
                           "2026-01-01T00:00:00Z,4278,489,0,0\n", encoding="utf-8")
            with self.assertRaises(SystemExit):
                hd.append_log("2026-01-08T00:00:00Z", 4279, 489, [], path=log)


class SummaryTest(unittest.TestCase):
    def _fixture(self, d):
        log, delta = Path(d) / "harvest_log.csv", Path(d) / "manifest_delta.csv"
        rows = hd.classify({u(SLOT_A, "1"), u(SLOT_C, "1")},
                           {u(SLOT_A, "2"), u(SLOT_B, "1")})
        hd.append_log("2026-01-08T00:00:00Z", 4279, 489, rows, path=log)
        hd.write_delta(rows, path=delta)
        return log, delta

    def test_the_summary_names_the_withdrawn_slots(self):
        with tempfile.TemporaryDirectory() as d:
            log, delta = self._fixture(d)
            md = hd.render_summary(log, delta)
        self.assertIn("Zurückgezogen", md)
        self.assertIn(SLOT_C, md, "der einzige echte Verlust wird nicht benannt")
        self.assertNotIn(SLOT_B, md, "Neuzugänge gehören nicht in die Verlustliste")

    def test_a_run_without_a_harvest_says_so_instead_of_failing(self):
        """Der Schritt läuft nur bei inputs.harvest — aber ein Aufruf ohne
        Dateien darf keinen Traceback in die Zusammenfassung schreiben."""
        with tempfile.TemporaryDirectory() as d:
            md = hd.render_summary(Path(d) / "nix.csv", Path(d) / "auch_nicht.csv")
        self.assertIn("Kein Harvest-Log", md)

    def test_the_summary_counts_match_the_delta_file(self):
        with tempfile.TemporaryDirectory() as d:
            log, delta = self._fixture(d)
            md = hd.render_summary(log, delta)
            with delta.open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
        n = hd.counts(rows)
        self.assertIn(f"Neu: **{n['neu']}**", md)
        self.assertIn(f"zurückgezogen: **{n['zurueckgezogen']}**", md)


class RealCatalogTest(unittest.TestCase):
    """Gegen den committeten Katalog: die Klassifikation muss auf echten
    Dateinamen etwas Sinnvolles ergeben, nicht nur auf Kunstbeispielen."""

    def setUp(self):
        self.man = ROOT / "interim" / "edap_recon" / "manifest_full.csv"
        if not self.man.exists():
            self.skipTest("manifest_full.csv fehlt")
        self.urls = hd.read_urls(self.man)

    def test_the_catalog_really_carries_several_versions_per_slot(self):
        """Die Annahme, auf der die Unterscheidung ruht. Wäre je Meldeplatz nur
        eine Einreichung im Katalog, wäre „resubmission" eine leere Kategorie."""
        slots = {}
        for x in self.urls:
            slots[hd.slot_of(x)] = slots.get(hd.slot_of(x), 0) + 1
        multi = sum(1 for v in slots.values() if v > 1)
        self.assertGreater(multi, 0)
        self.assertLess(multi, len(slots),
                        "jeder Meldeplatz mehrfach belegt — dann trennt der "
                        "Zeitstempel nicht, was er soll")

    def test_no_filename_loses_its_timestamp_to_the_slot(self):
        """Ein Dateiname ohne `_<ts>.zip` würde als eigener Meldeplatz gelten
        und bei jedem Harvest als Resubmission auftauchen."""
        bad = [x for x in self.urls if not re.search(r"_[0-9]+\.zip$", x)]
        self.assertEqual(bad[:5], [], f"{len(bad)} URLs ohne Zeitstempel")

    def test_a_catalog_compared_with_itself_is_empty(self):
        self.assertEqual(hd.classify(self.urls, self.urls), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
