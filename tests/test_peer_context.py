"""Peer-Median und Perzentil an der Zelle (#23).

## Warum das der Unterschied zwischen Zahl und Aussage ist

Ein originalgetreuer Renderer zeigt „12,4 %". Ein interpretierender Viewer
zeigt „12,4 %" UND dass der Peer-Median 15,1 % ist. Fuer Nicht-Spezialisten ist
das der ganze Unterschied — und es ist die Abgrenzung zu EDAP: die Einordnung
braucht die Population als Massstab plus ein Urteil darueber, wer vergleichbar
ist.

## Was ausdruecklich KEINE Kontextzahl bekommt

Das Issue nennt die Abgrenzung selbst: „Sonst wird aus dem Feature eine
Fehlerquelle."

    UNIT_AMBIGUOUS_TEMPLATES (#9)   207.983 Fakten — wo die gemeldete Einheit
                                    strittig ist, mischt der Median Tausender
                                    und Einer
    mehrfach belegte Zellen (#52)    64.357 Zellen (3,8 %) — welcher von
                                    mehreren Fakten auf derselben Koordinate
                                    gegen den Median gehoert, ist nicht
                                    entscheidbar
    Peer-Gruppe unter 5 Reports      wie im Benchmark: darunter ist ein
                                    Perzentil Rauschen, nicht Signal

Fehlt die Kontextzahl, steht dort NICHTS — kein Platzhalter, der nach Null
aussieht.
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


class RundungTest(unittest.TestCase):
    def setUp(self):
        import build_zweig_a_shards as b
        self.b = b

    def test_the_median_is_rounded_because_it_is_a_display_value(self):
        """Volle Float-Stellen kosten 23 % Shard-Groesse und tragen nichts,
        was im Tooltip sichtbar waere."""
        self.assertEqual(self.b._sig(779425123.45), 779400000)
        self.assertEqual(self.b._sig(0.0123456), 0.01235)
        self.assertEqual(self.b._sig(-1234.5678), -1235.0)

    def test_zero_and_nonsense_survive_the_rounding(self):
        """log10(0) waere ein Absturz mitten im Shard-Bau."""
        self.assertEqual(self.b._sig(0), 0)
        self.assertEqual(self.b._sig(float("inf")), 0)
        self.assertEqual(self.b._sig(float("nan")), 0)

    def test_the_threshold_matches_the_benchmark(self):
        """Zwei Peer-Begriffe im selben Produkt waeren der sichere Weg zu zwei
        Antworten auf dieselbe Frage."""
        self.assertEqual(self.b.PEER_MIN, 5)
        src = VIEWER.read_text(encoding="utf-8")
        m = re.search(r"const PCT_MIN_GROUP=(\d+)", src)
        self.assertTrue(m, "PCT_MIN_GROUP im Viewer nicht gefunden")
        self.assertEqual(int(m.group(1)), self.b.PEER_MIN)


class ShardTest(unittest.TestCase):
    def setUp(self):
        if not SHARDS.exists() or not any(SHARDS.glob("*.json")):
            self.skipTest("Shards nicht gebaut")
        self.shards = sorted(SHARDS.glob("*.json"))

    def test_the_context_actually_reaches_the_shards(self):
        mit = [p for p in self.shards
               if "peer" in json.loads(p.read_text(encoding="utf-8"))]
        self.assertGreater(len(mit), 500,
                           "kaum Shards mit Peer-Kontext — Gruppierung pruefen")

    def test_no_context_for_templates_with_a_disputed_unit(self):
        """Der Median ueber eine Gruppe, die Tausender und Einer mischt, waere
        eine Scheinaussage — und wuerde ausgerechnet dort auftreten, wo der
        Leser sie fuer eine Einordnung haelt."""
        from check_unit_consistency import UNIT_AMBIGUOUS_TEMPLATES
        for p in self.shards:
            o = json.loads(p.read_text(encoding="utf-8"))
            for tid in o.get("peer", {}):
                with self.subTest(shard=p.name, tid=tid):
                    self.assertNotIn(tid, UNIT_AMBIGUOUS_TEMPLATES)

    def test_the_entry_shape_is_what_the_viewer_expects(self):
        gesehen = 0
        for p in self.shards:
            o = json.loads(p.read_text(encoding="utf-8"))
            for tid, zellen in o.get("peer", {}).items():
                for rc, e in zellen.items():
                    gesehen += 1
                    with self.subTest(shard=p.name, tid=tid, rc=rc):
                        self.assertEqual(len(e), 3)
                        self.assertTrue(0 <= e[0] <= 100, f"Perzentil {e[0]}")
                        self.assertGreaterEqual(e[2], 5, "Gruppe unter der Schwelle")
        self.assertGreater(gesehen, 10000)

    def test_every_context_number_sits_on_a_cell_that_exists(self):
        """Sonst staende eine Einordnung unter einer leeren Zelle."""
        verwaist = 0
        for p in self.shards:
            o = json.loads(p.read_text(encoding="utf-8"))
            for tid, zellen in o.get("peer", {}).items():
                da = {f"{c[0]}|{c[1]}" for c in o["tpl"].get(tid, [])}
                verwaist += sum(1 for rc in zellen if rc not in da)
        self.assertEqual(verwaist, 0, f"{verwaist} Kontextzahlen ohne Wert")

    def test_multiply_occupied_coordinates_are_left_out(self):
        """#52: dort liegen je Report mehrere Fakten auf derselben Koordinate.
        Ein Shard schreibt sie mit Diskriminator als vierten Eintrag — genau
        diese Koordinaten duerfen keine Kontextzahl tragen."""
        geprueft = 0
        for p in self.shards:
            o = json.loads(p.read_text(encoding="utf-8"))
            peer = o.get("peer", {})
            if not peer:
                continue
            for tid, cells in o["tpl"].items():
                mehrfach = {f"{c[0]}|{c[1]}" for c in cells if len(c) > 3}
                for rc in mehrfach:
                    geprueft += 1
                    with self.subTest(shard=p.name, tid=tid, rc=rc):
                        self.assertNotIn(rc, peer.get(tid, {}))
        self.assertGreater(geprueft, 100, "keine mehrfach belegten Zellen geprueft")


class ViewerTest(unittest.TestCase):
    def setUp(self):
        self.src = VIEWER.read_text(encoding="utf-8")

    def test_a_missing_peer_group_shows_nothing_at_all(self):
        """Kein Platzhalter, der nach Null aussieht — dieselbe Regel wie bei
        den leeren Zellen: ueber die einzelne Zelle wissen wir nichts und
        behaupten deshalb nichts."""
        m = re.search(r"const ctx\s*=\s*\(CTX&&pc\)\s*\?", self.src)
        self.assertTrue(m, "Sekundaerzeile haengt nicht an einer vorhandenen Peer-Gruppe")
        rest = self.src[m.end():]
        zweig = rest[:rest.index(";")]
        self.assertTrue(zweig.rstrip().endswith("''"),
                        "ohne Peer-Gruppe wird etwas anderes als nichts gezeigt")

    def test_the_value_itself_is_unchanged_by_the_context(self):
        """Die Einordnung tritt neben den Wert, nicht davor."""
        zelle = self.src[self.src.index("const pc=peerAt("):]
        zelle = zelle[:zelle.index("h+='</tr>'")]
        self.assertIn("fmtTyped(v,dt,unit", zelle)
        self.assertNotIn("if(pc) v=", zelle)

    def test_the_tooltip_names_the_group_size(self):
        """Ohne n weiss der Leser nicht, gegen wie viele Institute verglichen
        wird — ein Perzentil aus 5 Reports ist etwas anderes als eines aus 80."""
        tip = self.src[self.src.index("function peerTip("):]
        tip = tip[:tip.index("\nlet OPENTHEMES")]
        self.assertIn("vergleichbaren Reports", tip)
        self.assertIn("Perzentil", tip)

    def test_the_context_can_be_switched_off(self):
        """Wer den reinen Meldewert sehen will, muss das koennen."""
        self.assertIn('id="ctxChk"', self.src)
        self.assertIn("store.ctx", self.src)

    def test_the_javascript_still_parses(self):
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


class VerteilungsformTest(unittest.TestCase):
    """Die Form der Peer-Verteilung (#49, R4).

    Das Perzentil sagt, WO ein Institut steht, nicht WORIN. „P47" heisst in
    einer eng gepackten Gruppe etwas anderes als in einer, die über zwei
    Größenordnungen streut — an der Zahl ist das nicht zu sehen.

    Ausgeliefert wird die Form je GRUPPE, nicht je Zelle: 60.083 statt
    1.407.650 Einträge, Faktor 23. Je Zelle wären es rund 39 MB für eine
    Randnotiz, die man einzeln anschaut.
    """

    def setUp(self):
        import build_zweig_a_shards as b
        self.b = b

    def test_the_quantile_interpolates_like_the_viewer(self):
        """Dieselbe Formel wie `quart()` im Viewer. Zwei Quartilsdefinitionen
        zeigten die Verteilungskarte über der Liste (#48) und den Streifen in
        der Zeile (#49) nebeneinander verschieden — am selben Bildschirm."""
        arr = [1, 2, 3, 4]
        self.assertAlmostEqual(self.b.quantil(arr, 0.5), 2.5)
        self.assertAlmostEqual(self.b.quantil(arr, 0.25), 1.75)
        self.assertAlmostEqual(self.b.quantil(arr, 0.0), 1)
        self.assertAlmostEqual(self.b.quantil(arr, 1.0), 4)

    def test_an_empty_group_has_no_quantile(self):
        self.assertEqual(self.b.quantil([], 0.5), 0)

    def test_the_shape_file_exists_and_is_shaped_right(self):
        """Am gebauten Artefakt: fünf Zahlen je Gruppe, aufsteigend."""
        import json
        pfad = ROOT / "processed" / "zweig_a" / "data" / "peer_shape.json"
        if not pfad.exists():
            self.skipTest("peer_shape.json nicht gebaut")
        formen = json.loads(pfad.read_text(encoding="utf-8"))
        self.assertGreater(len(formen), 10000)
        for schluessel, werte in list(formen.items())[:500]:
            with self.subTest(gruppe=schluessel):
                self.assertEqual(len(werte), 5)
                self.assertEqual(werte, sorted(werte),
                                 "Quantile müssen aufsteigend sein")
                self.assertEqual(len(schluessel.split("|")), 6)

    def test_the_shape_is_per_group_not_per_cell(self):
        """Die Entscheidung, die den Unterschied zwischen 1,7 MB und 39 MB
        macht. Gäbe es so viele Formen wie Peer-Zellen, wäre sie
        zurückgedreht."""
        import json
        pfad = ROOT / "processed" / "zweig_a" / "data" / "peer_shape.json"
        if not pfad.exists():
            self.skipTest("peer_shape.json nicht gebaut")
        formen = json.loads(pfad.read_text(encoding="utf-8"))
        zellen = 0
        for f in sorted((ROOT / "processed" / "zweig_a" / "data" / "reports").glob("*.json"))[:60]:
            peer = json.loads(f.read_text(encoding="utf-8")).get("peer", {})
            zellen += sum(len(v) for v in peer.values())
        self.assertGreater(zellen, 0, "keine Peer-Zellen — Test prüft nichts")
        # 60 von 882 Shards tragen schon mehr Zellen als es Gruppen gibt.
        self.assertLess(len(formen), zellen * 3,
                        "die Formen skalieren mit den Zellen statt mit den Gruppen")

    def test_a_degenerate_group_yields_no_strip(self):
        """Wo p10 == p90 ist, gibt es keine Spur — und ein Streifen über eine
        Gruppe ohne Streuung wäre eine Behauptung über Unterschiede, die es
        nicht gibt. Der Viewer liefert dort einen leeren String."""
        src = (ROOT / "processed" / "zweig_a" / "viewer_json.html").read_text(
            encoding="utf-8")
        self.assertIn("if(!(spanne>0)) return ''", src)

    def test_the_strip_carries_no_colour_judgement(self):
        """#49: „Nie Rot/Grün als Wertung." Die Position trägt das Signal."""
        src = (ROOT / "processed" / "zweig_a" / "viewer_json.html").read_text(
            encoding="utf-8")
        block = src[src.index("function shapeStrip("):]
        block = block[:block.index("\n}")]
        for verboten in ("red", "green", "rot", "gruen", "#0f0", "#f00"):
            self.assertNotIn(verboten, block.lower())
