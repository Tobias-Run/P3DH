"""Tests zum Gestaltungssystem des Viewers (#61, vormals #51).

Zwei Zusagen, die man einer Oberfläche nicht ansieht und die deshalb
still verrotten — beide sind älter als das Gestaltungssystem und wurden
von ihm nur geerbt:

1. **Rot bedeutet Fokus, nie Wertung.** `docs/viewer_redesign.md`: „Farbe
   sparsam und nur mit Bedeutung; nie Rot/Grün als Wertung — es sind
   Offenlegungsdaten, keine Bewertung." Das Vorbild aus #61 benutzt seinen
   roten Akzent genau so: er sagt „darum geht es gerade", nicht „das ist
   schlecht". Eine einzige Zeile `color:var(--accent)` an einer Kennzahl
   würde daraus eine Wertung machen, und niemandem fiele es auf.

2. **Kontraste.** #51 hielt fest, dass Barrierefreiheit „heute nicht geprüft"
   ist. Eine Palette ist der eine Ort, an dem sich das billig und dauerhaft
   prüfen lässt — jede Textfarbe gegen jede Fläche, auf der sie steht.
"""

from pathlib import Path
import re
import unittest

VIEWER = (Path(__file__).resolve().parent.parent
          / "processed" / "zweig_a" / "viewer_json.html")

# Selektoren, die den Akzent tragen DÜRFEN. Jeder von ihnen beantwortet die
# Frage „wo bin ich / was ist gerade gewählt" — keiner bewertet einen Wert.
ACCENT_ALLOWED = {
    "header",                 # rote Oberkante: Identität (Zeitungsmittel)
    "nav.tabs button.on",     # gewählte Rubrik
    ".report.active",         # ausgewähltes Institut
    ".dcard.on",              # Spalte, nach der sortiert wird
    # Fokusring — Tastaturbedienung, Barrierefreiheit
    "nav.tabs button:focus-visible", ".hlink:focus-visible", ".iconbtn:focus-visible",
    ".dchip:focus-visible", "summary:focus-visible", ".dcard:focus-visible",
}


def css(src):
    """Der <style>-Block als (Selektorenliste, Deklarationen)-Paare."""
    block = re.search(r"<style>(.*?)</style>", src, re.S).group(1)
    block = re.sub(r"/\*.*?\*/", "", block, flags=re.S)      # Kommentare raus
    out = []
    for sel, decl in re.findall(r"([^{}]+)\{([^{}]*)\}", block):
        sel = " ".join(sel.split())
        if not sel or sel.startswith("@"):
            continue
        out.append(([s.strip() for s in sel.split(",")], decl))
    return out


def tokens(src, selector):
    m = re.search(re.escape(selector) + r"\{(.*?)\n  \}", src, re.S)
    return dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{3,8})", m.group(1)))


def _lum(hexv):
    h = hexv.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    ch = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in ch]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


class AccentDisciplineTest(unittest.TestCase):
    """Rot markiert Fokus, nicht Qualität."""

    def setUp(self):
        self.rules = css(VIEWER.read_text(encoding="utf-8"))

    def test_accent_only_on_focus_selectors(self):
        stray = []
        for sels, decl in self.rules:
            if "var(--accent)" not in decl:
                continue
            for s in sels:
                if s not in ACCENT_ALLOWED:
                    stray.append(f"{s} {{{' '.join(decl.split())}}}")
        self.assertEqual(
            stray, [],
            "Akzentfarbe außerhalb der Fokus-Selektoren. Rot heißt in diesem "
            "Viewer 'hier bist du', nicht 'das ist schlecht' — es sind "
            "Offenlegungsdaten, keine Bewertung:\n  " + "\n  ".join(stray))

    def test_the_allow_list_is_not_stale(self):
        """Ein Eintrag in der Liste, den es im Stylesheet nicht mehr gibt,
        macht die Prüfung oben lasch, ohne dass etwas rot wird."""
        used = {s for sels, decl in self.rules if "var(--accent)" in decl for s in sels}
        self.assertEqual(ACCENT_ALLOWED - used, set(),
                         "Allow-Liste nennt Selektoren, die den Akzent nicht tragen")

    def test_no_red_green_value_judgement_anywhere(self):
        """Auch nicht als Literal am Stylesheet vorbei: grün als „gut" ist
        derselbe Fehler wie rot als „schlecht"."""
        src = VIEWER.read_text(encoding="utf-8")
        block = re.search(r"<style>(.*?)</style>", src, re.S).group(1)
        greens = [m for m in re.findall(r"#[0-9a-fA-F]{6}", block)
                  if (lambda h: int(h[3:5], 16) > int(h[1:3], 16) + 40
                      and int(h[3:5], 16) > int(h[5:7], 16) + 40)(m)]
        self.assertEqual(greens, [], f"grüne Literalfarben im Stylesheet: {greens}")


class ContrastTest(unittest.TestCase):
    """WCAG-Kontrast für jede Text-auf-Fläche-Paarung, die tatsächlich vorkommt.

    Nicht geprüft und bewusst nicht:

    - `--grid` auf `--panel` (1,27): Gitterlinien SOLLEN kaum da sein. Sie
      tragen die Ablesbarkeit, sie sind keine Information und kein Text.
    - `--muted` auf `--panel`: auf der Grafikfläche steht kein Text —
      Achsenenden und Zusammenfassung liegen als HTML darunter auf `--card`.
    """

    PAIRS = [("--ink", "--card"), ("--ink", "--bg"), ("--ink2", "--card"),
             ("--muted", "--card"), ("--muted", "--bg"),
             ("--theadink", "--thead"), ("--softink", "--soft"),
             ("--blue", "--card")]
    NON_TEXT = [("--accent", "--card"), ("--line", "--card")]

    def setUp(self):
        self.src = VIEWER.read_text(encoding="utf-8")

    def _check(self, selector, label):
        t = tokens(self.src, selector)
        bad = []
        for fg, bg in self.PAIRS:
            r = contrast(t[fg], t[bg])
            if r < 4.5:
                bad.append(f"{label}: {fg} ({t[fg]}) auf {bg} ({t[bg]}) = {r:.2f}")
        self.assertEqual(bad, [], "Textkontrast unter WCAG AA (4,5:1):\n  "
                                  + "\n  ".join(bad))

    def test_light_theme_text_contrast(self):
        self._check(":root", "hell")

    def test_dark_theme_text_contrast(self):
        self._check("[data-theme=dark]", "dunkel")

    def test_non_text_contrast(self):
        """Ränder und Marken brauchen 3:1, nicht 4,5:1 — aber sie brauchen es.
        Ein Fokusring, den man nicht sieht, ist keiner."""
        for selector, label in ((":root", "hell"), ("[data-theme=dark]", "dunkel")):
            t = tokens(self.src, selector)
            for fg, bg in self.NON_TEXT:
                if fg == "--line":
                    continue     # Trennlinien dürfen zart sein
                r = contrast(t[fg], t[bg])
                self.assertGreaterEqual(
                    r, 3.0, f"{label}: {fg} auf {bg} = {r:.2f} — als Marke zu schwach")

    def test_both_themes_define_every_token(self):
        """Ein Token, das nur im hellen Block steht, erbt im dunklen den
        hellen Wert — der klassische Weg zu weißer Schrift auf Weiß."""
        light = set(tokens(self.src, ":root"))
        dark = set(tokens(self.src, "[data-theme=dark]"))
        self.assertEqual(light - dark, set(),
                         "im dunklen Modus nicht überschriebene Farbtokens")


class ProvenanceTest(unittest.TestCase):
    """Die Adaption, die über das Vorbild hinausgeht: jede Grafik nennt ihre
    exakte Herkunft, nicht nur die Institution."""

    def setUp(self):
        self.src = VIEWER.read_text(encoding="utf-8")

    def test_every_distribution_chart_carries_a_source_line(self):
        m = re.search(r'cards\+=`(.*?)`;', self.src, re.S)
        self.assertIsNotNone(m, "Verteilungskarte nicht gefunden")
        card = m.group(1)
        self.assertIn("dsrc", card, "Grafik ohne Quellzeile")
        for part in ("Quelle:", "${esc(cell)}", "${esc(period)}"):
            self.assertIn(part, card, f"Quellzeile ohne {part}")

    def test_the_acknowledgement_names_the_inspiration_and_denies_affiliation(self):
        """Namensnennung ist zulässig, eine suggerierte Verbindung nicht."""
        self.assertIn("colophon", self.src)
        colophon = re.search(r'<div class="colophon">(.*?)</div>', self.src, re.S).group(1)
        self.assertIn("The Economist", colophon)
        self.assertIn("in keiner Weise", colophon,
                      "Danksagung ohne Verbindungs-Ausschluss")


if __name__ == "__main__":
    unittest.main(verbosity=2)
