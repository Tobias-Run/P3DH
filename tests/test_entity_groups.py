"""Konzernzuordnung und Peer-Überschneidung (#32 Punkte 3 und 5).

Die Tests halten drei Dinge fest:

1. **`unbekannt` ist nicht `eigen`.** #32 sagt es selbst: „Ein fehlender Parent
   ist kein Beleg für Eigenständigkeit." GLEIF trennt `NO_KNOWN_PERSON` („es
   gibt keine") von `NO_LEI` („wir kennen sie nicht"), und nur das erste ist
   eine Auskunft.

2. **Geschwister zählen.** Die erste Messung fand nur Mutter-Tochter-Paare —
   sieben Stück, ein Randeffekt. Zwei Töchter derselben Mutter sind aber
   ebenfalls derselbe Konzern in derselben Verteilung, und richtig gezählt
   verliert die Klasse „Large subsidiaries" 63 % ihrer effektiven Stichprobe.

3. **Unbekannte werden nicht verschmolzen.** Zwei Institute ohne belegten Kopf
   sind nicht dadurch verwandt, dass beide unbekannt sind — sonst schrumpfte
   die effektive Stichprobe aus einem Mangel an Daten statt aus einem Befund.
"""

from pathlib import Path
import csv
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "entity_groups.csv"


class GleifTest(unittest.TestCase):
    def setUp(self):
        import build_entity_groups as b
        self.b = b
        self.p = Path(tempfile.mkdtemp()) / "rel.csv"

    def _schreib(self, zeilen):
        self.p.write_text(
            "lei,ultimate_parent_lei,ultimate_parent_status,"
            "ultimate_parent_reason\n" + "".join(zeilen), encoding="utf-8")

    def test_a_recorded_parent_is_a_group_head(self):
        self._schreib(["A,M,parent,\n"])
        self.assertEqual(self.b.lade_gleif(self.p)["A"], ("konzern", "M"))

    def test_no_known_person_means_its_own_head(self):
        self._schreib(["A,,exception,NO_KNOWN_PERSON\n"])
        self.assertEqual(self.b.lade_gleif(self.p)["A"], ("eigen", "A"))

    def test_no_lei_means_unknown_not_independent(self):
        """Der Unterschied, um den es #32 geht. `NO_LEI` heisst: es GIBT eine
        Mutter, sie hat nur keine LEI."""
        self._schreib(["A,,exception,NO_LEI\n"])
        self.assertEqual(self.b.lade_gleif(self.p)["A"], ("unbekannt", ""))

    def test_a_self_reference_is_no_parent(self):
        self._schreib(["A,A,parent,\n"])
        self.assertEqual(self.b.lade_gleif(self.p)["A"][0], "unbekannt")


class KopfTest(unittest.TestCase):
    def setUp(self):
        import build_entity_groups as b
        self.b = b

    def test_both_graphs_agreeing_is_the_strongest_case(self):
        kopf, quelle = self.b.kopf_von(
            "A", {"A": ("konzern", "M")}, {"A": ("M", "Mutter AG")})
        self.assertEqual((kopf, quelle), ("M", "beide"))

    def test_gleif_alone_still_answers(self):
        self.assertEqual(
            self.b.kopf_von("A", {"A": ("konzern", "M")}, {}), ("M", "gleif"))

    def test_the_ecb_hierarchy_answers_where_gleif_is_silent(self):
        """Die beiden Graphen beantworten verschiedene Fragen (#32/#42). Wo
        GLEIF nichts weiss, kann die EZB-Hierarchie den beaufsichtigten
        Gruppenkopf trotzdem kennen."""
        self.assertEqual(
            self.b.kopf_von("A", {"A": ("unbekannt", "")}, {"A": ("E", "EZB")}),
            ("E", "ezb"))

    def test_a_proven_own_head_is_not_unknown(self):
        self.assertEqual(
            self.b.kopf_von("A", {"A": ("eigen", "A")}, {}), ("A", "eigen"))

    def test_an_unknown_head_stays_empty(self):
        """Leer, nicht die eigene LEI: wer hier `A` einsetzte, machte aus
        „wir wissen es nicht" ein „es gibt keine Mutter"."""
        self.assertEqual(self.b.kopf_von("A", {}, {}), ("", "unbekannt"))


class UeberschneidungTest(unittest.TestCase):
    def setUp(self):
        import build_entity_groups as b
        self.b = b

    def _z(self, lei, kopf, gruppe="G"):
        return {"lei": lei, "bank_name": lei, "konzern_kopf": kopf,
                "peer_gruppe": gruppe, "peer_n": 0, "peer_effektiv": 0,
                "peer_konzernueberschneidung": "nein", "peer_verwandte": ""}

    def test_two_siblings_overlap(self):
        """Der Fall, den die erste Messung übersehen hat: keiner ist die
        Mutter des anderen, und es ist trotzdem derselbe Konzern."""
        zs = self.b.ueberschneidungen([self._z("A", "M"), self._z("B", "M")])
        self.assertEqual([z["peer_konzernueberschneidung"] for z in zs],
                         ["ja", "ja"])

    def test_different_heads_do_not_overlap(self):
        zs = self.b.ueberschneidungen([self._z("A", "M1"), self._z("B", "M2")])
        self.assertTrue(all(z["peer_konzernueberschneidung"] == "nein"
                            for z in zs))

    def test_two_unknown_heads_are_not_related(self):
        """Sonst schrumpfte die effektive Stichprobe aus einem Mangel an
        Daten statt aus einem Befund — genau verkehrt herum."""
        zs = self.b.ueberschneidungen([self._z("A", ""), self._z("B", "")])
        self.assertTrue(all(z["peer_konzernueberschneidung"] == "nein"
                            for z in zs))
        self.assertEqual(zs[0]["peer_effektiv"], 2)

    def test_the_effective_size_counts_groups_not_reports(self):
        """Die Zahl, um die es geht: drei Reports, zwei Konzerne."""
        zs = self.b.ueberschneidungen(
            [self._z("A", "M"), self._z("B", "M"), self._z("C", "X")])
        self.assertEqual(zs[0]["peer_n"], 3)
        self.assertEqual(zs[0]["peer_effektiv"], 2)

    def test_an_unknown_head_counts_as_its_own_unit(self):
        zs = self.b.ueberschneidungen(
            [self._z("A", "M"), self._z("B", "M"), self._z("C", "")])
        self.assertEqual(zs[0]["peer_effektiv"], 2)

    def test_peer_groups_are_kept_apart(self):
        zs = self.b.ueberschneidungen(
            [self._z("A", "M", "G1"), self._z("B", "M", "G2")])
        self.assertTrue(all(z["peer_konzernueberschneidung"] == "nein"
                            for z in zs))

    def test_a_relative_is_named(self):
        """Ohne den Namen ist die Markierung nicht nachprüfbar."""
        zs = self.b.ueberschneidungen([self._z("A", "M"), self._z("B", "M")])
        self.assertEqual(zs[0]["peer_verwandte"], "B")


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        if not OUT.exists():
            self.skipTest("entity_groups.csv nicht gebaut")
        with OUT.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))

    def test_the_artefact_has_content(self):
        self.assertGreater(len(self.rows), 500)

    def test_an_unknown_head_is_never_filled_in(self):
        for r in self.rows:
            if r["kopf_quelle"] == "unbekannt":
                with self.subTest(bank=r["bank_name"]):
                    self.assertEqual(r["konzern_kopf"], "")

    def test_a_proven_head_is_always_present(self):
        for r in self.rows:
            if r["kopf_quelle"] != "unbekannt":
                with self.subTest(bank=r["bank_name"]):
                    self.assertTrue(r["konzern_kopf"])

    def test_the_effective_size_never_exceeds_the_reported_one(self):
        for r in self.rows:
            with self.subTest(gruppe=r["peer_gruppe"]):
                self.assertLessEqual(int(r["peer_effektiv"]), int(r["peer_n"]))
                self.assertGreater(int(r["peer_effektiv"]), 0)

    def test_the_large_subsidiaries_class_really_is_thinner(self):
        """Der Befund von #32 Punkt 3. Bricht er weg, misst die Spalte nichts
        mehr — und der Benchmark behauptet wieder mehr Beobachtungen, als er
        unabhängige hat."""
        eng = [r for r in self.rows
               if int(r["peer_n"]) > 20
               and int(r["peer_effektiv"]) < int(r["peer_n"]) * 0.8]
        self.assertTrue(eng, "keine einzige verdünnte Peer-Gruppe — prüfen, "
                             "ob der Konzerngraph noch gelesen wird")
        self.assertTrue(any("subsidiaries" in r["peer_gruppe"] for r in eng))

    def test_overlap_and_relatives_agree(self):
        for r in self.rows:
            with self.subTest(bank=r["bank_name"]):
                self.assertEqual(r["peer_konzernueberschneidung"] == "ja",
                                 bool(r["peer_verwandte"]))

    def test_the_order_is_stable(self):
        k = [(r["refPeriod"], r["lei"], r["scope"]) for r in self.rows]
        self.assertEqual(k, sorted(k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
