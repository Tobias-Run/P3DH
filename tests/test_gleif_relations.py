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
        vermeiden will."""
        src = (ROOT / "scripts" / "fetch_gleif_relations.py").read_text(encoding="utf-8")
        self.assertIn("versuche=3", src)
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
        self.assertIn("if lei in schon:", src)
        self.assertIn("--refresh", src)


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
