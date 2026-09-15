"""Wie breit ziehen Institute den Kreis der Risikoträger? (#40)

REM1 liefert die Zahl der „identified staff" nach CRD Art. 92, Wikidata über die
LEI die Gesamtbelegschaft. Der Quotient ist eine Governance-Aussage, die in
keiner Einzelquelle steht.

## Die Falle, gegen die diese Tests geschrieben sind

Roh gerechnet misst die Kennzahl die **Grösse**, nicht das Ermessen:

    log10(Belegschaft) gegen log10(Anteil):   r = −0,869   r² = 0,755

    < 500 Beschäftigte      Median 14,37 %
    > 50.000                Median  1,14 %

Drei Viertel der Streuung erklärt die Belegschaftsgrösse allein — und das ist
Sachlogik, kein Artefakt: eine Grossbank hat Zehntausende im Filialvertrieb,
deren Tätigkeit das Risikoprofil nicht wesentlich beeinflusst. Wer die Rohquote
als Governance-Aussage veröffentlicht, veröffentlicht eine Grössenmessung mit
einem Governance-Etikett.

Dieselbe Falle wie die Rohquote in #43, die RWA-Dichte in #45 und die
Ländermittel in #11. Gemessen wird deshalb der REST.

## Und die Falle dahinter

Die Stichprobe ist nicht der Bestand: nur 24 % der Institute tragen in Wikidata
eine Mitarbeiterzahl, und sie sind nach TREA im Median 2,4-mal grösser.
"""

from pathlib import Path
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "risk_taker_share.csv"
WIKIDATA = ROOT / "codebook" / "wikidata_entities.csv"


class WikidataAuswahlTest(unittest.TestCase):
    def setUp(self):
        import fetch_wikidata_entities as f
        self.f = f

    def test_the_most_recent_dated_figure_wins(self):
        """ABN AMRO trägt 18.830 und 20.872 mit verschiedenen Stichtagen. Ohne
        diese Auswahl entschiede die Reihenfolge, die der Endpunkt zufällig
        liefert — und der Quotient hinge an einer Zufälligkeit."""
        wert, stand = self.f.juengste_zahl(
            [(18830, "2020-12-31T00:00:00Z"), (20872, "2023-12-31T00:00:00Z")])
        self.assertEqual(wert, 20872)
        self.assertEqual(stand, "2023-12-31")

    def test_a_dated_figure_beats_an_undated_one(self):
        """Eine datierte Zahl ist nachprüfbar, eine undatierte nicht — auch
        wenn sie grösser ist."""
        wert, stand = self.f.juengste_zahl([(999999, ""), (100, "2024-06-30")])
        self.assertEqual(wert, 100)

    def test_undated_figures_are_resolved_deterministically(self):
        """Gibt es nur undatierte, muss die Auswahl trotzdem reproduzierbar
        sein — sonst ändert sich die Ausgabe zwischen zwei Läufen."""
        a = self.f.juengste_zahl([(50, ""), (70, "")])
        b = self.f.juengste_zahl([(70, ""), (50, "")])
        self.assertEqual(a, b)

    def test_no_statement_yields_nothing(self):
        self.assertEqual(self.f.juengste_zahl([]), (None, ""))

    def test_a_network_failure_does_not_shrink_the_holdings(self):
        """Die Falle, die sich als Erfolg meldet: scheitert ein Block, kommt
        eine halbe Antwort zurück. Sie zu schreiben ersetzte eine gepflegte
        Zuordnung durch eine halbe — und der nächste Schritt rechnete
        stillschweigend auf einer geschrumpften Stichprobe weiter."""
        self.assertFalse(self.f.darf_schreiben(100, 232, fehlgeschlagen=1))
        self.assertFalse(self.f.darf_schreiben(0, 232, fehlgeschlagen=4))

    def test_a_complete_run_may_always_replace(self):
        """Verliert Wikidata selbst Einträge, ist das die Wahrheit der Quelle
        — sonst friert der erste gute Lauf den Stand für immer ein."""
        self.assertTrue(self.f.darf_schreiben(200, 232, fehlgeschlagen=0))

    def test_a_partial_run_that_lost_nothing_may_replace(self):
        self.assertTrue(self.f.darf_schreiben(232, 232, fehlgeschlagen=1))

    def test_several_rows_per_lei_collapse_to_one_record(self):
        """SPARQL liefert je zusätzlicher Aussage eine weitere Zeile. Wer sie
        einzeln zählt, hält ein Institut für mehrere."""
        b = [{"lei": {"value": "X"}, "item": {"value": "http://wd/Q1"},
              "itemLabel": {"value": "Bank"}, "employees": {"value": "100"}},
             {"lei": {"value": "X"}, "item": {"value": "http://wd/Q1"},
              "itemLabel": {"value": "Bank"}, "employees": {"value": "200"},
              "empDate": {"value": "2024-01-01"}}]
        roh = self.f.sammle(b)
        self.assertEqual(list(roh), ["X"])
        self.assertEqual(len(roh["X"]["emp"]), 2)


class ModellTest(unittest.TestCase):
    def setUp(self):
        import build_risk_taker_share as b
        self.b = b

    def test_the_regression_recovers_a_known_power_law(self):
        punkte = [(10 ** k, 10 ** (-0.5 * k + 0.3)) for k in
                  [i / 10 for i in range(5, 55)]]
        steigung, abschnitt = self.b.regression(punkte)
        self.assertAlmostEqual(steigung, -0.5, places=6)
        self.assertAlmostEqual(abschnitt, 0.3, places=6)

    def test_too_few_points_yield_no_model(self):
        """Ein „erwarteter Anteil" aus zehn Punkten wäre eine Zahl mit
        Nachkommastellen und ohne Inhalt."""
        self.assertIsNone(self.b.regression([(100, 0.1), (200, 0.05)]))

    def test_a_regressor_without_spread_yields_no_model(self):
        """Haben alle Institute dieselbe Belegschaft, ist die Steigung nicht
        bestimmbar — und ein Achsenabschnitt allein wäre eine Konstante mit dem
        Anschein eines Modells."""
        self.assertIsNone(self.b.regression([(100, 0.1 + i / 1000)
                                             for i in range(30)]))

    def test_the_expectation_follows_the_model(self):
        erw = self.b.erwarteter_anteil((-0.5, 0.3), 10000)
        self.assertAlmostEqual(erw, 10 ** (-0.5 * 4 + 0.3))

    def test_without_a_model_there_is_no_expectation(self):
        self.assertIsNone(self.b.erwarteter_anteil(None, 10000))
        self.assertIsNone(self.b.erwarteter_anteil((-0.5, 0.3), 0))


class VorbehaltTest(unittest.TestCase):
    """Beide Regeln treffen im heutigen Bestand NULL bzw. nur einen Fall.

    Über die Ausgabe geprüft liefe `staff_ueber_belegschaft` über nichts und
    meldete Erfolg. Deshalb hier gegen die Funktion — die Regel bleibt prüfbar,
    auch wenn die Daten sie gerade nicht auslösen.
    """

    def setUp(self):
        import build_risk_taker_share as b
        self.v = b.vorbehalt_von

    def test_a_usable_quotient_carries_no_reservation(self):
        self.assertEqual(self.v(120, 4000, False), "")

    def test_more_risk_takers_than_staff_is_caught(self):
        """Mehr Risikoträger als Mitarbeiter heisst, dass eine der beiden
        Zahlen einen anderen Perimeter meint. Der Quotient trägt dann nichts."""
        self.assertEqual(self.v(4001, 4000, False), "staff_ueber_belegschaft")

    def test_equal_counts_still_pass(self):
        """Genau alle Mitarbeiter als Risikoträger ist extrem, aber bei einem
        Spezialfinanzierer möglich — und die Regel soll das Unmögliche fangen,
        nicht das Auffällige."""
        self.assertEqual(self.v(4000, 4000, False), "")

    def test_a_known_outlier_wins_over_the_perimeter_reason(self):
        """Nur EIN Grund je Zeile; der bereits beanstandete Wert ist der
        nähere, weil #17 ihn schon benannt hat."""
        self.assertEqual(self.v(9999, 10, True), "rem_befund")


class AuswahlTest(unittest.TestCase):
    def setUp(self):
        import build_risk_taker_share as b
        self.f = b.ein_report_je_institut

    def _z(self, lei, scope, rp):
        return {"lei": lei, "scope": scope, "refPeriod": rp}

    def test_one_point_per_institution(self):
        """Ein Haus mit vier Stichtagen zählte sonst viermal und verschöbe das
        Modell zu sich hin — dieselbe Pseudoreplikation wie in #11."""
        z = [self._z("A", "CON", d) for d in
             ("2025-12-31", "2025-06-30", "2024-12-31")]
        self.assertEqual(len(self.f(z)), 1)

    def test_the_consolidated_report_wins(self):
        """Wikidatas P1128 ist eine Gruppenzahl. Gegen einen IND-Report
        gestellt untertreibt sie den Anteil systematisch — gemessen liegt der
        rohe IND-Median um Faktor 3,7 über dem von CON."""
        gewaehlt = self.f([self._z("A", "IND", "2025-12-31"),
                           self._z("A", "CON", "2025-12-31")])
        self.assertEqual(gewaehlt["A"]["scope"], "CON")

    def test_the_choice_does_not_depend_on_input_order(self):
        z = [self._z("A", "IND", "2025-12-31"), self._z("A", "CON", "2025-06-30"),
             self._z("A", "SUB", "2025-12-31")]
        self.assertEqual(self.f(z)["A"], self.f(z[::-1])["A"])

    def test_without_a_consolidated_report_the_latest_date_wins(self):
        """Gesucht ist, wie das Haus den Kreis HEUTE zieht."""
        z = [self._z("A", "IND", "2025-06-30"), self._z("A", "IND", "2025-12-31")]
        self.assertEqual(self.f(z)["A"]["refPeriod"], "2025-12-31")

    def test_an_unreadable_date_does_not_break_the_ordering(self):
        z = [self._z("A", "IND", "n/a"), self._z("A", "IND", "2025-12-31")]
        self.assertEqual(self.f(z)["A"]["refPeriod"], "2025-12-31")


class ModellBasisTest(unittest.TestCase):
    """Worauf das Modell geschätzt wird — die Frage, die an der Ausgabe nicht
    zu stellen ist: der Unterschied beträgt dort 0,8 bis 4,5 %, fiele in keiner
    Kennzahl auf und wäre damit unbemerkt aufhebbar."""

    def setUp(self):
        import build_risk_taker_share as b
        self.b = b

    def _zeilen(self, n=30):
        # Eine saubere Potenzfunktion: Anteil = 10^(-0.5·log10(N) + 0.3)
        return [{"lei": f"L{i:03d}", "scope": "CON", "refPeriod": "2025-12-31",
                 "mitarbeiter": 10 ** (1 + i / 10),
                 "anteil": 10 ** (-0.5 * (1 + i / 10) + 0.3),
                 "vorbehalt": ""} for i in range(n)]

    def test_the_model_recovers_the_truth_from_clean_rows(self):
        m, je = self.b.schaetze_modell(self._zeilen())
        self.assertEqual(len(je), 30)
        self.assertAlmostEqual(m[0], -0.5, places=6)

    def test_a_row_we_flagged_ourselves_does_not_move_the_expectation(self):
        """Sonst zieht ein bekannter Ausreisser die Latte zu sich hin — und
        macht alle übrigen Häuser genau um seinen Fehler auffälliger."""
        z = self._zeilen()
        z.append({"lei": "BAD", "scope": "CON", "refPeriod": "2025-12-31",
                  "mitarbeiter": 100000, "anteil": 0.95,
                  "vorbehalt": "staff_ueber_belegschaft"})
        m, je = self.b.schaetze_modell(z)
        self.assertNotIn("BAD", je)
        self.assertAlmostEqual(m[0], -0.5, places=6)

    def test_the_same_institution_twice_does_not_count_twice(self):
        """Pseudoreplikation: ein Haus mit vier Stichtagen zöge das Modell
        vierfach gewichtet zu sich."""
        z = self._zeilen()
        z += [dict(z[0], refPeriod=d) for d in
              ("2025-06-30", "2024-12-31", "2024-06-30")]
        _, je = self.b.schaetze_modell(z)
        self.assertEqual(len(je), 30)


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        if not OUT.exists():
            self.skipTest("risk_taker_share.csv nicht gebaut")
        with OUT.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))
        self.sauber = [r for r in self.rows if not r["vorbehalt"]]

    def test_the_combination_actually_produces_rows(self):
        self.assertGreater(len(self.rows), 40)

    def test_the_raw_share_is_dominated_by_size(self):
        """Der Befund, der die Kennzahl rettet, indem er sie relativiert: die
        rohe Quote fällt monoton mit der Belegschaft. Bricht das, wäre die
        Korrektur gegen die Grösse unnötig — und dann stimmt eine der beiden
        Seiten der Division nicht mehr."""
        import statistics as st
        klein = [float(r["anteil"]) for r in self.sauber
                 if int(r["mitarbeiter"]) < 500]
        gross = [float(r["anteil"]) for r in self.sauber
                 if int(r["mitarbeiter"]) >= 5000]
        self.assertGreater(len(klein), 5)
        self.assertGreater(len(gross), 5)
        self.assertGreater(st.median(klein), st.median(gross) * 3,
                           "der Grösseneffekt ist verschwunden — dann misst "
                           "die Rohquote plötzlich etwas anderes")

    def test_the_residual_is_much_narrower_than_the_raw_share(self):
        """Der Zweck der Korrektur. Roh spannt die Quote über Faktor 180; nach
        Abzug der Grösse bleibt rund ein Zehntel davon — und ERST das ist eine
        Aussage über die Auslegung."""
        roh = sorted(float(r["anteil"]) for r in self.sauber)
        fak = sorted(float(r["faktor_gegen_erwartung"]) for r in self.sauber
                     if r["faktor_gegen_erwartung"])
        self.assertGreater(len(fak), 20)
        self.assertLess(fak[-1] / fak[0], roh[-1] / roh[0] / 3)

    def test_the_expectation_is_centred(self):
        """Der Median des Faktors muss nahe 1 liegen — sonst sagt das Modell
        systematisch zu viel oder zu wenig voraus, und jede Abweichung davon
        wäre ein Modellfehler statt eines Befunds."""
        fak = sorted(float(r["faktor_gegen_erwartung"]) for r in self.sauber
                     if r["faktor_gegen_erwartung"])
        self.assertAlmostEqual(fak[len(fak) // 2], 1.0, delta=0.25)

    def test_implausible_head_counts_are_marked_not_used(self):
        """REM1 ist das Template, in dem #17 die stärksten Ausreisser findet.
        Ein Report mit `rem_per_head`-Befund darf nicht als
        Governance-Aussage durchgehen."""
        self.assertTrue(any(r["vorbehalt"] == "rem_befund" for r in self.rows),
                        "kein einziger REM-Befund markiert — dann greift der "
                        "Filter nicht mehr")

    def test_the_size_correction_removes_the_perimeter_effect(self):
        """Das Argument für die Korrektur, an den Daten geprüft.

        Wikidata führt die Belegschaft der GRUPPE, ein IND-Report die
        Risikoträger des Einzelinstituts — roh liegen die IND-Quoten deshalb um
        ein Vielfaches höher (gemessen Faktor 3,7). Wäre der Faktor gegen die
        Erwartung ebenso gespalten, hätte das Modell Perimeter mit Grösse
        verwechselt und die Kennzahl misste weiter die Konsolidierungsstufe.
        """
        import statistics as st
        def med(feld, scope):
            w = [float(r[feld]) for r in self.sauber
                 if r["scope"] == scope and r[feld]]
            self.assertGreater(len(w), 10, f"zu wenige {scope}-Zeilen")
            return st.median(w)

        roh = med("anteil", "IND") / med("anteil", "CON")
        rest = (med("faktor_gegen_erwartung", "IND")
                / med("faktor_gegen_erwartung", "CON"))
        self.assertGreater(roh, 2.0,
                           "der Perimeterunterschied ist roh verschwunden — "
                           "dann prüft dieser Test nichts mehr")
        self.assertLess(rest, 1.3,
                        "der Faktor trennt weiter nach Konsolidierungsstufe — "
                        "die Korrektur hat den Perimeter nicht aufgelöst")

    def test_every_row_carries_its_source(self):
        """Wikidata ist crowdsourced. Ohne die Item-ID ist der Wert nicht
        nachprüfbar, und ohne den Stand nicht datierbar."""
        for r in self.rows:
            with self.subTest(bank=r["bank_name"]):
                self.assertTrue(r["wikidata_id"])

    def test_the_order_is_stable(self):
        k = [(r["lei"], r["scope"], r["refPeriod"]) for r in self.rows]
        self.assertEqual(k, sorted(k))


class StichprobeTest(unittest.TestCase):
    def test_the_sample_is_not_the_population(self):
        """#40 verlangt es ausdrücklich: „65 % Trefferquote heisst 35 % Lücke,
        und die ist nicht zufällig verteilt." Gemessen liegt die Quote bei 49 %,
        und die mit Mitarbeiterzahl bei 24 %."""
        if not WIKIDATA.exists():
            self.skipTest("wikidata_entities.csv nicht gebaut")
        with WIKIDATA.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        mit = [r for r in rows if r["mitarbeiter"]]
        self.assertGreater(len(rows), 100)
        self.assertLess(len(mit), len(rows),
                        "alle Treffer tragen eine Mitarbeiterzahl — dann ist "
                        "die zweite, kleinere Quote keine eigene Aussage mehr")


if __name__ == "__main__":
    unittest.main(verbosity=2)
