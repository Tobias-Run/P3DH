"""Gruppen mit gemeinsamem Länder-Fussabdruck (#11, #13).

Die drei Wege, hier etwas zu finden, das keines ist, und je ein Test dagegen:

1. **Eine Kette als Block ausgeben.** Zusammenhangskomponenten auf einem
   Ähnlichkeitsgraphen verbinden A mit C über B, auch wenn A und C nichts
   gemeinsam haben. Die Kohäsion — die KLEINSTE paarweise Überlappung in der
   Gruppe — macht das sichtbar. Ohne sie sähe eine Kette aus wie ein Block.

2. **Ein Haus, das sich selbst ähnelt.** Die Einheit ist
   (LEI, scope, refPeriod). Ohne `MIN_INSTITUTE` bestand die Ausgabe beim
   ersten Lauf zu über der Hälfte aus einem einzigen Institut über mehrere
   Quartale — 37 von 69 „Gruppen".

3. **„Keine Mutter gemeldet" als „eigenständig" lesen.** Arbeitsprinzip 3.
   GLEIF trennt sauber zwischen „es gibt keine" (`NO_KNOWN_PERSON`) und „wir
   kennen sie nicht" (`NO_LEI`). Nur das erste ist eine Auskunft.
"""

from pathlib import Path
import csv
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "peer_clusters.csv"


class KomponentenTest(unittest.TestCase):
    def setUp(self):
        import build_peer_clusters as c
        self.c = c

    def test_a_connected_pair_is_one_group(self):
        self.assertEqual(self.c.komponenten(["a", "b"], {("a", "b")}),
                         [["a", "b"]])

    def test_an_isolated_node_forms_no_group(self):
        """Wer zu niemandem passt, gehört zu nichts — und das als Einzelgruppe
        zu führen suggerierte eine Zugehörigkeit, die es nicht gibt."""
        self.assertEqual(self.c.komponenten(["a", "b", "c"], {("a", "b")}),
                         [["a", "b"]])

    def test_a_chain_becomes_a_single_component(self):
        """Das ist keine Fehlfunktion, sondern die Eigenschaft, gegen die die
        Kohäsion antritt: A~B und B~C machen A, B, C zu EINER Komponente, auch
        wenn A und C sich fremd sind."""
        self.assertEqual(
            self.c.komponenten(["a", "b", "c"], {("a", "b"), ("b", "c")}),
            [["a", "b", "c"]])

    def test_the_order_depends_on_neither_the_edges_nor_the_nodes(self):
        """Sonst wechselten die Gruppennummern zwischen zwei Läufen, und ein
        Diff der Ausgabe wäre wertlos.

        Beide Eingaben werden verdreht, weil beide es könnten: `kanten` ist
        eine Menge (Iterationsreihenfolge nicht zugesichert), und die Knoten
        kommen aus einem Aufrufer, der sie irgendwann anders sortieren mag.
        """
        eins = self.c.komponenten(["a", "b", "c", "d", "e"],
                                  {("a", "b"), ("d", "e"), ("b", "c")})
        zwei = self.c.komponenten(["e", "c", "a", "d", "b"],
                                  {("b", "c"), ("a", "b"), ("e", "d")})
        self.assertEqual(eins, zwei)
        self.assertEqual(eins, [["a", "b", "c"], ["d", "e"]])

    def test_larger_groups_come_first(self):
        aus = self.c.komponenten(["a", "b", "c", "d", "e"],
                                 {("a", "b"), ("c", "d"), ("d", "e")})
        self.assertEqual([len(g) for g in aus], [3, 2])


class KohaesionTest(unittest.TestCase):
    def setUp(self):
        import build_peer_clusters as c
        self.c = c

    def test_a_block_keeps_its_cohesion(self):
        sim = {("a", "b"): 0.95, ("a", "c"): 0.93, ("b", "c"): 0.97}
        self.assertAlmostEqual(self.c.kohaesion(["a", "b", "c"], sim), 0.93)

    def test_a_chain_is_exposed_by_its_weakest_pair(self):
        """Der eigentliche Zweck. A und B hängen eng zusammen, B und C auch —
        A und C gar nicht. Ein Durchschnitt (0,63) sähe brauchbar aus; das
        Minimum zeigt, dass die Gruppe eine Aussage über den Weg ist."""
        sim = {("a", "b"): 0.95, ("b", "c"): 0.93, ("a", "c"): 0.02}
        self.assertAlmostEqual(self.c.kohaesion(["a", "b", "c"], sim), 0.02)

    def test_a_pair_that_never_overlapped_counts_as_zero(self):
        """Ein fehlendes Paar im Ähnlichkeitsindex heisst „Überlappung 0", nicht
        „unbekannt": die vollständige Matrix wird gerechnet, ein fehlender
        Eintrag ist also gemessene Null."""
        self.assertEqual(self.c.kohaesion(["a", "b"], {}), 0.0)


class TraegerschaftTest(unittest.TestCase):
    """Die Unterscheidung, an der #13 hängt."""

    def setUp(self):
        import build_peer_clusters as c
        self.c = c

    def test_one_shared_parent_is_a_rediscovered_group(self):
        """OTP Luxembourg und OTP banka d.d. — grenzüberschreitend und trotzdem
        keine Neuigkeit. Dass das Verfahren sie findet, ist eine
        Gültigkeitsprobe, kein Befund."""
        traeger = {"A": ("konzern", "M"), "B": ("konzern", "M")}
        self.assertEqual(self.c.traegerschaft({"A", "B"}, traeger),
                         ("konzern", 1))

    def test_two_different_parents_are_independent(self):
        traeger = {"A": ("konzern", "M1"), "B": ("konzern", "M2")}
        self.assertEqual(self.c.traegerschaft({"A", "B"}, traeger)[0],
                         "unabhaengig")

    def test_two_institutions_without_any_parent_are_independent(self):
        """`NO_KNOWN_PERSON` ist eine positive Auskunft: es GIBT keine Mutter.
        Zwei solche Häuser gehören belegt verschiedenen Trägern."""
        traeger = {"A": ("eigen", "A"), "B": ("eigen", "B")}
        self.assertEqual(self.c.traegerschaft({"A", "B"}, traeger)[0],
                         "unabhaengig")

    def test_an_unknown_parent_is_not_evidence_of_independence(self):
        """Arbeitsprinzip 3. Ein Haus mit belegtem Konzern und eines, dessen
        Mutter wir nicht kennen — das könnte dieselbe Gruppe sein. `konzern`
        wäre falsch, `unabhaengig` wäre es auch."""
        traeger = {"A": ("konzern", "M"), "B": ("unbekannt", "B")}
        self.assertEqual(self.c.traegerschaft({"A", "B"}, traeger)[0],
                         "ungeklaert")

    def test_all_unknown_is_unresolved_rather_than_independent(self):
        traeger = {"A": ("unbekannt", "A"), "B": ("unbekannt", "B")}
        self.assertEqual(self.c.traegerschaft({"A", "B"}, traeger)[0],
                         "ungeklaert")

    def test_an_unknown_alongside_two_proven_bearers_stays_independent(self):
        """Zwei belegt verschiedene Träger reichen — der Unbekannte kann daran
        nichts mehr ändern."""
        traeger = {"A": ("konzern", "M1"), "B": ("eigen", "B"),
                   "C": ("unbekannt", "C")}
        self.assertEqual(self.c.traegerschaft({"A", "B", "C"}, traeger)[0],
                         "unabhaengig")

    def test_an_institution_missing_from_the_graph_is_unknown(self):
        self.assertEqual(self.c.traegerschaft({"A", "B"}, {})[0], "ungeklaert")


class TraegerLadenTest(unittest.TestCase):
    def setUp(self):
        import build_peer_clusters as c
        self.c = c
        self.p = Path(tempfile.mkdtemp()) / "rel.csv"

    def _schreib(self, zeilen):
        self.p.write_text(
            "lei,ultimate_parent_lei,ultimate_parent_status,"
            "ultimate_parent_reason\n" + "".join(zeilen), encoding="utf-8")

    def test_a_recorded_parent_makes_it_a_group_member(self):
        self._schreib(["A,M,parent,\n"])
        self.assertEqual(self.c.lade_traeger(self.p), {"A": ("konzern", "M")})

    def test_no_known_person_is_proof_of_its_own_bearer(self):
        self._schreib(["A,,exception,NO_KNOWN_PERSON\n"])
        self.assertEqual(self.c.lade_traeger(self.p), {"A": ("eigen", "A")})

    def test_non_consolidating_counts_too(self):
        self._schreib(["A,,exception,NON_CONSOLIDATING\n"])
        self.assertEqual(self.c.lade_traeger(self.p)["A"][0], "eigen")

    def test_no_lei_means_there_IS_a_parent_we_cannot_name(self):
        """Der Unterschied, der Arbeitsprinzip 3 ausmacht. `NO_LEI` heisst: es
        gibt eine Mutter, sie hat nur keine LEI. Das als Eigenständigkeit zu
        werten wäre eine Aussage über Daten, die nicht vorliegen."""
        self._schreib(["A,,exception,NO_LEI\n"])
        self.assertEqual(self.c.lade_traeger(self.p), {"A": ("unbekannt", "A")})

    def test_non_public_is_unknown_as_well(self):
        self._schreib(["A,,exception,NON_PUBLIC\n"])
        self.assertEqual(self.c.lade_traeger(self.p)["A"][0], "unbekannt")

    def test_nothing_reported_is_unknown(self):
        self._schreib(["A,,nichts_gemeldet,\n"])
        self.assertEqual(self.c.lade_traeger(self.p)["A"][0], "unbekannt")

    def test_a_self_reference_is_not_a_parent(self):
        self._schreib(["A,A,parent,\n"])
        self.assertEqual(self.c.lade_traeger(self.p)["A"][0], "unbekannt")

    def test_a_missing_file_is_not_an_error(self):
        self.assertEqual(self.c.lade_traeger(self.p.parent / "gibtsnicht.csv"),
                         {})


class GemeinsameLaenderTest(unittest.TestCase):
    def setUp(self):
        import build_peer_clusters as c
        self.c = c

    def test_only_countries_every_member_reports_count(self):
        profile = {"a": {"DE": 0.5, "FR": 0.5}, "b": {"DE": 0.9, "IT": 0.1}}
        self.assertEqual(self.c.gemeinsame_laender(["a", "b"], profile), {"DE"})

    def test_a_third_member_can_only_shrink_the_set(self):
        profile = {"a": {"DE": 1.0}, "b": {"DE": 1.0}, "c": {"FR": 1.0}}
        self.assertEqual(
            self.c.gemeinsame_laender(["a", "b", "c"], profile), set())

    def test_an_unknown_member_does_not_empty_the_set(self):
        profile = {"a": {"DE": 1.0}, "b": {"DE": 1.0}}
        self.assertEqual(
            self.c.gemeinsame_laender(["a", "b", "x"], profile), {"DE"})


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        if not OUT.exists():
            self.skipTest("peer_clusters.csv nicht gebaut")
        with OUT.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))
        self.gruppen = {}
        for r in self.rows:
            self.gruppen.setdefault(r["gruppe"], []).append(r)

    def test_the_clustering_actually_produces_groups(self):
        """Eine Gruppierung ohne Gruppen liefe über nichts und meldete Erfolg."""
        self.assertGreater(len(self.gruppen), 5)

    def test_no_group_is_one_institution_across_quarters(self):
        """Der Fehler, der beim ersten Lauf 37 von 69 „Gruppen" ausmachte. Eine
        Bank ähnelt sich selbst — das ist eine Identität, keine Peer-Gruppe.

        Die Zwei steht hier als Zahl und NICHT als `c.MIN_INSTITUTE`. Gegen die
        Konstante geprüft wanderte der Test mit ihr mit: mit `MIN_INSTITUTE=1`
        hätte er weiter bestanden, während die Ausgabe wieder zur Hälfte aus
        Selbstähnlichkeiten bestand. Ein Test, der seinen eigenen Massstab vom
        Prüfling bezieht, prüft nichts.
        """
        for nr, zs in self.gruppen.items():
            with self.subTest(gruppe=nr):
                self.assertGreaterEqual(
                    len({z["lei"] for z in zs}), 2,
                    "eine Gruppe aus einem einzigen Institut ist dieselbe Bank "
                    "über mehrere Quartale, keine Peer-Gruppe")

    def test_the_recorded_institution_count_matches_the_rows(self):
        for nr, zs in self.gruppen.items():
            with self.subTest(gruppe=nr):
                self.assertEqual(int(zs[0]["institute"]),
                                 len({z["lei"] for z in zs}))

    def test_every_member_of_a_group_carries_the_same_group_facts(self):
        """Die Gruppenspalten sind je Gruppe konstant. Wichen sie ab, wäre
        nicht mehr entscheidbar, welcher Wert gilt."""
        for nr, zs in self.gruppen.items():
            for feld in ("groesse", "kohaesion", "traegerschaft",
                         "laender_gemeinsam", "grenzueberschreitend"):
                with self.subTest(gruppe=nr, feld=feld):
                    self.assertEqual(len({z[feld] for z in zs}), 1)

    def test_no_aggregate_row_is_reported_as_a_shared_country(self):
        """Derselbe Fehler wie in #13/#27: `x1` ist die Gesamtzeile, `x28` der
        Residualbucket. Als „gemeinsames Land" behaupteten sie eine Geografie,
        die es nicht gibt — und genau daran hing der einzige Cluster, der die
        These aus #13 zu stützen schien."""
        for r in self.rows:
            for token in (r["laender"] or "").split("|"):
                if token:
                    with self.subTest(token=token):
                        self.assertRegex(token, r"^[A-Z]{2}$")

    def test_cross_border_groups_are_not_silently_credited_to_the_thesis(self):
        """#13 erwartet Cluster, die nicht mit dem Heimatland zusammenfallen.
        Ein wiedergefundener Konzern erfüllt das formal und sagt nichts —
        deshalb muss die Trägerschaft danebenstehen."""
        for r in self.rows:
            if r["grenzueberschreitend"] == "ja":
                with self.subTest(bank=r["bank_name"]):
                    self.assertIn(r["traegerschaft"],
                                  ("konzern", "unabhaengig", "ungeklaert"))

    def test_a_cross_border_flag_needs_more_than_one_home_country(self):
        for r in self.rows:
            mehrere = len(r["heimatlaender"].split("|")) > 1
            with self.subTest(bank=r["bank_name"]):
                self.assertEqual(r["grenzueberschreitend"] == "ja", mehrere)

    def test_cohesion_never_exceeds_what_the_threshold_promises(self):
        """Die Kohäsion ist ein Minimum über Paare, von denen mindestens eines
        die Schwelle gerissen haben kann (Kette). Sie darf also darunter
        liegen — aber niemals über 1."""
        for nr, zs in self.gruppen.items():
            with self.subTest(gruppe=nr):
                self.assertLessEqual(float(zs[0]["kohaesion"]), 1.0)
                self.assertGreaterEqual(float(zs[0]["kohaesion"]), 0.0)

    def test_group_numbers_are_dense_and_start_at_one(self):
        nummern = sorted({int(n) for n in self.gruppen})
        self.assertEqual(nummern, list(range(1, len(nummern) + 1)))

    def test_the_order_is_stable(self):
        k = [(int(r["gruppe"]), r["lei"], r["scope"], r["refPeriod"])
             for r in self.rows]
        self.assertEqual(k, sorted(k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
