"""Skalenbefunde je Report (#83) — und die Reihenfolge, die sie brauchen.

## Was hier eigentlich geprüft wird

Nicht „findet das Skript Skalenfehler". Das ist die leichte Hälfte. Die schwere
ist, dass **die vorhandene Prüfung sie nicht finden kann** — und dass niemand
das merkt, weil sie dann einfach nichts meldet.

`check_plausibility.py` misst mit `robust_z()` nur den Abstand ÜBER dem
Zellmedian. Das ist richtig so (die untere Flanke einer Exposure-Verteilung ist
natürlich), aber ein Skalenfehler macht Werte IMMER zu klein. Er landet damit
genau dort, wo nicht hingesehen wird: 1.524 der 1.966 prüfbaren Fakten der
Deutschen Pfandbriefbank am 2025-06-30 liegen mindestens drei Grössenordnungen
unter ihrem Zellmedian, und kein einziger löst etwas aus. Die Prüfung meldet
null Befunde für einen Report, in dem 67 von 69 Templates danebenliegen.

Ein Test, der nur „0 Befunde == kein Problem" liest, hätte das nie gesehen.
Deshalb prüfen die Tests unten drei Dinge getrennt:

  * der Detektor erkennt die belegten Fälle und **nicht** das echt kleine
    Institut (Kommuninvest),
  * die REIHENFOLGE in der Pipeline steht — ohne sie schliesst
    `check_plausibility.py` stillschweigend nichts aus und liefert nur
    schlechtere Zahlen, ohne zu scheitern,
  * die Marke kommt im Viewer an, auch für Reports mit null Befunden.
"""

from pathlib import Path
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

OUT = ROOT / "processed" / "scale_flags.csv"


def zeilen():
    if not OUT.exists():
        return []
    with OUT.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class UrteilTest(unittest.TestCase):
    """Die Entscheidungsregel, isoliert — ohne Parquet."""

    def setUp(self):
        import build_report_scale as b
        self.b = b

    def test_the_impossible_trea_decides_alone(self):
        """446 EUR Gesamtrisikobetrag gibt es bei keiner Säule-3-pflichtigen
        Bank. Dafür braucht es kein zweites Signal."""
        self.assertEqual(self.b.urteil_von(["untergrenze"], 446.0), "skaliert")

    def test_a_clean_body_overrules_the_lower_bound(self):
        """Die Untergrenze liest EINE Zelle (`61.00` r0040) und schliesst daraus
        auf den ganzen Report. Gegen 300 gemessene Zellen, die sauber sind,
        trägt dieser eine Wert das Urteil nicht.

        Der Fall: Axa banque meldet KM1 in Millionen (TREA 2.998,88) und die
        übrigen 317 monetären Werte in Einheiten. „Der ganze Report ist
        skaliert" wäre für 317 von 318 Werten falsch."""
        self.assertEqual(self.b.urteil_von(["untergrenze"], 2999.0, -0.777),
                         "unauffaellig")
        self.assertEqual(self.b.urteil_von(["untergrenze"], 2999.0, -6.158),
                         "skaliert")

    def test_an_unmeasurable_body_is_not_an_acquittal(self):
        """`versatz=None` heisst „zu wenige vergleichbare Zellen", nicht
        „sauber". Fehlendes Wissen als Entlastung zu lesen ist genau der Fehler,
        den das Projekt als „Fehlt ≠ Null" führt — und er beträfe vier der sechs
        Reports, bei denen die Untergrenze allein feuert."""
        self.assertEqual(self.b.urteil_von(["untergrenze"], 3865.0, None),
                         "skaliert")

    def test_an_overruled_lower_bound_still_leaves_the_other_signals(self):
        """Widerlegt ist nur die Untergrenze. Ein Report mit sauberem Rumpf,
        aber zwei weiteren Signalen, fällt nicht durch das Raster."""
        self.assertEqual(
            self.b.urteil_von(["untergrenze", "zeitreihe", "decimals"], 5e7, -0.5),
            "skaliert")

    def test_a_missing_trea_does_not_silence_the_check(self):
        """Der Fehlertyp, der dieses Projekt am häufigsten getroffen hat: eine
        Prüfung, die sich für zufrieden erklärt, WEIL die Kennzahl fehlt, an der
        sie hängt. Ohne TREA greift die Untergrenze nicht, es bleibt bei einem
        Signal — und ein Versatz von -6,2 wäre folgenlos.

        Belegt an DLR Kredit A/S (2025-12-31): 598 monetäre Werte, Median 23
        EUR, Maximum 29.712 EUR, bei einer dänischen Realkreditbank. Ein
        Stichtag, also auch kein Zeitreihensignal."""
        self.assertEqual(self.b.urteil_von(["versatz"], None, -6.206), "skaliert")
        self.assertEqual(self.b.urteil_von(["versatz"], None, -2.1), "unauffaellig",
                         "zwischen -2 und -4 bleibt der Versatz Zweitsignal")

    def test_the_grey_zone_needs_two_independent_signals(self):
        """Zwischen 10^6 und 10^8 kann ein sehr kleines Institut echt liegen.
        Ein Signal ist dort ein Verdacht, kein Urteil — sonst trifft es die
        kleinen Häuser systematisch."""
        trea = 5e7
        self.assertEqual(self.b.urteil_von(["versatz"], trea), "verdacht")
        self.assertEqual(self.b.urteil_von(["versatz", "zeitreihe"], trea), "skaliert")

    def test_a_large_bank_is_never_called_scaled_on_signals_alone(self):
        """Oberhalb der Grauzone reicht auch zwei Signale nur für einen
        Verdacht: der Versatz ist von der Institutsgrösse mitverursacht, und ein
        grosses Haus mit ungewöhnlichem Geschäft ist keine Fehlmeldung."""
        self.assertEqual(self.b.urteil_von(["versatz", "decimals"], 5e11), "verdacht")
        self.assertEqual(self.b.urteil_von(["versatz"], 5e11), "unauffaellig")
        self.assertEqual(self.b.urteil_von([], 5e11), "unauffaellig")

    def test_the_time_series_compares_against_the_largest_own_date(self):
        """Der erste Entwurf verglich gegen den MEDIAN der eigenen Stichtage.
        Der Median folgt der MEHRHEIT: sind drei von vier Stichtagen skaliert,
        sitzt er im kaputten Bereich und die Regel verstummt — ausgerechnet
        dort, wo der Defekt am ausgeprägtesten ist.

        Das Verhältnis 3:1 ist deshalb der Fall, der die beiden Bezugsgrössen
        überhaupt trennt. Bei 2:2 liefern Median und Maximum dasselbe; ein Test
        mit dieser Belegung ist gegen die Verwechslung blind, und genau das war
        die erste Fassung dieses Tests."""
        trea = {("E", "2025-06-30"): 1e4, ("E", "2025-09-30"): 1e4,
                ("E", "2025-12-31"): 1e4, ("E", "2026-03-31"): 1e10}
        f = self.b.zeitreihen_faktor(trea)
        ueber = {rp for (_, rp), v in f.items() if v >= self.b.ZEITREIHE_FAKTOR}
        self.assertEqual(ueber, {"2025-06-30", "2025-09-30", "2025-12-31"},
                         "gegen den Median gemessen verstummt die Regel ganz")

    def test_a_single_date_yields_no_time_series_signal(self):
        """Mit einem Stichtag gibt es keine Vergleichsgrundlage. Dann steht
        hier NICHTS — nicht „sauber". Das ist der Unterschied zwischen „geprüft
        und in Ordnung" und „nicht prüfbar" (Arbeitsprinzip 3)."""
        self.assertEqual(self.b.zeitreihen_faktor({("E", "2025-06-30"): 1e4}), {})

    def test_the_template_rule_keeps_the_one_documented_case(self):
        """ING Bank Slaski, 67.01.A, Versatz -6,672. Eine Verschärfung auf
        „nahe an einer Tausenderpotenz" warf ihn hinaus — 0,672 war mehr als
        die Toleranz. Eine Regel, die den einzigen belegten Fall ihrer Klasse
        verliert, ist keine Verschärfung, sondern eine Fehlkalibrierung."""
        je = [("E", "2025-06-30", "67.01.A", -6.672, 30),
              ("E", "2025-09-30", "67.01.A", -0.15, 30),
              ("E", "2025-12-31", "67.01.A", -0.12, 30)]
        out = self.b.template_spruenge(je)
        self.assertIn(("E", "2025-06-30", "67.01.A"), out)
        self.assertNotIn(("E", "2025-09-30", "67.01.A"), out)

    def test_a_template_seen_only_once_is_not_judged(self):
        self.assertEqual(self.b.template_spruenge(
            [("E", "2025-06-30", "67.01.A", -6.672, 30)]), {})

    def test_the_estimated_factor_is_a_power_of_a_thousand_or_nothing(self):
        """Melder skalieren in Tausend oder Million. Ein Schätzer mit drei
        Nachkommastellen suggeriert eine Genauigkeit, die die Grösse nicht hat."""
        self.assertEqual(self.b.faktor_von(-6.158, None), "10^6")
        self.assertEqual(self.b.faktor_von(-2.9, None), "10^3")
        self.assertEqual(self.b.faktor_von(-0.4, None), "",
                         "ein kleiner Versatz ist keine Skala")


class ErgebnisTest(unittest.TestCase):
    """Gegen die gebaute Datei — die Fälle, an denen die Regeln geeicht sind."""

    def setUp(self):
        self.rows = zeilen()
        if not self.rows:
            self.skipTest("scale_flags.csv nicht gebaut")
        self.reports = [r for r in self.rows if r["ebene"] == "report"]

    def _bank(self, teil, ebene="report"):
        return [r for r in self.rows if teil.lower() in r["bank_name"].lower()
                and r["ebene"] == ebene]

    def test_every_report_gets_a_verdict(self):
        """Auch `unauffaellig` ist ein Urteil und gehört in die Datei. Nur die
        markierten zu schreiben hiesse, „nicht geprüft" und „geprüft und in
        Ordnung" ununterscheidbar zu machen."""
        self.assertGreater(len(self.reports), 800)
        self.assertEqual({r["urteil"] for r in self.reports},
                         {"skaliert", "verdacht", "unauffaellig"})

    def test_the_documented_cases_are_flagged(self):
        """pbb und Bank of Valletta — beide mit TREA unter der fachlichen
        Untergrenze und einem Versatz um -6."""
        for teil in ("Pfandbriefbank", "Valletta"):
            with self.subTest(bank=teil):
                sk = [r for r in self._bank(teil) if r["urteil"] == "skaliert"]
                self.assertTrue(sk, f"{teil} nicht als skaliert erkannt")
                self.assertTrue(all(r["faktor_geschaetzt"] == "10^6" for r in sk))

    def test_the_defect_is_dated_not_permanent(self):
        """Die pbb meldet an VIER Stichtagen und liegt an ZWEI daneben. Eine
        Regel, die das Institut statt der Meldung markiert, wäre ein Werturteil
        — und nachweislich falsch."""
        pbb = self._bank("Pfandbriefbank")
        self.assertGreaterEqual(len(pbb), 4, "pbb meldet an vier Stichtagen")
        sk = {r["refPeriod"] for r in pbb if r["urteil"] == "skaliert"}
        self.assertEqual(sk, {"2025-06-30", "2025-09-30"})

    def test_a_genuinely_small_institution_is_not_flagged(self):
        """Der wichtigste Negativfall. Kommuninvest ist ein Kommunalfinanzierer
        mit fast nur nullgewichteten Aktiva: 3,4 Mrd SEK TREA gegen 12 Mrd SEK
        Kapital, also 355 % CET1 — nachprüfbar KORREKT. Wer Kommuninvest als
        skaliert führt, hat eine Regel gebaut, die kleine Häuser bestraft."""
        km = self._bank("Kommuninvest")
        self.assertTrue(km, "Kommuninvest fehlt im Bestand")
        for r in km:
            with self.subTest(rp=r["refPeriod"]):
                self.assertEqual(r["urteil"], "unauffaellig", f"Signale: {r['signale']}")

    def test_a_report_with_a_clean_scale_stays_clean(self):
        """National Bank of Greece hat einen EINZELNEN auffälligen Wert (Klasse
        C). Reportweit ist nichts daran; das gehört zur Zellprüfung, nicht
        hierher."""
        for r in self._bank("National Bank of Greece"):
            self.assertEqual(r["urteil"], "unauffaellig")

    def test_the_template_level_catches_what_the_report_level_misses(self):
        """Klasse B, und der Grund für die Spalte `ebene`. ING Bank Slaski ist
        reportweit unauffällig (Versatz -0,15) und hat trotzdem ein skaliertes
        Template. Ohne diese Ebene fällt der Fall durch beide Netze."""
        tpl = self._bank("Slaski", ebene="template")
        self.assertTrue(tpl, "ING Bank Slaski nicht auf Templateebene erkannt")
        self.assertTrue(any(r["template_id"].startswith("67.01") for r in tpl))
        rep = [r for r in self._bank("Slaski") if r["urteil"] != "unauffaellig"]
        self.assertFalse(rep, "reportweit sollte Slaski gerade NICHT auffallen")

    def test_an_overruled_finding_is_not_lost_but_relocated(self):
        """Axa banque: die Reportzeile führt `untergrenze_widerlegt` und steht
        auf `unauffaellig`, der Befund selbst steht auf `61.00`. Ginge er
        verloren, hätte die Verfeinerung einen echten Fund gekostet."""
        axa = [r for r in self.rows if "Axa banque" in r["bank_name"]]
        if not axa:
            self.skipTest("Axa banque nicht im Bestand")
        rep = [r for r in axa if r["ebene"] == "report"]
        tpl = [r for r in axa if r["ebene"] == "template"]
        self.assertTrue(all(r["urteil"] == "unauffaellig" for r in rep))
        self.assertIn("untergrenze_widerlegt", "|".join(r["signale"] for r in rep))
        self.assertTrue(any(r["template_id"] == "61.00" and r["urteil"] == "skaliert"
                            for r in tpl), "der Befund ist ersatzlos verschwunden")

    def test_no_row_is_clean_despite_a_signal_that_decides_alone(self):
        """Zwei Signale entscheiden für sich: die unwiderlegte Untergrenze und
        ein Versatz jenseits von VERSATZ_ALLEIN. Steht eines davon neben
        `unauffaellig`, hat die Regel sich selbst widersprochen.

        Ein einzelner `versatz` zwischen -2 und -4 darf dagegen sehr wohl neben
        `unauffaellig` stehen — er ist von der Institutsgrösse mitverursacht und
        deshalb ausdrücklich nur Zweitsignal."""
        import build_report_scale as b
        for r in self.rows:
            if r["urteil"] != "unauffaellig":
                continue
            with self.subTest(bank=r["bank_name"], rp=r["refPeriod"]):
                self.assertNotIn("untergrenze", r["signale"].split("|"))
                if r["versatz_log10"]:
                    self.assertGreater(float(r["versatz_log10"]), b.VERSATZ_ALLEIN)

    def test_the_template_level_never_repeats_a_flagged_report(self):
        """Eine Template-Zeile in einem schon markierten Report sagte dasselbe
        noch einmal, nur kleinteiliger — und bliese die Datei auf."""
        markiert = {(r["entityID"], r["refPeriod"]) for r in self.reports
                    if r["urteil"] in ("skaliert", "verdacht")}
        for r in self.rows:
            if r["ebene"] == "template":
                self.assertNotIn((r["entityID"], r["refPeriod"]), markiert)

    def test_the_order_is_stable(self):
        k = [(r["ebene"], r["entityID"], r["refPeriod"], r["template_id"])
             for r in self.rows]
        self.assertEqual(k, sorted(k))


class KopplungTest(unittest.TestCase):
    """Die Reihenfolge und der Verbrauch — hier sitzt die stille Inkonsistenz."""

    def setUp(self):
        self.pipeline = (ROOT / ".github" / "workflows" / "pipeline.yml").read_text(
            encoding="utf-8")
        self.plaus = (ROOT / "scripts" / "check_plausibility.py").read_text(
            encoding="utf-8")

    def test_the_scale_flags_are_built_before_the_plausibility_check(self):
        """Die eigentliche Falle. Läuft check_plausibility.py zuerst, findet es
        keine scale_flags.csv, schliesst nichts aus — und SCHEITERT NICHT. Es
        liefert nur stillschweigend schlechtere Zahlen. Ein Ausfall, der sich
        als Erfolg meldet, ist der Fehlertyp, der hier am teuersten war."""
        i = self.pipeline.index("scripts/build_report_scale.py")
        j = self.pipeline.index("scripts/check_plausibility.py")
        self.assertLess(i, j, "build_report_scale.py läuft NACH check_plausibility.py")

    def test_only_proven_scale_defects_are_excluded(self):
        """Ein Verdacht reicht nicht, um jemanden aus der Grundgesamtheit zu
        nehmen, und die Templateebene betrifft ohnehin nur einzelne Zellen."""
        import check_plausibility as cp
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".csv", newline="",
                                         delete=False, encoding="utf-8") as fh:
            w = csv.DictWriter(fh, ["ebene", "lei", "scope", "refPeriod", "urteil"])
            w.writeheader()
            w.writerows([
                {"ebene": "report", "lei": "A", "scope": "CON",
                 "refPeriod": "2025-06-30", "urteil": "skaliert"},
                {"ebene": "report", "lei": "B", "scope": "CON",
                 "refPeriod": "2025-06-30", "urteil": "verdacht"},
                {"ebene": "template", "lei": "C", "scope": "CON",
                 "refPeriod": "2025-06-30", "urteil": "skaliert"},
                {"ebene": "report", "lei": "D", "scope": "CON",
                 "refPeriod": "2025-06-30", "urteil": "unauffaellig"},
            ])
            pfad = fh.name
        self.assertEqual(cp.lade_skalenmarken(pfad),
                         {("A", "CON", "2025-06-30")})
        Path(pfad).unlink()

    def test_a_missing_file_excludes_nothing(self):
        """Fehlt die Datei, verhält sich die Prüfung wie vorher — statt
        stillschweigend die halbe Population zu verlieren."""
        import check_plausibility as cp
        self.assertEqual(
            cp.lade_skalenmarken(ROOT / "processed" / "gibt_es_nicht.csv"), set())

    def test_only_the_statistics_query_excludes_them(self):
        """Der Ausschluss gilt dem NENNER, nicht der Prüfung. Die markierten
        Reports werden weiter geprüft — sonst verschwänden ihre übrigen
        Befunde mit dem Skalenurteil.

        Geprüft wird an den beiden SQL-Blöcken selbst, abgegrenzt über ihre
        Namen im `ordered_query`-Aufruf: der Statistikblock trägt den
        Ausschluss, der Einzelbefundblock nicht."""
        def block(name):
            ende = self.plaus.index(f'"{name}"')
            anfang = self.plaus.rindex("ordered_query(con,", 0, ende)
            return self.plaus[anfang:ende]
        self.assertIn("{ausschluss_sql}", block("Zellstatistik"))
        self.assertNotIn("ausschluss_sql", block("Einzelbefunde"),
                         "die Einzelbefunde schliessen die markierten Reports aus — "
                         "damit verschwinden ihre Befunde mit dem Defekt")


class ViewerTest(unittest.TestCase):
    """Die Marke muss den Leser erreichen — sonst ist der Befund nicht gemacht."""

    def setUp(self):
        import build_zweig_a_shards as b
        self.b = b
        self.viewer = (ROOT / "processed" / "zweig_a" / "viewer_json.html").read_text(
            encoding="utf-8")

    def test_a_report_wide_defect_carries_no_template_list(self):
        """`t` leer heisst „gilt für den ganzen Report", nicht „für kein
        Template". Wer das verwechselt, markiert ausgerechnet die schwersten
        Fälle gar nicht — und der Viewer muss beide Fälle getrennt formulieren."""
        self.assertIn("!q.sc.t.length || q.sc.t.includes(tpl)", self.viewer)
        self.assertIn("im gesamten Report", self.viewer)

    def test_a_report_without_findings_still_gets_an_entry(self):
        """Die Zusammenführung selbst, ohne gebaute Artefakte — sonst prüft der
        Test eine Datei von gestern und bleibt grün, während der Code kaputt
        ist. Genau das war die erste Fassung: sie las `index.json` und überlebte
        eine Mutation, die die Marke für befundfreie Reports wegwarf."""
        quality = {"rs:MIT.CON|2025-06-30": {"n": 7, "h": 0, "m": 3, "d": 1.2,
                                             "t": ["61.00"], "th": []}}
        flags = {"rs:MIT.CON|2025-06-30": {"u": "skaliert", "f": "10^6",
                                           "s": "untergrenze", "t": []},
                 "rs:OHNE.CON|2025-06-30": {"u": "skaliert", "f": "10^6",
                                            "s": "untergrenze", "t": []}}
        out = self.b.merge_scale_flags(quality, flags)
        self.assertEqual(set(out), set(flags), "der befundfreie Report fehlt")
        self.assertEqual(out["rs:OHNE.CON|2025-06-30"]["n"], 0)
        self.assertEqual(out["rs:OHNE.CON|2025-06-30"]["sc"]["u"], "skaliert")
        self.assertEqual(out["rs:MIT.CON|2025-06-30"]["n"], 7,
                         "die vorhandenen Befunde wurden überschrieben")

    def test_the_shipped_index_carries_the_marks(self):
        """Und dieselbe Aussage einmal am ausgelieferten Artefakt — die Datei,
        die der Leser wirklich bekommt."""
        flags = self.b.load_scale_flags(ROOT)
        if not flags:
            self.skipTest("scale_flags.csv nicht gebaut")
        idx = ROOT / "processed" / "zweig_a" / "data" / "index.json"
        if not idx.exists():
            self.skipTest("Zweig-A-Index nicht gebaut")
        import json
        reports = json.loads(idx.read_text(encoding="utf-8"))["reports"]
        mit = [r for r in reports if (r.get("q") or {}).get("sc")]
        self.assertEqual(len(mit), len(flags))
        ohne_befund = [r for r in mit if not r["q"]["n"]]
        self.assertGreater(len(ohne_befund), 10,
                           "kein markierter Report ohne Befunde — unerwartet, "
                           "denn genau die sind der Grund für diese Marke")

    def test_the_scale_mark_is_visually_distinct_from_the_plausibility_mark(self):
        """Zwei verschiedene Aussagen. „Ein Wert passt nicht zur Verteilung"
        und „die absoluten Beträge sind um einen Faktor daneben" dürfen nicht
        als dieselbe Marke gelesen werden."""
        self.assertIn(".qb.sb{", self.viewer)
        self.assertIn(".ovq.ovsc{", self.viewer)

    def test_the_viewer_says_that_ratios_survive(self):
        """Ein Verhältnis überlebt einen gleichmässigen Skalenfehler — die
        RWA-Dichte der pbb ist mit 0,43 richtig, obwohl Zähler und Nenner beide
        zu klein sind. Ohne diesen Satz liest die Marke sich als „Report
        unbrauchbar", und dann gehen Quoten verloren, die stimmen."""
        self.assertIn("Quoten und Verhältnisse dieses Reports bleiben gültig",
                      self.viewer)

    def test_the_runtime_check_actually_looks_for_the_mark(self):
        """Zwei Funktionen sind in diesem Projekt schon fertig gebaut, getestet
        und committet worden, ohne irgendetwas zu tun. Quelltextprüfungen allein
        haben das nicht gesehen."""
        rt = (ROOT / "scripts" / "check_viewer_runtime.py").read_text(encoding="utf-8")
        self.assertIn(".ovsc", rt)
        self.assertIn("zeigt keine Marke", rt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
