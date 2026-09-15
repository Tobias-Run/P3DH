"""LEI → Aktien-ISIN → Primärnotierung (#39).

Die Verknüpfung, die eine Ereignisstudie braucht — und die Falle, an der sie
scheitert, ohne es zu zeigen:

Wikidata listet mit `P414` **alle** Notierungen ohne Rangfolge. Die erstbeste
zu nehmen trifft bei Banca Monte dei Paschi das OTC-gehandelte ADR (`BMDPY`)
statt der Mailänder Aktie. Ein Ereignisfenster auf einem dünn gehandelten
Zweitpapier misst Rauschen — und es sähe aus wie ein Ergebnis, weil am Ende
Zahlen mit Nachkommastellen stehen.

Entschieden wird deshalb über das Länderpräfix der ISIN.
"""

from pathlib import Path
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "equity_link.csv"


class IsinTest(unittest.TestCase):
    def setUp(self):
        import build_equity_link as b
        self.b = b

    def test_the_prefix_is_the_country(self):
        self.assertEqual(self.b.isin_land("DE0005140008"), "DE")
        self.assertEqual(self.b.isin_land("it0005218752"), "IT")

    def test_a_malformed_isin_yields_nothing(self):
        self.assertEqual(self.b.isin_land("12345"), "")
        self.assertEqual(self.b.isin_land(""), "")
        self.assertEqual(self.b.isin_land(None), "")


class NotierungTest(unittest.TestCase):
    def setUp(self):
        import build_equity_link as b
        self.b = b

    def test_the_home_listing_wins_over_the_adr(self):
        """Der Fall, der die Regel erzwungen hat. Wikidata liefert beide ohne
        Rangfolge; die Reihenfolge hier ist absichtlich die ungünstige."""
        b, land, t, s = self.b.waehle_notierung("IT0005218752", [
            ("OTC Markets Group", "US", "BMDPY"),
            ("Borsa Italiana", "IT", "BMPS")])
        self.assertEqual((b, land, t), ("Borsa Italiana", "IT", "BMPS"))
        self.assertEqual(s, "eindeutig")

    def test_a_foreign_only_listing_is_refused_not_used(self):
        """Ein Ticker ohne belegte Primärnotierung wäre schlimmer als keiner:
        er sieht benutzbar aus."""
        b, _, t, s = self.b.waehle_notierung("IT0005218752", [
            ("OTC Markets Group", "US", "BMDPY")])
        self.assertEqual((b, t), ("", ""))
        self.assertEqual(s, "keine Notierung im ISIN-Land")

    def test_no_isin_is_its_own_state(self):
        """„Keine ISIN bei Wikidata" ist etwas anderes als „ISIN da, aber
        unbrauchbar" — beides in einen Topf zu werfen verwischt, ob die Lücke
        bei der Quelle oder bei der Form liegt."""
        self.assertEqual(self.b.waehle_notierung("", [])[3], "keine isin")
        self.assertEqual(self.b.waehle_notierung("123", [])[3], "isin unbrauchbar")

    def test_a_supranational_prefix_is_not_a_share(self):
        """`XS` ist Euroclear/Clearstream — internationale Anleihen. Eine
        Aktie mit diesem Präfix gibt es nicht."""
        self.assertEqual(
            self.b.waehle_notierung("XS1234567890",
                                    [("Euronext", "NL", "X")])[3],
            "isin nicht national (kein Aktienpapier)")

    def test_several_listings_in_the_country_are_flagged(self):
        b, _, t, s = self.b.waehle_notierung("DE0005140008", [
            ("Xetra", "DE", "DBK"), ("Börse Stuttgart", "DE", "DBK")])
        self.assertEqual(s, "mehrere im ISIN-Land")
        self.assertTrue(t)

    def test_a_listing_with_a_ticker_beats_one_without(self):
        """Ohne Ticker ist die Notierung für eine Kursabfrage wertlos."""
        b, _, t, _ = self.b.waehle_notierung("DE0005140008", [
            ("Regionalbörse", "DE", ""), ("Xetra", "DE", "DBK")])
        self.assertEqual(t, "DBK")

    def test_the_choice_does_not_depend_on_input_order(self):
        eingabe = [("Xetra", "DE", "DBK"), ("OTC", "US", "DBOEY"),
                   ("Börse Stuttgart", "DE", "DBKS")]
        self.assertEqual(self.b.waehle_notierung("DE0005140008", eingabe),
                         self.b.waehle_notierung("DE0005140008", eingabe[::-1]))

    def test_no_listing_at_all_is_named(self):
        self.assertEqual(self.b.waehle_notierung("DE0005140008", [])[3],
                         "keine Notierung bei Wikidata")


class SammelTest(unittest.TestCase):
    def setUp(self):
        import build_equity_link as b
        self.b = b

    def test_several_rows_per_item_collapse(self):
        """SPARQL liefert je Notierung eine Zeile. Wer sie einzeln zählt, hält
        ein Institut für mehrere."""
        bind = [{"item": {"value": "http://wd/Q1"}, "isin": {"value": "DE1"},
                 "exchange": {"value": "x"}, "exchangeLabel": {"value": "Xetra"},
                 "iso": {"value": "DE"}, "ticker": {"value": "DBK"}},
                {"item": {"value": "http://wd/Q1"}, "isin": {"value": "DE1"},
                 "exchange": {"value": "y"}, "exchangeLabel": {"value": "OTC"},
                 "iso": {"value": "US"}}]
        roh = self.b.sammle(bind)
        self.assertEqual(list(roh), ["Q1"])
        self.assertEqual(roh["Q1"][0], "DE1")
        self.assertEqual(len(roh["Q1"][1]), 2)

    def test_an_item_without_listings_still_keeps_its_isin(self):
        roh = self.b.sammle([{"item": {"value": "http://wd/Q1"},
                              "isin": {"value": "DE1"}}])
        self.assertEqual(roh["Q1"], ["DE1", []])


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        if not OUT.exists():
            self.skipTest("equity_link.csv nicht gebaut")
        with OUT.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))

    def test_every_row_carries_a_verdict(self):
        for r in self.rows:
            with self.subTest(lei=r["lei"]):
                self.assertTrue(r["sicherheit"])

    def test_a_ticker_never_stands_without_its_exchange(self):
        """Ein Ticker ohne Handelsplatz ist nicht abfragbar — und sähe
        trotzdem benutzbar aus."""
        for r in self.rows:
            if r["ticker"]:
                with self.subTest(lei=r["lei"]):
                    self.assertTrue(r["boerse"])
                    self.assertEqual(r["boerse_land"], r["isin_land"])

    def test_the_linked_subset_is_smaller_than_the_listed_one(self):
        """Der Befund, der die Machbarkeit begrenzt: nicht jedes notierte
        Institut ist an eine Kursreihe anschliessbar. Wäre das verschwunden,
        hätte die Quelle sich geändert und die Zahl in #39 stimmte nicht mehr."""
        mit = [r for r in self.rows if r["ticker"]]
        self.assertGreater(len(mit), 20)
        self.assertLess(len(mit), len(self.rows))

    def test_the_order_is_stable(self):
        k = [r["lei"] for r in self.rows]
        self.assertEqual(k, sorted(k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
