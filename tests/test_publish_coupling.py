"""Was der Viewer holt, muss die Veroeffentlichung auch frisch halten (#82).

## Der Befund

`processed/zweig_a/viewer_json.html` laedt seine Daten im Netz ueber jsDelivr:

    https://cdn.jsdelivr.net/gh/Tobias-Run/P3DH@data/

jsDelivr cacht **Branch-URLs je Datei** bis zu zwoelf Stunden. Deshalb purgt
`scripts/publish_data_branch.sh` nach jedem Lauf die Dateien, die sich aendern —
aus einer von Hand gepflegten Liste.

Als `labels.json` aus `codebook.json` herausgeloest wurde (#23/#82), blieb die
Liste stehen. Folge waere gewesen: frischer Index und frische Shards neben bis
zu zwoelf Stunden alten Beschriftungen. Neue Zellen haetten kein Label
getragen — **kein Fehler, nur eine Luecke**, also genau die Sorte Schaden, die
niemand meldet.

Die Datei wurde trotzdem veroeffentlicht (`cp -R` kopiert das ganze
Verzeichnis); es ging allein um die Frische. Das ist der Unterschied zwischen
„fehlt" und „ist alt" — der zweite Fall ist der leisere.

## Warum ein Test und nicht nur ein Eintrag

Die Liste wird beim naechsten Aufteilen wieder vergessen. Der Test koppelt sie
an das, was der Viewer TATSAECHLICH aufruft, statt an die Erinnerung.
"""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent
VIEWER = ROOT / "processed" / "zweig_a" / "viewer_json.html"
PUBLISH = ROOT / "scripts" / "publish_data_branch.sh"


def _geholt():
    """Die JSON-Dateien, die der Viewer als Literal aus dem Wurzelverzeichnis
    holt. `reports/...` ist ausgenommen: ein Shard je Report, und die Liste
    waere unbrauchbar lang."""
    src = VIEWER.read_text(encoding="utf-8")
    treffer = set(re.findall(r"getJSON\('([^']+\.json)'\)", src))
    return {t for t in treffer if "/" not in t}


def _purge_liste():
    """Die Schleife, die WIRKLICH purgt — an `purge.jsdelivr.net` erkannt.

    Ein Regex auf die erste `for f in`-Schleife griff die Zustands-Schleife
    weiter oben und verglich Pfade gegen Dateinamen.
    """
    src = PUBLISH.read_text(encoding="utf-8")
    for m in re.finditer(r"^for f in ([^;]+); do(.*?)^done", src, re.M | re.S):
        if "purge.jsdelivr.net" in m.group(2):
            return set(m.group(1).split())
    return set()


class PurgeKopplungTest(unittest.TestCase):
    def test_the_viewer_actually_fetches_something(self):
        """Ein leerer Soll-Wert machte jeden Vergleich darunter wertlos."""
        self.assertGreaterEqual(len(_geholt()), 3, "getJSON-Aufrufe nicht gefunden")

    def test_every_file_the_viewer_fetches_is_purged(self):
        """Faellt eine heraus, liefert jsDelivr sie bis zu zwoelf Stunden alt —
        neben frischen Shards. Bei labels.json waeren das Zellen ohne
        Beschriftung."""
        fehlend = sorted(_geholt() - _purge_liste())
        self.assertEqual(fehlend, [],
                         f"vom Viewer geholt, aber nicht gepurgt: {fehlend}")

    def test_the_purge_list_carries_no_ghosts(self):
        """Eine Datei purgen, die es nicht mehr gibt, ist ein stiller Hinweis
        darauf, dass die Liste den Stand verloren hat."""
        ueberzaehlig = sorted(_purge_liste() - _geholt())
        self.assertEqual(ueberzaehlig, [],
                         f"gepurgt, aber vom Viewer nie geholt: {ueberzaehlig}")

    def test_the_whole_directory_is_published_not_a_list(self):
        """Die Veroeffentlichung selbst darf KEINE Dateiliste sein — sonst
        fehlte eine neue Datei ganz, nicht nur ihre Frische. Genau das hatte
        ich beim Lesen zuerst befuerchtet; es kopiert das Verzeichnis."""
        src = PUBLISH.read_text(encoding="utf-8")
        self.assertRegex(src, r'cp -R "\$SRC"/\. "\$TMP"/',
                         "die Veroeffentlichung kopiert nicht mehr das ganze Verzeichnis")


if __name__ == "__main__":
    unittest.main(verbosity=2)
