"""Konzerngraph über GLEIF (#32).

## Warum das die Voraussetzung für jedes Populationsaggregat ist

325 Institute melden nur konsolidiert, 148 nur auf Einzelinstitutsebene. Die
IND-Melder sind fast alle Toechter von irgendwem — von wem, steht nirgends in
den Daten. Wer ueber alle Institute summiert, zaehlt Mutter und Tochter doppelt.

## Die Unterscheidung, an der alles haengt

„Kein Parent gemeldet" ist **nicht** „eigenstaendig". GLEIF traegt das mit:
neben dem Parent-Endpunkt gibt es die Reporting Exception mit einem Grund, und
die Gruende sagen Verschiedenes.

    NO_KNOWN_PERSON      es gibt wirklich keine Mutter    -> eigenstaendig
    NON_CONSOLIDATING    niemand konsolidiert            -> eigenstaendig
    NO_LEI               es GIBT eine, nur ohne LEI      -> NICHT eigenstaendig
    LEGAL_OBSTACLES      Meldung verhindert              -> unbekannt

Ein Graph, der `NO_LEI` wie `NO_KNOWN_PERSON` behandelt, behauptet
Eigenstaendigkeit, wo die Quelle das Gegenteil sagt (Arbeitsprinzip 3).
"""

from pathlib import Path
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

REL = ROOT / "processed" / "lei_relations.csv"
META = ROOT / "processed" / "entity_meta.csv"


def zeilen():
    if not REL.exists():
        return []
    with REL.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class GrundlagenTest(unittest.TestCase):
    """Die Gruende-Tabelle ist der Kern — sie darf nicht stillschweigend
    verwaessern."""

    def setUp(self):
        import fetch_gleif_relations as f
        self.f = f

    def test_only_two_reasons_prove_independence(self):
        """`NO_LEI` darf nicht dazu. Es heisst ausdruecklich: es GIBT eine
        Mutter, sie hat nur keinen LEI."""
        self.assertIn("NO_KNOWN_PERSON", self.f.EIGENSTAENDIG)
        self.assertIn("NON_CONSOLIDATING", self.f.EIGENSTAENDIG)
        self.assertNotIn("NO_LEI", self.f.EIGENSTAENDIG)
        self.assertNotIn("LEGAL_OBSTACLES", self.f.EIGENSTAENDIG)

    def test_natural_persons_answers_one_question_but_not_the_other(self):
        """Neun Institute — überwiegend dänische Sparkassen — werden von
        natürlichen Personen kontrolliert. Sie sind NICHT eigenstaendig, es gibt
        jemanden ueber ihnen. Aber eine natuerliche Person kann nie im Bestand
        stehen (der ist nach LEI verschluesselt) und niemanden doppelt zaehlen.

        Eine einzige Menge fuer beide Fragen muesste eine davon falsch
        beantworten."""
        self.assertNotIn("NATURAL_PERSONS", self.f.EIGENSTAENDIG,
                         "behauptet Eigenstaendigkeit, wo Kontrolle besteht")
        self.assertIn("NATURAL_PERSONS", self.f.KEINE_MUTTER_IM_BESTAND_MOEGLICH,
                      "zaehlt ein Doppelzaehlungsrisiko, das es nicht geben kann")
        self.assertTrue(self.f.EIGENSTAENDIG < self.f.KEINE_MUTTER_IM_BESTAND_MOEGLICH,
                        "die strengere Menge muss die Teilmenge sein")

    def test_no_lei_stays_unknown_in_both_sets(self):
        """`NO_LEI` heisst: es GIBT eine Mutter, sie hat nur keinen LEI. Der
        direkte Weg ist damit versperrt — aber eine Ur-Mutter weiter oben kann
        sehr wohl im Bestand stehen. Also unbekannt, nicht 'kopflos'."""
        for menge in (self.f.EIGENSTAENDIG, self.f.KEINE_MUTTER_IM_BESTAND_MOEGLICH):
            self.assertNotIn("NO_LEI", menge)
            self.assertNotIn("LEGAL_OBSTACLES", menge)
            self.assertNotIn("NON_PUBLIC", menge)

    def test_double_counting_is_measured_on_parents_that_report_themselves(self):
        """„Hat irgendwo eine Mutter" waere die falsche Zahl: Doppelzaehlung
        entsteht nur, wo die Mutter SELBST im Bestand meldet."""
        zeilen = [
            {"lei": "A", "direct_parent_lei": "B", "direct_parent_reason": "",
             "ultimate_parent_lei": "B"},                      # Mutter meldet mit
            {"lei": "B", "direct_parent_lei": "", "direct_parent_reason": "NO_KNOWN_PERSON",
             "ultimate_parent_lei": ""},
            {"lei": "C", "direct_parent_lei": "Z", "direct_parent_reason": "",
             "ultimate_parent_lei": "Z"},                      # Mutter ausserhalb
            {"lei": "D", "direct_parent_lei": "", "direct_parent_reason": "NATURAL_PERSONS",
             "ultimate_parent_lei": ""},
            {"lei": "E", "direct_parent_lei": "", "direct_parent_reason": "NO_LEI",
             "ultimate_parent_lei": ""},
        ]
        t = "\n".join(self.f.bericht(zeilen, {"A", "B", "C", "D", "E"}))
        self.assertRegex(t, r"Mutter SELBST im Bestand\s*:\s*1\b")
        self.assertRegex(t, r"mit Mutter irgendwo\s*:\s*2\b")
        self.assertRegex(t, r"\(davon 1 ausserhalb\)")
        self.assertRegex(t, r"keine Mutter möglich\s*:\s*2\b")   # B und D
        self.assertRegex(t, r"Mutter da, aber unbekannt\s*:\s*1\b")  # E

    def test_a_404_is_an_answer_not_an_error(self):
        """Kein hinterlegter Parent ist eine Aussage der Quelle, kein
        Abrufproblem — sonst braeche der Lauf bei jedem eigenstaendigen
        Institut ab."""
        src = (ROOT / "scripts" / "fetch_gleif_relations.py").read_text(encoding="utf-8")
        self.assertIn("if e.code == 404:", src)
        self.assertIn("return 404, None", src)

    def test_transient_errors_are_retried(self):
        """Von 60 Probeabrufen scheiterten 3 sporadisch. Eine fehlende Kante
        sieht aus wie Eigenstaendigkeit — genau der Fehler, den dieses Issue
        vermeiden will.

        Drei Versuche reichten nicht: der erste Vollabruf starb nach rund 1.000
        Anfragen an `Connection reset by peer`. Deshalb wird hier eine
        Untergrenze geprueft, keine feste Zahl."""
        import inspect
        n = inspect.signature(self.f._get).parameters["versuche"].default
        self.assertGreaterEqual(n, 6, "zu wenige Versuche fuer 1.500 Abrufe am Stueck")
        src = (ROOT / "scripts" / "fetch_gleif_relations.py").read_text(encoding="utf-8")
        self.assertIn("time.sleep(2 ** i)", src)
        for code in ("429", "500", "503"):
            self.assertIn(code, src)

    def test_three_states_are_distinguished(self):
        """parent / exception / nichts_gemeldet — zwei davon zusammenzufassen
        waere der Verlust der ganzen Unterscheidung."""
        src = (ROOT / "scripts" / "fetch_gleif_relations.py").read_text(encoding="utf-8")
        for zustand in ('"parent"', '"exception"', '"nichts_gemeldet"'):
            self.assertIn(zustand, src)

    def test_the_run_is_idempotent(self):
        """474 Abrufe sind hoeflich nur einmal. Ein zweiter Lauf darf nur
        Neuzugaenge holen."""
        src = (ROOT / "scripts" / "fetch_gleif_relations.py").read_text(encoding="utf-8")
        self.assertIn("offen = [l for l in leis if l not in schon]", src)
        self.assertIn("for lei in offen:", src)
        self.assertIn("--refresh", src)

    def test_a_crash_does_not_discard_what_was_already_fetched(self):
        """Das Versprechen „holt nur Neuzugaenge" ist wertlos, wenn der Lauf
        erst am Ende schreibt: der erste Vollabruf lief 30 Minuten und starb
        ohne eine einzige Zeile Ergebnis. Zwischenstand und Abbruchsicherung
        sind deshalb Teil der Zusage, nicht Komfort."""
        src = (ROOT / "scripts" / "fetch_gleif_relations.py").read_text(encoding="utf-8")
        self.assertIn("if neu % checkpoint == 0:", src)
        rumpf = src.split("def build(", 1)[1]
        ausser = rumpf.split("except Exception as e:", 1)
        self.assertEqual(len(ausser), 2, "kein Abbruchzweig in build()")
        vor_raise = ausser[1].split("raise", 1)[0]
        self.assertIn("_schreibe(zeilen)", vor_raise,
                      "Abbruch wirft weiter, ohne den Zwischenstand zu sichern")


class TabelleTest(unittest.TestCase):
    def setUp(self):
        self.rows = zeilen()
        if not self.rows:
            self.skipTest("lei_relations.csv nicht abgerufen")
        with META.open(encoding="utf-8") as fh:
            self.bestand = {r["lei"] for r in csv.DictReader(fh)}

    def test_every_institution_has_a_row(self):
        """Ein fehlendes Institut waere ein stiller blinder Fleck im Graphen."""
        fehlend = sorted(self.bestand - {r["lei"] for r in self.rows})
        self.assertEqual(fehlend, [], f"ohne Beziehungszeile: {fehlend[:5]}")

    def test_a_parent_and_a_reason_never_coexist(self):
        """Entweder GLEIF kennt die Mutter, oder es nennt einen Grund. Beides
        zugleich hiesse, dass wir die Antwort falsch gelesen haben."""
        for r in self.rows:
            with self.subTest(lei=r["lei"]):
                if r["direct_parent_lei"]:
                    self.assertEqual(r["direct_parent_reason"], "")
                    self.assertEqual(r["direct_parent_status"], "parent")

    def test_no_institution_is_its_own_parent(self):
        for r in self.rows:
            with self.subTest(lei=r["lei"]):
                self.assertNotEqual(r["direct_parent_lei"], r["lei"])
                self.assertNotEqual(r["ultimate_parent_lei"], r["lei"])

    def test_the_order_is_stable(self):
        leis = [r["lei"] for r in self.rows]
        self.assertEqual(leis, sorted(leis))

    def test_the_edges_inside_our_population_are_the_point(self):
        """Nur dort tritt Doppelzaehlung real auf. Faende sich keine einzige,
        waere der Abruf vermutlich kaputt — gemessen sind es rund 14 %."""
        kanten = [r for r in self.rows if r["direct_parent_lei"] in self.bestand]
        self.assertGreater(len(kanten), 0,
                           "keine einzige Konzernkante im Bestand — Abruf pruefen")


if __name__ == "__main__":
    unittest.main(verbosity=2)
