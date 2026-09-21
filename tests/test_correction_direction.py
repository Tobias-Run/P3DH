"""Richtung der Korrekturen (Nachfolger von #31, `korrekturspiel.md` §8).

Fünf Dinge halten die Tests fest, und jedes davon war im ersten Entwurf falsch:

1. **Nicht jede Nachmeldung ist eine Korrektur.** 60 von 202 ändern kein
   einziges Faktum, 25 ergänzen nur. Sie alle als „Korrektur" zu zählen war
   der erste Entwurf — und hätte die Grundgesamtheit mehr als verdoppelt.
2. **Die Prüfreihenfolge trägt das Ergebnis.** Eine CET1-Quote von 2.456 % ist
   ein Skalenfehler; prüft man die Richtung zuerst, bekommt er ein Vorzeichen
   und zählt als Selbstdarstellung mit.
3. **Der Skalenfilter allein genügt nicht.** Er prüft die *Änderung*
   (2.456 % -> 2.466 % ist Faktor 1,004 und fällt durch), das Plausibilitätsband
   prüft das *Niveau*.
4. **Fehlt ≠ Null.** Ein Wert, der erst in der zweiten Fassung auftaucht, ist
   Vollständigkeit, keine Richtung.
5. **Die Wesentlichkeitsschwelle ist abgelesen, nicht gesetzt.** Ein Drittel
   aller Änderungen liegt unter 0,005 pp — Rundung in der fünften
   Nachkommastelle des Bruchs.
"""

from pathlib import Path
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "correction_direction.csv"
OUT_SUM = ROOT / "processed" / "correction_summary.csv"


class RahmenwerkTest(unittest.TestCase):
    def setUp(self):
        import build_correction_direction as c
        self.c = c

    def test_the_framework_comes_from_the_path(self):
        u = ("https://errp.eba.europa.eu/public-documents/CODIS/input/"
             "X.CON_DE_PILLAR3020000_CODIS_2025-06-30_2026.zip")
        self.assertEqual(self.c.rahmenwerk(u), "CODIS")

    def test_two_frameworks_are_not_the_same_report(self):
        """Der Fehler, der #31 einmal auf 2.539 statt 472 Korrekturen brachte:
        CODIS und FINDIS desselben Instituts tragen dieselbe Modulnummer und
        galten als Fassungen voneinander."""
        basis = "https://errp.eba.europa.eu/public-documents/{}/input/x.zip"
        self.assertNotEqual(self.c.rahmenwerk(basis.format("CODIS")),
                            self.c.rahmenwerk(basis.format("FINDIS")))

    def test_an_unexpected_url_does_not_raise(self):
        self.assertEqual(self.c.rahmenwerk("https://example.org/x.zip"), "")


class LatenzTest(unittest.TestCase):
    def setUp(self):
        import build_correction_direction as c
        self.c = c

    def test_an_immediate_resubmission_is_an_upload(self):
        self.assertEqual(self.c.latenzklasse(0.001), "unter_1h")

    def test_the_boundaries_are_where_they_claim_to_be(self):
        self.assertEqual(self.c.latenzklasse(0.5), "unter_1t")
        self.assertEqual(self.c.latenzklasse(3.0), "unter_7t")
        self.assertEqual(self.c.latenzklasse(20.0), "unter_30t")

    def test_a_late_correction_is_its_own_class(self):
        """Die einzige Klasse, in der sich die Frage des Dokuments stellt:
        ein Fehler, der die interne Endkontrolle überlebt hat."""
        self.assertEqual(self.c.latenzklasse(45.0), "ueber_30t")
        self.assertEqual(self.c.latenzklasse(400.0), "ueber_30t")


class SkalenTest(unittest.TestCase):
    def setUp(self):
        import build_correction_direction as c
        self.c = c

    def test_a_factor_of_a_hundred_is_a_unit_fix(self):
        self.assertTrue(self.c.skalenkorrektur(0.1836, 18.36))

    def test_an_ordinary_revision_is_not(self):
        self.assertFalse(self.c.skalenkorrektur(0.2789, 0.1368))

    def test_a_ratio_needs_two_positive_values(self):
        """Ein Vorzeichenwechsel ist etwas anderes als eine Einheit, und eine
        Null hätte kein Verhältnis — beides hier ausdrücklich keine
        Skalenkorrektur."""
        self.assertFalse(self.c.skalenkorrektur(-0.0024, 0.2521))
        self.assertFalse(self.c.skalenkorrektur(0.0, 0.25))
        self.assertFalse(self.c.skalenkorrektur(None, 0.25))


class PlausibelTest(unittest.TestCase):
    def setUp(self):
        import build_correction_direction as c
        self.c = c

    def test_an_ordinary_capital_ratio_passes(self):
        self.assertTrue(self.c.plausibel(0.1836, (0.0, 1.0)))

    def test_a_ratio_of_twentyfour_hundred_percent_does_not(self):
        self.assertFalse(self.c.plausibel(24.56, (0.0, 1.0)))

    def test_a_negative_capital_ratio_does_not(self):
        self.assertFalse(self.c.plausibel(-0.0024, (0.0, 1.0)))

    def test_without_a_band_nothing_is_rejected(self):
        self.assertTrue(self.c.plausibel(24.56, None))


class UrteilTest(unittest.TestCase):
    def setUp(self):
        import build_correction_direction as c
        self.c = c
        self.band = (0.0, 1.0)

    def test_a_rising_ratio_flatters(self):
        self.assertEqual(
            self.c.urteil_von(0.1767, 0.1883, +1, band=self.band), "guenstiger")

    def test_a_falling_ratio_gives_a_good_number_back(self):
        """Standard Chartered Bank AG: 27,89 % -> 13,68 %, mehr als 30 Tage
        später. Die grösste Einzelkorrektur im Bestand, und sie halbiert die
        eigene Kapitalquote."""
        self.assertEqual(
            self.c.urteil_von(0.27887, 0.13676, +1, band=self.band),
            "unguenstiger")

    def test_the_level_is_checked_before_the_direction(self):
        """Die Prüfreihenfolge. 2.456 % -> 2.466 % ist eine Erhöhung und wäre
        `guenstiger`, wenn das Niveau nicht zuerst geprüft würde — der
        Skalenfilter fängt es nicht, weil die ÄNDERUNG winzig ist."""
        self.assertEqual(
            self.c.urteil_von(24.56, 24.66, +1, band=self.band), "unplausibel")

    def test_a_correction_out_of_the_implausible_is_not_a_flattery(self):
        """-0,24 % -> 25,21 %: eine Fehlerbereinigung. Als `guenstiger`
        gezählt wäre sie die grösste positive Änderung im Bestand."""
        self.assertEqual(
            self.c.urteil_von(-0.0024, 0.2521, +1, band=self.band),
            "unplausibel")

    def test_a_unit_fix_is_no_direction(self):
        self.assertEqual(
            self.c.urteil_von(0.1836, 18.36, +1, band=None), "skalenkorrektur")

    def test_a_missing_value_is_not_a_zero(self):
        self.assertEqual(self.c.urteil_von(None, 0.18, +1), "neu_gemeldet")
        self.assertEqual(self.c.urteil_von(0.18, None, +1), "entfallen")
        self.assertEqual(self.c.urteil_von(None, None, +1), "unveraendert")

    def test_rounding_in_the_fifth_decimal_is_not_a_correction(self):
        """26,702 % -> 26,700 %. Ein Drittel aller Änderungen sieht so aus;
        ohne Schwelle bekäme jede davon ein Vorzeichen."""
        self.assertEqual(
            self.c.urteil_von(0.26702, 0.26700, +1, band=self.band),
            "unveraendert")

    def test_the_threshold_is_actually_used(self):
        self.assertEqual(
            self.c.urteil_von(0.1767, 0.1883, +1, min_pp=5.0, band=self.band),
            "unveraendert")

    def test_the_direction_table_is_pinned(self):
        """Das ganze Ergebnis hängt an diesen sieben Vorzeichen, und ein
        vertipptes davon fällt sonst nirgends auf: es dreht nur eine Kennzahl
        und lässt alle Summen plausibel aussehen.

        Alle sieben sind `+1`, weil nur Kennzahlen aufgenommen sind, bei denen
        „höher" für das Institut eindeutig besser ist. Eine Grösse, bei der das
        umgekehrt gilt, gehört in die Tabelle — aber nicht unbemerkt.
        """
        self.assertEqual(
            self.c.KENNZAHLEN,
            {"0050": ("CET1-Quote", +1),
             "0060": ("Tier-1-Quote", +1),
             "0070": ("Gesamtkapitalquote", +1),
             "0200": ("CET1 nach SREP-Anforderung", +1),
             "0220": ("Verschuldungsquote", +1),
             "0320": ("LCR", +1),
             "0350": ("NSFR", +1)})

    def test_no_supervisory_requirement_is_in_the_table(self):
        """SREP-Anforderung (0110), Pufferanforderungen (0120–0190) und die
        Niveaus (Kapital 0010–0030, TREA 0040) sind bewusst draussen: das eine
        setzt die Aufsicht, das andere trägt ohne Bezugsgrösse kein Urteil."""
        for zeile in ("0010", "0030", "0040", "0110", "0180", "0190"):
            with self.subTest(zeile=zeile):
                self.assertNotIn(zeile, self.c.KENNZAHLEN)

    def test_a_metric_where_lower_is_better_would_flip(self):
        """Gegenprobe zur Richtungstabelle: die Vorzeichenlogik hängt an ihr
        und nicht am Vorzeichen der Differenz."""
        self.assertEqual(
            self.c.urteil_von(0.1767, 0.1883, -1, band=self.band),
            "unguenstiger")


class ArtTest(unittest.TestCase):
    def setUp(self):
        import build_correction_direction as c
        self.c = c

    def test_an_identical_resubmission_changes_nothing(self):
        """60 von 202 Nachmeldungen sehen so aus."""
        self.assertEqual(self.c.art_der_nachmeldung(0, 0, 0), "inhaltsgleich")

    def test_pure_addition_is_completeness_not_correction(self):
        """Ein Institut meldet zuerst null Fakten und liefert 1.284 nach. Das
        als Korrektur zu führen hiesse, eine unvollständige Erstmeldung mit
        einer falschen Zahl gleichzusetzen."""
        self.assertEqual(self.c.art_der_nachmeldung(1284, 0, 0),
                         "vervollstaendigung")

    def test_pure_removal_is_its_own_case(self):
        self.assertEqual(self.c.art_der_nachmeldung(0, 40, 0), "kuerzung")

    def test_a_single_changed_value_makes_it_a_correction(self):
        """Der Vorrang ist Absicht: sobald ein gemeldeter Wert sich ändert,
        ist die Richtungsfrage gestellt — auch wenn daneben ergänzt wurde."""
        self.assertEqual(self.c.art_der_nachmeldung(100, 5, 1),
                         "wertkorrektur")

    def test_adding_and_removing_without_changing_is_a_rebuild(self):
        self.assertEqual(self.c.art_der_nachmeldung(10, 10, 0), "umbau")


class GesamturteilTest(unittest.TestCase):
    def setUp(self):
        import build_correction_direction as c
        self.c = c

    def test_both_directions_at_once_are_not_netted(self):
        """Saldieren würde gegenläufige Korrekturen zum Verschwinden bringen
        und ein Paar als unauffällig ausweisen, das zwei Bewegungen enthält."""
        self.assertEqual(
            self.c.gesamturteil({"guenstiger": 3, "unguenstiger": 2}, 5),
            "gemischt")

    def test_one_direction_carries(self):
        self.assertEqual(
            self.c.gesamturteil({"guenstiger": 2, "unguenstiger": 0}, 2),
            "guenstiger")
        self.assertEqual(
            self.c.gesamturteil({"guenstiger": 0, "unguenstiger": 1}, 1),
            "unguenstiger")

    def test_untouched_and_touched_without_direction_are_different(self):
        """Zusammengefasst sähe beides wie Unauffälligkeit aus: das eine heisst
        „die Kennzahlen blieben", das andere „sie änderten sich, aber nur durch
        Ergänzung, Einheit oder Rundung"."""
        leer = {"guenstiger": 0, "unguenstiger": 0}
        self.assertEqual(self.c.gesamturteil(leer, 0), "kennzahl_unberuehrt")
        self.assertEqual(self.c.gesamturteil(leer, 7), "ohne_richtung")


class MengenvergleichTest(unittest.TestCase):
    def setUp(self):
        import build_correction_direction as c
        self.c = c

    def test_three_numbers_not_one(self):
        alt = {"a": "1", "b": "2", "c": "3"}
        neu = {"a": "1", "b": "9", "d": "4"}
        self.assertEqual(self.c.mengenvergleich(alt, neu), (1, 1, 1))

    def test_identical_sets_yield_zeroes(self):
        alt = {"a": "1"}
        self.assertEqual(self.c.mengenvergleich(alt, dict(alt)), (0, 0, 0))


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        if not OUT.exists() or not OUT_SUM.exists():
            self.skipTest("correction_direction.csv nicht gebaut")
        with OUT.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))
        with OUT_SUM.open(encoding="utf-8") as fh:
            self.summen = list(csv.DictReader(fh))

    def test_the_comparison_has_content(self):
        self.assertGreater(len(self.summen), 150)

    def test_every_row_carries_a_verdict(self):
        erlaubt = {"guenstiger", "unguenstiger", "unveraendert", "neu_gemeldet",
                   "entfallen", "skalenkorrektur", "unplausibel"}
        for r in self.rows:
            with self.subTest(lei=r["lei"], kennzahl=r["kennzahl"]):
                self.assertIn(r["urteil"], erlaubt)

    def test_every_pair_carries_a_kind(self):
        erlaubt = {"inhaltsgleich", "vervollstaendigung", "kuerzung",
                   "wertkorrektur", "umbau"}
        for s in self.summen:
            with self.subTest(lei=s["lei"]):
                self.assertIn(s["art"], erlaubt)

    def test_content_identical_resubmissions_exist_and_are_many(self):
        """Der Befund, der die Fragestellung verschiebt: ein knappes Drittel
        der Nachmeldungen ändert kein einziges Faktum. Verschwände er, wäre
        entweder der Vergleich kaputt oder die Klassifikation."""
        gleich = [s for s in self.summen if s["art"] == "inhaltsgleich"]
        self.assertGreater(len(gleich), 30)
        for s in gleich:
            with self.subTest(lei=s["lei"]):
                self.assertEqual(int(s["n_wert_geaendert"]), 0)
                self.assertEqual(int(s["n_nur_neu"]), 0)

    def test_a_value_correction_really_changed_a_value(self):
        for s in self.summen:
            if s["art"] == "wertkorrektur":
                with self.subTest(lei=s["lei"]):
                    self.assertGreater(int(s["n_wert_geaendert"]), 0)

    def test_no_direction_survives_an_implausible_level(self):
        """Die Gegenprobe zur Prüfreihenfolge am fertigen Blatt."""
        import build_correction_direction as c
        for r in self.rows:
            if r["urteil"] in ("guenstiger", "unguenstiger"):
                band = c.PLAUSIBEL.get(r["kennzahl"])
                with self.subTest(lei=r["lei"], kennzahl=r["kennzahl"]):
                    self.assertTrue(c.plausibel(float(r["wert_alt"]), band))
                    self.assertTrue(c.plausibel(float(r["wert_neu"]), band))

    def test_the_direction_matches_its_own_delta(self):
        for r in self.rows:
            if r["urteil"] in ("guenstiger", "unguenstiger"):
                with self.subTest(lei=r["lei"], kennzahl=r["kennzahl"]):
                    d = float(r["delta_pp"])
                    self.assertEqual(r["urteil"] == "guenstiger", d > 0,
                                     "alle geführten Kennzahlen sind +1")

    def test_neither_direction_dominates(self):
        """Die Antwort auf die Frage des Blattes — und zugleich der Wächter
        darüber: kippt das Verhältnis einmal deutlich, ist entweder die Welt
        eine andere geworden oder die Messung kaputt."""
        echt = {(s["lei"], s["refPeriod"], s["fassung"])
                for s in self.summen if s["art"] == "wertkorrektur"}
        g = sum(1 for r in self.rows
                if r["urteil"] == "guenstiger"
                and (r["lei"], r["refPeriod"], r["fassung"]) in echt)
        u = sum(1 for r in self.rows
                if r["urteil"] == "unguenstiger"
                and (r["lei"], r["refPeriod"], r["fassung"]) in echt)
        self.assertGreater(g, 0)
        self.assertGreater(u, 0)
        self.assertLess(max(g, u) / min(g, u), 2.0)

    def test_the_order_is_stable(self):
        k = [(r["lei"], r["refPeriod"], r["fassung"]) for r in self.summen]
        self.assertEqual(k, sorted(k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
