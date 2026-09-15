"""Die Reihenfolge der Pipeline gegen die Abhängigkeiten der Skripte (#8).

#8 will den wöchentlichen Cron scharf schalten, mit der Vorbedingung „ein
manueller Lauf komplett grün". Grün heisst aber nur, dass kein Schritt mit
Exit-Code != 0 endete — und genau das ist bei einer Reihenfolgenverletzung
nicht der Fall:

    build_footprint.py         ohne scale_flags.csv         -> Exit 0, nichts markiert
    build_omission_profile.py  ohne disclosure_frequency.csv -> Exit 0, leere Datei
    check_plausibility.py      ohne disclosure_frequency.csv -> Exit 0, Hinweis fehlt

Alle drei sind im September 2026 tatsächlich passiert, und der dritte wurde erst
von diesem Guard gefunden — beim ersten Lauf, in frisch committetem Code.

## Was der Guard NICHT kann

Er findet FALSCHE Reihenfolgen, nicht VERGESSENE Abhängigkeiten. Wer ein
Artefakt liest und die Tabelle nicht pflegt, bekommt keinen Fehler. Dagegen
hilft nur ein echter Lauf — und genau deshalb bleibt die Vorbedingung aus #8
bestehen.
"""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

WORKFLOW = ROOT / ".github" / "workflows" / "pipeline.yml"


class SchritteTest(unittest.TestCase):
    def setUp(self):
        import check_pipeline_order as c
        self.c = c

    def test_the_steps_come_out_in_order(self):
        text = """
        - run: python scripts/a.py
        - run: python scripts/b.py
        """
        self.assertEqual(self.c.schritte(text), ["a.py", "b.py"])

    def test_a_repeated_call_keeps_its_first_position(self):
        """`xbrl_csv_parser.py` steht in drei Zweigen. Für die Reihenfolge
        zählt, wann ein Artefakt FRÜHESTENS entsteht — die spätere Nennung
        dürfte einen Leser sonst scheinbar rechtfertigen."""
        text = "python scripts/a.py\npython scripts/b.py\npython scripts/a.py"
        self.assertEqual(self.c.schritte(text), ["a.py", "b.py"])


class VerletzungTest(unittest.TestCase):
    def setUp(self):
        import check_pipeline_order as c
        self.c = c

    def test_reading_before_writing_is_a_violation(self):
        ab = {"leser.py": (["x.csv"], []), "schreiber.py": ([], ["x.csv"])}
        v = self.c.verletzungen(["leser.py", "schreiber.py"], ab)
        self.assertEqual(v, [("leser.py", "x.csv", "schreiber.py")])

    def test_the_correct_order_passes(self):
        ab = {"leser.py": (["x.csv"], []), "schreiber.py": ([], ["x.csv"])}
        self.assertEqual(self.c.verletzungen(["schreiber.py", "leser.py"], ab), [])

    def test_a_script_reading_its_own_output_is_not_a_violation(self):
        ab = {"a.py": (["x.csv"], ["x.csv"])}
        self.assertEqual(self.c.verletzungen(["a.py"], ab), [])

    def test_an_artefact_from_outside_the_chain_is_not_a_violation(self):
        """`country_gdp.csv` wird ausserhalb der Pipeline gepflegt. Ohne diese
        Regel schlüge der Guard bei jedem externen Artefakt an und wäre nach
        drei Tagen abgeschaltet."""
        ab = {"leser.py": (["extern.csv"], [])}
        self.assertEqual(self.c.verletzungen(["leser.py"], ab), [])

    def test_a_script_outside_the_workflow_cannot_violate(self):
        ab = {"leser.py": (["x.csv"], []), "schreiber.py": ([], ["x.csv"])}
        self.assertEqual(self.c.verletzungen(["schreiber.py"], ab), [])


class DeklarationTest(unittest.TestCase):
    """Die Gegenprobe zur Tabelle: eine Deklaration, die niemand nachhält,
    ist schlimmer als keine."""

    def setUp(self):
        import check_pipeline_order as c
        self.c = c

    def test_a_declared_path_must_appear_in_the_source(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.py").write_text("PFAD = 'processed/echt.csv'\n")
            ab = {"a.py": ([], ["processed/echt.csv"])}
            self.assertEqual(self.c.pruefe_deklaration(ab, d), [])
            ab = {"a.py": ([], ["processed/erfunden.csv"])}
            self.assertEqual(len(self.c.pruefe_deklaration(ab, d)), 1)

    def test_a_missing_script_is_reported(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            ab = {"gibt-es-nicht.py": ([], [])}
            self.assertEqual(len(self.c.pruefe_deklaration(ab, d)), 1)

    def test_the_real_declaration_matches_the_real_sources(self):
        """Am echten Repo. Bricht das, ist die Tabelle veraltet — und ein
        Guard mit veralteter Tabelle prüft die falsche Kette."""
        falsch = self.c.pruefe_deklaration()
        self.assertEqual(falsch, [])


class EchteKetteTest(unittest.TestCase):
    def setUp(self):
        import check_pipeline_order as c
        self.c = c
        if not WORKFLOW.exists():
            self.skipTest("pipeline.yml fehlt")
        self.reihenfolge = c.schritte()

    def test_the_real_pipeline_is_a_valid_topology(self):
        """Das Ergebnis. Jede Verletzung hier ist ein stiller Ausfall im
        unbeaufsichtigten Betrieb — der Schritt läuft durch und liefert
        weniger, als er soll."""
        v = self.c.verletzungen(self.reihenfolge)
        self.assertEqual(v, [], "Reihenfolgenverletzung in pipeline.yml: " + "; ".join(
            f"{a} liest {b} von {c} (läuft später)" for a, b, c in v))

    def test_the_guard_actually_has_edges_to_check(self):
        """Gegenprobe gegen einen Guard, der nichts prüft: fände er keine
        Abhängigkeit zwischen zwei Pipeline-Schritten, wäre „keine Verletzung"
        bedeutungslos."""
        pos = set(self.reihenfolge)
        erzeugt = {d for s, (_, w) in self.c.ABHAENGIG.items() if s in pos for d in w}
        kanten = [(s, d) for s, (r, _) in self.c.ABHAENGIG.items() if s in pos
                  for d in r if d in erzeugt]
        self.assertGreater(len(kanten), 15)

    def test_the_two_known_traps_are_covered(self):
        """Die drei Reihenfolgen, die schon einmal falsch waren, müssen als
        Kante in der Tabelle stehen — sonst schützt der Guard ausgerechnet
        dort nicht, wo es bereits schiefging."""
        for leser, datei in (("build_footprint.py", "processed/scale_flags.csv"),
                             ("build_omission_profile.py",
                              "processed/disclosure_frequency.csv"),
                             ("check_plausibility.py",
                              "processed/disclosure_frequency.csv"),
                             ("build_zweig_a_shards.py",
                              "processed/peer_similarity.csv")):
            with self.subTest(leser=leser, datei=datei):
                self.assertIn(datei, self.c.ABHAENGIG[leser][0])

    def test_no_declared_script_is_missing_from_the_workflow(self):
        """Eine Zeile in ABHAENGIG für ein Skript, das die Pipeline gar nicht
        aufruft, ist tote Deklaration — sie sieht wie Absicherung aus und
        sichert nichts."""
        fremd = [s for s in self.c.ABHAENGIG if s not in set(self.reihenfolge)]
        self.assertEqual(fremd, [])

    def test_every_producing_pipeline_script_is_declared(self):
        """Wer in der Kette ein Artefakt ERZEUGT, muss deklariert sein — sonst
        kennt der Guard den Erzeuger nicht und hält jede Lesung für harmlos.

        Gemessen wird am Modul, nicht am Quelltext: geprüft werden
        Ausgabe-Konstanten (`OUT…`), die auf `processed/` oder `interim/`
        zeigen. Eine Textsuche kann Lesen nicht von Schreiben unterscheiden und
        hielte `build_dataset_manifest.py` für einen Erzeuger des Parquets, das
        es nur zählt."""
        import importlib
        fehlend = []
        for skript in self.reihenfolge:
            name = skript[:-3]
            if skript in self.c.ABHAENGIG or not (ROOT / "scripts" / skript).exists():
                continue
            try:
                mod = importlib.import_module(name)
            except Exception:                       # noqa: BLE001
                continue                            # nicht importierbar: kein Urteil
            for attr in dir(mod):
                if not attr.startswith("OUT"):
                    continue
                wert = getattr(mod, attr)
                if isinstance(wert, Path) and any(
                        t in wert.as_posix() for t in ("/processed/", "/interim/")):
                    fehlend.append((skript, attr, wert.name))
                    break
        self.assertEqual(fehlend, [],
                         "erzeugende Pipeline-Skripte ohne Eintrag in ABHAENGIG")


if __name__ == "__main__":
    unittest.main(verbosity=2)
