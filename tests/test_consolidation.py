"""Tochter gegen Mutter (#32 Punkt 4).

Die Prüfung war durch #83 blockiert, und mit Grund. Die Machbarkeitsprobe des
Issues fand

    Addiko Bank d.d. (IND)   1,4 Mrd  >  Addiko Bank AG (CON)  4.296 EUR

Das sieht aus wie ein Konsolidierungsfehler und ist ein **Skalenfehler**. Wer
solche Paare nicht aussortiert, veröffentlicht eine Liste von Verstössen, die
keine sind — und niemand kann sie von echten unterscheiden.

Die Tests halten deshalb drei Dinge fest:

1. Ein Report mit Skalenvorbehalt ist `nicht_pruefbar`, nicht `stimmig` und
   erst recht kein Befund. Beides wäre falsch, aber auf verschiedene Weise:
   `stimmig` behauptete eine bestandene Prüfung, die gar nicht lief.
2. Die Toleranzen sind da, weil CCyB1 nicht die Bilanz ist — ein Vergleich auf
   die zweite Nachkommastelle fände in jedem Paar etwas.
3. Direkte und oberste Mutter sind meist dieselbe LEI. Getrennt gezählt stünde
   jedes Paar zweimal da, und eine doppelte Zeile ist keine zweite Beobachtung.
"""

from pathlib import Path
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "consolidation_check.csv"


def zeile(betrag, vorbehalt="", name="X"):
    return {"total_exposure_eur": str(betrag), "vorbehalt": vorbehalt,
            "bank_name": name, "x28_share": "0.0"}


class BrauchbarTest(unittest.TestCase):
    def setUp(self):
        import check_consolidation as c
        self.c = c

    def test_a_scale_reservation_disqualifies_the_amount(self):
        ok, grund = self.c.brauchbar(zeile(4296.63, "skala"))
        self.assertFalse(ok)
        self.assertIn("skala", grund)

    def test_the_template_local_one_too(self):
        """`unter_trea` kam mit #83 dazu und meint denselben Schaden für diesen
        Vergleich: der absolute Betrag ist unbrauchbar."""
        self.assertFalse(self.c.brauchbar(zeile(215.30, "unter_trea"))[0])

    def test_a_residual_reservation_does_NOT_disqualify_it(self):
        """`residual` und `kein_heimatland` betreffen die LÄNDERzuordnung. Die
        Summe bleibt gültig — sie hier auszuschliessen verschenkte Paare ohne
        Grund."""
        self.assertTrue(self.c.brauchbar(zeile(1e9, "residual"))[0])
        self.assertTrue(self.c.brauchbar(zeile(1e9, "kein_heimatland"))[0])

    def test_a_mixed_reservation_still_disqualifies(self):
        self.assertFalse(self.c.brauchbar(zeile(1e9, "residual|skala"))[0])

    def test_a_clean_row_passes(self):
        self.assertTrue(self.c.brauchbar(zeile(1e9))[0])

    def test_a_missing_row_is_not_usable(self):
        self.assertFalse(self.c.brauchbar(None)[0])


class VergleichTest(unittest.TestCase):
    def setUp(self):
        import check_consolidation as c
        self.c = c

    def test_a_subsidiary_larger_than_its_group_is_a_finding(self):
        urteil, grund, quote, _ = self.c.vergleiche(
            zeile(2e9), zeile(1e9), {"DE"}, {"DE"})
        self.assertEqual(urteil, "groesser")
        self.assertAlmostEqual(quote, 2.0)
        self.assertIn("2.00", grund)

    def test_the_addiko_case_is_not_pruefbar_rather_than_a_finding(self):
        """Der Fall, der #32 Punkt 4 blockiert hat. Die Tochter IST grösser —
        aber nur, weil der CON-Report um Grössenordnungen zu klein gemeldet
        ist. Als Befund stünde hier ein Verstoss, den es nicht gibt."""
        urteil, grund, quote, _ = self.c.vergleiche(
            zeile(1.4e9), zeile(4296.63, "skala"), {"HR"}, {"AT"})
        self.assertEqual(urteil, "nicht_pruefbar")
        self.assertIn("Mutter", grund)
        self.assertIsNone(quote)

    def test_a_scaled_report_is_never_silently_stimmig(self):
        """Die gefährlichere Hälfte: `stimmig` behauptete eine bestandene
        Prüfung, die gar nicht gelaufen ist."""
        urteil, _, _, _ = self.c.vergleiche(
            zeile(1e3, "skala"), zeile(1e9), {"DE"}, {"DE"})
        self.assertNotEqual(urteil, "stimmig")

    def test_a_small_excess_stays_within_tolerance(self):
        """CCyB1 ist nicht die Bilanz, und zwei Meldungen desselben Konzerns
        haben Stichtagseffekte. Ohne Toleranz fände die Prüfung in jedem Paar
        etwas."""
        urteil, _, _, _ = self.c.vergleiche(
            zeile(1.02e9), zeile(1e9), {"DE"}, {"DE"})
        self.assertEqual(urteil, "stimmig")

    def test_the_tolerance_is_actually_used(self):
        self.assertEqual(self.c.vergleiche(zeile(1.2e9), zeile(1e9),
                                           {"DE"}, {"DE"}, toleranz=1.5)[0],
                         "stimmig")
        self.assertEqual(self.c.vergleiche(zeile(1.2e9), zeile(1e9),
                                           {"DE"}, {"DE"}, toleranz=1.1)[0],
                         "groesser")

    def test_missing_countries_are_a_finding_of_their_own(self):
        urteil, grund, _, fehlend = self.c.vergleiche(
            zeile(1e8), zeile(1e9), {"DE", "FR", "IT"}, {"DE"})
        self.assertEqual(urteil, "laender_fehlen")
        self.assertEqual(fehlend, ["FR", "IT"])

    def test_the_size_finding_wins_over_the_country_one(self):
        """Ein Exposure grösser als die Gruppe ist der schwerere Befund. Beide
        zu melden verdoppelte die Zeile ohne Erkenntnisgewinn."""
        urteil, _, _, _ = self.c.vergleiche(
            zeile(2e9), zeile(1e9), {"DE", "FR", "IT"}, {"DE"})
        self.assertEqual(urteil, "groesser")

    def test_a_subsidiary_without_countries_is_not_a_country_finding(self):
        """Division durch null wäre der eine Weg; sie als vollständig fehlend
        zu zählen der andere. Beides falsch."""
        self.assertEqual(self.c.vergleiche(zeile(1e8), zeile(1e9),
                                           set(), {"DE"})[0], "stimmig")

    def test_a_parent_without_exposure_is_not_pruefbar(self):
        self.assertEqual(self.c.vergleiche(zeile(1e8), zeile(0),
                                           {"DE"}, {"DE"})[0], "nicht_pruefbar")


class KantenTest(unittest.TestCase):
    """Direkte und oberste Mutter sind meist dieselbe LEI."""

    def setUp(self):
        import tempfile
        import check_consolidation as c
        self.c = c
        self.p = Path(tempfile.mkdtemp()) / "rel.csv"

    def _schreib(self, zeilen):
        self.p.write_text(
            "lei,direct_parent_lei,direct_parent_status,direct_parent_reason,"
            "ultimate_parent_lei,ultimate_parent_status,ultimate_parent_reason\n"
            + "".join(zeilen), encoding="utf-8")

    def test_the_same_parent_twice_is_one_edge(self):
        self._schreib(["K,M,parent,,M,parent,\n"])
        self.assertEqual(self.c.lade_kanten(self.p), {"K": {"M": "direkt|oberste"}})

    def test_two_different_parents_stay_two_edges(self):
        self._schreib(["K,M1,parent,,M2,parent,\n"])
        self.assertEqual(self.c.lade_kanten(self.p),
                         {"K": {"M1": "direkt", "M2": "oberste"}})

    def test_a_self_reference_is_no_edge(self):
        """Ein Institut ist nicht seine eigene Mutter — sonst verglichen wir
        einen Report mit sich selbst und fänden erwartungsgemäss nichts."""
        self._schreib(["K,K,parent,,K,parent,\n"])
        self.assertEqual(self.c.lade_kanten(self.p), {})

    def test_a_reporting_exception_is_no_edge(self):
        """Ein fehlender Parent ist kein Beleg für Eigenständigkeit (#32,
        Arbeitsprinzip 3) — aber eben auch keine Kante."""
        self._schreib(["K,,exception,NO_KNOWN_PERSON,,exception,NO_KNOWN_PERSON\n"])
        self.assertEqual(self.c.lade_kanten(self.p), {})


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        if not OUT.exists():
            self.skipTest("consolidation_check.csv nicht gebaut")
        with OUT.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))

    def test_the_check_actually_finds_pairs(self):
        """Eine Prüfung ohne Paare liefe über nichts und meldete Erfolg."""
        self.assertGreater(len(self.rows), 5)

    def test_no_pair_appears_twice(self):
        k = [(r["refPeriod"], r["kind_lei"], r["mutter_lei"]) for r in self.rows]
        self.assertEqual(len(k), len(set(k)))

    def test_the_scale_filter_actually_removes_something(self):
        """Der Addiko-Fall. Greift der Filter nicht mehr, stehen
        Scheinverstösse in der Liste — und #83 wäre umsonst gewesen."""
        self.assertTrue(any(r["urteil"] == "nicht_pruefbar" for r in self.rows),
                        "kein einziges Paar ausgefiltert — prüfen, ob die "
                        "Vorbehaltsspalte noch gelesen wird")

    def test_every_finding_carries_its_reason(self):
        for r in self.rows:
            if r["urteil"] != "stimmig":
                with self.subTest(kind=r["kind_name"]):
                    self.assertTrue(r["grund"])

    def test_a_country_finding_names_the_parents_residual(self):
        """Der naheliegende Einwand — das Land steckt im x28-Bucket der
        Mutter — muss nachprüfbar danebenstehen, sonst ist der Befund nicht
        zu bewerten."""
        for r in self.rows:
            if r["urteil"] == "laender_fehlen":
                with self.subTest(kind=r["kind_name"]):
                    self.assertTrue(r["mutter_x28"])

    def test_the_order_is_stable(self):
        k = [(r["refPeriod"], r["kind_lei"], r["mutter_lei"]) for r in self.rows]
        self.assertEqual(k, sorted(k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
