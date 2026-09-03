"""Tests der kuratierten Themenzuordnung (#47, R2).

Die Randbedingung von #47 lautet: **nichts darf verschwinden.** Kuratieren heißt
Reihenfolge und Sichtbarkeit ändern, nicht Daten weglassen — „sonst wird aus
urteilend unvollständig, und der Vorwurf gegen EDAP fällt auf uns zurück."

Diese Tests sind die Einlösung dieser Zusage. Der Viewer hat einen Auffangblock
für Unzugeordnetes, damit ein Template auch bei einer Lücke sichtbar bleibt;
hier wird geprüft, dass die Lücke gar nicht erst entsteht.
"""

from pathlib import Path
import json
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import template_themes as tt  # noqa: E402

CODEBOOK = ROOT / "processed" / "zweig_a" / "data" / "codebook.json"
SUBLETTER = re.compile(r"\.[a-z]$")


class RegistryShapeTest(unittest.TestCase):
    def test_no_template_is_assigned_twice(self):
        """Zwei Blöcke würden dasselbe Template zeigen — der Nutzer müsste
        raten, welcher der richtige ist."""
        seen = []
        for _key, _label, tids in tt.THEMES:
            seen.extend(tids)
        dupes = sorted({t for t in seen if seen.count(t) > 1})
        self.assertEqual(dupes, [], f"mehrfach zugeordnet: {dupes}")
        self.assertEqual(len(seen), len(tt.THEME_OF))

    def test_keys_and_labels_are_unique_and_non_empty(self):
        keys = [k for k, _l, _t in tt.THEMES]
        labels = [l for _k, l, _t in tt.THEMES]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(labels), len(set(labels)))
        self.assertTrue(all(k and l for k, l in zip(keys, labels)))

    def test_keys_are_base_templates_not_sheets(self):
        """Schlüssel ist das Basistemplate: '60.00', nicht '60.00.A'. Die
        Buchstaben-Suffixe sind Teilblätter desselben Templates und gehören
        immer in denselben Block."""
        bad = [t for t in tt.THEME_OF if not re.fullmatch(r"\d{2,3}\.\d{2}", t)]
        self.assertEqual(bad, [], f"keine Basistemplate-Codes: {bad}")

    def test_payload_round_trips(self):
        p = tt.theme_payload()
        self.assertEqual([k for k, _ in p["order"]], [k for k, _l, _t in tt.THEMES])
        self.assertEqual(set(p["map"].values()), {k for k, _l, _t in tt.THEMES},
                         "jeder Block muss mindestens ein Template tragen")


class CoverageAgainstTheCodebookTest(unittest.TestCase):
    """Gegen die tatsächlich vorhandenen Templates, nicht gegen eine Liste im
    Kopf. Läuft mit, sobald codebook.json gebaut ist."""

    def _bases(self):
        if not CODEBOOK.exists():
            self.skipTest("codebook.json nicht gebaut")
        titles = json.loads(CODEBOOK.read_text(encoding="utf-8"))["titles"]
        # 'K_60.00.a' -> '60.00'  (Spiegel von dpm_code()/base_tid())
        return {SUBLETTER.sub("", k[2:]) for k in titles}

    def test_every_template_in_the_codebook_has_a_theme(self):
        """Der Kern der Zusage. Ein neues Template im DPM landet sonst
        stillschweigend im Auffangblock — sichtbar zwar, aber unsortiert."""
        missing = sorted(self._bases() - set(tt.THEME_OF))
        self.assertEqual(missing, [],
                         f"{len(missing)} Templates ohne Themenzuordnung: {missing}")

    def test_registry_has_no_phantom_templates(self):
        """Die andere Richtung: ein Eintrag für ein Template, das es nicht gibt,
        ist ein Tippfehler — er würde nie auffallen, weil ein Block, der es
        nicht zeigt, genauso aussieht wie einer, der es nicht hat."""
        phantom = sorted(set(tt.THEME_OF) - self._bases())
        self.assertEqual(phantom, [], f"Zuordnung für unbekannte Templates: {phantom}")

    def test_the_codebook_ships_the_registry(self):
        """Der Viewer führt die Zuordnung NICHT selbst — er liest sie aus
        codebook.json. Fehlt sie dort, fällt alles in den Auffangblock."""
        if not CODEBOOK.exists():
            self.skipTest("codebook.json nicht gebaut")
        themes = json.loads(CODEBOOK.read_text(encoding="utf-8")).get("themes")
        self.assertIsNotNone(themes, "codebook.json trägt keine Themen")
        self.assertEqual(themes, tt.theme_payload(),
                         "codebook.json ist gegenüber der Registry veraltet")


class ViewerFallbackTest(unittest.TestCase):
    """Die Registry kann lückenhaft sein — ein neues Template im DPM, ein
    `codebook.json` aus einem älteren Lauf. Dann darf das Template trotzdem
    nicht aus dem Report fallen. Der Auffangblock ist die Sicherung, die den
    Tests oben ihre Schärfe nimmt, falls sie einmal übergangen werden.
    """

    def setUp(self):
        self.src = (ROOT / "processed" / "zweig_a" / "viewer_json.html").read_text(
            encoding="utf-8")

    def test_unknown_templates_fall_into_a_visible_block(self):
        self.assertIn("THEME_OF.get(baseTid(t))||'__rest'", self.src,
                      "kein Auffang für unzugeordnete Templates")
        self.assertIn("THEME_REST", self.src)

    def test_the_viewer_does_not_keep_a_second_registry(self):
        """#47: „Beide sollten dieselbe Registry nutzen." Eine zweite Liste in
        JavaScript würde genau so lange stimmen, bis jemand nur eine pflegt."""
        for tid in sorted(tt.THEME_OF)[:20]:
            self.assertNotIn(f'"{tid}"', self.src,
                             f"Templatecode {tid} steht im Viewer — Registry doppelt geführt?")


if __name__ == "__main__":
    unittest.main(verbosity=2)
