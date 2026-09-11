"""Teilbarer Zustand im Viewer (#50).

## Warum

Ein Analysewerkzeug, dessen Zustand sich nicht verlinken laesst, erzeugt
Screenshots statt Zusammenarbeit. Wer eine Auffaelligkeit findet, kann sie nicht
weitergeben — er kann nur beschreiben, welche Filter der andere setzen muss.

## Die Zusagen

1. **Bestehende Links brechen nicht.** `#r/<lei>/<refPeriod>/<scope>` und
   `#benchmark` sind vermutlich schon geteilt worden. Alles hinter `?` ist
   optional; ein Link ohne Parameter ergibt exakt die heutigen Vorgaben.
2. **Lesbar, nicht kodiert.** Wer den Link sieht, sieht den Zustand. Eine
   undurchsichtige Kodierung widerspraeche einem Werkzeug, das fuer
   Nachvollziehbarkeit gebaut ist.

## Verhalten, mit einem DOM-Ersatz am echten Code durchgespielt

    leer            -> #benchmark
    gefiltert       -> #benchmark?q=helaba&c=Germany&g=1
    wiederhergest.  -> q=helaba c=Germany g=true
    alter Link      -> Vorgaben, Route unveraendert
    unbek. Land     -> verworfen, Filter bleibt stehen
"""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent
VIEWER = ROOT / "processed" / "zweig_a" / "viewer_json.html"


class TeilbarerZustandTest(unittest.TestCase):
    def setUp(self):
        self.src = VIEWER.read_text(encoding="utf-8")

    def test_the_state_is_serialised_at_all(self):
        self.assertIn("function shareState()", self.src)
        self.assertIn("function applyShared()", self.src)

    def test_the_existing_routes_are_read_without_the_parameters(self):
        """`route()` darf nicht mehr den ganzen Hash matchen — sonst scheitert
        `#r/…/CON?q=x` an der Routenerkennung."""
        self.assertIn("const hsh=decodeURIComponent(hashRoute());", self.src)
        self.assertIn("return (location.hash||'').split('?')[0];", self.src)

    def test_the_parameters_are_plain_text(self):
        """Klartext statt Base64 — der Link soll lesbar sein."""
        block = self.src[self.src.index("const SHARE_FIELDS"):
                         self.src.index("function setTabs(){")]
        self.assertIn("URLSearchParams", block)
        for verboten in ("btoa(", "atob(", "JSON.stringify(state"):
            self.assertNotIn(verboten, block)

    def test_only_non_default_values_reach_the_link(self):
        """Sonst traegt jeder Link einen Rattenschwanz leerer Parameter."""
        block = self.src[self.src.index("function shareParams()"):
                         self.src.index("function hashRoute()")]
        self.assertIn("if(el && el.value) p.set(k, el.value);", block)
        self.assertIn("if(BMP!=='km1')", block)

    def test_writing_does_not_trigger_the_router(self):
        """`location.hash=` loeste hashchange aus — route() riefe sich bei
        jedem Tastendruck selbst auf und fuellte die Zurueck-Historie."""
        block = self.src[self.src.index("function shareState()"):
                         self.src.index("function applyShared()")]
        self.assertIn("history.replaceState", block)
        self.assertNotIn("location.hash=", block.replace("location.hash||", ""))

    def test_an_unknown_select_value_is_discarded(self):
        """Ein veralteter Link darf den Filter nicht auf etwas Leeres setzen —
        sonst sieht der Empfaenger eine andere Auswahl als der Absender, ohne
        dass es jemand merkt."""
        block = self.src[self.src.index("function applyShared()"):
                         self.src.index("function setTabs(){")]
        self.assertIn("el.tagName==='SELECT'", block)
        self.assertIn("continue", block)

    def test_the_filter_survives_a_tab_switch(self):
        """Ein Filter, der beim Umschalten verfaellt, macht den Vergleich
        zwischen den Sichten unmoeglich."""
        self.assertIn("location.hash='#benchmark'+hashQuery();", self.src)
        self.assertIn("location.hash='#compare'+hashQuery();", self.src)

    def test_the_benchmark_state_is_shared_too(self):
        for feld in ("prof", "pct", "hide"):
            with self.subTest(feld=feld):
                self.assertIn(f"p.set('{feld}'", self.src)

    def test_changing_a_filter_updates_the_link(self):
        self.assertRegex(self.src, r"const rerender=\(\)=>\{[^}]*shareState\(\);")

    def test_the_route_patterns_are_untouched(self):
        """Die drei bestehenden Routen muessen buchstaeblich bleiben."""
        for muster in (r"/^#r\/([A-Z0-9]{20})\/([\d-]+)", "'#benchmark'", "'#compare'"):
            with self.subTest(muster=muster):
                self.assertIn(muster, self.src, f"Route {muster} nicht mehr vorhanden")


if __name__ == "__main__":
    unittest.main(verbosity=2)
