"""Vergütungs-Auswertung REM1 (#18).

## Warum dieses Profil einen eigenen Test bekommt

Das Issue formuliert die Begründung selbst: *„Eine Vergütungs-Rangliste mit
falschen Zahlen wäre der schädlichste denkbare Fehler in diesem Projekt."*
Vergütung ist reputationsrelevant und wird zitiert; eine Fehlmeldung hier ist
nicht wie eine falsche Nachkommastelle bei einer RWA-Kennzahl.

Und die Rohdaten laden dazu ein. Die fixe Vergütung pro Kopf streut über 14
Größenordnungen: Rabobank meldet 11,7 Bio. EUR für 9 Vorstandsmitglieder,
andere melden `0` oder `0,03`. Ungefiltert führt Rabobank die Rangliste mit
1,3 Bio. EUR pro Kopf an.

## Die drei Zusagen, die hier gehalten werden

1. **Ein Korridor, nicht zwei.** `metrics.REM_PER_HEAD` ist die einzige
   Definition. `check_plausibility.RATIO_RULES` prüft den Bestand damit, der
   Viewer filtert die Liste damit. Zwei Zahlenpaare an zwei Orten wären eine
   Rangliste, die nach anderen Grenzen filtert als die, gegen die geprüft wurde
   — und niemand sähe es.
2. **Das Tor ist gesetzt.** Ein Vergütungsprofil ohne `gate` sähe genauso aus,
   nur mit Rabobank an der Spitze.
3. **Gefiltert wird sichtbar.** Der Ausschluss ist eine Behauptung über
   Institute; er gehört genannt, mit Quote und Namen.
"""

from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import check_plausibility as cp  # noqa: E402
import metrics as mx  # noqa: E402

VIEWER = ROOT / "processed" / "zweig_a" / "viewer_json.html"
SHARDS = ROOT / "scripts" / "build_zweig_a_shards.py"

REM = "30.01"
PROFILE = "verg"


def profile():
    return next(p for p in mx.PROFILES if p["id"] == PROFILE)


def metric(mid):
    return next(m for m in mx.METRICS if m["id"] == mid)


class OneCorridorTest(unittest.TestCase):
    """Bestandsprüfung und Viewer-Filter müssen dieselben Grenzen benutzen."""

    def test_the_plausibility_rule_takes_its_bounds_from_the_registry(self):
        rule = next(r for r in cp.RATIO_RULES if r["id"] == "rem_per_head")
        self.assertEqual((rule["lo"], rule["hi"]), tuple(mx.REM_PER_HEAD),
                         "check_plausibility.py prüft gegen andere Grenzen, als "
                         "der Viewer zum Filtern benutzt")

    def test_every_gated_metric_carries_exactly_that_corridor(self):
        for mid in profile()["gate"]:
            self.assertEqual(metric(mid).get("plausible"), list(mx.REM_PER_HEAD),
                             f"{mid} filtert nach einem eigenen Korridor")

    def test_the_corridor_is_wide_enough_to_be_a_unit_check_not_a_pay_judgement(self):
        """Der Korridor darf keine Gehaltsaussage treffen. Beobachtet über 1.784
        Paare: p25 46.500 · Median 142.516 · p75 305.537 EUR. Die Grenzen liegen
        weit ausserhalb — unten geringfügige Aufsichtsratsvergütungen, oben die
        höchstbezahlten Banker Europas."""
        lo, hi = mx.REM_PER_HEAD
        self.assertLess(lo, 46_500, "Untergrenze schneidet ins p25 der Population")
        self.assertGreater(hi, 6_000_000,
                           "Obergrenze schneidet echte Spitzenvergütungen weg — "
                           "gemessener Höchstwert nach Filter: 5.686.699 EUR")

    def test_the_documented_extremes_land_on_the_right_side(self):
        lo, hi = mx.REM_PER_HEAD
        # Rabobank: 11,7 Bio. EUR fixe Vergütung für 9 Vorstandsmitglieder.
        self.assertGreater(1.1736e13 / 9, hi)
        # In Millionen gemeldet statt in Währungseinheiten.
        self.assertLess(0.11, lo)
        # Und die grössten echten Werte bleiben drin.
        for real in (5_686_699, 4_843_054, 3_533_330):
            self.assertTrue(lo <= real <= hi, f"{real} EUR wäre ausgeschlossen")


class GateTest(unittest.TestCase):
    def test_the_remuneration_profile_declares_a_gate(self):
        """Ohne `gate` unterscheidet sich das Profil nicht von einer ungefilterten
        Rangliste — und die wird von Rabobank angeführt."""
        self.assertTrue(profile().get("gate"),
                        "Vergütungsprofil ohne Plausibilitäts-Tor")

    def test_the_gate_covers_every_function_level_the_profile_shows(self):
        """Eine ungeprüfte Funktionsstufe wäre eine Spalte, in der eine falsche
        Meldeeinheit stehen bleibt, während die Zeile im Übrigen zugelassen ist."""
        shown = {m for m in profile()["metrics"] if metric(m)["op"] == "perhead"}
        self.assertEqual(shown, set(profile()["gate"]))

    def test_all_four_function_levels_are_present(self):
        cols = {c[2] for mid in profile()["gate"] for c in metric(mid)["cells"]}
        self.assertEqual(cols, {"0010", "0020", "0030", "0040"},
                         "REM1 hat vier Funktionsstufen; es fehlt eine")

    def test_the_viewer_applies_the_gate_before_it_measures_anything(self):
        """Die Reihenfolge ist der Punkt: eine Meldung in falscher Einheit darf
        weder in der Liste stehen NOCH Verteilung, Perzentile oder Zaunwerte
        verschieben. Ein Filter, der erst auf die Tabelle wirkt, verschöbe still
        den Median, an dem sich alle anderen messen."""
        src = VIEWER.read_text(encoding="utf-8")
        marker = "const allRows=prof.gate.length?gross.filter(r=>!r._out)"
        self.assertIn(marker, src,
                      "Die Zeilenmenge wird nicht mehr am Tor geteilt — dann "
                      "messen Verteilung und Perzentile die ungefilterte Menge")
        gate = src.index(marker)
        for later in ("percentileMap(allRows", "fenceOutliers(allRows",
                      "distributionRow(allRows"):
            self.assertGreater(src.index(later), gate,
                               f"{later} misst vor dem Plausibilitäts-Tor")

    def test_a_reported_zero_does_not_remove_a_report(self):
        """Ein unentgeltlich arbeitender Aufsichtsrat ist eine Governance-Tatsache,
        kein Meldefehler — und der Korridor prüft Einheiten. Ohne diese Ausnahme
        verlöre die Rangliste zwei Institute samt ihren drei intakten
        Funktionsstufen, weil eine vierte Stufe null meldet."""
        src = VIEWER.read_text(encoding="utf-8")
        self.assertIn("const outsideCorridor=", src)
        body = re.search(r"const outsideCorridor=\(m,v\)=>\s*(.*?);", src, re.S).group(1)
        self.assertIn("v!==0", body,
                      "Eine gemeldete Null wirft den Report aus der Liste")

    def test_one_bad_level_removes_the_whole_report(self):
        """Gemessen: bei 35 der 59 betroffenen Reports liegen ALLE VIER Stufen
        daneben. Das ist eine falsche Meldeeinheit für das ganze Template, kein
        einzelner Wert — also fliegt der Report, nicht die Zelle."""
        src = VIEWER.read_text(encoding="utf-8")
        self.assertIn("row._out = prof.gate.some(", src,
                      "Das Tor prüft nicht mehr alle Stufen (`some`) — bei `every` "
                      "bliebe ein Report drin, solange eine Stufe plausibel ist")


class TransparencyTest(unittest.TestCase):
    """„Implausible Melder ausschließen UND die Ausschlussquote transparent
    ausweisen (nicht still filtern)" — Punkt 1 des Issues."""

    def setUp(self):
        self.src = VIEWER.read_text(encoding="utf-8")

    def test_the_exclusion_is_reported_with_count_and_share(self):
        note = re.search(r"function gateNote\(prof, out, total\)\{(.*?)\n\}",
                         self.src, re.S)
        self.assertIsNotNone(note, "gateNote nicht gefunden")
        body = note.group(1)
        self.assertIn("out.length", body, "Ausschluss ohne Anzahl")
        self.assertIn("out.length/total", body, "Ausschluss ohne Quote")

    def test_the_excluded_institutions_are_named(self):
        """Der Ausschluss ist eine Behauptung über ein Institut. Eine Zahl allein
        lässt sich nicht nachprüfen."""
        note = re.search(r"function gateNote\(prof, out, total\)\{(.*?)\n\}",
                         self.src, re.S).group(1)
        self.assertIn("gatelist", note)
        self.assertIn("esc(r.name)", note, "Ausschlussliste ohne Namen")
        self.assertIn("esc(nf(w,", note,
                      "Ausschlussliste ohne den Wert, der den Ausschluss auslöst")

    def test_the_named_value_is_the_one_furthest_outside(self):
        """Sonst stünde bei fast jedem Institut die Funktionsstufe, die im Profil
        zufällig vorn steht — die Liste behauptete dann einen Grund, der nicht
        der ausschlaggebende ist."""
        note = re.search(r"function gateNote\(prof, out, total\)\{(.*?)\n\}",
                         self.src, re.S).group(1)
        self.assertIn("const worst=prof.gate.filter(g=>outsideCorridor(g,r[g.id]))", note)
        self.assertIn(".sort(", note)

    def test_the_profile_carries_the_caveats_the_issue_asks_for(self):
        """Konsolidierungskreis, „identified staff" als regulatorische Teilmenge,
        Teilzeit/unterjährige Zugänge — Punkt 4 des Issues."""
        note = profile()["note"]
        for term in ("identified staff", "Teilzeit", "Konsolidierungskreis"):
            self.assertIn(term, note, f"Caveat ohne „{term}“")

    def test_the_bonus_cap_is_not_presented_as_a_group_limit(self):
        """Die 100-%-Grenze der CRD gilt je PERSON. Neben einen
        Gruppendurchschnitt gestellt behauptet sie einen Verstoß, wo keiner
        belegt ist — derselbe Fehler wie KM1 r0190 neben der CET1-Quote (#25)."""
        for mid in ("rem_varfix_mb", "rem_varfix_ot"):
            m = metric(mid)
            self.assertIsNotNone(m.get("floor"))
            self.assertIn("Person", m.get("note", ""),
                          f"{mid}: Bonusdeckel ohne den Hinweis, dass er je "
                          "Person gilt")


class WiringTest(unittest.TestCase):
    def test_the_benchmark_payload_carries_the_template(self):
        """Ohne 30.01 in HEAD_TEMPLATES fände der Viewer keine Zellen und zeigte
        ein leeres Profil — ohne Fehler."""
        src = SHARDS.read_text(encoding="utf-8")
        block = re.search(r"HEAD_TEMPLATES = \{(.*?)\n\}", src, re.S).group(1)
        self.assertIn(f'"{REM}"', block)

    def test_the_viewer_can_evaluate_the_per_head_form(self):
        src = VIEWER.read_text(encoding="utf-8")
        body = re.search(r"function metricValue\(rep, m\)\{(.*?)\n\}", src, re.S).group(1)
        self.assertIn("case 'perhead':", body)

    def test_the_amount_is_converted_before_it_is_divided(self):
        """Zähler in Meldewährung, Nenner eine Kopfzahl: ohne Umrechnung
        verglichen wir Währungen statt Vergütungen. Bei Swedbank Hypotek
        (28 Mio. SEK, 2 Köpfe) wären das 14 Mio. statt 1,29 Mio. EUR."""
        src = VIEWER.read_text(encoding="utf-8")
        body = re.search(r"case 'perhead': \{(.*?)\n    \}", src, re.S).group(1)
        self.assertIn("eurOf(rep, at(0))", body,
                      "Betrag wird ohne EZB-Kurs durch die Kopfzahl geteilt")

    def test_a_headcount_of_zero_yields_no_value_instead_of_infinity(self):
        src = VIEWER.read_text(encoding="utf-8")
        body = re.search(r"case 'perhead': \{(.*?)\n    \}", src, re.S).group(1)
        self.assertIn("heads<=0", body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
