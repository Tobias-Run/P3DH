"""Reports mit zwei Währungen (#55).

## Der Befund

`build_zweig_a_shards.py` schrieb `baseCurrency` je Report aus der **ersten
Zeile** des Pass-1-Ergebnisses fest. 12 Reports melden aber in zwei Währungen —
durchweg Landeswährung plus EUR —, und der Viewer rechnet jeden monetären Wert
mit dieser einen Währung um. Gemessen: **9.086 monetäre Fakten** mit dem
falschen Kurs.

Sichtbar wurde es an Zahlen, die eine Woche zuvor ausgeliefert worden waren:

| | angezeigt | richtig | Faktor |
|---|---|---|---|
| NOBA Group, Fixvergütung/Kopf Vorstand | 441.335 EUR | 4.775.833 EUR | 10,8 |
| BRD-Groupe SG, dasselbe | 65.562 EUR | 334.161 EUR | 5,1 |
| Eurobank Bulgaria, NPE Kredite | 0,2 Mrd | 0,4 Mrd | 2,0 |

Die Analyseschicht war nie betroffen: `fact_value_eur` im Parquet rechnet je
Fakt mit dessen eigener Währung. Falsch war ausschließlich die Anzeige — Zweig A
leitet EUR selbst ab, statt den gerechneten Wert zu übernehmen.

## Warum eine Karte je Template genügt

Gemessen: **0 von 919** (Report, Template)-Paaren tragen intern mehr als eine
Währung. Die Währung wechselt zwischen Templates, nie innerhalb eines. Deshalb
123 Ausnahmen statt 12.351 Koordinaten.

## Was hier gehalten wird

Die Auflösung als reine Funktion, die Zusage, dass der Viewer die Ausnahme
überhaupt fragt — und dass er auf Report-Ebene keine Währung mehr behauptet,
die nur für einen Teil gilt.
"""

from pathlib import Path
import json
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_zweig_a_shards as bz  # noqa: E402

VIEWER = ROOT / "processed" / "zweig_a" / "viewer_json.html"
INDEX = ROOT / "processed" / "zweig_a" / "data" / "index.json"

R = "rs:LEI1.CON|2025-12-31"


class ResolveTest(unittest.TestCase):
    """`report_currencies` — (report, template, currency, n) -> Auflösung."""

    def test_a_single_currency_needs_no_exception(self):
        dom, ov = bz.report_currencies([(R, "61.00", "EUR", 100)])[R]
        self.assertEqual(dom, "EUR")
        self.assertEqual(ov, {})

    def test_the_dominant_currency_is_the_one_with_the_most_facts(self):
        """Nicht die erstsortierte — genau daran ist es gescheitert."""
        dom, _ = bz.report_currencies([(R, "61.00", "EUR", 3),
                                       (R, "82.00.A", "PLN", 900)])[R]
        self.assertEqual(dom, "PLN")

    def test_the_deviating_templates_are_listed(self):
        dom, ov = bz.report_currencies([(R, "61.00", "PLN", 900),
                                        (R, "30.01", "EUR", 40),
                                        (R, "41.00", "EUR", 12)])[R]
        self.assertEqual(dom, "PLN")
        self.assertEqual(ov, {"30.01": "EUR", "41.00": "EUR"})

    def test_only_the_deviations_are_listed(self):
        """Eine vollständige Karte wäre 919 Einträge je Report statt 123 im
        ganzen Bestand — und sie würde bei jedem Lauf mitwachsen."""
        _, ov = bz.report_currencies([(R, "61.00", "PLN", 900),
                                      (R, "82.00.A", "PLN", 50)])[R]
        self.assertEqual(ov, {})

    def test_a_tie_is_broken_deterministically(self):
        """Bei Gleichstand entschied vorher die Einfügereihenfolge. Das ist der
        Fehlermodus, den #55 aufgedeckt hat — er darf nicht zurückkommen."""
        rows = [(R, "a", "EUR", 10), (R, "b", "PLN", 10)]
        first = bz.report_currencies(rows)[R]
        self.assertEqual(bz.report_currencies(list(reversed(rows)))[R], first)

    def test_the_output_is_sorted(self):
        """Der Index wird committet; eine unsortierte Karte erzeugte bei jedem
        Lauf einen Diff, der nichts bedeutet."""
        _, ov = bz.report_currencies([(R, "61.00", "PLN", 900),
                                      (R, "82.00.A", "EUR", 5),
                                      (R, "30.01", "EUR", 40)])[R]
        self.assertEqual(list(ov), sorted(ov))

    def test_facts_without_a_currency_do_not_vote(self):
        """Nicht-monetäre Fakten tragen keine Währung — sie dürfen die Mehrheit
        nicht verschieben."""
        dom, _ = bz.report_currencies([(R, "61.00", "PLN", 10),
                                       (R, "60.00.A", "", 5000)])[R]
        self.assertEqual(dom, "PLN")


class ViewerTest(unittest.TestCase):
    def setUp(self):
        self.src = VIEWER.read_text(encoding="utf-8")

    def test_the_viewer_asks_for_the_template_currency(self):
        m = re.search(r"function curOf\(rep, tid\)\{(.*?)\n\}", self.src, re.S)
        self.assertIsNotNone(m, "curOf nimmt kein Template entgegen")
        self.assertIn("rep.cur", m.group(1), "Die Ausnahmeliste wird nicht gelesen")

    def _calls(self, name):
        """Aufrufe von `name(...)` samt Argumenten — mit Klammerzählung, weil
        die Argumente selbst Klammern enthalten (`m.cells[0][0]`, `at(0)`)."""
        out = []
        for m in re.finditer(r"\b" + name + r"\(", self.src):
            i, depth = m.end(), 1
            while i < len(self.src) and depth:
                depth += (self.src[i] == "(") - (self.src[i] == ")")
                i += 1
            out.append(self.src[m.end():i - 1])
        return out

    def test_every_euro_conversion_names_its_template(self):
        """`eurOf(rep, v)` ohne Template rechnet wieder mit der
        Report-Währung — und genau das war der Fehler."""
        found = 0
        for name in ("eurOf", "eurBn"):
            for args in self._calls(name):
                if args.startswith("rep,v,tid"):
                    continue                      # die Definition selbst
                found += 1
                # Argumente auf oberster Ebene zählen
                depth, n = 0, 1
                for ch in args:
                    depth += (ch in "([") - (ch in ")]")
                    n += (ch == "," and depth == 0)
                self.assertEqual(n, 3, f"{name}({args}) rechnet ohne Template "
                                       "und damit mit der Report-Währung")
        self.assertGreater(found, 0, "keine EUR-Umrechnung gefunden — "
                                     "prüft der Test noch, was er soll?")

    def test_the_index_entry_carries_the_exception_list(self):
        self.assertIn("cur:r.cur||null", self.src,
                      "Der Viewer übernimmt die Ausnahmeliste nicht aus dem Index")

    def test_a_mixed_report_no_longer_claims_one_currency(self):
        """Auf Report-Ebene gibt es keine richtige Einzelantwort. Eine zu
        nennen wäre dieselbe Behauptung wie vorher, nur besser begründet."""
        self.assertIn("function curLabel(rep)", self.src)
        self.assertIn("curLabel(rep)", self.src)
        self.assertIn("je Template verschieden", self.src,
                      "Der Report-Kopf sagt nicht, dass die Währung wechselt")


class ShippedIndexTest(unittest.TestCase):
    """Gegen den gebauten Index — die Kunstbeispiele oben sagen nichts darüber,
    ob der Bestand tatsächlich so aussieht."""

    def setUp(self):
        if not INDEX.exists():
            self.skipTest("index.json nicht gebaut")
        self.reports = json.loads(INDEX.read_text(encoding="utf-8"))["reports"]

    def test_the_mixed_reports_carry_their_exceptions(self):
        mixed = [r for r in self.reports if r.get("cur")]
        self.assertEqual(len(mixed), 12,
                         f"{len(mixed)} Reports mit Währungswechsel — erwartet 12")
        self.assertEqual(sum(len(r["cur"]) for r in mixed), 123)

    def test_no_exception_repeats_the_dominant_currency(self):
        for r in self.reports:
            for tid, cur in (r.get("cur") or {}).items():
                self.assertNotEqual(cur, r["baseCurrency"],
                                    f"{r['entityID']} {tid}: Ausnahme ohne Abweichung")

    def test_every_report_still_names_a_currency(self):
        """Der Rückfallwert muss stehen: ohne ihn rechnet der Viewer für alle
        Templates ohne Ausnahme gar nicht mehr um."""
        without = [r["entityID"] for r in self.reports if not r.get("baseCurrency")]
        self.assertEqual(without, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
