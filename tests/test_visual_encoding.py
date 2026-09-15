"""Visuelle Kodierung in der Benchmark-Tabelle (#49).

Ein Balken ist eine Behauptung über Vergleichbarkeit. Er sagt „dieser Wert
verhält sich zu jenem wie diese Länge zu jener" — und genau das gilt in zwei
Fällen nicht:

    strittige Einheit (#9)   `41.00` und `45.00.A`: Institute melden dort
                             nachweislich in verschiedenen Einheiten.
    Skalenbefund (#83)       ein Report, dessen Beträge um 10^6 zu klein sind,
                             bekäme einen Balken nahe null — und sähe damit aus
                             wie ein winziges Institut statt wie ein Meldefehler.

Diese Datei prüft den Quelltext auf die Vorsätze. Dass die Balken WIRKLICH
erscheinen und in beiden Fällen wegbleiben, prüft `check_viewer_runtime.py` im
echten Browser — Quelltextprüfungen allein haben in diesem Projekt schon zwei
Funktionen durchgewinkt, die nichts taten.
"""

from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

VIEWER = ROOT / "processed" / "zweig_a" / "viewer_json.html"


class KodierungTest(unittest.TestCase):
    def setUp(self):
        self.src = VIEWER.read_text(encoding="utf-8")

    def test_bars_only_on_size_columns(self):
        """Für eine Quote wäre ein Balken gegen das Spaltenmaximum sinnlos:
        15 % CET1 sind nicht „ein Drittel von 45 %", sondern ein eigener Wert.
        Dort steht die Perzentilmarke, nicht der Balken."""
        m = re.search(r"const BAR_KINDS = new Set\(\[([^\]]+)\]\)", self.src)
        self.assertIsNotNone(m, "BAR_KINDS fehlt")
        arten = set(re.findall(r"'([^']+)'", m.group(1)))
        self.assertEqual(arten, {"eur", "eurPlain", "num"})
        for quote in ("pct", "ratio", "shareOfTrea", "pp"):
            self.assertNotIn(quote, arten, f"{quote} ist eine Quote, kein Betrag")

    def test_the_bar_is_linear_not_logarithmic(self):
        """Ein Logbalken machte aus Faktor 50 optisch Faktor 2 und schmeichelte
        den kleinen Häusern. Dass die meisten Balken kurz sind, IST das
        Ergebnis."""
        rumpf = self.src[self.src.index("function sizeBar("):]
        rumpf = rumpf[:rumpf.index("\nfunction ")]
        self.assertIn("v/max*100", rumpf)
        self.assertNotIn("log", rumpf.lower())

    def test_the_bar_is_suppressed_where_it_would_lie(self):
        rumpf = self.src[self.src.index("function barErlaubt("):]
        rumpf = rumpf[:rumpf.index("\nfunction ")]
        self.assertIn("UA.has(prof.tpl)", rumpf, "Einheiten-Sperrliste (#9) fehlt")
        self.assertIn("row.q && row.q.sc", rumpf, "Skalenbefund (#83) fehlt")

    def test_a_template_level_scale_finding_only_hits_its_own_template(self):
        """`sc.t` leer heisst „ganzer Report", eine gefüllte Liste nennt die
        betroffenen Templates. Wer das verwechselt, unterdrückt entweder zu
        viele Balken oder ausgerechnet die falschen."""
        rumpf = self.src[self.src.index("function barErlaubt("):]
        rumpf = rumpf[:rumpf.index("\nfunction ")]
        self.assertIn("!sc.t.length || sc.t.includes(prof.tpl)", rumpf)

    def test_no_red_green_valuation(self):
        """Es sind Offenlegungsdaten, keine Bewertung — eine niedrige CET1-Quote
        ist nicht „schlecht". Der Balken nimmt deshalb die Textfarbe, keine
        Ampel."""
        css = self.src[self.src.index(".szb{"):]
        css = css[:css.index(".bmlegend")]
        self.assertIn("var(--ink)", css)
        for ampel in ("green", "red", "#0a0", "#c00", "crimson", "--red", "--green"):
            self.assertNotIn(ampel, css, f"Ampelfarbe '{ampel}' im Größenbalken")

    def test_length_carries_the_signal_not_colour(self):
        """Barrierefreiheit: wer keine Farben unterscheidet, liest die Länge —
        und die Zahl steht ohnehin daneben. Der Balken selbst ist für
        Screenreader ausgeblendet, weil er die Zahl nur wiederholt."""
        rumpf = self.src[self.src.index("function sizeBar("):]
        rumpf = rumpf[:rumpf.index("\nfunction ")]
        self.assertIn('aria-hidden="true"', rumpf)
        self.assertIn("style=\"width:${pct}%\"", rumpf)

    def test_the_bar_has_a_stated_reference(self):
        """Eine Länge ohne Bezug ist eine Behauptung, die niemand prüfen kann.
        Der Bezug ist das Spaltenmaximum der aktuellen Auswahl — und er steht
        als Legende über der Tabelle, nicht nur im Tooltip."""
        self.assertIn('class="bmlegend"', self.src)
        self.assertIn("grössten Wert der Spalte in der aktuellen Auswahl", self.src)

    def test_the_reference_follows_the_visible_rows(self):
        """Die Filter sind Teil der Frage: wer auf Schweden filtert, will
        schwedische Grössen vergleichen, nicht gegen BNP Paribas.

        Geprüft wird der ERSTE Parameter — die Zeilenmenge. Der zweite ist seit
        der Spaltenwahl (#50) `spalten` statt `prof.cols`; daran hängt die
        Aussage dieses Tests nicht."""
        self.assertRegex(self.src, r"barBasis\(rows,")
        self.assertNotIn("barBasis(allRows", self.src)

    def test_the_runtime_check_covers_both_suppressions(self):
        """Die Sperrlisten-Bedingung feuert heute an keinem Profil — das
        einzige auf einem strittigen Template hat nur Quotenspalten. An der
        gerenderten Tabelle wäre ein Test dafür grün, ohne etwas zu belegen;
        deshalb prüft der Laufzeitlauf `barErlaubt` als Funktion."""
        rt = (ROOT / "scripts" / "check_viewer_runtime.py").read_text(encoding="utf-8")
        self.assertIn("barErlaubt({tpl:", rt)
        self.assertIn("tplDaneben", rt)
        self.assertIn("skalierte Reports (#83) tragen einen", rt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
