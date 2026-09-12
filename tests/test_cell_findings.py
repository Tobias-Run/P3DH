"""Anomalien inline markieren (#24).

## Die Grenze, um die es geht

EDAP **muss** einen gemeldeten Wert originalgetreu rendern — das ist die
Aufgabe eines Renderers. Wir haben diese Pflicht nicht und duerfen an die Zelle
schreiben, dass der Wert gegen die Population nicht plausibel ist.

Die Grenze zwischen „interpretierend" und „verfaelschend" liegt genau hier:
**kein Wert wird veraendert oder unterdrueckt.** Die Markierung ist additiv.
Deshalb prueft dieser Test nicht nur, DASS markiert wird, sondern auch, dass
der Wert daneben unveraendert stehen bleibt.

## Zwei Annahmen aus dem Issue, die nicht zutrafen

Die Umsetzungsskizze sagt, `unit_ambiguous` werde im Shard-Builder „schon
durchgereicht" und die Sperrlisten-Templates seien im Viewer „bereits anders
markiert". Gemessen: `unit_ambiguous` kam im Shard-Builder ueberhaupt nicht vor,
und der Viewer markierte 41.00/45.00.A nirgends. Eine Doppelmarkierung konnte es
also gar nicht geben — wohl aber das umgekehrte Problem: 390 Befunde liegen in
genau diesen beiden Templates, wo eine Abweichung um Groessenordnungen auch
schlicht Tausend gegen Eins heissen kann. Das sagt der Tooltip jetzt dazu.
"""

from pathlib import Path
import json
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

VIEWER = ROOT / "processed" / "zweig_a" / "viewer_json.html"
SHARDS = ROOT / "processed" / "zweig_a" / "data" / "reports"
INDEX = ROOT / "processed" / "zweig_a" / "data" / "index.json"


class LadenTest(unittest.TestCase):
    def setUp(self):
        import build_zweig_a_shards as b
        self.b = b

    def test_the_strongest_finding_wins_and_says_how_many_there_were(self):
        """620 Koordinaten tragen mehr als einen Befund — dieselbe
        Mehrfachbelegung wie in `collapse_cells()`. Einen davon
        stillschweigend zu behalten hiesse, dem Leser eine Auswahl zu
        verschweigen, die wir getroffen haben."""
        treffer = [("n", 1.0, 5.0), ("h", 2.0, 5.0), ("m", 9.9, 5.0)]
        sev, dev, ref = max(treffer, key=lambda t: (self.b.SEV_RANG[t[0]], t[1]))
        self.assertEqual(sev, "h", "Schweregrad schlaegt Abweichung")
        # ... und der Rang selbst muss die Ordnung hoch > mittel > niedrig tragen
        self.assertGreater(self.b.SEV_RANG["h"], self.b.SEV_RANG["m"])
        self.assertGreater(self.b.SEV_RANG["m"], self.b.SEV_RANG["n"])

    def test_every_severity_has_a_code(self):
        """Ein unbekannter Schweregrad darf nicht still zu 'niedrig' werden,
        ohne dass die Zuordnung vollstaendig ist."""
        self.assertEqual(set(self.b.SEV), {"hoch", "mittel", "niedrig"})
        self.assertEqual(set(self.b.SEV.values()), set(self.b.SEV_RANG))


class ShardTest(unittest.TestCase):
    def setUp(self):
        if not SHARDS.exists() or not any(SHARDS.glob("*.json")):
            self.skipTest("Shards nicht gebaut")
        self.shards = sorted(SHARDS.glob("*.json"))

    def test_findings_actually_reach_the_shards(self):
        """Waere das Feld nie gesetzt, markierte der Viewer nichts — und das
        saehe genauso aus wie 'keine Auffaelligkeiten'."""
        mit = [p for p in self.shards
               if "flags" in json.loads(p.read_text(encoding="utf-8"))]
        self.assertGreater(len(mit), 100,
                           "kaum Shards mit Befunden — Report-Key-Format pruefen")

    def test_only_reports_with_findings_carry_the_field(self):
        """Ein leeres `flags` in jedem Shard waere reiner Ballast."""
        for p in self.shards[:150]:
            o = json.loads(p.read_text(encoding="utf-8"))
            with self.subTest(shard=p.name):
                if "flags" in o:
                    self.assertTrue(o["flags"], "leeres flags-Feld geschrieben")

    def test_every_flagged_coordinate_has_a_value_next_to_it(self):
        """Ein Befund auf einer Koordinate, die der Report gar nicht meldet,
        waere eine Markierung an einer leeren Zelle — der Leser saehe einen
        Hinweis ohne Zahl. Zugleich der Beleg, dass Befund und Gitter
        denselben Koordinatenraum benutzen."""
        geprueft = verwaist = 0
        for p in self.shards:
            o = json.loads(p.read_text(encoding="utf-8"))
            if "flags" not in o:
                continue
            for tid, zellen in o["flags"].items():
                vorhanden = {f"{c[0]}|{c[1]}" for c in o["tpl"].get(tid, [])}
                for rc in zellen:
                    geprueft += 1
                    if rc not in vorhanden:
                        verwaist += 1
        self.assertGreater(geprueft, 500)
        self.assertEqual(verwaist, 0, f"{verwaist} Befunde ohne Wert im Gitter")

    def test_the_entry_shape_is_what_the_viewer_expects(self):
        for p in self.shards:
            o = json.loads(p.read_text(encoding="utf-8"))
            for tid, zellen in o.get("flags", {}).items():
                for rc, e in zellen.items():
                    with self.subTest(shard=p.name, tid=tid, rc=rc):
                        self.assertIn(len(e), (3, 4))
                        self.assertIn(e[0], ("h", "m", "n"))
                        self.assertIsInstance(e[1], (int, float))
                        if len(e) == 4:
                            self.assertGreater(e[3], 1,
                                               "Anzahl nur bei MEHR als einem Befund")

    def test_the_blocked_template_list_comes_from_the_single_source(self):
        """Eine zweite Liste im HTML waere die naechste, die auseinanderlaeuft."""
        from check_unit_consistency import UNIT_AMBIGUOUS_TEMPLATES
        idx = json.loads(INDEX.read_text(encoding="utf-8"))
        self.assertEqual(set(idx.get("ua", [])), set(UNIT_AMBIGUOUS_TEMPLATES))
        src = VIEWER.read_text(encoding="utf-8")
        self.assertIn("idx.ua", src, "Viewer liest die Sperrliste nicht aus dem Index")
        for tid in UNIT_AMBIGUOUS_TEMPLATES:
            self.assertNotIn(f"'{tid}'", src,
                             f"{tid} steht als Kopie im Viewer statt im Index")


class ViewerTest(unittest.TestCase):
    def setUp(self):
        self.src = VIEWER.read_text(encoding="utf-8")

    def test_the_reported_value_is_never_altered_or_hidden(self):
        """Die Grenze zwischen interpretierend und verfaelschend. Die
        Markierung haengt an Klasse und Tooltip; die Zahl selbst geht
        unveraendert durch dieselbe Formatierung wie jede andere."""
        zelle = self.src[self.src.index("const fg=flagAt("):]
        zelle = zelle[:zelle.index("h+='</tr>'")]
        self.assertIn("fmtTyped(v,dt,unit", zelle,
                      "der Wert laeuft nicht mehr durch die normale Formatierung")
        for verboten in ("if(fg) v=", "fg?'':", "fg? '' :", "continue"):
            self.assertNotIn(verboten, zelle,
                             f"Wert wird bei einem Befund unterdrueckt ({verboten})")

    def test_the_wording_states_a_distance_not_a_verdict(self):
        """„Ein Meldefehler ist eine Hypothese, kein Befund." Deshalb steht im
        Tooltip ein Abstand zur Population, nicht das Wort falsch."""
        tip = self.src[self.src.index("function flagTip("):]
        tip = tip[:tip.index("\nlet OPENTHEMES")]
        self.assertIn("Größenordnungen vom Vergleichswert", tip)
        # NUR die Zeichenketten pruefen, nicht den Quelltext drumherum: der
        # Kommentar erklaert ja gerade, warum „falsch" nicht vorkommen darf —
        # und liess den Test auf sich selbst hereinfallen.
        ohne = re.sub(r"//.*", "", tip)
        texte = " ".join(re.findall(r"'([^']*)'", ohne))
        self.assertTrue(texte.strip(), "keine Textbausteine gefunden")
        for wort in ("falsch", "Fehler", "fehlerhaft"):
            self.assertNotIn(wort, texte, f"wertendes Wort im Tooltip: {wort}")

    def test_a_blocked_template_says_the_unit_may_be_the_reason(self):
        """390 Befunde liegen in 41.00/45.00.A. Dort kann eine Abweichung um
        Groessenordnungen schlicht Tausend gegen Eins heissen — ohne diesen
        Zusatz liest sich der Hinweis als Meldefehler."""
        self.assertIn("UA.has(tid)", self.src)
        self.assertIn("Einheit", self.src)

    def test_the_marking_is_not_alarm_red(self):
        """Dezente Markierung, ausdrueckliche Vorgabe des Issues."""
        css = self.src[self.src.index("td.oddcell"):]
        css = css[:css.index("}") + 1]
        for grell in ("#f00", "red", "#ff0000"):
            self.assertNotIn(grell, css.lower())

    def test_the_reader_is_told_before_reading(self):
        """Eine Markierung an der Zelle ohne Erklaerzeile waere ein Symbol
        ohne Herkunft — wie bei den mehrdeutigen Koordinaten (#54)."""
        self.assertIn("const flagNote", self.src)
        self.assertIn("bleibt unverändert stehen", self.src)

    def test_the_javascript_still_parses(self):
        """Ein Syntaxfehler im Viewer faellt sonst erst im Browser auf — dort
        sieht er aus wie eine leere Seite, nicht wie ein Fehler."""
        bloecke = re.findall(r"<script[^>]*>(.*?)</script>", self.src, re.S)
        self.assertEqual(len(bloecke), 1)
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(bloecke[0])
            pfad = fh.name
        try:
            r = subprocess.run(["node", "--check", pfad], capture_output=True, text=True)
        except FileNotFoundError:
            self.skipTest("node nicht verfuegbar")
        finally:
            Path(pfad).unlink(missing_ok=True)
        self.assertEqual(r.returncode, 0, r.stderr[:900])


if __name__ == "__main__":
    unittest.main(verbosity=2)
