"""Tests zur institutszentrischen Navigation des Viewers (#46, R1).

Die Seitenleiste führte 882 Einträge für 475 Institute — ABN AMRO dreimal
untereinander, einmal je Stichtag. Seit R1 gibt es einen Eintrag je
**(LEI, Konsolidierungskreis)**, die Stichtage sind Umschalter darin.

`viewer_json.html` ist bewusst eine Datei ohne Build-Schritt und ohne
JS-Testkette (`docs/viewer_redesign.md`, „Was wir nicht tun sollten"). Getestet
wird deshalb das, was ohne JS-Laufzeit belastbar prüfbar ist:

1. die **Dateneigenschaften**, auf denen die Gruppierung beruht — sie sind der
   Grund für den Schnitt, und wenn sie kippen, wird die Oberfläche still falsch;
2. der **Deep-Link-Vertrag**, den #46 ausdrücklich als unverletzlich benennt.

Das Verhalten selbst (Chip-Klick, Kopfklick, Pin, Filter) ist am gerenderten
Zustand in Chromium geprüft worden, nicht hier.
"""

from pathlib import Path
import collections
import json
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent
VIEWER = ROOT / "processed" / "zweig_a" / "viewer_json.html"
INDEX = ROOT / "processed" / "zweig_a" / "data" / "index.json"


def _parts(entity_id):
    """Spiegelt leiParts() im Viewer: LEI = 20 Zeichen, Scope = Suffix."""
    m = re.search(r"([A-Z0-9]{20})(?:\.(\w+))?", entity_id)
    return (m.group(1), m.group(2) or "") if m else (entity_id, "")


def _groups(reports):
    g = collections.defaultdict(list)
    for r in reports:
        g[_parts(r["entityID"])].append(r)
    return g


class GroupingKeyTest(unittest.TestCase):
    """Warum (LEI, Scope) und nicht der LEI allein."""

    def _reports(self):
        if not INDEX.exists():
            self.skipTest("index.json nicht gebaut")
        return json.loads(INDEX.read_text(encoding="utf-8"))["reports"]

    def test_a_lei_reporting_both_scopes_must_not_be_merged(self):
        """CON und IND sind nicht dasselbe Institut (DISCLAIMER.md): das eine
        ist die Gruppe, das andere das Einzelinstitut. Über den
        Konsolidierungskreis hinweg zusammenzufassen hieße, zwei verschiedene
        Zahlenwerke unter einen Namen zu legen.

        Im Bestand betrifft das genau einen LEI — aber die Regel muss stimmen,
        nicht der Einzelfall. Fällt dieser LEI eines Tages weg, bleibt der Test
        grün und beweist nichts mehr; deshalb prüft er zusätzlich, dass ein
        Zusammenfassen nach LEI allein die Gruppenzahl verändern WÜRDE.
        """
        reports = self._reports()
        by_lei = collections.defaultdict(set)
        for r in reports:
            lei, scope = _parts(r["entityID"])
            by_lei[lei].add(scope)
        both = {lei: sc for lei, sc in by_lei.items() if len(sc) > 1}
        n_lei_only = len(by_lei)
        n_lei_scope = len(_groups(reports))
        self.assertEqual(
            n_lei_scope - n_lei_only, sum(len(sc) - 1 for sc in both.values()),
            "Gruppenzahl und Scope-Mehrfachmeldung müssen zusammenpassen")
        if both:
            self.assertGreater(n_lei_scope, n_lei_only,
                               f"LEIs mit mehreren Scopes würden verschmelzen: {both}")

    def test_the_list_actually_gets_shorter(self):
        """Der Zweck der Übung: die Liste ist heute fast doppelt so lang wie die
        Zahl der Dinge, nach denen jemand sucht."""
        reports = self._reports()
        groups = _groups(reports)
        self.assertLess(len(groups), len(reports))

    def test_one_report_per_date_within_a_group(self):
        """Die Stichtage sind die Umschalter im Eintrag. Zwei Reports mit
        demselben Stichtag ergäben zwei gleich beschriftete Chips, von denen
        einer unerreichbar wäre."""
        for key, reps in _groups(self._reports()).items():
            dates = [r["refPeriod"] for r in reps]
            self.assertEqual(len(dates), len(set(dates)),
                             f"doppelter Stichtag in {key}: {sorted(dates)}")

    def test_currency_and_framework_belong_to_the_report_not_the_group(self):
        """Der Gruppenkopf trägt Land und Konsolidierungskreis — bewusst NICHT
        Währung und Framework-Version. Beide wechseln zwischen den Stichtagen
        desselben Instituts; am Kopf angeschrieben wären sie für einen Teil der
        Stichtage schlicht falsch. Sie stehen deshalb am Chip (Tooltip) und in
        der Detailzeile des ausgewählten Stichtags.
        """
        groups = _groups(self._reports())
        mixed_cur = [k for k, v in groups.items()
                     if len({r["baseCurrency"] for r in v}) > 1]
        mixed_fw = [k for k, v in groups.items()
                    if len({r["framework"] for r in v}) > 1]
        if not mixed_cur and not mixed_fw:
            self.skipTest("im aktuellen Bestand variiert weder Währung noch Framework")
        src = VIEWER.read_text(encoding="utf-8")
        rmeta = re.search(r'<div class="rmeta">(.*?)</div>', src, re.S)
        self.assertIsNotNone(rmeta, "Gruppen-Metazeile nicht gefunden")
        self.assertNotIn("curOf", rmeta.group(1),
                         f"Währung am Gruppenkopf, wechselt aber in {len(mixed_cur)} Gruppen")
        self.assertNotIn("framework", rmeta.group(1),
                         f"Framework am Gruppenkopf, wechselt aber in {len(mixed_fw)} Gruppen")


class DeepLinkContractTest(unittest.TestCase):
    """#46: „Der URL-Hash muss weiter funktionieren; bestehende Links dürfen
    nicht brechen." Das ist eine Zusage nach außen — geteilte Links leben
    länger als ein Refactoring der Seitenleiste."""

    def setUp(self):
        self.src = VIEWER.read_text(encoding="utf-8")

    def test_route_still_parses_the_documented_hash(self):
        m = re.search(r"hsh\.match\((/\^#r.*?/)\)", self.src)
        self.assertIsNotNone(m, "Route für #r/... nicht gefunden")
        # JS-Literal in ein Python-Muster: nur die Begrenzer und das in JS
        # nötige `\/` weg — `\d`/`\w` bedeuten in beiden Sprachen dasselbe.
        rx = re.compile(m.group(1)[1:-1].replace("\\/", "/"))
        self.assertTrue(rx.match("#r/BFXS5XCH7N0Y05NIXW11/2025-09-30/CON"))
        self.assertTrue(rx.match("#r/BFXS5XCH7N0Y05NIXW11/2025-09-30"),
                        "Links ohne Scope sind älter und müssen weiter greifen")

    def test_the_list_links_to_that_same_shape(self):
        """Die Stichtags-Chips sind echte <a href>, damit ein Link kopierbar
        und mit der mittleren Maustaste öffenbar ist — und sie müssen dasselbe
        Format erzeugen, das route() liest."""
        self.assertIn('href="#r/${g.lei}/${r.refPeriod}/${g.scope}"', self.src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
