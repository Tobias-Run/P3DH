"""Der LLM-Client (#38b) — geprüft ohne Modell.

Diese Tests rufen **kein** Modell auf. Sie prüfen genau das, was auch in CI
deterministisch prüfbar ist und was am Ende trägt: dass ein erfundenes Zitat
auffliegt, dass der Cache nicht die falsche Antwort liefert, und dass keine
Zeile ohne Herkunft entsteht.

Vier Dinge halten sie fest:

1. **Ein erfundenes Zitat fliegt auf, ein anders formatiertes nicht.** Die
   Halluzinationsrate ist die Grösse, an der Modelle vergleichbar werden —
   sie darf nicht heimlich Typografie messen.
2. **Der Cache-Schlüssel trägt Modell und Prompt-Fassung.** Ohne sie
   beantwortete er eine Frage, die so nicht mehr gestellt wird.
3. **Keine Antwort ohne Herkunft.** Eine Zeile ohne sie ist nicht
   nachvollziehbar und für dieses Projekt wertlos.
4. **Lokal oder gehostet steht in der Zeile.** Ob der Korpus das Haus
   verlassen hat, ist keine Fussnote.
"""

from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


class ZitatTest(unittest.TestCase):
    def setUp(self):
        import llm_client as c
        self.c = c
        self.quelle = ("Die Kreditqualität des Portfolios blieb im "
                       "Berichtszeitraum stabil; die NPL-Quote lag bei 2,4 %.")

    def test_a_literal_quote_is_confirmed(self):
        self.assertTrue(self.c.zitat_geprueft(
            "die NPL-Quote lag bei 2,4 %", self.quelle))

    def test_an_invented_quote_is_caught(self):
        """Der ganze Zweck. Ein Modell erfindet Belege, und zwar
        überzeugend — hier entscheidet ein Stringvergleich, kein Urteil."""
        self.assertFalse(self.c.zitat_geprueft(
            "die NPL-Quote lag bei 1,1 % und sinkt weiter", self.quelle))

    def test_typography_is_not_a_hallucination(self):
        """Ein Modell normalisiert Anführungszeichen und Zeilenumbrüche. Das
        als Erfindung zu zählen machte die Halluzinationsrate zu einem Mass
        für Typografie."""
        quelle = 'Der Bericht nennt die Quote „stabil“\nim Jahresverlauf.'
        self.assertTrue(self.c.zitat_geprueft(
            'nennt die Quote "stabil" im Jahresverlauf', quelle))

    def test_a_wrong_number_is_not_typography(self):
        """Die Grenze: Ziffern werden NICHT vereinheitlicht. Wer 4,2 schreibt,
        wo 2,4 steht, hat nicht anders formatiert."""
        self.assertFalse(self.c.zitat_geprueft(
            "die NPL-Quote lag bei 4,2 %", self.quelle))

    def test_a_short_quote_proves_nothing(self):
        """„Kreditqualität" kommt in jedem Bericht vor. Unterhalb der
        Mindestlänge gilt ein Zitat als ungeprüft, nicht als bestätigt."""
        self.assertFalse(self.c.zitat_geprueft("Kreditqualität", self.quelle))

    def test_nothing_is_never_a_proof(self):
        self.assertFalse(self.c.zitat_geprueft("", self.quelle))
        self.assertFalse(self.c.zitat_geprueft("die NPL-Quote lag bei 2,4 %", ""))

    def test_the_minimum_length_is_actually_used(self):
        self.assertTrue(self.c.zitat_geprueft(
            "Kreditqualität", self.quelle, min_zeichen=5))


class SchemaTest(unittest.TestCase):
    def setUp(self):
        import llm_client as c
        self.c = c

    def test_a_complete_answer_passes(self):
        self.assertTrue(self.c.antwort_gueltig(
            {"aussage": "stabil", "zitat": "…", "seite": 7}))

    def test_a_prose_answer_is_not_silently_dropped(self):
        """Kleine Modelle antworten oft in Fliesstext. Ein `except: pass`
        hiesse: die Ausbeute sieht aus wie „nichts gefunden" statt wie
        „Modell hält sich nicht ans Format"."""
        self.assertFalse(self.c.antwort_gueltig("Der Bericht sagt dazu …"))

    def test_an_empty_field_is_not_an_answer(self):
        self.assertFalse(self.c.antwort_gueltig(
            {"aussage": "stabil", "zitat": "", "seite": 7}))
        self.assertFalse(self.c.antwort_gueltig(
            {"aussage": "stabil", "zitat": "…", "seite": None}))


class SchluesselTest(unittest.TestCase):
    def setUp(self):
        import llm_client as c
        self.c = c

    def test_another_model_is_another_answer(self):
        """Dieselbe Frage an ein anderes Modell darf die erste nicht
        verdrängen — sonst überschreibt ein Vergleichslauf die Grundlage,
        gegen die er vergleicht."""
        a = self.c.cache_schluessel("modell-a", "P", "E")
        b = self.c.cache_schluessel("modell-b", "P", "E")
        self.assertNotEqual(a, b)

    def test_a_changed_prompt_version_invalidates(self):
        """Sonst beantwortet der Cache eine Frage, die so nicht mehr gestellt
        wird — und niemand merkt es."""
        a = self.c.cache_schluessel("m", "P", "E", fassung=1)
        b = self.c.cache_schluessel("m", "P", "E", fassung=2)
        self.assertNotEqual(a, b)

    def test_a_changed_prompt_invalidates(self):
        self.assertNotEqual(self.c.cache_schluessel("m", "P1", "E"),
                            self.c.cache_schluessel("m", "P2", "E"))

    def test_a_changed_input_invalidates(self):
        self.assertNotEqual(self.c.cache_schluessel("m", "P", "E1"),
                            self.c.cache_schluessel("m", "P", "E2"))

    def test_the_same_question_is_the_same_key(self):
        self.assertEqual(self.c.cache_schluessel("m", "P", "E"),
                         self.c.cache_schluessel("m", "P", "E"))


class HerkunftTest(unittest.TestCase):
    def setUp(self):
        import llm_client as c
        self.c = c

    def test_every_field_is_present(self):
        h = self.c.herkunft("m", "P", "E")
        for f in self.c.HERKUNFT:
            with self.subTest(feld=f):
                self.assertIn(f, h)

    def test_localhost_is_local(self):
        self.assertEqual(self.c.endpunkt_art("http://localhost:1234/v1"), "lokal")
        self.assertEqual(self.c.endpunkt_art("http://127.0.0.1:1234/v1"), "lokal")

    def test_anything_else_left_the_house(self):
        """Ob der Korpus zu einem Dritten gewandert ist, gehört in die Zeile
        und nicht in eine Fussnote."""
        self.assertEqual(self.c.endpunkt_art("https://api.example.com/v1"),
                         "gehostet")


class CacheTest(unittest.TestCase):
    def setUp(self):
        import llm_client as c
        self.c = c
        self.p = Path(tempfile.mkdtemp()) / "cache.jsonl"

    def test_a_missing_cache_is_empty_not_an_error(self):
        self.assertEqual(self.c.lade_cache(self.p), ({}, 0))

    def test_a_written_line_comes_back(self):
        self.c.schreibe_cache({"key": "k1", "antwort": "ja"}, self.p)
        eintraege, kaputt = self.c.lade_cache(self.p)
        self.assertEqual(eintraege["k1"]["antwort"], "ja")
        self.assertEqual(kaputt, 0)

    def test_a_broken_line_is_counted_not_swallowed(self):
        """Ein stillschweigend halber Cache wäre eine stille Wiederholung
        teurer Aufrufe."""
        self.c.schreibe_cache({"key": "k1", "antwort": "ja"}, self.p)
        with self.p.open("a", encoding="utf-8") as fh:
            fh.write("{kaputt\n")
        eintraege, kaputt = self.c.lade_cache(self.p)
        self.assertEqual(len(eintraege), 1)
        self.assertEqual(kaputt, 1)

    def test_a_line_without_a_key_is_broken(self):
        with self.p.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps({"antwort": "ja"}) + "\n")
        self.assertEqual(self.c.lade_cache(self.p), ({}, 1))

    def test_writing_appends_rather_than_replaces(self):
        """Ein Lauf über 1.073 Dokumente darf bei Abbruch nicht alles
        verlieren — dieselbe Lehre wie beim GLEIF-Abruf."""
        self.c.schreibe_cache({"key": "k1"}, self.p)
        self.c.schreibe_cache({"key": "k2"}, self.p)
        self.assertEqual(set(self.c.lade_cache(self.p)[0]), {"k1", "k2"})


class TrockenlaufTest(unittest.TestCase):
    """`--dry-run`: was gesendet WÜRDE, ohne zu senden."""

    def setUp(self):
        import llm_client as c
        self.c = c
        self.p = Path(tempfile.mkdtemp()) / "cache.jsonl"

    def test_nothing_is_sent_and_the_payload_is_shown(self):
        r = self.c.frage("Prompt", "Eingabe", modell="m",
                         cache_pfad=self.p, trocken=True)
        self.assertTrue(r["trocken"])
        self.assertEqual(r["nutzlast"]["model"], "m")
        self.assertEqual(r["nutzlast"]["temperature"], 0.0)
        self.assertFalse(self.p.exists(), "ein Trockenlauf schreibt nichts")

    def test_the_estimate_is_marked_as_one(self):
        """Zeichen/3,5 ist eine Faustregel, kein Tokenizer. Sie steht unter
        einem Namen, der das sagt."""
        r = self.c.frage("x" * 350, "y" * 350, modell="m",
                         cache_pfad=self.p, trocken=True)
        self.assertEqual(r["zeichen"], 700)
        self.assertEqual(r["tokens_geschaetzt"], 200)

    def test_a_cached_answer_is_returned_without_asking(self):
        schluessel = self.c.cache_schluessel("m", "Prompt", "Eingabe")
        self.c.schreibe_cache({"key": schluessel, "antwort": "aus dem Cache"},
                              self.p)
        r = self.c.frage("Prompt", "Eingabe", modell="m", cache_pfad=self.p)
        self.assertTrue(r["aus_cache"])
        self.assertEqual(r["antwort"], "aus dem Cache")


class ErreichbarkeitTest(unittest.TestCase):
    def setUp(self):
        import llm_client as c
        self.c = c

    def test_an_unreachable_endpoint_is_a_finding_not_a_crash(self):
        """Die Lehre aus dem GLEIF-Abruf: geprüft wird VOR dem Lauf, nicht
        nach 300 Dokumenten."""
        ok, meldung = self.c.erreichbar("http://127.0.0.1:1/v1", timeout=1)
        self.assertFalse(ok)
        self.assertIn("nicht erreichbar", meldung)


if __name__ == "__main__":
    unittest.main(verbosity=2)
