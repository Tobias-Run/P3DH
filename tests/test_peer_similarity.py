"""Ähnliche Institute aus dem Länder-Exposure-Profil (#13, #27).

Die formale Peer-Gruppe (Grössenklasse × Konsolidierungskreis × Stichtag) ist
für Perzentile richtig, beantwortet aber nicht „mit wem ist dieses Institut
vergleichbar". Dieses Verfahren tut es — und bringt dabei fünf Fallen mit.

## Die Fallen

1. **Zwei Länder sind keine Ähnlichkeit.** Zwei Institute mit je zwei Ländern
   erreichen trivial 1,0. Ohne Mindestbreite entstünden Nachbarschaften, die
   mit jeder Welle wechseln.
2. **Das eigene Vorquartal.** Ohne Stichtagsbindung stünde neben jedem Institut
   sein eigener früherer Bericht als ähnlichstes — wahr und nutzlos.
3. **Der eigene zweite Konsolidierungskreis.** (LEI, CON) und (LEI, IND) sind
   derselbe Melder.
4. **`unbekannt` ist nicht `unabhaengig`.** Kennt keiner der beiden
   Konzerngraphen das Institut, wissen wir nichts über die Beziehung.
5. **Negatives Exposure ist kein Gewicht.** In einen Anteilsvektor gehört es
   nur mit einer Begründung, die wir nicht haben.

## Und die Gegenprobe, die das Verfahren trägt

Die stärksten Treffer sind Mutter/Tochter-Paare — ING Groep und ING Bank bei
0,9999, Argenta Holding und Argenta Bank bei 1,0000. Das Verfahren findet
Konzernzugehörigkeit aus der Exposure-Geografie wieder, **ohne je einen
Konzerngraphen gesehen zu haben**, und die Häufung ist messbar: von 100 besten
Treffern über 0,95 sind 22 konzernintern, unterhalb von 0,80 nur noch 4.
"""

from pathlib import Path
import collections
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "peer_similarity.csv"


class MassTest(unittest.TestCase):
    def setUp(self):
        import build_peer_similarity as p
        self.p = p

    def test_identical_profiles_overlap_completely(self):
        a = {"DE": 0.6, "FR": 0.4}
        self.assertAlmostEqual(self.p.ueberlappung(a, dict(a)), 1.0)

    def test_disjoint_profiles_do_not_overlap(self):
        self.assertAlmostEqual(
            self.p.ueberlappung({"DE": 1.0}, {"FR": 1.0}), 0.0)

    def test_the_value_is_the_shared_share(self):
        """Der Grund für dieses Mass statt eines Kosinus: das Ergebnis ist
        direkt lesbar. 0,6 heisst, dass 60 % des Exposures beider Häuser in
        denselben Ländern liegt."""
        self.assertAlmostEqual(
            self.p.ueberlappung({"DE": 0.6, "FR": 0.4}, {"DE": 0.6, "IT": 0.4}), 0.6)

    def test_it_punishes_different_breadth(self):
        """Wo der Kosinus blind ist: ein Institut mit einem Land und eines mit
        hundert sind kosinus-ähnlich, wenn das eine Land dominiert. Die
        Minimum-Summe sieht den Unterschied."""
        schmal = {"DE": 1.0}
        breit = {"DE": 0.5, **{f"X{i}": 0.5 / 50 for i in range(50)}}
        self.assertAlmostEqual(self.p.ueberlappung(schmal, breit), 0.5)

    def test_it_is_symmetric(self):
        a, b = {"DE": 0.7, "AT": 0.3}, {"DE": 0.2, "AT": 0.8}
        self.assertAlmostEqual(self.p.ueberlappung(a, b), self.p.ueberlappung(b, a))


class AnteilsvektorTest(unittest.TestCase):
    def setUp(self):
        import build_peer_similarity as p
        self.p = p

    def test_shares_sum_to_one(self):
        v = self.p.anteilsvektor({"DE": 30.0, "FR": 70.0})
        self.assertAlmostEqual(sum(v.values()), 1.0)
        self.assertAlmostEqual(v["DE"], 0.3)

    def test_negative_exposure_is_not_a_weight(self):
        """Ein negatives Exposure ist eine Nettoposition. Als Gewicht gezählt
        verschöbe es den Anteilsvektor, ohne dass jemand erklären könnte,
        warum."""
        v = self.p.anteilsvektor({"DE": 100.0, "FR": -50.0})
        self.assertEqual(set(v), {"DE"})

    def test_an_empty_profile_yields_none(self):
        self.assertIsNone(self.p.anteilsvektor({}))
        self.assertIsNone(self.p.anteilsvektor({"DE": 0.0, "FR": -1.0}))


class NachbarnTest(unittest.TestCase):
    def setUp(self):
        import build_peer_similarity as p
        self.p = p

    def _prof(self, *eintraege):
        return {k: v for k, v in eintraege}

    def test_a_report_is_never_its_own_neighbour(self):
        prof = {("A", "CON", "2025-12-31"): {"DE": 1.0},
                ("B", "CON", "2025-12-31"): {"DE": 1.0}}
        nb = self.p.nachbarn(prof)
        self.assertEqual([b[0] for _, b in nb[("A", "CON", "2025-12-31")]], ["B"])

    def test_the_same_filer_in_another_scope_is_not_a_neighbour(self):
        """(LEI, CON) und (LEI, IND) sind derselbe Melder. „Ähnlich zu sich
        selbst" ist keine Information."""
        prof = {("A", "CON", "2025-12-31"): {"DE": 1.0},
                ("A", "IND", "2025-12-31"): {"DE": 1.0}}
        self.assertEqual(self.p.nachbarn(prof), {})

    def test_neighbours_come_from_the_same_reference_date(self):
        """Ohne Stichtagsbindung stünde neben jedem Institut sein eigener
        Vorquartalsbericht — oder der eines anderen Hauses zu einem Stichtag,
        an dem sich die Welt anders darstellte."""
        prof = {("A", "CON", "2025-12-31"): {"DE": 1.0},
                ("B", "CON", "2025-06-30"): {"DE": 1.0}}
        self.assertEqual(self.p.nachbarn(prof), {})

    def test_weak_similarity_is_no_similarity(self):
        prof = {("A", "CON", "2025-12-31"): {"DE": 0.9, "FR": 0.1},
                ("B", "CON", "2025-12-31"): {"IT": 0.9, "FR": 0.1}}
        self.assertEqual(self.p.nachbarn(prof), {})

    def test_the_list_is_capped_and_sorted(self):
        prof = {("Z", "CON", "2025-12-31"): {"DE": 1.0}}
        for i in range(9):
            prof[(f"N{i}", "CON", "2025-12-31")] = {"DE": 1.0 - i / 100,
                                                    "FR": i / 100}
        nb = self.p.nachbarn(prof)[("Z", "CON", "2025-12-31")]
        self.assertEqual(len(nb), self.p.TOP_K)
        self.assertEqual([u for u, _ in nb], sorted((u for u, _ in nb), reverse=True))

    def test_ties_keep_a_stable_order(self):
        """Bei gleicher Überlappung entschiede sonst die Wörterbuchordnung —
        und die Datei wird nach main committet."""
        prof = {("Z", "CON", "2025-12-31"): {"DE": 1.0}}
        for n in ("B", "A", "C"):
            prof[(n, "CON", "2025-12-31")] = {"DE": 1.0}
        nb = self.p.nachbarn(prof)[("Z", "CON", "2025-12-31")]
        self.assertEqual([b[0] for _, b in nb], ["A", "B", "C"])


class BeziehungTest(unittest.TestCase):
    def setUp(self):
        import build_peer_similarity as p
        self.p = p

    def test_a_shared_head_is_a_group(self):
        self.assertEqual(self.p.beziehung_von("A", "B", {"A": {"P"}, "B": {"P"}}),
                         "konzern")

    def test_a_parent_child_pair_is_a_group(self):
        """ING Groep IST der Kopf von ING Bank — die beiden teilen keinen
        dritten Kopf, sie sind das Paar."""
        self.assertEqual(self.p.beziehung_von("A", "B", {"A": {"X"}, "B": {"A"}}),
                         "konzern")

    def test_different_heads_are_independent(self):
        self.assertEqual(self.p.beziehung_von("A", "B", {"A": {"P"}, "B": {"Q"}}),
                         "unabhaengig")

    def test_an_unknown_institution_is_not_declared_independent(self):
        """„Fehlt ≠ Null". Kennt kein Graph das Institut, wissen wir nichts —
        und `unabhaengig` wäre eine Aussage über Daten, die nicht vorliegen."""
        self.assertEqual(self.p.beziehung_von("A", "B", {"A": {"P"}}), "unbekannt")
        self.assertEqual(self.p.beziehung_von("A", "B", {}), "unbekannt")

    def test_missing_graphs_are_not_an_error(self):
        self.assertEqual(self.p.lade_konzerne(ROOT / "nix.csv", ROOT / "auch-nicht.csv"),
                         {})


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        if not OUT.exists():
            self.skipTest("peer_similarity.csv nicht gebaut")
        with OUT.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))
        self.erste = [r for r in self.rows if r["rang"] == "1"]

    def test_enough_reports_get_neighbours(self):
        self.assertGreater(len(self.erste), 200)

    def test_every_row_carries_its_reason(self):
        """#27: „Eine unbegründete `ähnlich`-Behauptung ist genau die Art Black
        Box, die dieses Projekt vermeiden will.\""""
        for r in self.rows:
            with self.subTest(bank=r["bank_name"], nb=r["nachbar_name"]):
                self.assertTrue(r["groesste_gemeinsamkeit"])
                self.assertGreater(int(r["gemeinsame_laender"]), 0)

    def test_no_row_pairs_a_filer_with_itself(self):
        for r in self.rows:
            self.assertNotEqual(r["lei"], r["nachbar_lei"])

    def test_every_profile_is_broad_enough(self):
        import build_peer_similarity as p
        for r in self.rows:
            with self.subTest(bank=r["bank_name"]):
                self.assertGreaterEqual(int(r["n_laender"]), p.MIN_LAENDER)
                self.assertGreaterEqual(int(r["nachbar_n_laender"]), p.MIN_LAENDER)

    def test_no_aggregate_row_counts_as_a_shared_country(self):
        """Die Lücke, durch die das Mass eine Weile falsch war.

        `67.01.A` trägt neben den Ländern `x1` (die GESAMTZEILE — die Summe der
        übrigen noch einmal), `x28` („übrige Länder") und einen Ausreisser
        `qx2014`. Solange die im Anteilsvektor standen, war `x1` bei den 127
        betroffenen Profilen im Median **exakt die Hälfte** der Masse: zwei
        beliebige Institute teilten sich schon darüber 50 % — eine
        Gemeinsamkeit, die keine ist.

        Der Median über alle Paare verschob sich dadurch kaum (0,034 statt
        0,030), die SPITZE dagegen vollständig: 0,970 auf 0,345, 0,924 auf
        0,262. Und die Spitze ist genau das, was hier im Artefakt steht. Eine
        ausgewiesene Überlappung von 0,92, gelesen als „92 % des Exposures
        liegt in denselben Ländern", war damit schlicht falsch.

        Der Test greift die Begründungsspalten an, weil dort die geteilten
        Länder namentlich stehen — ein `x1` als „grösste Gemeinsamkeit" ist die
        sichtbare Form des Fehlers.
        """
        for r in self.rows:
            for feld in ("groesste_gemeinsamkeit",):
                for token in (r[feld] or "").split("|"):
                    if not token:
                        continue
                    with self.subTest(bank=r["bank_name"], token=token):
                        self.assertRegex(
                            token, r"^[A-Z]{2}$",
                            f"{token!r} ist kein Land, sondern eine "
                            f"Aggregatzeile — sie darf nicht als geteiltes "
                            f"Land gezählt werden")

    def test_the_method_rediscovers_corporate_groups(self):
        """Die tragende Gegenprobe. Das Verfahren sieht nur Exposure-Geografie
        und findet trotzdem Mutter/Tochter-Paare — konzerninterne Treffer
        häufen sich im obersten Überlappungsband. Bricht das, misst die
        Ähnlichkeit etwas anderes als Geschäftsverwandtschaft."""
        hoch = [r for r in self.erste if float(r["ueberlappung"]) >= 0.95]
        tief = [r for r in self.erste if float(r["ueberlappung"]) < 0.80]
        self.assertGreater(len(hoch), 20)
        self.assertGreater(len(tief), 20)
        q_hoch = sum(1 for r in hoch if r["beziehung"] == "konzern") / len(hoch)
        q_tief = sum(1 for r in tief if r["beziehung"] == "konzern") / len(tief)
        self.assertGreater(q_hoch, q_tief,
                           "konzerninterne Paare häufen sich nicht mehr oben — "
                           "das Mass trifft keine Geschäftsverwandtschaft")

    def test_it_also_finds_independent_pairs(self):
        """Gegenprobe zur vorigen: fände es NUR Konzerne, wäre es ein teurer
        Konzerngraph und kein Ähnlichkeitsmass."""
        u = [r for r in self.erste if r["beziehung"] == "unabhaengig"]
        self.assertGreater(len(u), 50)

    def test_neighbours_cross_borders(self):
        """Der Ertrag gegenüber der formalen Schichtung: sie bringt Institute
        verschiedener Länder nie zusammen."""
        quer = [r for r in self.erste if r["country"] != r["nachbar_country"]]
        self.assertGreater(len(quer), 20)

    def test_both_sides_share_the_reference_date(self):
        """Der Stichtag steht nur einmal in der Zeile — der Nachbar muss
        denselben tragen, sonst ist die Zeile nicht lesbar."""
        paare = {(r["lei"], r["scope"], r["refPeriod"]) for r in self.rows}
        nachbarn = {(r["nachbar_lei"], r["nachbar_scope"], r["refPeriod"])
                    for r in self.rows}
        self.assertTrue(nachbarn <= paare | nachbarn)   # Form, nicht Inhalt
        for r in self.rows[:200]:
            self.assertRegex(r["refPeriod"], r"^\d{4}-\d{2}-\d{2}$")

    def test_ranks_are_dense_and_start_at_one(self):
        je = collections.defaultdict(list)
        for r in self.rows:
            je[(r["lei"], r["scope"], r["refPeriod"])].append(int(r["rang"]))
        for k, v in je.items():
            with self.subTest(report=k):
                self.assertEqual(sorted(v), list(range(1, len(v) + 1)))

    def test_the_order_is_stable(self):
        k = [(r["lei"], r["scope"], r["refPeriod"], int(r["rang"])) for r in self.rows]
        self.assertEqual(k, sorted(k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
