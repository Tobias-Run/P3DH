"""Was der Viewer beim Start laedt — und was erst spaeter (Performance).

## Der Befund

`codebook.json` wurde im `Promise.all` mit `index.json` geladen, also
BLOCKIEREND vor der ersten Ansicht. Gemessen im Browser: 116 ms fetch +
54 ms parse + 87 ms Map-Aufbau ueber 94.398 Eintraege = **257 ms** — auf
localhost, ohne Leitung.

Dabei besteht die Datei zu 99,3 % aus `cb`, den Zelllabels (9,41 von 9,48 MB),
und die erste Ansicht fasst kein einziges davon an. Gebraucht werden sie erst
bei einer aufgeklappten Rohtabelle, einem Kennzahlen-Beleg oder der
Vergleichsansicht.

A/B gemessen (4 Mbit/s, 60 ms RTT, gzip wie auf Pages):

    vorher   2.027 ms bis zur ersten nutzbaren Ansicht · 681 KB
    nachher    634 ms                                   · 105 KB

## Die Falle beim Nachladen

Nicht einfach im Hintergrund holen und hoffen. Eine Tabelle, die vor dem
Eintreffen rendert, saehe aus wie eine Tabelle ohne Beschriftung — ein stiller
Fehler. Die drei Stellen, die `CB` lesen, warten deshalb ausdruecklich auf
`ensureLabels()`; der Vorabruf nach dem ersten Rendern beschleunigt nur.
"""

from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent
VIEWER = ROOT / "processed" / "zweig_a" / "viewer_json.html"
DATA = ROOT / "processed" / "zweig_a" / "data"


class AufteilungTest(unittest.TestCase):
    def setUp(self):
        if not (DATA / "codebook.json").exists():
            self.skipTest("Zweig-A-Artefakte nicht gebaut")
        self.cb = json.loads((DATA / "codebook.json").read_text(encoding="utf-8"))

    def test_the_boot_payload_carries_no_cell_labels(self):
        """Sie sind 99,3 % der Datei und werden von der ersten Ansicht nie
        gelesen."""
        self.assertNotIn("cb", self.cb,
                         "die Zelllabels stecken wieder im Boot-Payload")

    def test_the_boot_payload_stays_small(self):
        gross = (DATA / "codebook.json").stat().st_size
        self.assertLess(gross, 1_000_000,
                        f"codebook.json ist {gross/1e6:.1f} MB — etwas Grosses "
                        "ist zurueck in den Start gewandert")

    def test_the_structure_the_first_view_needs_is_still_there(self):
        """Titel, Themen und Kennzahlen braucht die Report-Ansicht sofort —
        sie duerfen NICHT mit ausgelagert werden."""
        for k in ("titles", "themes", "metrics", "axis", "bridge"):
            self.assertIn(k, self.cb, f"{k} fehlt im Boot-Payload")

    def test_the_labels_are_complete_in_their_own_file(self):
        labels = json.loads((DATA / "labels.json").read_text(encoding="utf-8"))
        self.assertIn("cb", labels)
        self.assertGreater(len(labels["cb"]), 50_000,
                           "labels.json wirkt unvollstaendig")


class ViewerTest(unittest.TestCase):
    def setUp(self):
        self.src = VIEWER.read_text(encoding="utf-8")

    def test_every_reader_of_the_labels_waits_for_them(self):
        """Der Kern. Wer `CB` liest, ohne auf `ensureLabels()` gewartet zu
        haben, rendert stillschweigend unbeschriftet."""
        self.assertIn("function ensureLabels()", self.src)
        # Rohtabellen
        fill = self.src[self.src.index("const fillTheme="):]
        fill = fill[:fill.index("body.dataset.done='1';")]
        self.assertIn("await ensureLabels()", fill,
                      "fillTheme rendert ohne auf die Beschriftungen zu warten")
        # Vergleichsansicht
        cmp_ = self.src[self.src.index("async function renderCompare()"):][:400]
        self.assertIn("ensureLabels()", cmp_)
        # Kennzahlen-Beleg
        self.assertIn("if(OPENMETRIC && !LABELS_LOADED)", self.src)

    def test_the_prefetch_is_not_the_guarantee(self):
        """Der Vorabruf laeuft NACH dem ersten Rendern und darf nichts
        blockieren — und er darf auch nicht die einzige Absicherung sein."""
        init = self.src[self.src.index("async function init()"):]
        init = init[:init.index("}catch(err)")]
        self.assertIn("route();", init)
        i_route = init.index("route();")
        i_pre = init.index("ensureLabels()")
        self.assertGreater(i_pre, i_route,
                           "die Labels werden wieder vor der ersten Ansicht geholt")
        self.assertNotIn("await ensureLabels()", init,
                         "der Vorabruf blockiert den Start")

    def test_optional_shard_keys_are_all_assigned(self):
        """Der reale Defekt in #23: der Shard trug 6.177 Peer-Zellen, aber
        `ensureLoaded()` wies `rep.peer` nie zu — der Viewer las eine leere
        Map und zeigte nichts. Wer `rep.X` liest, muss X auch setzen."""
        el = self.src[self.src.index("async function ensureLoaded(rep)"):]
        el = el[:el.index("rep.loaded=true;")]
        gelesen = set(re.findall(r"\(rep\.(\w+)\|\|\{\}\)", self.src))
        for schluessel in gelesen:
            with self.subTest(schluessel=schluessel):
                self.assertRegex(
                    el, rf"rep\.{schluessel}\s*=",
                    f"rep.{schluessel} wird gelesen, aber beim Laden nie gesetzt")

    def test_number_formatting_never_asks_for_more_minimum_than_maximum(self):
        """`nf(v, min, max)` sind minimum- und maximumFractionDigits. Vertauscht
        wirft `toLocaleString` — und der Fehler reisst das GESAMTE Rendern der
        Tabelle mit: keine Zelle erscheint mehr. Genau so sind die Tooltips aus
        #23 und #24 ausgefallen, bei gruenen Tests."""
        schlecht = []
        for m in re.finditer(r"\bnf\(([^()]*(?:\([^()]*\)[^()]*)*)\)", self.src):
            teile = [t.strip() for t in re.split(r",(?![^()]*\))", m.group(1))]
            if len(teile) < 3:
                continue
            mins, maxs = teile[1], teile[2]
            if re.fullmatch(r"\d+", mins) and re.fullmatch(r"\d+", maxs):
                if int(mins) > int(maxs):
                    schlecht.append(m.group(0))
            # Ein Ausdruck als MIN neben einer kleineren Konstanten als MAX ist
            # der Fall, der real passiert ist.
            elif re.fullmatch(r"\d+", maxs) and "?" in mins:
                for zahl in re.findall(r"\d+", mins):
                    if int(zahl) > int(maxs):
                        schlecht.append(m.group(0))
                        break
        self.assertEqual(schlecht, [], f"nf(min > max) — wirft zur Laufzeit: {schlecht}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
