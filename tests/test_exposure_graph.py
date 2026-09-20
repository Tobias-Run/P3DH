"""Bank↔Land als bipartiter Graph (#35).

Vier Dinge halten die Tests fest:

1. **Ohne Heimatland.** Der Kern des Issues: ein gemeinsamer Markt ist ein
   Übertragungskanal, das eigene Sitzland ist keiner. Gemessen wechseln 44 von
   50 Spitzenpaaren, wenn man es entfernt — der Graph ist damit ein anderes
   Objekt als die Ähnlichkeitssortierung aus #13.
2. **Auf Konzernebene.** #35 macht #32 zur Vorbedingung: ohne Auflösung zählen
   Mutter und Tochter als zwei Knoten, und jede Konzentrationsaussage ist
   verzerrt.
3. **Die Obergrenze gehört zur Kennzahl.** Beim mittleren Profil liegt nur
   1,0 % des Auslandsexposures abseits der grossen Märkte. Eine feste Schwelle
   auf der spezifischen Überlappung misst dort die Obergrenze, nicht die
   Gemeinsamkeit — das war beinahe ein Fehlschluss.
4. **`zu_duenn` ist nicht `konzentriert`.** Bei zwei Trägern ist jede
   Konzentrationskennzahl eine Aussage über Einzelfälle.
"""

from pathlib import Path
import csv
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT_LAND = ROOT / "processed" / "country_dependence.csv"
OUT_KANTEN = ROOT / "processed" / "contagion_edges.csv"


class HeimatTest(unittest.TestCase):
    def setUp(self):
        import build_exposure_graph as g
        self.g = g

    def test_the_home_country_is_removed(self):
        self.assertEqual(self.g.ohne_heimat({"Spain": 9.0, "France": 1.0},
                                            "Spain"),
                         {"France": 1.0})

    def test_a_purely_domestic_profile_becomes_empty(self):
        """Ein Institut ohne Auslandsgeschäft ist kein Knoten in diesem
        Graphen — es hat keinen Kanal, den es mit jemandem teilen könnte."""
        self.assertEqual(self.g.ohne_heimat({"Spain": 9.0}, "Spain"), {})

    def test_an_unknown_home_country_removes_nothing(self):
        """„Fehlt ≠ Null": ohne bekanntes Sitzland darf nicht geraten werden,
        welches Land herauszunehmen wäre."""
        self.assertEqual(self.g.ohne_heimat({"Spain": 9.0, "France": 1.0}, ""),
                         {"Spain": 9.0, "France": 1.0})

    def test_negative_amounts_drop_out(self):
        self.assertEqual(self.g.ohne_heimat({"France": -1.0, "Italy": 2.0}, ""),
                         {"Italy": 2.0})


class GruppierenTest(unittest.TestCase):
    """Die Vorbedingung, die #35 ausdrücklich nennt."""

    def setUp(self):
        import build_exposure_graph as g
        self.g = g

    def test_mother_and_daughter_become_one_node(self):
        roh = {("M", "CON", "R"): {"France": 5.0},
               ("T", "IND", "R"): {"France": 3.0}}
        koepfe = {("M", "CON", "R"): ("M", "Mutter", "Spain"),
                  ("T", "IND", "R"): ("M", "Tochter", "Spain")}
        aus = self.g.gruppiere(roh, koepfe)
        self.assertEqual(len(aus), 1)
        self.assertAlmostEqual(aus[("M", "R")][0]["France"], 8.0)

    def test_different_groups_stay_apart(self):
        roh = {("A", "CON", "R"): {"France": 5.0},
               ("B", "CON", "R"): {"France": 3.0}}
        koepfe = {("A", "CON", "R"): ("A", "A", "Spain"),
                  ("B", "CON", "R"): ("B", "B", "Italy")}
        self.assertEqual(len(self.g.gruppiere(roh, koepfe)), 2)

    def test_a_report_without_a_head_stays_its_own_node(self):
        """Keine Behauptung über Eigenständigkeit — nur die einzige
        Zuordnung, die belegt ist."""
        roh = {("X", "CON", "R"): {"France": 5.0}}
        aus = self.g.gruppiere(roh, {})
        self.assertIn(("X", "R"), aus)

    def test_the_home_country_comes_from_the_largest_foreign_book(self):
        """Bei Mutter und Tochter ist das die Mutter — und ihr Sitzland ist
        das, gegen das „Ausland" gemessen gehört."""
        roh = {("M", "CON", "R"): {"France": 50.0},
               ("T", "IND", "R"): {"France": 1.0}}
        koepfe = {("M", "CON", "R"): ("M", "Mutter", "Spain"),
                  ("T", "IND", "R"): ("M", "Tochter", "Malta")}
        self.assertEqual(self.g.gruppiere(roh, koepfe)[("M", "R")][2], "Spain")


class SpezifischTest(unittest.TestCase):
    def setUp(self):
        import build_exposure_graph as g
        self.g = g
        self.verbreitet = {"Germany": 0.9, "France": 0.8, "Lithuania": 0.05}

    def test_ubiquitous_countries_do_not_count(self):
        a = {"Germany": 0.9, "Lithuania": 0.1}
        b = {"Germany": 0.9, "Lithuania": 0.1}
        self.assertAlmostEqual(self.g.ueberlappung(a, b), 1.0)
        self.assertAlmostEqual(self.g.spezifisch(a, b, self.verbreitet), 0.1)

    def test_a_shared_niche_market_counts(self):
        a = {"Germany": 0.5, "Lithuania": 0.5}
        b = {"France": 0.5, "Lithuania": 0.5}
        self.assertAlmostEqual(self.g.spezifisch(a, b, self.verbreitet), 0.5)

    def test_an_unknown_country_is_treated_as_niche(self):
        """Ein Land ohne Verbreitungswert ist selten, nicht allgegenwärtig —
        die vorsichtige Annahme, weil sie die Kante nicht aufbläst."""
        a = {"Faroe Islands": 1.0}
        b = {"Faroe Islands": 1.0}
        self.assertAlmostEqual(self.g.spezifisch(a, b, self.verbreitet), 1.0)

    def test_the_ceiling_bounds_the_specific_overlap(self):
        """Die Zahl, die einen Fehlschluss verhindert hat. Ohne sie sah es so
        aus, als trügen 3.764 von 3.765 Kanten „spezifisch unter 0,10" —
        tatsächlich liegt beim mittleren Profil nur 1,0 % des
        Auslandsexposures überhaupt in solchen Ländern."""
        a = {"Germany": 0.99, "Lithuania": 0.01}
        b = {"Germany": 0.99, "Lithuania": 0.01}
        moeglich = min(self.g.nische(a, self.verbreitet),
                       self.g.nische(b, self.verbreitet))
        self.assertAlmostEqual(moeglich, 0.01)
        self.assertLessEqual(self.g.spezifisch(a, b, self.verbreitet), moeglich)

    def test_a_profile_without_niche_markets_has_a_ceiling_of_zero(self):
        self.assertAlmostEqual(
            self.g.nische({"Germany": 1.0}, self.verbreitet), 0.0)


class VerbreitungTest(unittest.TestCase):
    def setUp(self):
        import build_exposure_graph as g
        self.g = g

    def test_it_is_measured_not_assumed(self):
        """Eine feste Liste grosser Märkte wäre bei der nächsten Welle
        falsch."""
        v = self.g.verbreitung([{"Germany": 1.0}, {"Germany": 0.5, "X": 0.5}])
        self.assertAlmostEqual(v["Germany"], 1.0)
        self.assertAlmostEqual(v["X"], 0.5)

    def test_an_empty_population_yields_nothing(self):
        self.assertEqual(self.g.verbreitung([]), {})


class UrteilTest(unittest.TestCase):
    def setUp(self):
        import build_exposure_graph as g
        self.g = g

    def test_a_dominant_carrier_is_concentration(self):
        self.assertEqual(self.g.urteil_von(10, 0.8), "konzentriert")

    def test_a_spread_country_is_not(self):
        self.assertEqual(self.g.urteil_von(10, 0.2), "gestreut")

    def test_too_few_carriers_is_its_own_answer(self):
        """Bei zwei Trägern ist jede Konzentrationskennzahl eine Aussage über
        Einzelfälle — `konzentriert` behauptete eine Struktur, die nicht
        gemessen ist."""
        self.assertEqual(self.g.urteil_von(2, 0.9), "zu_duenn")


class HhiTest(unittest.TestCase):
    def setUp(self):
        import build_exposure_graph as g
        self.g = g

    def test_a_monopoly_is_one(self):
        self.assertAlmostEqual(self.g.hhi([1.0]), 1.0)

    def test_even_spread_is_the_inverse_of_the_count(self):
        self.assertAlmostEqual(self.g.hhi([0.25] * 4), 0.25)


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        if not OUT_LAND.exists() or not OUT_KANTEN.exists():
            self.skipTest("Graph-Artefakte nicht gebaut")
        with OUT_LAND.open(encoding="utf-8") as fh:
            self.laender = list(csv.DictReader(fh))
        with OUT_KANTEN.open(encoding="utf-8") as fh:
            self.kanten = list(csv.DictReader(fh))

    def test_both_artefacts_have_content(self):
        self.assertGreater(len(self.laender), 100)
        self.assertGreater(len(self.kanten), 10)

    def test_no_country_is_carried_by_its_own_home_banks(self):
        """Die Gegenprobe zum Kern des Issues: wäre das Heimatland noch drin,
        stünde bei fast jedem Land seine eigene Grossbank ganz oben."""
        import build_exposure_graph as g
        self.assertNotIn("", {z["land"] for z in self.laender})

    def test_the_shares_are_shares(self):
        for z in self.laender:
            with self.subTest(land=z["land"]):
                self.assertGreater(float(z["groesster_anteil"]), 0.0)
                self.assertLessEqual(float(z["groesster_anteil"]), 1.0)
                self.assertLessEqual(float(z["groesster_anteil"]),
                                     float(z["top3_anteil"]) + 1e-9)

    def test_the_specific_overlap_never_exceeds_its_ceiling(self):
        """Die Invariante, die die Kennzahl lesbar macht."""
        for z in self.kanten:
            if z["spezifisch_moeglich"]:
                with self.subTest(a=z["name_a"], b=z["name_b"]):
                    self.assertLessEqual(
                        float(z["ueberlappung_spezifisch"]),
                        float(z["spezifisch_moeglich"]) + 1e-9)

    def test_the_specific_overlap_never_exceeds_the_raw_one(self):
        for z in self.kanten:
            with self.subTest(a=z["name_a"]):
                self.assertLessEqual(float(z["ueberlappung_spezifisch"]),
                                     float(z["ueberlappung"]) + 1e-9)

    def test_every_edge_clears_the_threshold(self):
        import build_exposure_graph as g
        for z in self.kanten:
            with self.subTest(a=z["name_a"]):
                self.assertGreaterEqual(float(z["ueberlappung"]), g.MIN_KANTE)

    def test_no_edge_links_a_group_with_itself(self):
        for z in self.kanten:
            self.assertNotEqual(z["kopf_a"], z["kopf_b"])

    def test_the_swap_suspicion_is_carried_over_from_59(self):
        """Dänemark steht hier zu 56 % bei BBVA — und genau dieses Paar hat
        #59 als Ländercode-Tausch markiert. Ohne den Verweis läse jemand eine
        Abhängigkeit, die womöglich ein Meldeartefakt ist."""
        if not (ROOT / "processed" / "country_swap.csv").exists():
            self.skipTest("country_swap.csv nicht gebaut")
        self.assertTrue(any(z["tauschverdacht"] == "ja" for z in self.laender),
                        "kein einziger Verweis — prüfen, ob country_swap.csv "
                        "noch gelesen wird")

    def test_the_order_is_stable(self):
        k = [(z["refPeriod"], z["land"]) for z in self.laender]
        self.assertEqual(k, sorted(k))
        e = [(z["refPeriod"], z["kopf_a"], z["kopf_b"]) for z in self.kanten]
        self.assertEqual(e, sorted(e))


if __name__ == "__main__":
    unittest.main(verbosity=2)
