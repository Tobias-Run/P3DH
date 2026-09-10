"""Kuerzel-Suche: „BBVA" findet „Banco Bilbao Vizcaya Argentaria, S.A.".

## Warum die Teilstringsuche das nicht leisten kann

Institute sind unter ihrem Kuerzel bekannt, im Bestand stehen sie unter ihrem
Registernamen. „BBVA" kommt in „Banco Bilbao Vizcaya Argentaria, S.A." nicht als
zusammenhaengende Zeichenkette vor — die Buchstaben sind ueber vier Woerter
verteilt.

## Warum kein vorab erzeugtes Akronym

Der naheliegende Weg waere, je Institut ein Akronym zu bilden. Dafuer muss man
die Rechtsform abschneiden, und daran scheitert es: gemessen ueber die 508
Institute liefert eine solche Regel fuer BBVA **„BBVASA"** statt „BBVA", weil
„S.A." als zwei Tokens zerfaellt. Dazu kollidierten 38 Akronyme — unter „SB"
lagen sieben verschiedene Banken.

## Die Regel

Gefragt wird zur Suchzeit, ob die Eingabe ein PRAEFIX der Wortanfaenge ist:

    Banco Bilbao Vizcaya Argentaria, S.A.  ->  bbvasa
    "bbva" ist ein Praefix davon           ->  Treffer

Das umgeht die Rechtsform, weil ihr Rest einfach hinter dem Praefix liegt.
"""

from pathlib import Path
import csv
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent
VIEWER = ROOT / "processed" / "zweig_a" / "viewer_json.html"
META = ROOT / "processed" / "entity_meta.csv"


def initialen(name):
    """Die JS-Regel aus `initialenVon`, hier nachgebildet."""
    return "".join(w[0] for w in re.findall(r"[0-9A-Za-zÀ-ÿ&]+", name)).lower()


def kuerzel_trifft(name, q):
    """Nur die Kuerzel-Regel — `kuerzelTrifft` im Viewer."""
    k = re.sub(r"[^0-9a-zà-ÿ&]", "", q.lower())
    return len(k) >= 2 and initialen(name).startswith(k)


def trifft(name, q):
    """Die Suchbedingung des Viewers: Teilstring ODER Kuerzel-Praefix."""
    return q.lower() in name.lower() or kuerzel_trifft(name, q)


def namen():
    if not META.exists():
        return []
    with META.open(encoding="utf-8") as fh:
        return [r["name"] for r in csv.DictReader(fh) if r["name"]]


class RegelTest(unittest.TestCase):
    def test_the_example_from_the_request(self):
        self.assertTrue(trifft("Banco Bilbao Vizcaya Argentaria, S.A.", "BBVA"))

    def test_the_legal_form_does_not_get_in_the_way(self):
        """Genau hier scheitert ein vorab gebildetes Akronym: es liefert
        „BBVASA". Als Praefix gefragt stoert der Rest nicht."""
        self.assertEqual(initialen("Banco Bilbao Vizcaya Argentaria, S.A."), "bbvasa")
        self.assertTrue(trifft("Banco Bilbao Vizcaya Argentaria, S.A.", "bbva"))

    def test_dots_in_the_query_are_ignored(self):
        self.assertTrue(trifft("Banco Bilbao Vizcaya Argentaria, S.A.", "B.B.V.A."))

    def test_a_single_letter_is_not_a_kuerzel(self):
        """Sonst waere jeder Name mit passendem Anfangsbuchstaben ein Treffer.

        Geprueft wird die Kuerzel-Regel ALLEIN: als Teilstring trifft „b" hier
        selbstverstaendlich, und das soll es auch."""
        self.assertFalse(kuerzel_trifft("Banco Bilbao Vizcaya Argentaria, S.A.", "b"))
        self.assertTrue(trifft("Banco Bilbao Vizcaya Argentaria, S.A.", "b"),
                        "die Teilstringsuche muss unberuehrt bleiben")

    def test_substring_search_still_works(self):
        for name, q in (("Deutsche Bank AG", "deutsche"),
                        ("KBC Groupe", "kbc"),
                        ("BNP Paribas Fortis", "paribas")):
            with self.subTest(q=q):
                self.assertTrue(trifft(name, q))

    def test_it_is_a_prefix_not_a_subsequence(self):
        """Eine Teilfolge-Regel wuerde „BVA" auf BBVA passen lassen und damit
        die Trefferliste fluten. Der Anfang muss stimmen."""
        self.assertFalse(kuerzel_trifft("Banco Bilbao Vizcaya Argentaria, S.A.", "bva"))

    def test_no_hit_is_invented(self):
        self.assertFalse(trifft("Deutsche Bank AG", "bbva"))


class BestandTest(unittest.TestCase):
    """Gegen die echten Institutsnamen — eine Regel, die nur an einem
    ausgedachten Beispiel funktioniert, ist keine."""

    def setUp(self):
        self.namen = namen()
        if not self.namen:
            self.skipTest("entity_meta.csv fehlt")

    def test_bbva_is_unambiguous_in_the_real_data(self):
        treffer = [n for n in self.namen if trifft(n, "BBVA")]
        self.assertEqual(len(treffer), 1, f"nicht eindeutig: {treffer}")
        self.assertIn("Bilbao", treffer[0])

    def test_a_known_acronym_finds_its_bank(self):
        treffer = [n for n in self.namen if trifft(n, "RBI")]
        self.assertTrue(any("Raiffeisen Bank International" in n for n in treffer),
                        f"RBI findet Raiffeisen Bank International nicht: {treffer}")

    def test_the_kuerzel_rule_does_not_flood_the_list(self):
        """Ein Kuerzel darf die Trefferliste nicht unbrauchbar machen. Gemessen
        bleiben die gaengigen Kuerzel weit unter einem Prozent des Bestands."""
        for q in ("BBVA", "RBI", "KBC"):
            with self.subTest(q=q):
                n = sum(1 for name in self.namen if trifft(name, q))
                self.assertLessEqual(n, 5, f"{q} liefert {n} Treffer")


class ViewerTest(unittest.TestCase):
    """Die Regel muss im Viewer auch angewandt werden."""

    def setUp(self):
        self.src = VIEWER.read_text(encoding="utf-8")

    def test_the_filter_asks_for_the_kuerzel(self):
        self.assertIn("kuerzelTrifft(name,f.q)", self.src,
                      "passFilters fragt die Kuerzel-Regel nicht — sie waere "
                      "definiert, aber wirkungslos")

    def test_the_substring_search_is_not_replaced(self):
        """Die Kuerzel-Suche kommt HINZU. Sie zu ersetzen naehme der Suche
        alles, was heute funktioniert (Land, Stichtag, LEI)."""
        self.assertIn("!hay.includes(f.q) && !kuerzelTrifft", self.src)

    def test_the_minimum_length_is_enforced_in_the_viewer(self):
        self.assertRegex(self.src, r"k\.length\s*>=\s*2")

    def test_the_placeholder_mentions_it(self):
        """Eine Suchfunktion, die niemand kennt, hilft nicht."""
        self.assertIn("Kürzel", self.src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
