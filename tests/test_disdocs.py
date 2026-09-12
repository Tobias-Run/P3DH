"""DISDOCS-Korpus erschliessen (#38).

## Die Reihenfolge ist der Inhalt des Issues

„**Ehrlicher Extraktionstest zuerst**: Textausbeute je PDF messen, bevor
irgendeine Auswertung gebaut wird. Gescannte Berichte ohne Textebene liefern
nichts."

Eine Auswertung vor dieser Messung waere eine Auswertung ueber die Teilmenge,
die zufaellig maschinenlesbar ist — mit einer Verzerrung, die niemand beziffern
koennte. Deshalb pruefen diese Tests auch, dass hier NOCH KEINE inhaltliche
Auswertung steht.

## Die Sprachfalle

31 Laender, entsprechend viele Sprachen. Eine Stichwortsuche auf Deutsch oder
Englisch traefe systematisch die Institute, die auf Englisch berichten. Deshalb
wird die Sprache nicht geraten: was das PDF selbst im Feld /Lang angibt, wird
uebernommen, der Rest bleibt leer und damit sichtbar unbekannt.
"""

from pathlib import Path
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

MANIFEST = ROOT / "interim" / "disdocs_manifest.csv"
VOLL = ROOT / "interim" / "edap_recon" / "manifest_full.csv"
PROBE = ROOT / "interim" / "disdocs_probe.csv"


class ManifestTest(unittest.TestCase):
    def setUp(self):
        if not MANIFEST.exists():
            self.skipTest("disdocs_manifest.csv nicht gebaut")
        with MANIFEST.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))

    def test_it_holds_exactly_what_the_parser_throws_away(self):
        """Die Auswahlregel muss dieselbe sein wie in
        `build_parse_manifest.py` — sonst beschreibt das Manifest einen
        anderen Korpus als den ausgeschlossenen."""
        with VOLL.open(encoding="utf-8") as fh:
            alle = list(csv.DictReader(fh))
        soll = [r for r in alle if "DISDOCS" in r["url"]]
        self.assertEqual(len(self.rows), len(soll))
        self.assertEqual({r["url"] for r in self.rows}, {r["url"] for r in soll})

    def test_not_a_single_xbrl_package_slipped_in(self):
        """Ein XBRL-Paket hier waere doppelt verarbeitet — einmal als Zahl,
        einmal als vermeintlicher Text."""
        for r in self.rows:
            with self.subTest(url=r["url"][-60:]):
                self.assertIn("DISDOCS", r["url"])

    def test_the_link_to_the_numbers_is_marked(self):
        """Der ganze Zweck ist, Text gegen Zahl zu halten. Ein Bericht eines
        Instituts OHNE XBRL-Meldung laesst sich gegen nichts halten — das muss
        an der Zeile stehen, nicht erst beim Auswerten auffallen."""
        with VOLL.open(encoding="utf-8") as fh:
            alle = list(csv.DictReader(fh))
        mit_xbrl = {r["lei"] for r in alle if "DISDOCS" not in r["url"]}
        ohne = [r for r in self.rows if r["im_xbrl_bestand"] == "false"]
        for r in self.rows:
            with self.subTest(lei=r["lei"]):
                self.assertEqual(r["im_xbrl_bestand"],
                                 "true" if r["lei"] in mit_xbrl else "false")
        self.assertGreater(len(ohne), 0,
                           "kein einziges Institut ohne XBRL — Zuordnung pruefen")

    def test_the_order_is_stable(self):
        k = [(r["lei"], r["refdate"], r["submission_ts"]) for r in self.rows]
        self.assertEqual(k, sorted(k))

    def test_it_covers_many_countries(self):
        """Die Sprachfrage haengt daran: waere der Korpus einsprachig, gaebe
        es die Verzerrung nicht, vor der das Issue warnt."""
        self.assertGreater(len({r["country"] for r in self.rows}), 20)


class ProbeLogikTest(unittest.TestCase):
    def setUp(self):
        import probe_disdocs as p
        self.p = p
        self.src = (ROOT / "scripts" / "probe_disdocs.py").read_text(encoding="utf-8")

    def test_the_language_is_never_guessed(self):
        """Eine Stichwortheuristik ueber 31 Sprachen traefe systematisch die
        englisch berichtenden Institute. Was das PDF angibt, wird uebernommen;
        sonst bleibt das Feld leer."""
        self.assertIn('"/Lang"', self.src)
        for verraeter in ("langdetect", "guess_language", "STOPWORDS", "def rate_sprache"):
            self.assertNotIn(verraeter, self.src,
                             f"Sprache wird geraten ({verraeter})")

    def test_an_empty_package_is_a_finding_not_a_crash(self):
        """Ein Paket ohne PDF heisst: der Korpus traegt dort nichts
        Auswertbares. Das gehoert in die Ausgabe, nicht in einen Abbruch."""
        self.assertIn("kein PDF im Paket", self.src)
        self.assertEqual(self.p._pdfs(b"kein zip"), [])

    def test_the_text_threshold_is_per_page_not_absolute(self):
        """Ein 300-seitiger Scan hat viele Zeichen aus Kopfzeilen und ist
        trotzdem ohne Textebene. Die Dichte entscheidet, nicht die Summe."""
        self.assertGreaterEqual(self.p.MIN_ZEICHEN_JE_SEITE, 100)
        self.assertIn("zeichen_pro_seite", self.p.FELDER)

    def test_nothing_is_downloaded_by_the_manifest_step(self):
        """Das Manifest ist billig und vollstaendig, der Abruf teuer und
        stichprobenhaft. Beides in einem Skript hiesse, 4,3 GB zu ziehen, um
        eine Liste zu bekommen."""
        m = (ROOT / "scripts" / "build_disdocs_manifest.py").read_text(encoding="utf-8")
        for netz in ("urlopen", "requests", "curl"):
            self.assertNotIn(netz, m, f"das Manifest-Skript geht ins Netz ({netz})")

    def test_no_content_analysis_is_built_yet(self):
        """Das Issue verlangt die Reihenfolge ausdruecklich. Eine Auswertung
        vor dem Extraktionstest liefe ueber die zufaellig maschinenlesbare
        Teilmenge — mit unbezifferbarer Verzerrung."""
        for begriff in ("solide Kreditqualität", "sentiment", "NPL-Quote",
                        "schlagwort", "keyword"):
            self.assertNotIn(begriff.lower(), self.src.lower(),
                             f"inhaltliche Auswertung vor dem Extraktionstest ({begriff})")


class ProbeErgebnisTest(unittest.TestCase):
    def setUp(self):
        if not PROBE.exists():
            self.skipTest("disdocs_probe.csv nicht erzeugt")
        with PROBE.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))
        if not self.rows:
            self.skipTest("Probe leer")

    def test_every_row_says_what_happened(self):
        """Eine Zeile ohne Status waere ein stiller Ausfall — und ein Paket,
        das nicht geladen werden konnte, saehe aus wie eines ohne Text."""
        for r in self.rows:
            with self.subTest(lei=r["lei"]):
                self.assertTrue(r["status"], "Zeile ohne Status")

    def test_the_density_matches_its_parts(self):
        for r in self.rows:
            if r["status"] != "ok" or not int(r["seiten"]):
                continue
            with self.subTest(lei=r["lei"], datei=r["datei"]):
                self.assertEqual(int(r["zeichen_pro_seite"]),
                                 round(int(r["zeichen"]) / int(r["seiten"])))

    def test_the_sample_actually_reached_the_source(self):
        """Waeren alle Zeilen Fehler, saehe der Bericht aus wie ein Befund
        ueber den Korpus — er waere aber einer ueber unsere Verbindung."""
        ok = [r for r in self.rows if r["status"] == "ok"]
        self.assertGreater(len(ok), 0.3 * len(self.rows),
                           "ueberwiegend Abrufe fehlgeschlagen — kein Korpusbefund")


if __name__ == "__main__":
    unittest.main(verbosity=2)
