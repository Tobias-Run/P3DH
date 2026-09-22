"""Teilbarer Zustand und Export (#50).

Zwei Dinge, die dasselbe Problem lösen: eine Ansicht, die nur der sieht, der sie
gerade eingestellt hat.

**Der Link.** Filter und Profil hingen schon im Hash, Sortierung und Auswahl
nicht — obwohl beide die Aussage tragen. Wer die Liste umsortiert, ändert, WER
sie anführt; ein Link ohne Sortierung zeigt dem Empfänger eine andere Spitze.
Und ohne die Auswahl lässt sich ein Vergleich nur AUFZÄHLEN („pinn mal diese
vier"), nicht weitergeben.

**Die Datei.** Der gefährlichere Teil. Die Tabelle im Viewer steht zwischen
Caveats — Konsolidierungskreis, Framework-Version, strittige Meldeeinheit,
Skalenbefund. Eine nackte CSV verliert genau die und wandert als scheinbar
sauberer Datensatz weiter; wer sie in drei Wochen wiederfindet, sieht Zahlen
ohne jede Einschränkung.

Dass der Export WIRKLICH entsteht und lesbar ist, prüft `check_viewer_runtime.py`
im echten Browser — dort wird die Datei erzeugt, mit `comment='#'` zurückgelesen
und auf ihre Spalten geprüft.
"""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

VIEWER = ROOT / "processed" / "zweig_a" / "viewer_json.html"


class TeilbarkeitTest(unittest.TestCase):
    def setUp(self):
        self.src = VIEWER.read_text(encoding="utf-8")

    def test_sort_and_selection_are_in_the_shared_state(self):
        rumpf = self.src[self.src.index("function shareParams()"):]
        rumpf = rumpf[:rumpf.index("\n/* Nur der Routenteil")]
        self.assertIn("p.set('sort'", rumpf)
        self.assertIn("p.set('pin'", rumpf)

    def test_the_default_sort_is_not_written_to_the_link(self):
        """Ein Link soll den ABWEICHENDEN Zustand tragen, nicht den ohnehin
        geltenden. Sonst wächst der Hash bei jedem Klick um Parameter, die
        nichts ändern."""
        rumpf = self.src[self.src.index("function shareParams()"):]
        rumpf = rumpf[:rumpf.index("\n/* Nur der Routenteil")]
        self.assertIn("s.col!==prof.defaultSort.col", rumpf)

    def test_a_link_cannot_exceed_the_selection_limit(self):
        """Vier ist eine Lesbarkeitsgrenze, keine technische. Sie muss für den
        LINK genauso gelten wie für die Schaltfläche — sonst umgeht ein
        geteilter Link, was die Oberfläche verbietet."""
        self.assertIn("const PIN_MAX=4", self.src)
        self.assertIn("PINS.size>=PIN_MAX", self.src)
        self.assertIn("gibt.slice(0, PIN_MAX)", self.src)

    def test_unknown_values_from_a_link_are_discarded(self):
        """Ein Link aus einer älteren Welle nennt womöglich Reports oder
        Spalten, die es hier nicht gibt. Sie stillschweigend zu übernehmen
        hiesse, einen leeren Vergleich oder eine Tabelle ohne Sortierung zu
        zeigen — beides ohne sichtbaren Grund."""
        rumpf = self.src[self.src.index("function applyShared()"):]
        rumpf = rumpf[:rumpf.index("\nfunction setTabs")]
        self.assertIn("wollte.filter(k=>byKey(k))", rumpf)
        self.assertIn("prof.cols.some(c=>c.id===col)", rumpf)

    def test_existing_links_keep_working(self):
        """`#r/<lei>/<refPeriod>/<scope>` und `#benchmark` sind vermutlich schon
        geteilt worden. Alles Neue hängt hinter '?' und ist optional.

        Geprüft wird die Zusage, nicht der Wortlaut: die Route kommt aus
        `hashRoute()` und bleibt unangetastet, und der Zustand hängt als
        `?…` dahinter. Vorher stand hier der Ausdruck selbst — und der
        musste sich ändern, als sich zeigte, dass auf der Startseite gar
        keine Route existiert und `replaceState` den Parameterblock
        stattdessen als Querystring an die Adresse hängte.
        """
        self.assertIn("(location.hash||'').split('?')[0]", self.src)
        rumpf = self.src[self.src.index("function shareState()"):]
        rumpf = rumpf[:rumpf.index("\n}")]
        self.assertIn("hashRoute()", rumpf,
                      "die Route kommt nicht mehr aus hashRoute()")
        self.assertIn("(p?'?'+p:'')", rumpf,
                      "der Zustand hängt nicht mehr optional hinter '?'")

    def test_the_state_never_lands_in_the_query_string(self):
        """Der Fehler, den das gekostet hat: auf der Startseite gibt es keinen
        Hash, `hashRoute()` lieferte den leeren String, und `replaceState`
        bekam '?c=Austria' — das ist ein QUERYSTRING, kein Hash.

        `location.hash` blieb damit leer. `applyShared()` fand beim nächsten
        Sprung nichts und setzte jeden Filter zurück; wer auf der Startseite
        nach Land filterte und dann ein Institut anklickte, verlor die
        Filterung. Nicht weil der Sprung sie wegwarf, sondern weil sie nie im
        Hash stand.
        """
        rumpf = self.src[self.src.index("function shareState()"):]
        rumpf = rumpf[:rumpf.index("\n}")]
        self.assertIn("hashRoute() || (p ? '#' : '')", rumpf,
                      "ohne Route fällt der Parameterblock wieder in den "
                      "Querystring")

    def test_an_internal_jump_carries_the_state(self):
        """Eine Stelle dafür, und zwei Wege hinein: der Klick auf die
        Listenzeile (ein `<div>`) und der Klick auf einen echten Link. Sie
        lagen in verschiedenen Handlern und sind auseinandergelaufen."""
        self.assertIn("function springZu(route){ location.hash = route + hashQuery(); }",
                      self.src)
        self.assertIn("springZu(row.dataset.h)", self.src,
                      "der Klick auf die Listenzeile setzt den Hash wieder "
                      "an springZu() vorbei")

    def test_the_state_is_readable_not_encoded(self):
        """Ein Werkzeug für Nachvollziehbarkeit darf seinen Zustand nicht
        verschlüsseln. Wer den Link sieht, sieht den Zustand."""
        rumpf = self.src[self.src.index("function shareParams()"):]
        rumpf = rumpf[:rumpf.index("\nfunction setTabs")]
        for kodierung in ("btoa(", "atob(", "JSON.stringify(p"):
            self.assertNotIn(kodierung, rumpf)


class ExportTest(unittest.TestCase):
    def setUp(self):
        self.src = VIEWER.read_text(encoding="utf-8")

    def test_the_caveats_travel_with_the_file(self):
        """Der Kern von #50. Eine exportierte Tabelle ohne die Warnungen, die im
        Viewer daneben stehen, ist gefährlicher als gar keine."""
        block = self.src[self.src.index("const CSV_CAVEATS"):]
        block = block[:block.index("];")]
        # Quellsprache ist Englisch; die deutsche Fassung steht in der
        # DE-Tabelle und wird von der Laufzeitpruefung abgenommen.
        for pflicht in ("supervisory metric", "scope of consolidation", "4.2",
                        "scale_finding", "not zero"):
            self.assertIn(pflicht, block, f"Caveat zu '{pflicht}' fehlt im Export")

    def test_the_marks_are_columns_not_only_prose(self):
        """Ein Caveat im Kopf erklärt die Tabelle, aber es sagt nicht, WELCHE
        Zeile betroffen ist — und wer nach Excel kopiert, verliert den Kopf
        zuerst."""
        rumpf = self.src[self.src.index("function benchmarkCSV("):]
        rumpf = rumpf[:rumpf.index("\nfunction ladeHerunter")]
        self.assertIn("'scale_finding','plausibility'", rumpf)
        self.assertIn("'framework'", rumpf,
                      "der Kopf warnt vor dem Meldewerkswechsel, ohne dass eine "
                      "Spalte sagt, welche Zeile betroffen ist")

    def test_the_export_points_back_at_its_own_view(self):
        """Ohne die URL ist eine exportierte Tabelle nicht mehr auf die Ansicht
        zurückzuführen, aus der sie stammt — und damit nicht reproduzierbar."""
        rumpf = self.src[self.src.index("function benchmarkCSV("):]
        rumpf = rumpf[:rumpf.index("\nfunction ladeHerunter")]
        self.assertIn("location.href", rumpf)
        self.assertIn("tr('filter/state:')", rumpf)
        self.assertIn("tr('sorting:')", rumpf)

    def test_the_unit_blocklist_gets_its_own_warning(self):
        """Bei `41.00` und `45.00.A` ist der Vergleich absoluter Beträge
        zwischen Instituten nicht nur eingeschränkt, sondern falsch. Das gehört
        nicht in dieselbe Zeile wie die allgemeinen Caveats."""
        rumpf = self.src[self.src.index("function benchmarkCSV("):]
        rumpf = rumpf[:rumpf.index("\nfunction ladeHerunter")]
        self.assertIn("UA.has(prof.tpl)", rumpf)
        self.assertIn("NOT comparable across institutions", rumpf)

    def test_comments_use_a_character_the_usual_readers_know(self):
        """Ein Export, den man erst von Hand aufräumen muss, wird nicht
        benutzt. `#` liest pandas mit `comment='#'` und DuckDB ebenso."""
        rumpf = self.src[self.src.index("function benchmarkCSV("):]
        rumpf = rumpf[:rumpf.index("\nfunction ladeHerunter")]
        self.assertIn("'# '", rumpf)

    def test_numbers_are_not_exported_with_their_binary_remainder(self):
        """`387.59999999999997` behauptet 17 signifikante Stellen für einen
        Wert, der im Meldebogen vier hatte. Das ist keine Genauigkeit."""
        self.assertIn("toPrecision(12)", self.src)

    def test_the_export_takes_what_the_user_sees(self):
        """Hat jemand die auffälligen Reports eingeklappt, sind sie auch nicht
        in der Datei — und die Zeilenzahl im Kopf sagt, wie viele es waren."""
        rumpf = self.src[self.src.index("document.getElementById('bmCsv')"):]
        rumpf = rumpf[:rumpf.index("});") + 3]
        self.assertIn("benchmarkCSV(rows, prof)", rumpf)
        self.assertNotIn("allRows", rumpf)

    def test_quoting_survives_a_separator_in_a_bank_name(self):
        """Institutsnamen tragen Kommas („Banco Santander, S.A."). Ohne
        Anführungszeichen verschiebt sich dort die halbe Zeile."""
        rumpf = self.src[self.src.index("function csvFeld("):]
        rumpf = rumpf[:rumpf.index("\n/* Gleitkomma")]
        self.assertIn('replace(/"/g,\'""\')', rumpf)
        self.assertIn('/[",;\\n]/', rumpf)

    def test_the_runtime_check_reads_the_file_back(self):
        """Quelltextprüfungen haben in diesem Projekt schon zwei Funktionen
        durchgewunken, die nichts taten. Der Export wird deshalb im Browser
        erzeugt und wieder eingelesen."""
        rt = (ROOT / "scripts" / "check_viewer_runtime.py").read_text(encoding="utf-8")
        self.assertIn("benchmarkCSV(", rt)
        self.assertIn("_csv.DictReader", rt)
        self.assertIn("verschiedene Spaltenzahlen", rt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
