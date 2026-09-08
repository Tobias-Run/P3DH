"""Der Datensatz trägt seine Herkunft mit (#20).

## Warum ein Manifest kein Beiwerk ist

Der `data`-Branch wird force-gepusht und trägt genau EINEN Commit. Er hat keine
Historie: jeder Lauf ersetzt den vorigen Stand vollständig. Ein heruntergeladenes
Parquet ohne beiliegendes Manifest ist damit nicht identifizierbar — man sieht ihm
nicht an, aus welchem Code, welchem Codebook und welchem Katalogstand es entstand,
und zwei Downloads von verschiedenen Tagen sind ununterscheidbar.

## Gezählt, nicht gepflegt

Jede Kennzahl im Manifest kommt aus einer Abfrage gegen das Parquet. Der Grund
steht im Repo: `SESSION_STATUS.md` trug handgepflegte Zahlen und behauptete am
Ende 209.231 Records, während der Bestand bei 2.295.224 stand. Eine Zahl, die
jemand pflegen muss, ist eine Zahl, die irgendwann lügt.
"""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

WORKFLOW = ROOT / ".github" / "workflows" / "pipeline.yml"
PUBLISH = ROOT / "scripts" / "publish_data_branch.sh"
BUILDER = ROOT / "scripts" / "build_dataset_manifest.py"
DOC = ROOT / "docs" / "datensatz.md"


class BuilderTest(unittest.TestCase):
    def setUp(self):
        self.src = BUILDER.read_text(encoding="utf-8")

    def test_every_headline_number_comes_from_a_query(self):
        """Keine Kennzahl darf als Literal im Skript stehen."""
        import build_dataset_manifest as bm

        for name in ("facts", "reports", "institutions", "countries",
                     "templates", "datapoints", "facts_without_row"):
            self.assertIn(f'"{name}": one(', self.src,
                          f"{name} wird nicht aus dem Parquet gezählt")
        self.assertTrue(callable(bm.counts))

    def test_the_dataset_is_not_claimed_under_our_licence(self):
        """Der Datensatz ist inhaltlich EBA-Material. Ein Manifest, das das
        verschweigt, lädt genau zur falschen Nachnutzung ein."""
        import build_dataset_manifest as bm

        rights = bm.SOURCE["rights"]
        self.assertIn("EBA", rights)
        self.assertIn("MIT", rights, "die Abgrenzung zur Code-Lizenz fehlt")

    def test_a_missing_parquet_says_so_instead_of_writing_an_empty_manifest(self):
        self.assertIn("kein Parquet unter", self.src)
        self.assertIn("raise SystemExit", self.src)

    def test_git_details_are_optional(self):
        """Ein Manifest ohne Commit ist besser als ein abgebrochener Lauf —
        das Manifest ist Beiwerk zum Publish, nicht sein Torwächter."""
        import build_dataset_manifest as bm

        self.assertEqual(bm._git("definitiv-kein-git-unterkommando"), "")

    def test_the_output_is_stable_apart_from_the_timestamp(self):
        """sort_keys, damit zwei Läufe sich nur dort unterscheiden, wo sie
        sollen — sonst rauscht jeder data-Commit."""
        self.assertIn("sort_keys=True", self.src)


class WiringTest(unittest.TestCase):
    def test_the_manifest_is_built_before_the_publish(self):
        wf = WORKFLOW.read_text(encoding="utf-8")
        build = wf.index("- name: Datensatz-Manifest")
        publish = wf.index("- name: Publish data branch")
        self.assertLess(build, publish,
                        "Das Manifest entsteht nach dem Publish — dann geht der "
                        "Bestand ohne Herkunftsnachweis raus")

    def test_the_manifest_is_built_after_the_guards(self):
        """Ein Manifest ueber einen Bestand, den die Paritaetspruefung noch nicht
        gesehen hat, beglaubigt moeglicherweise Falsches."""
        wf = WORKFLOW.read_text(encoding="utf-8")
        self.assertLess(wf.index("- name: Zweig-A-Parität"),
                        wf.index("- name: Datensatz-Manifest"))

    def test_the_manifest_travels_with_the_parquet(self):
        """Auf das KOPIERKOMMANDO prüfen, nicht auf das Vorkommen des Namens.

        Die erste Fassung dieses Tests suchte nur „manifest.json" im Skript — und
        blieb grün, als das Kopieren entfernt wurde: der Name steht auch im
        data-README, das dasselbe Skript schreibt. Eine Zusage, die Prosa erfüllt
        statt Mechanik, prüft nichts.
        """
        pub = PUBLISH.read_text(encoding="utf-8")
        copies = [l for l in pub.splitlines()
                  if l.strip().startswith("cp ") and "manifest.json" in l]
        self.assertTrue(copies,
                        "Kein cp für manifest.json — das Manifest läge nur auf "
                        "dem Runner und stürbe mit ihm")
        self.assertTrue(any('"$TMP/state/"' in l for l in copies),
                        f"Manifest wird nicht nach state/ kopiert: {copies}")

    def test_the_data_branch_explains_itself(self):
        """Punkt 5 aus #20: der Branch soll ohne das Code-Repo verständlich sein."""
        pub = PUBLISH.read_text(encoding="utf-8")
        self.assertIn("README.md", pub)
        for claim in ("keine Historie", "EBA", "datensatz.md"):
            self.assertIn(claim, pub, f"das data-README verschweigt: {claim}")


class DocumentationTest(unittest.TestCase):
    """Die Einschränkungen an EINER Stelle — das war der Kern von #20."""

    def setUp(self):
        self.doc = DOC.read_text(encoding="utf-8")

    def test_the_schema_documents_every_column(self):
        """Eine undokumentierte Spalte wird geraten statt gelesen."""
        import duckdb

        parquet = ROOT / "processed" / "long" / "p3dh_long.parquet"
        if not parquet.exists():
            self.skipTest("Parquet nicht gebaut")
        cols = [r[0] for r in duckdb.connect().execute(
            f"DESCRIBE SELECT * FROM '{parquet.as_posix()}'").fetchall()]
        fehlt = [c for c in cols if f"`{c}`" not in self.doc]
        self.assertEqual(fehlt, [], f"nicht dokumentierte Spalten: {fehlt}")

    def test_the_traps_that_bit_us_are_written_down(self):
        for trap in ("eba_GA:x1", "unit_ambiguous", "template_reported"):
            self.assertIn(trap, self.doc)

    def test_the_framework_confound_is_stated(self):
        """RF 4.2 deckt sich exakt mit einem Stichtag — wer die Versionen
        vergleicht, vergleicht zugleich die Zeit. Das ist nicht offensichtlich."""
        self.assertIn("2026-03-31", self.doc)
        self.assertIn("Zeitvergleich", self.doc)

    def test_the_data_rights_are_not_buried(self):
        self.assertIn("gesondert zu zitieren", self.doc)
        self.assertIn("MIT-Lizenz", self.doc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
