"""Rechtzeitigkeit der Offenlegung (#33).

## Die drei Weichen, an denen diese Kennzahl kippt

**Erste oder letzte Einreichung.** 66 % der Kombinationen haben mehr als eine.
Wer die letzte misst, misst Korrekturverhalten (#31) und bestraft Institute,
die nachbessern.

**Innerhalb oder ueber die Klasse.** CRR Art. 433a–c geben verschiedenen
Institutstypen verschiedene Fristen. Gemessen liegen „Large highest EEA" bei 58
und „Large subsidiaries" bei 69 Tagen — 11 Tage Klassenunterschied bei einem
Median von 58. Ein roher Vergleich liest das als Sorgfalt.

**Vor oder nach dem Hub-Start.** Die vier aelteren Stichtage wurden
nachgereicht (Median 246/160/180/131 gegen 58). Diese Zahlen als Verspaetung zu
lesen, waere die Umkehrung dessen, was sie sind.
"""

from datetime import datetime
from pathlib import Path
import collections
import csv
import statistics as st
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

LAG = ROOT / "processed" / "disclosure_lag.csv"
MANIFEST = ROOT / "interim" / "edap_recon" / "manifest_full.csv"


def zeilen():
    if not LAG.exists():
        return []
    with LAG.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class LogikTest(unittest.TestCase):
    def setUp(self):
        import build_disclosure_lag as b
        self.b = b

    def test_the_first_submission_is_the_one_that_counts(self):
        """Rechtzeitigkeit heisst: wann lag die Offenlegung ERSTMALS vor.
        Die letzte zu nehmen misst Korrekturverhalten und bestraft
        ausgerechnet das Nachbessern."""
        man = [
            {"lei": "A", "refdate": "2026-03-31", "module": "010000",
             "submission_ts": "20260601120000000"},
            {"lei": "A", "refdate": "2026-03-31", "module": "010000",
             "submission_ts": "20260701120000000"},
        ]
        (ts0, ts1, n), = self.b.einreichungen(man).values()
        self.assertEqual(ts0[:8], "20260601", "nicht die erste Einreichung")
        self.assertEqual(ts1[:8], "20260701")
        self.assertEqual(n, 2)

    def test_submissions_out_of_order_do_not_fool_it(self):
        """Das Manifest ist ein Harvest-Schnappschuss, keine sortierte Liste."""
        man = [
            {"lei": "A", "refdate": "2026-03-31", "module": "010000",
             "submission_ts": "20260901120000000"},
            {"lei": "A", "refdate": "2026-03-31", "module": "010000",
             "submission_ts": "20260501120000000"},
        ]
        (ts0, _, _), = self.b.einreichungen(man).values()
        self.assertEqual(ts0[:8], "20260501")

    def test_a_reference_date_before_the_hub_went_live_is_not_lateness(self):
        """26.01.2026 ging P3DH live. Was davor lag, wurde nachgereicht —
        der Abstand ist eine Eigenschaft des Hub-Starts."""
        self.assertTrue(self.b._nachgereicht("2025-12-31"))
        self.assertTrue(self.b._nachgereicht("2025-06-30"))
        self.assertFalse(self.b._nachgereicht("2026-03-31"))

    def test_the_percentile_runs_from_early_to_late(self):
        """0 = frueheste Offenlegung der Klasse, 100 = spaeteste. Andersherum
        haette ein 'gutes' Perzentil die Verspaetung gelobt."""
        werte = [10, 20, 30, 40, 50]
        self.assertLess(self.b.perzentil(10, werte), self.b.perzentil(50, werte))
        self.assertEqual(self.b.perzentil(30, werte), 50.0)

    def test_a_thin_class_gets_no_percentile(self):
        """Unter fuenf Instituten ist ein Perzentil eine Scheinaussage —
        dieselbe Schwelle wie in der Peer-Logik des Viewers."""
        self.assertGreaterEqual(self.b.MIN_KLASSE, 5)


class TabelleTest(unittest.TestCase):
    def setUp(self):
        self.rows = zeilen()
        if not self.rows:
            self.skipTest("disclosure_lag.csv nicht gebaut")

    def test_the_lag_matches_the_manifest(self):
        """Gegen die Quelle nachgerechnet, nicht gegen sich selbst."""
        with MANIFEST.open(encoding="utf-8") as fh:
            man = list(csv.DictReader(fh))
        erste = {}
        for r in man:
            k = (r["lei"], r["refdate"], r["module"])
            if k not in erste or r["submission_ts"] < erste[k]:
                erste[k] = r["submission_ts"]
        geprueft = 0
        for z in self.rows[:200]:
            k = (z["lei"], z["refdate"], z["module"])
            with self.subTest(k=k):
                self.assertIn(k, erste)
                soll = (datetime.strptime(erste[k][:14], "%Y%m%d%H%M%S")
                        - datetime.strptime(z["refdate"], "%Y-%m-%d")).days
                self.assertEqual(int(z["lag_days"]), soll)
                geprueft += 1
        self.assertGreater(geprueft, 100)

    def test_the_last_submission_is_never_earlier_than_the_first(self):
        for z in self.rows:
            with self.subTest(lei=z["lei"]):
                self.assertLessEqual(int(z["lag_days"]), int(z["lag_days_last"]))

    def test_resubmissions_actually_occur(self):
        """Faende sich keine einzige, waere die Gruppierung kaputt — gemessen
        sind es rund zwei Drittel."""
        mehr = [z for z in self.rows if int(z["n_submissions"]) > 1]
        self.assertGreater(len(mehr), 0.3 * len(self.rows),
                           "zu wenige Wiedereinreichungen — Gruppierung pruefen")

    def test_the_percentile_never_crosses_a_class(self):
        """Der Kern der Randbedingung aus #33. Ein Perzentil, das ueber
        Institutstypen hinweg gebildet wird, misst die
        Proportionalitaetsklasse statt der Sorgfalt."""
        klassen = collections.defaultdict(list)
        for z in self.rows:
            klassen[(z["refdate"], z["institution_type"])].append(int(z["lag_days"]))
        mit = [z for z in self.rows if z["percentile"]]
        # OHNE diese Schranke ist der Test wertlos: gruppiert man versehentlich
        # nach einem anderen Schluessel, laeuft die Nachschlagung ins Leere,
        # KEIN Perzentil wird geschrieben — und eine Schleife ueber „Zeilen mit
        # Perzentil" prueft dann nichts und meldet Erfolg. Genau so ist diese
        # Pruefung beim ersten Mutationstest durchgerutscht.
        self.assertGreater(len(mit), 0.5 * len(self.rows),
                           "fast keine Perzentile vergeben — falsch gruppiert?")
        for z in mit:
            werte = klassen[(z["refdate"], z["institution_type"])]
            with self.subTest(lei=z["lei"], refdate=z["refdate"]):
                self.assertEqual(int(z["klasse_n"]), len(werte))
                self.assertAlmostEqual(float(z["klasse_median"]),
                                       st.median(werte), places=1)

    def test_no_percentile_below_the_threshold(self):
        for z in self.rows:
            with self.subTest(lei=z["lei"]):
                if int(z["klasse_n"]) < 5 or not z["institution_type"]:
                    self.assertEqual(z["percentile"], "",
                                     "Perzentil trotz zu duenner Klasse")

    def test_only_post_launch_reference_dates_are_marked_reliable(self):
        for z in self.rows:
            with self.subTest(refdate=z["refdate"]):
                erwartet = "true" if z["refdate"] >= "2026-01-26" else "false"
                self.assertEqual(z["belastbar"], erwartet)

    def test_the_reliable_window_is_dominated_by_large_institutions(self):
        """Kein Schoenheitsfehler, sondern CRR Art. 433a: quartalsweise legen
        nur grosse Institute offen. Fuer rund die Haelfte des Bestands ist
        Rechtzeitigkeit am eingeschwungenen Stichtag nicht messbar — wer das
        uebersieht, haelt die Kennzahl faelschlich fuer flaechendeckend."""
        belastbar = [z for z in self.rows if z["belastbar"] == "true"]
        self.assertTrue(belastbar)
        typen = collections.Counter(z["institution_type"] for z in belastbar)
        gross = typen["Large highest EEA"] + typen["Large subsidiaries"]
        self.assertGreater(gross / len(belastbar), 0.9,
                           f"Klassenverteilung hat sich geaendert: {dict(typen)}")

    def test_the_order_is_stable(self):
        k = [(z["lei"], z["refdate"], z["module"]) for z in self.rows]
        self.assertEqual(k, sorted(k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
