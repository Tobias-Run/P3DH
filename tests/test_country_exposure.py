"""Exposure gemessen am BIP des Gastlandes (#14).

#14 will eine **deskriptive** Kontextspalte und schliesst die Regressorlesart
ausdrücklich aus. Die Tests halten die vier Wege fest, auf denen hier eine
falsche Zahl entstünde:

1. Die Gesamtzeile `x1` als Land zählen — derselbe Fehler, der in #13/#27 eine
   Weile das Ähnlichkeitsmass verdorben hat.
2. Weltbank-Dollar gegen Meldeeuro stellen (rund 17 % daneben).
3. Ein fehlendes BIP als Null lesen. Für Jersey, Guernsey, die Britischen
   Jungferninseln und Taiwan gibt es keines — „Fehlt ≠ Null".
4. Konzerne doppelt zählen. Der CON-Report einer Gruppe enthält ihre Töchter
   bereits; die IND-Reports derselben Töchter dazuzuaddieren meldet eine
   Konzentration, die es nicht gibt. Bei Österreich macht das 7,8 % aus.
"""

from pathlib import Path
import csv
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

JE_REPORT = ROOT / "processed" / "country_exposure.csv"
JE_LAND = ROOT / "processed" / "country_concentration.csv"


class BipLadenTest(unittest.TestCase):
    def setUp(self):
        import build_country_exposure as b
        self.b = b
        self.p = Path(tempfile.mkdtemp()) / "gdp.csv"

    def _schreib(self, zeilen):
        self.p.write_text("iso2,country,year,gdp_usd,worldbank_name\n"
                          + "".join(zeilen), encoding="utf-8")

    def test_the_join_key_is_the_iso_code_not_the_name(self):
        """Von 216 gemeinsamen Codes tragen 32 bei der Weltbank einen anderen
        Namen („Korea, Rep." gegen „Korea, Republic of"). Über den Namen
        verbunden gingen sie verloren — und zwar lautlos, die Auswertung fände
        einfach weniger Länder."""
        self._schreib(["KR,\"Korea, Republic of\",2025,1800000000000,"
                       "\"Korea, Rep.\"\n"])
        self.assertIn("KR", self.b.lade_bip(self.p))

    def test_the_vintage_travels_with_the_value(self):
        """Das Jahr steht je Land in der Zeile, statt einen einheitlichen Stand
        vorzutäuschen — im Bestand reichen die Jahrgänge von 2015 bis 2025."""
        self._schreib(["AD,Andorra,2015,4500982732,Andorra\n"])
        self.assertEqual(self.b.lade_bip(self.p)["AD"][1], "2015")

    def test_a_country_without_a_value_does_not_enter(self):
        """Taiwan und die Offshore-Plätze. Mit einer Null im Nenner wäre der
        Quotient unendlich; als fehlender Schlüssel bleibt die Spalte leer."""
        self._schreib(["TW,Taiwan,,,Taiwan\n"])
        self.assertNotIn("TW", self.b.lade_bip(self.p))

    def test_a_missing_file_is_not_an_error(self):
        self.assertEqual(self.b.lade_bip(self.p.parent / "weg.csv"), {})


class KursTest(unittest.TestCase):
    def setUp(self):
        import build_country_exposure as b
        self.b = b

    def test_the_matching_date_wins(self):
        kurs, datum = self.b.usd_kurs("2025-12-31",
                                      {"2025-10-31": 0.8655,
                                       "2025-12-31": 0.85106})
        self.assertAlmostEqual(kurs, 0.85106)
        self.assertEqual(datum, "2025-12-31")

    def test_without_a_matching_date_the_nearest_one_is_named(self):
        """Für 2025-06-30 liegt kein USD-Kurs vor. Raten wäre das eine, die
        Zeile fallenzulassen das andere — beides schlechter, als den nächsten
        zu nehmen und zu sagen, welcher es war."""
        kurs, datum = self.b.usd_kurs("2025-06-30",
                                      {"2025-10-31": 0.8655,
                                       "2025-12-31": 0.85106})
        self.assertEqual(datum, "2025-10-31")
        self.assertAlmostEqual(kurs, 0.8655)

    def test_no_rates_at_all_is_a_gap_not_a_one(self):
        """Ein fehlender Kurs darf nicht als 1,0 durchgehen — dann stünde der
        Dollarwert als Eurowert da und niemand sähe es."""
        self.assertEqual(self.b.usd_kurs("2025-12-31", {}), (None, ""))


class VorbehaltTest(unittest.TestCase):
    def setUp(self):
        import build_country_exposure as b
        self.b = b

    def test_a_scale_reservation_disqualifies_the_amount(self):
        self.assertTrue(self.b.skaliert("skala"))
        self.assertTrue(self.b.skaliert("unter_trea"))

    def test_a_country_reservation_does_not(self):
        """`residual` und `kein_heimatland` betreffen die Länderzuordnung; die
        Summe bleibt gültig. Sie hier auszuschliessen verschenkte Reports."""
        self.assertFalse(self.b.skaliert("residual"))
        self.assertFalse(self.b.skaliert("kein_heimatland"))
        self.assertFalse(self.b.skaliert(""))

    def test_a_mixed_reservation_still_disqualifies(self):
        self.assertTrue(self.b.skaliert("residual|skala"))


class DoppelzaehlungTest(unittest.TestCase):
    """Der teuerste Fehler dieser Auswertung."""

    def setUp(self):
        import build_country_exposure as b
        self.b = b
        self.muetter = {"KIND": {"MUTTER"}}
        self.con = {("MUTTER", "2025-12-31")}

    def test_a_subsidiary_inside_its_parents_group_report_is_skipped(self):
        self.assertTrue(self.b.doppelt_gezaehlt(
            "KIND", "IND", "2025-12-31", self.muetter, self.con))

    def test_a_group_report_is_never_skipped(self):
        self.assertFalse(self.b.doppelt_gezaehlt(
            "MUTTER", "CON", "2025-12-31", self.muetter, self.con))

    def test_a_standalone_filer_is_kept(self):
        """Ohne belegte Mutter gibt es nichts zu entdoppeln — und das Institut
        wegzulassen verlöre echtes Exposure."""
        self.assertFalse(self.b.doppelt_gezaehlt(
            "EINZEL", "IND", "2025-12-31", self.muetter, self.con))

    def test_a_parent_that_did_not_file_CON_leaves_the_subsidiary_in(self):
        """Nur wenn die Mutter für DENSELBEN Stichtag konsolidiert gemeldet
        hat, steckt die Tochter schon darin. Sonst wäre ihr Exposure sonst
        nirgends erfasst."""
        self.assertFalse(self.b.doppelt_gezaehlt(
            "KIND", "IND", "2025-06-30", self.muetter, self.con))


class JeReportTest(unittest.TestCase):
    def setUp(self):
        import build_country_exposure as b
        self.b = b
        self.bip = {"DE": (4.0e12, "2025", "Germany"),
                    "MT": (2.0e10, "2025", "Malta")}
        self.roh = [
            ("L1", "CON", "2025-12-31", "Bank", "Germany", "DE", "Germany", 8e9),
            ("L1", "CON", "2025-12-31", "Bank", "Germany", "MT", "Malta", 2e9),
        ]

    def _bau(self, **kw):
        kw.setdefault("bip", self.bip)
        kw.setdefault("kurs", 1.0)
        kw.setdefault("kurs_datum", "2025-12-31")
        kw.setdefault("vorbehalte", {})
        return self.b.je_report(self.roh, **kw)

    def test_the_same_amount_weighs_differently_per_host(self):
        """Der Satz, um den es #14 geht. 2 Mrd in Malta sind 10 % des
        maltesischen BIP; 8 Mrd in Deutschland sind 0,2 % des deutschen. Der
        absolute Betrag stellt die Reihenfolge genau andersherum."""
        je = {z["land"]: z for z in self._bau()}
        self.assertAlmostEqual(float(je["MT"]["exposure_je_bip"]), 0.10, 3)
        self.assertAlmostEqual(float(je["DE"]["exposure_je_bip"]), 0.002, 4)
        self.assertGreater(float(je["DE"]["exposure_eur"]),
                           float(je["MT"]["exposure_eur"]))

    def test_the_share_of_the_report_sums_to_one(self):
        anteile = [float(z["anteil_am_report"]) for z in self._bau()]
        self.assertAlmostEqual(sum(anteile), 1.0)

    def test_the_rank_follows_the_amount(self):
        je = {z["land"]: z for z in self._bau()}
        self.assertEqual(je["DE"]["rang"], 1)
        self.assertEqual(je["MT"]["rang"], 2)

    def test_equal_amounts_keep_a_stable_rank(self):
        """Ohne zweites Sortierkriterium entschiede bei Gleichstand die
        Reihenfolge, in der DuckDB die Zeilen liefert — der Rang wechselte
        zwischen zwei Läufen und ein Diff der Ausgabe wäre wertlos."""
        self.roh = [
            ("L1", "CON", "2025-12-31", "B", "Germany", "MT", "Malta", 5e9),
            ("L1", "CON", "2025-12-31", "B", "Germany", "DE", "Germany", 5e9),
        ]
        einmal = {z["land"]: z["rang"] for z in self._bau()}
        self.roh.reverse()
        nochmal = {z["land"]: z["rang"] for z in self._bau()}
        self.assertEqual(einmal, nochmal)
        self.assertEqual(einmal["DE"], 1)

    def test_a_country_without_a_gdp_leaves_the_columns_empty(self):
        """„Fehlt ≠ Null" (Arbeitsprinzip 3). Eine Null im Nenner wäre keine
        kleine Wirtschaft, sondern gar keine — und der Quotient unendlich."""
        zeilen = self._bau(bip={"DE": (4.0e12, "2025", "Germany")})
        mt = [z for z in zeilen if z["land"] == "MT"][0]
        self.assertEqual(mt["bip_eur"], "")
        self.assertEqual(mt["exposure_je_bip"], "")
        self.assertEqual(mt["bip_jahr"], "")
        # Das Exposure selbst bleibt natürlich stehen.
        self.assertTrue(mt["exposure_eur"])

    def test_the_currency_conversion_actually_happens(self):
        """Ohne Umrechnung stünde ein Dollar-BIP im Nenner eines Euro-Zählers —
        rund 17 % daneben, gross genug um falsch zu sein und klein genug um
        durchzugehen."""
        je = {z["land"]: z for z in self._bau(kurs=0.85)}
        self.assertAlmostEqual(float(je["DE"]["bip_eur"]), 4.0e12 * 0.85, 0)

    def test_the_applied_rate_is_named_in_the_row(self):
        je = {z["land"]: z for z in self._bau(kurs_datum="2025-10-31")}
        self.assertEqual(je["DE"]["bip_fx_refdate"], "2025-10-31")

    def test_the_home_country_is_marked(self):
        je = {z["land"]: z for z in self._bau()}
        self.assertEqual(je["DE"]["ist_heimatland"], "ja")
        self.assertEqual(je["MT"]["ist_heimatland"], "nein")

    def test_the_reservation_travels_with_the_row(self):
        zeilen = self._bau(
            vorbehalte={("L1", "CON", "2025-12-31"): "skala"})
        for z in zeilen:
            self.assertEqual(z["vorbehalt"], "skala")


class JeLandTest(unittest.TestCase):
    def setUp(self):
        import build_country_exposure as b
        self.b = b
        self.bip = {"DE": (4.0e12, "2025", "Germany")}

    def _zeile(self, lei, scope, betrag, vorbehalt=""):
        return {"refPeriod": "2025-12-31", "lei": lei, "scope": scope,
                "bank_name": lei, "land": "DE", "land_name": "Germany",
                "home_country": "", "x28_anteil": "",
                "exposure_eur": str(betrag), "vorbehalt": vorbehalt}

    def test_amounts_are_added_up(self):
        aus = self.b.je_land([self._zeile("A", "CON", 1e9),
                              self._zeile("B", "CON", 2e9)],
                             self.bip, 1.0, "2025-12-31", {}, set())
        self.assertEqual(len(aus), 1)
        self.assertAlmostEqual(float(aus[0]["exposure_eur"]), 3e9)
        self.assertEqual(aus[0]["melder"], 2)

    def test_a_subsidiary_of_a_reporting_group_is_not_added_again(self):
        """Ohne diese Zeile stünde dasselbe Geschäft zweimal in der Summe. Bei
        Österreich sind das 7,8 %."""
        aus = self.b.je_land([self._zeile("MUTTER", "CON", 2e9),
                              self._zeile("KIND", "IND", 1e9)],
                             self.bip, 1.0, "2025-12-31",
                             {"KIND": {"MUTTER"}},
                             {("MUTTER", "2025-12-31")})
        self.assertAlmostEqual(float(aus[0]["exposure_eur"]), 2e9)
        self.assertEqual(aus[0]["melder"], 1)

    def test_a_scaled_report_never_enters_a_sum(self):
        """#83: ein Report, dessen Beträge um Grössenordnungen danebenliegen,
        verdirbt jede Summe, in die er eingeht."""
        aus = self.b.je_land([self._zeile("A", "CON", 2e9),
                              self._zeile("B", "CON", 9e15, "skala")],
                             self.bip, 1.0, "2025-12-31", {}, set())
        self.assertAlmostEqual(float(aus[0]["exposure_eur"]), 2e9)

    def test_the_breadth_has_a_denominator(self):
        """#19 will „Breite, nicht nur Volumen". Ohne den Nenner ist `melder`
        nicht lesbar: 55 Melder sind viel oder wenig, je nachdem, ob 60 oder
        600 in Frage kamen."""
        aus = self.b.je_land([self._zeile("A", "CON", 1e9),
                              self._zeile("B", "CON", 2e9)],
                             self.bip, 1.0, "2025-12-31", {}, set())
        self.assertEqual(aus[0]["melder_gesamt"], 2)
        self.assertAlmostEqual(float(aus[0]["breite"]), 1.0)

    def test_the_denominator_counts_filers_not_present_in_this_country(self):
        """Der Nenner ist die ganze meldende Population des Stichtags, nicht
        die Teilmenge mit Exposure in diesem Land — sonst wäre die Breite
        immer 100 %."""
        zeilen = [self._zeile("A", "CON", 1e9), self._zeile("B", "CON", 2e9)]
        zeilen[1]["land"] = "FR"
        zeilen[1]["land_name"] = "France"
        aus = {z["land"]: z for z in self.b.je_land(
            zeilen, self.bip, 1.0, "2025-12-31", {}, set())}
        self.assertEqual(aus["DE"]["melder_gesamt"], 2)
        self.assertAlmostEqual(float(aus["DE"]["breite"]), 0.5)

    def test_an_incomplete_geography_is_counted(self):
        """#19: „Institute, die fast alles in den Residual-Bucket legen,
        verzerren Länder-Aggregate nach unten." Die Zahl muss danebenstehen,
        sonst liest niemand die Summe mit Vorbehalt."""
        a = self._zeile("A", "CON", 1e9)
        a["x28_anteil"] = "0.5300"
        aus = self.b.je_land([a, self._zeile("B", "CON", 2e9)],
                             self.bip, 1.0, "2025-12-31", {}, set())
        self.assertEqual(aus[0]["melder_unvollstaendig"], 1)

    def test_a_small_residual_share_is_not_counted(self):
        a = self._zeile("A", "CON", 1e9)
        a["x28_anteil"] = "0.0100"
        aus = self.b.je_land([a], self.bip, 1.0, "2025-12-31", {}, set())
        self.assertEqual(aus[0]["melder_unvollstaendig"], 0)

    def test_a_domestic_concentration_is_told_apart_from_a_foreign_one(self):
        """Der Unterschied, ohne den eine hohe Konzentration nicht zu deuten
        ist. Islands 84,9 % liegen bei Íslandsbanki — einer isländischen Bank
        im eigenen Land, also dem Normalfall. Brasiliens 80,1 % liegen bei
        Santander, und DAS ist ein Drittstaatenrisiko im Sinne von #19."""
        inland = self._zeile("IS", "CON", 9e9)
        inland["home_country"] = "Germany"      # == land_name der Testzeile
        aus = self.b.je_land([inland], self.bip, 1.0, "2025-12-31", {}, set())
        self.assertEqual(aus[0]["groesster_inlaendisch"], "ja")

        fremd = self._zeile("ES", "CON", 9e9)
        fremd["home_country"] = "Spain"
        aus = self.b.je_land([fremd], self.bip, 1.0, "2025-12-31", {}, set())
        self.assertEqual(aus[0]["groesster_inlaendisch"], "nein")
        self.assertEqual(aus[0]["groesster_heimat"], "Spain")

    def test_an_unknown_home_country_is_not_claimed_as_domestic(self):
        """„Fehlt ≠ Null": ohne Heimatland ist die Frage unbeantwortet, und
        `ja` wäre eine Behauptung über Daten, die nicht vorliegen."""
        z = self._zeile("X", "CON", 1e9)
        z["home_country"] = ""
        aus = self.b.je_land([z], self.bip, 1.0, "2025-12-31", {}, set())
        self.assertEqual(aus[0]["groesster_inlaendisch"], "nein")

    def test_the_largest_filer_is_named_with_its_share(self):
        """Eine Ländersumme ohne Angabe, wie viel davon aus einem Haus kommt,
        lässt Konzentration wie Breite aussehen."""
        aus = self.b.je_land([self._zeile("A", "CON", 3e9),
                              self._zeile("B", "CON", 1e9)],
                             self.bip, 1.0, "2025-12-31", {}, set())
        self.assertEqual(aus[0]["groesster_melder"], "A")
        self.assertAlmostEqual(float(aus[0]["groesster_anteil"]), 0.75)


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        if not JE_REPORT.exists() or not JE_LAND.exists():
            self.skipTest("country_exposure.csv nicht gebaut")
        with JE_REPORT.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))
        with JE_LAND.open(encoding="utf-8") as fh:
            self.laender = list(csv.DictReader(fh))

    def test_the_artefact_actually_has_content(self):
        self.assertGreater(len(self.rows), 1000)
        self.assertGreater(len(self.laender), 50)

    def test_no_aggregate_row_is_treated_as_a_country(self):
        """`x1` ist die Gesamtzeile, `x28` der Residualbucket. Als Land
        gezählt verdoppelte `x1` jeden Report und stünde mit einem BIP-Quotienten
        da, der nichts bedeutet."""
        for r in self.rows:
            with self.subTest(land=r["land"]):
                self.assertRegex(r["land"], r"^[A-Z]{2}$")

    def test_a_missing_gdp_leaves_the_ratio_empty_rather_than_zero(self):
        ohne = [r for r in self.rows if not r["bip_eur"]]
        self.assertTrue(ohne, "kein einziges Land ohne BIP — prüfen, ob die "
                              "Weltbank-Tabelle noch gelesen wird")
        for r in ohne:
            with self.subTest(land=r["land"]):
                self.assertEqual(r["exposure_je_bip"], "")

    def test_every_ratio_names_the_vintage_and_the_rate_it_used(self):
        """Ohne beides ist der Quotient nicht nachprüfbar: das BIP-Jahr reicht
        im Bestand von 2015 bis 2025, und der USD-Kurs liegt nicht für jeden
        Stichtag vor."""
        for r in self.rows:
            if r["exposure_je_bip"]:
                with self.subTest(land=r["land"]):
                    self.assertTrue(r["bip_jahr"])
                    self.assertTrue(r["bip_fx_refdate"])

    def test_the_ratio_matches_its_own_inputs(self):
        for r in self.rows[:500]:
            if r["exposure_je_bip"]:
                with self.subTest(land=r["land"]):
                    self.assertAlmostEqual(
                        float(r["exposure_je_bip"]),
                        float(r["exposure_eur"]) / float(r["bip_eur"]),
                        places=4)

    def test_the_aggregate_carries_no_scaled_report(self):
        """Gegenprobe zur Entdopplung: wäre der Filter weg, stünde mindestens
        ein Land um Grössenordnungen zu hoch. Geprüft wird an der Quote — über
        die Schiffsregister hinaus ist alles jenseits 100 000 % unsinnig."""
        for r in self.laender:
            if r["exposure_je_bip"]:
                with self.subTest(land=r["land"]):
                    self.assertLess(float(r["exposure_je_bip"]), 1000.0)

    def test_the_share_of_the_largest_filer_is_a_share(self):
        for r in self.laender:
            if r["groesster_anteil"]:
                with self.subTest(land=r["land"]):
                    self.assertGreater(float(r["groesster_anteil"]), 0.0)
                    self.assertLessEqual(float(r["groesster_anteil"]), 1.0)

    def test_the_normalisation_reorders_the_countries(self):
        """Der Ertrag des Issues in einem Satz: wäre die Reihenfolge nach
        Quote dieselbe wie nach Betrag, hätte die Normierung nichts
        hinzugefügt."""
        jung = max(r["refPeriod"] for r in self.laender)
        aktuell = [r for r in self.laender
                   if r["refPeriod"] == jung and r["exposure_je_bip"]]
        nach_betrag = [r["land"] for r in
                       sorted(aktuell, key=lambda r: -float(r["exposure_eur"]))]
        nach_quote = [r["land"] for r in
                      sorted(aktuell,
                             key=lambda r: -float(r["exposure_je_bip"]))]
        self.assertNotEqual(nach_betrag[:10], nach_quote[:10])

    def test_the_order_is_stable(self):
        k = [(r["refPeriod"], r["land"]) for r in self.laender]
        self.assertEqual(k, sorted(k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
