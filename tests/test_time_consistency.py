"""Intra-Instituts-Konsistenz über die Zeit — vierte Regelfamilie (#36).

Die drei älteren Regelfamilien in `check_plausibility.py` messen einen Wert an
ANDEREN: an der Population derselben Zelle oder an einem fachlichen Korridor.
Die vierte misst ihn am Institut selbst, zwei Stichtage vorher.

## Die vier Fallen, gegen die diese Tests geschrieben sind

1. **Der Schlüssel ist keine Zelle.** #36 schlägt (LEI, Scope, Template, Zeile,
   Spalte) vor. Nachgemessen liegen auf 268 dieser Koordinaten MEHRERE
   Datenpunkte (74.00.B r0110 c0010 trägt vier). Über sie gepaart entstehen
   16.048 „Sprünge" zwischen dem 30.06. und sich selbst — ein Vergleich über
   null Tage, der wie ein Befund aussieht.

2. **Der Framework-Bruch.** Über den Wechsel 4.1 -> 4.2 wird ein Teil der
   Zellen auf neue dp-Codes umgebunden. Ein naiver Join über den dp-Code
   verliert diese Zeitreihen STILL — eine fehlende Zeitreihe sieht aus wie ein
   Institut ohne Historie, nicht wie ein Fehler.

3. **Zwei effektive Nullen sind kein Sprung.** Die AIB Group meldet 0,0008 EUR
   und ein halbes Jahr später 5·10^-23 EUR. Das sind 19,2 Größenordnungen und
   bedeutet nichts — genau die Falle, die im Querschnitt unter (1a) steht.
   Die Schwelle darf aber nicht für Quoten gelten, wo ein Wert unter 1 der
   Normalfall ist.

4. **Ein Sprung ist nicht per se ein Fehler.** Springen 79,9 % der Zellen eines
   Reports, ist die Aussage über den REPORT zu treffen und nicht über 1.152
   einzelne Zellen.

## Und die Falle hinter Falle 2

`lade_framework_bruecke()` liefert heute eine LEERE Menge unsicherer
Koordinaten. Alle 123 `ambiguous`-Zeilen der Brücke haben dp_41 == dp_42 — sie
sind Mehrfachbelegungen einer Koordinate, keine Bedeutungsänderungen. Eine
Prüfung, deren Sperrliste leer ist, sieht aus wie eine, die nicht greift. Der
Unterschied ist die Gegenprobe: 60 umgebundene dp-Codes WERDEN übersetzt, und
die Tests unten halten beides fest — dass heute nichts gesperrt wird UND dass
sich das füllt, sobald die Brücke eine echte Mehrdeutigkeit enthält.
"""

from pathlib import Path
import csv
import io
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import check_plausibility as cp  # noqa: E402

FINDINGS = ROOT / "interim" / "plausibility_findings.csv"
PROFILE = ROOT / "processed" / "quality_profile.csv"
BRIDGE = ROOT / "codebook" / "framework_bridge.csv"


def _paar(v1, v2, report="r", zelle="z", **rest):
    return dict(report=report, zelle=zelle, v1=v1, v2=v2, **rest)


class JumpOrdersTest(unittest.TestCase):
    def test_a_factor_of_a_million_is_six_orders(self):
        self.assertAlmostEqual(cp.jump_orders(1e3, 1e9), 6.0)

    def test_the_measure_is_blind_to_direction(self):
        """Der entscheidende Unterschied zu `robust_z`, das nur nach oben
        sieht. Ein Skalenfehler macht Werte zu KLEIN; wäre dieses Maß ebenfalls
        einseitig, fände es genau die Fälle nicht, für die es gebaut wurde."""
        self.assertEqual(cp.jump_orders(1e9, 1e3), cp.jump_orders(1e3, 1e9))

    def test_a_sign_change_does_not_hide_the_jump(self):
        """Die Deutsche Bank meldet in 63.02.A 2,7 Mrd EUR und danach
        −9,5·10^-8. Über den vorzeichenbehafteten Quotienten wäre das gar nicht
        messbar; über den Betrag sind es 16,5 Größenordnungen."""
        self.assertGreater(cp.jump_orders(2.69e9, -9.5e-8), 16)

    def test_a_reported_zero_has_no_order_of_magnitude(self):
        """Nicht „kein Sprung", sondern „nicht messbar". Eine Null ist eine
        ANGABE, und keine Zehnerpotenz bildet einen Betrag auf null ab — ein
        Einheitenfehler kann also gar nicht so aussehen. 196.302 der 658.149
        Zeitpaare fallen hier heraus, und der Bericht zählt sie."""
        self.assertIsNone(cp.jump_orders(0, 1e9))
        self.assertIsNone(cp.jump_orders(1e9, 0))
        self.assertIsNone(cp.jump_orders(0, 0))

    def test_two_values_below_the_floor_are_noise(self):
        """AIB Group: 0,0008 EUR gegen 5·10^-23 EUR. 19,2 Größenordnungen
        zwischen zwei Beträgen, die beide nichts sind."""
        self.assertIsNone(cp.jump_orders(8e-4, 5e-23, cp.MATERIALITAET["monetary"]))

    def test_one_material_side_still_counts(self):
        """Die Gegenprobe zur vorigen, und sie ist der Kern: ein echter
        Skalenfehler macht einen großen Wert klein. Sperrte die Schwelle auch
        diese Paare, verlöre die Regel ihren Zweck."""
        self.assertGreater(cp.jump_orders(8.2e7, 9.3e-9, cp.MATERIALITAET["monetary"]), 15)

    def test_a_quota_gets_its_own_floor(self):
        """Quoten brauchen eine eigene Grenze: dort ist ein Wert unter 1 der
        Normalfall. BPER Banca fällt in 41.00 von 0,24 auf 3·10^-6 — mit der
        EUR-Grenze wäre dieser Befund mit dem Rauschen zusammen verworfen
        worden, weil beide Seiten unter 1 liegen."""
        self.assertIsNone(cp.jump_orders(0.24247, 3e-6, cp.MATERIALITAET["monetary"]))
        self.assertGreater(cp.jump_orders(0.24247, 3e-6, cp.MATERIALITAET["percentage"]), 4)

    def test_two_immaterial_quotas_are_noise_too(self):
        """Všeobecná úverová banka meldet einen „of which environmentally
        sustainable"-Anteil von 2,8·10^-10 gegen 5,0·10^-7. Beide sind null,
        und 3,25 Größenordnungen dazwischen sind keine Aussage."""
        self.assertIsNone(cp.jump_orders(2.8e-10, 5e-7, cp.MATERIALITAET["percentage"]))

    def test_head_counts_get_no_floor(self):
        """`integer` fehlt in MATERIALITAET, und das ist gemessen: es gibt im
        Bestand keine einzige Kopfzahl unter 1. Eine Schwelle dort wäre
        folgenlose Dekoration."""
        self.assertNotIn("integer", cp.MATERIALITAET)

    def test_without_a_floor_nothing_is_suppressed(self):
        self.assertGreater(cp.jump_orders(1e-20, 1e-30), 9)


class TimeFindingsTest(unittest.TestCase):
    def test_a_lone_jump_is_reported_per_cell(self):
        paare = [_paar(1e9, 1e9 * 1.05, zelle=str(i)) for i in range(99)]
        paare.append(_paar(1e9, 1e3, zelle="ausreisser"))
        sprünge, brüche = cp.time_findings(paare)
        self.assertEqual(brüche, [])
        self.assertEqual([s["zelle"] for s in sprünge], ["ausreisser"])

    def test_many_simultaneous_jumps_become_one_statement_about_the_report(self):
        """Die Randbedingung aus #36: bei sehr vielen gleichzeitigen Sprüngen
        ist ein Strukturbruch wahrscheinlicher als ein Tippfehler. Die Deutsche
        Pfandbriefbank stellt 1.152 von 1.442 Zellen um — 1.152 Einzelbefunde
        wären nicht 1.152 Aussagen, sondern eine, 1.152-mal wiederholt."""
        paare = ([_paar(1e9, 1e3, zelle=str(i)) for i in range(80)]
                 + [_paar(1e9, 1e9, zelle="s%d" % i) for i in range(20)])
        sprünge, brüche = cp.time_findings(paare)
        self.assertEqual(sprünge, [])
        self.assertEqual(len(brüche), 1)
        self.assertEqual(brüche[0]["n_sprung"], 80)
        self.assertEqual(brüche[0]["n_vergleichbar"], 100)
        self.assertAlmostEqual(brüche[0]["anteil"], 0.8)

    def test_the_break_carries_the_median_jump(self):
        """Ohne diese Zahl ist der Strukturbruch nicht lesbar. Liegt der Median
        bei ~3 oder ~6, war es ein Faktorwechsel (Pfandbriefbank 5,98, Groupe
        BPCE 6,01); streut er, ist ein echter Bruch wahrscheinlicher. Die
        Prüfung entscheidet das nicht — sie legt die Zahl daneben."""
        paare = ([_paar(1e9, 1e3, zelle=str(i)) for i in range(60)]
                 + [_paar(1e9, 1e15, zelle="x%d" % i) for i in range(40)])
        _, brüche = cp.time_findings(paare)
        self.assertAlmostEqual(brüche[0]["sprung_median"], 6.0)

    def test_a_small_report_does_not_become_a_break(self):
        """Bei 12 Zellen sind zwei Sprünge schon 17 %, ohne dass das etwas über
        den Report aussagt."""
        paare = ([_paar(1e9, 1e3, zelle=str(i)) for i in range(10)]
                 + [_paar(1e9, 1e9, zelle="s%d" % i) for i in range(2)])
        sprünge, brüche = cp.time_findings(paare)
        self.assertEqual(brüche, [])
        self.assertEqual(len(sprünge), 10)

    def test_unmeasurable_pairs_dilute_neither_side_of_the_share(self):
        """Nullen zählen weder im Zähler noch im Nenner. Täten sie es im
        Nenner, könnte eine nullreiche Vorlage jeden Strukturbruch beliebig
        klein rechnen — ein Ausfall, der sich als Erfolg meldet."""
        paare = ([_paar(1e9, 1e3, zelle=str(i)) for i in range(60)]
                 + [_paar(0, 0, zelle="n%d" % i) for i in range(900)])
        _, brüche = cp.time_findings(paare)
        self.assertEqual(brüche[0]["n_vergleichbar"], 60)
        self.assertAlmostEqual(brüche[0]["anteil"], 1.0)

    def test_a_report_lands_in_exactly_one_of_the_two_lists(self):
        paare = ([_paar(1e9, 1e3, report="A", zelle=str(i)) for i in range(80)]
                 + [_paar(1e9, 1e9, report="A", zelle="s%d" % i) for i in range(20)]
                 + [_paar(1e9, 1e3, report="B", zelle="einzeln")]
                 + [_paar(1e9, 1e9, report="B", zelle="q%d" % i) for i in range(99)])
        sprünge, brüche = cp.time_findings(paare)
        self.assertEqual({b["report"] for b in brüche}, {"A"})
        self.assertEqual({s["report"] for s in sprünge}, {"B"})

    def test_the_direction_is_recorded(self):
        auf, = cp.time_findings([_paar(1e3, 1e9)])[0]
        ab, = cp.time_findings([_paar(1e9, 1e3)])[0]
        self.assertEqual((auf["richtung"], ab["richtung"]), ("auf", "ab"))

    def test_a_sign_flip_is_recorded(self):
        s, = cp.time_findings([_paar(1e9, -1e3)])[0]
        self.assertTrue(s["vorzeichenwechsel"])

    def test_the_order_is_deterministic(self):
        """Dieselbe Eingabe in anderer Reihenfolge muss dieselbe Ausgabe
        ergeben — die Befunde werden nach main committet."""
        paare = [_paar(1e9, 1e3, report="R%d" % (i % 3), zelle=str(i)) for i in range(30)]
        a = [b["report"] for b in cp.time_findings(paare)[1]]
        b = [x["report"] for x in cp.time_findings(list(reversed(paare)))[1]]
        self.assertEqual(a, b)


class MedianTest(unittest.TestCase):
    def test_odd_and_even(self):
        self.assertEqual(cp.median([3, 1, 2]), 2)
        self.assertEqual(cp.median([1, 2, 3, 4]), 2.5)

    def test_a_single_extreme_value_does_not_move_it(self):
        """Der Grund, warum es der Median ist und nicht der Mittelwert: der
        Strukturbruch soll den TYPISCHEN Sprung zeigen. Ein Faktorwechsel mit
        einem einzigen Ausreißer darunter muss weiter als Faktorwechsel
        erkennbar sein — [6, 6, 6, 6, 60] hat den Mittelwert 16,8."""
        self.assertEqual(cp.median([6, 6, 6, 6, 60]), 6)


class FrameworkBridgeTest(unittest.TestCase):
    def _brücke(self, zeilen):
        f = io.StringIO()
        w = csv.DictWriter(f, ["template_id", "cell_row", "cell_col",
                               "dp_41", "dp_42", "status"])
        w.writeheader()
        w.writerows(zeilen)
        pfad = Path(self.enterContext(__import__("tempfile").TemporaryDirectory())) / "b.csv"
        pfad.write_text(f.getvalue(), encoding="utf-8")
        return cp.lade_framework_bruecke(pfad)

    def test_a_rebound_cell_is_translated_back(self):
        """Ohne diese Übersetzung reisst die Zeitreihe am 31.03.2026 ab — und
        zwar still. 1.055 Zeitpaare im Bestand entstehen erst durch sie."""
        um, unsicher = self._brücke([{"template_id": "61.00", "cell_row": "0190",
                                      "cell_col": "0010", "dp_41": "dp410432",
                                      "dp_42": "dp410433", "status": "rebound"}])
        self.assertEqual(um, {"dp410433": "dp410432"})
        self.assertEqual(unsicher, set())

    def test_a_stable_cell_needs_no_translation(self):
        um, unsicher = self._brücke([{"template_id": "00.02", "cell_row": "0010",
                                      "cell_col": "0010", "dp_41": "dp1",
                                      "dp_42": "dp1", "status": "stable"}])
        self.assertEqual((um, unsicher), ({}, set()))

    def test_one_datapoint_on_several_coordinates_is_not_ambiguous(self):
        """63.01.B/C/D r0070 teilen sich einen Datenpunkt; alle drei zeigen auf
        DASSELBE dp_41. Das per Überschreiben aufzulösen ginge gut — aber nur
        zufällig, und der Unterschied zum echten Konflikt wäre nicht mehr
        sichtbar."""
        um, unsicher = self._brücke([
            {"template_id": "63.01.B", "cell_row": "0070", "cell_col": "0020",
             "dp_41": "dp3529562", "dp_42": "dp3295812", "status": "rebound"},
            {"template_id": "63.01.C", "cell_row": "0070", "cell_col": "0030",
             "dp_41": "dp3529562", "dp_42": "dp3295812", "status": "rebound"}])
        self.assertEqual(um, {"dp3295812": "dp3529562"})
        self.assertEqual(unsicher, set())

    def test_one_code_with_two_predecessors_is_blocked_not_guessed(self):
        """Der echte Konflikt: dasselbe 4.2-Kürzel, zwei verschiedene
        Vorgänger. Hier ist jede Wahl geraten, also wird keine getroffen."""
        um, unsicher = self._brücke([
            {"template_id": "T1", "cell_row": "0010", "cell_col": "0010",
             "dp_41": "dpA", "dp_42": "dpNEU", "status": "rebound"},
            {"template_id": "T2", "cell_row": "0020", "cell_col": "0010",
             "dp_41": "dpB", "dp_42": "dpNEU", "status": "rebound"}])
        self.assertEqual(um, {})
        self.assertEqual(unsicher, {("T1", "0010", "0010"), ("T2", "0020", "0010")})

    def test_a_genuinely_ambiguous_cell_is_blocked(self):
        """Die Kategorie, die heute leer ist — und die sich füllen MUSS, sobald
        die Brücke eine `ambiguous`-Zeile mit unterschiedlichen dp-Mengen
        bekommt. Ohne diesen Test wäre „nichts gesperrt" nicht von „die Sperre
        greift nicht" zu unterscheiden."""
        um, unsicher = self._brücke([{"template_id": "71.00", "cell_row": "0010",
                                      "cell_col": "0010", "dp_41": "dpA|dpB",
                                      "dp_42": "dpC|dpD", "status": "ambiguous"}])
        self.assertEqual(um, {})
        self.assertEqual(unsicher, {("71.00", "0010", "0010")})

    def test_a_missing_bridge_blocks_nothing(self):
        self.assertEqual(cp.lade_framework_bruecke(ROOT / "gibt-es-nicht.csv"),
                         ({}, set()))

    def test_the_real_bridge_translates_and_blocks_nothing_today(self):
        """Am echten Artefakt. Die Gegenprobe zur leeren Sperrliste: die
        Übersetzung ist NICHT leer, der Mechanismus greift also."""
        if not BRIDGE.exists():
            self.skipTest("framework_bridge.csv nicht gebaut")
        um, unsicher = cp.lade_framework_bruecke()
        self.assertGreater(len(um), 20)
        self.assertEqual(unsicher, set(),
                         "die Brücke hat eine echte Mehrdeutigkeit bekommen — "
                         "der Zeitvergleich lässt diese Koordinaten jetzt aus, "
                         "und das gehört in den Bericht")

    def test_every_multiply_occupied_row_is_stable_on_the_datapoint(self):
        """Die Begründung dafür, dass `mehrfach` hier nichts sperrt: solche
        Zeilen haben dp_41 == dp_42. Sie sind Mehrfachbelegungen einer
        Koordinate (74.00.A r0010 c0010 trägt vier Datenpunkte), keine
        Bedeutungsänderungen. Bricht das, ist die Begründung hinfällig — und
        der vorige Test bricht mit.

        Bis #70 trugen genau diese Zeilen das Etikett `ambiguous`, und die
        Begründung stand nur hier im Test. Jetzt sagt die Einstufung selbst,
        was der Fall ist."""
        if not BRIDGE.exists():
            self.skipTest("framework_bridge.csv nicht gebaut")
        with BRIDGE.open(encoding="utf-8") as fh:
            zeilen = list(csv.DictReader(fh))
        mehrfach = [r for r in zeilen if r["status"] == "mehrfach"]
        self.assertGreater(len(mehrfach), 50)
        for r in mehrfach:
            with self.subTest(zelle=(r["template_id"], r["cell_row"], r["cell_col"])):
                self.assertEqual(r["dp_41"], r["dp_42"])
                self.assertIn("|", r["dp_41"], "`mehrfach` ohne Mehrfachbelegung")

    def test_no_row_is_labelled_ambiguous_while_its_datapoints_match(self):
        """Die Regel hinter #70, am echten Artefakt. `ambiguous` heisst „die
        Brücke kann nichts sagen" — bei identischen dp-Mengen ist das falsch,
        und der Viewer gäbe dem Leser eine Warnung, die nicht zutrifft."""
        if not BRIDGE.exists():
            self.skipTest("framework_bridge.csv nicht gebaut")
        with BRIDGE.open(encoding="utf-8") as fh:
            falsch = [r for r in csv.DictReader(fh)
                      if r["status"] == "ambiguous" and r["dp_41"] == r["dp_42"]]
        self.assertEqual(falsch, [])


class FrequenzmodellTest(unittest.TestCase):
    def test_a_missing_model_is_not_an_error(self):
        """Das Modell trägt einen Vorbehalt, keinen Filter. Fehlt es, läuft die
        Prüfung vollständig weiter — ein Filter auf Abwesenheit hätte sie
        stillschweigend abgeschaltet."""
        self.assertEqual(cp.lade_frequenzmodell(ROOT / "gibt-es-nicht.csv"), {})

    def test_the_real_model_is_read(self):
        if not cp.FREQUENZ.exists():
            self.skipTest("disclosure_frequency.csv nicht gebaut")
        m = cp.lade_frequenzmodell()
        self.assertGreater(len(m), 100)
        self.assertTrue(all(len(k) == 2 for k in m))


class ErgebnisTest(unittest.TestCase):
    """Am gebauten Artefakt."""

    def setUp(self):
        if not FINDINGS.exists():
            self.skipTest("plausibility_findings.csv nicht gebaut")
        with FINDINGS.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))
        self.zeit = [r for r in self.rows if r["rule"].startswith("time_")]

    def test_the_time_rules_actually_produce_findings(self):
        self.assertGreater(len(self.zeit), 500)

    def test_the_older_rules_are_untouched(self):
        """#36 ergänzt eine vierte Regelfamilie, es ändert die ersten drei
        nicht. Gemessen: 5.816 cell_outlier und 214 rem_per_head, unverändert
        gegenüber dem Stand vor dem Zeitvergleich."""
        alt = [r for r in self.rows if not r["rule"].startswith("time_")]
        self.assertEqual(sum(1 for r in alt if r["rule"] == "rem_per_head"), 214)
        self.assertGreater(sum(1 for r in alt if r["rule"] == "cell_outlier"), 5000)

    def test_a_time_finding_names_the_other_reference_date(self):
        """Ohne diese Spalte ist der Befund nicht nachprüfbar: „springt um 6
        Größenordnungen" ist keine Aussage, solange offen bleibt, wogegen."""
        for r in self.zeit:
            with self.subTest(bank=r["bank_name"], rp=r["refPeriod"]):
                self.assertTrue(r["vergleich_refPeriod"])
                self.assertNotEqual(r["vergleich_refPeriod"], r["refPeriod"])

    def test_both_reports_of_a_pair_carry_the_finding(self):
        """Welcher der beiden Reports falsch liegt, kann diese Prüfung nicht
        sagen. Die naheliegende Wahl wäre sogar die falsche: bei der Deutschen
        Pfandbriefbank ist der FRÜHERE Report der von #83 als skaliert
        erkannte, der spätere ist sauber. Wer den Sprung dem jeweils neueren
        zuschriebe, markierte systematisch den richtigen.

        Gezählt wird paarweise, nicht auf exakt zwei Zeilen: auf einer
        Koordinate können mehrere Datenpunkte oder offene Achsen liegen (34
        Koordinaten tragen vier Zeilen, 31 sechs, 4 acht). Was gelten muss, ist
        die Symmetrie — zu jeder Zeile für Stichtag A gegen B gibt es eine für
        B gegen A."""
        vor, zurück = {}, {}
        for r in self.zeit:
            k = (r["lei"], r["scope"], r["rule"], r["template_id"],
                 r["cell_row"], r["cell_col"])
            vor.setdefault((k, r["refPeriod"], r["vergleich_refPeriod"]), 0)
            vor[(k, r["refPeriod"], r["vergleich_refPeriod"])] += 1
            zurück.setdefault((k, r["vergleich_refPeriod"], r["refPeriod"]), 0)
            zurück[(k, r["vergleich_refPeriod"], r["refPeriod"])] += 1
        self.assertTrue(vor)
        self.assertEqual([k for k in vor if vor[k] != zurück.get(k)][:5], [])

    def test_a_structural_break_names_no_template(self):
        """Ein `time_break` gilt dem ganzen Report. Trüge er ein Template,
        markierte der Viewer eine Stelle, an der nichts Besonderes ist — und
        `load_cell_findings()` verlangt Zeile und Spalte, überspringt diese
        Zeilen also von sich aus."""
        for r in self.zeit:
            if r["rule"] == "time_break":
                with self.subTest(bank=r["bank_name"]):
                    self.assertEqual((r["template_id"], r["cell_row"], r["cell_col"]),
                                     ("", "", ""))

    def test_no_finding_compares_a_report_with_itself(self):
        """Die Falle aus dem Kopf des Moduls. Über (Template, Zeile, Spalte)
        statt über den dp-Code gepaart entstünden 16.048 Sprünge zwischen dem
        30.06. und sich selbst."""
        for r in self.zeit:
            self.assertNotEqual(r["refPeriod"], r["vergleich_refPeriod"])

    def test_every_time_jump_clears_the_threshold(self):
        for r in self.zeit:
            if r["rule"] == "time_jump":
                with self.subTest(bank=r["bank_name"]):
                    self.assertGreaterEqual(float(r["deviation_orders"]),
                                            cp.TIME_JUMP_MIN)

    def test_no_time_jump_sits_between_two_immaterial_amounts(self):
        """Die AIB-Falle am fertigen Artefakt. `value` und `reference` sind die
        beiden Seiten des Paares. Der Test prüft gegen die KLEINSTE Schwelle
        aus MATERIALITAET — unter ihr ist kein Datentyp mehr wesentlich, und
        ein Befund dort wäre in jedem Fall Rauschen."""
        boden = min(cp.MATERIALITAET.values())
        for r in self.zeit:
            if r["rule"] != "time_jump":
                continue
            v, ref = abs(float(r["value"])), abs(float(r["reference"]))
            if max(v, ref) < boden:
                self.fail(f"beide Seiten effektiv null: {r['bank_name']} "
                          f"{r['template_id']} r{r['cell_row']} c{r['cell_col']} "
                          f"({r['value']} / {r['reference']})")

    def test_the_structural_breaks_agree_with_the_scale_detector(self):
        """Die Gegenprobe, die den Zeitvergleich trägt: #83 urteilt aus
        TREA-Größen und `decimals`, #36 aus der Zeitreihe, ohne gemeinsame
        Evidenz. 8 der 21 Report-Paare mit Strukturbruch enthalten trotzdem
        einen Report, den #83 unabhängig als `skaliert` führt.

        Bricht das auf null, zeigen die beiden Verfahren nicht mehr
        aufeinander — dann irrt eines von beiden, und zwar nachweisbar."""
        pfad = ROOT / "processed" / "scale_flags.csv"
        if not pfad.exists():
            self.skipTest("scale_flags.csv nicht gebaut")
        with pfad.open(encoding="utf-8") as fh:
            skaliert = {(r["lei"], r["scope"], r["refPeriod"])
                        for r in csv.DictReader(fh)
                        if r["ebene"] == "report" and r["urteil"] == "skaliert"}
        paare = {(r["lei"], r["scope"],
                  tuple(sorted((r["refPeriod"], r["vergleich_refPeriod"]))))
                 for r in self.zeit if r["rule"] == "time_break"}
        treffer = sum(1 for lei, sc, ds in paare
                      if any((lei, sc, d) in skaliert for d in ds))
        self.assertGreater(len(paare), 5, "keine Strukturbrüche — nichts zu prüfen")
        self.assertGreater(treffer, 3,
                           f"nur {treffer} von {len(paare)} Strukturbrüchen treffen "
                           f"einen #83-Befund; die beiden Verfahren driften "
                           f"auseinander")

    def test_the_break_share_is_above_the_threshold(self):
        for r in self.zeit:
            if r["rule"] == "time_break":
                with self.subTest(bank=r["bank_name"]):
                    self.assertGreaterEqual(float(r["value"]), cp.TIME_BREAK_SHARE)

    def test_the_findings_stay_sorted(self):
        sev = {"hoch": 0, "mittel": 1, "niedrig": 2}
        k = [(sev[r["severity"]], -float(r["deviation_orders"] or 0)) for r in self.rows]
        self.assertEqual(k, sorted(k))


class ProfilTest(unittest.TestCase):
    def setUp(self):
        if not PROFILE.exists():
            self.skipTest("quality_profile.csv nicht gebaut")
        with PROFILE.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))

    def test_the_profile_carries_the_time_columns(self):
        """#36 verlangt EIN Profil, nicht zwei Artefakte."""
        self.assertIn("n_zeitpaare", self.rows[0])
        self.assertIn("n_zeitbefunde", self.rows[0])

    def test_reports_with_time_findings_exist(self):
        self.assertGreater(sum(1 for r in self.rows if int(r["n_zeitbefunde"] or 0)), 20)

    def test_the_rate_is_measured_against_both_kinds_of_opportunity(self):
        """Der Nenner zählt Gelegenheiten, auffällig zu werden, und seit #36
        gibt es davon zwei Arten. Ein Report mit vielen Zeitpaaren bekäme sonst
        dieselbe Rate wie einer ohne, obwohl er öfter geprüft wurde."""
        for r in self.rows:
            basis = int(r["n_facts_checked"] or 0) + int(r["n_zeitpaare"] or 0)
            if not basis or not r["findings_per_1000"]:
                continue
            with self.subTest(bank=r["bank_name"], rp=r["refPeriod"]):
                self.assertAlmostEqual(float(r["findings_per_1000"]),
                                       int(r["n_findings"]) / basis * 1000, places=1)

    def test_a_report_with_time_findings_names_them(self):
        """Gegenprobe gegen eine Spalte, die immer 0 ist: es muss Reports
        geben, deren Befunde AUSSCHLIESSLICH aus dem Zeitvergleich kommen —
        sonst hätte die vierte Regelfamilie nichts beigetragen, was die
        anderen drei nicht schon sahen."""
        nur_zeit = [r for r in self.rows
                    if int(r["n_zeitbefunde"] or 0) == int(r["n_findings"])
                    and int(r["n_findings"]) > 0]
        self.assertGreater(len(nur_zeit), 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
