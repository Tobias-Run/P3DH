"""Machbarkeitsprüfung OSM-Filialen (#41, Schritt 1).

Das Issue verlangt die Messung **vor** der Analyse und nennt eine Trefferquote
unter ~50 % einen legitimen Abbruchgrund. Eine solche Messung ist nur dann
etwas wert, wenn sie sich nicht schönrechnen lässt — und genau dagegen sind
diese Tests geschrieben.

Die Verknüpfung läuft über den **Namen**, nicht über die LEI. Damit hat die
Regel zwei Freiheitsgrade, und beide laden zum Frisieren ein:

1. **Wie weit wird normalisiert?** Streicht man genug, passt irgendwann alles
   auf alles.
2. **Wie kurz darf ein Treffer sein?** Ohne Mindestlänge trifft „Bank" jedes
   Institut in jedem Land, und die Quote sähe grossartig aus.

Dazu die Verbundmarken: ein Treffer auf „Sparkasse" ist keine Zuordnung,
sondern eine Verwechslung — dieselbe Schwierigkeit, die #32 hat.
"""

from pathlib import Path
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PROBE = ROOT / "interim" / "osm_probe.csv"
LAND = ROOT / "interim" / "osm_country.csv"


class MatchingTest(unittest.TestCase):
    def setUp(self):
        import probe_osm_branches as p
        self.p = p

    def test_the_legal_form_is_not_part_of_the_identity(self):
        """`Bank of Valletta Plc` und `Bank of Valletta` sind dasselbe Haus."""
        self.assertEqual(self.p.kern("Bank of Valletta Plc"),
                         self.p.kern("Bank of Valletta"))
        self.assertEqual(self.p.kern("HSBC Bank Malta p.l.c."),
                         self.p.kern("HSBC Malta"))

    def test_a_short_core_never_matches(self):
        """Ohne Mindestlänge trifft „Bank" jedes Institut in jedem Land. Das
        ist die Schraube, an der sich diese Messung am leichtesten frisieren
        liesse — und deshalb steht sie in einer Konstanten."""
        self.assertFalse(self.p.passt("abc", "abc irgendwas"))
        self.assertFalse(self.p.passt("", "bank of valletta"))
        self.assertGreaterEqual(self.p.MIN_KERN, 5)
        # Dreibuchstabige Akronyme bleiben draussen: `seb` steckt in
        # `Liepājas SEBiznesa centrs` genauso wie in der Bank.
        self.assertFalse(self.p.passt("seb", "sebiznesa centrs"))

    def test_a_containment_in_either_direction_counts(self):
        """OSM trägt mal den kürzeren, mal den längeren Namen: „Bank of
        Valletta - Head Office" gegen „Bank of Valletta"."""
        k = self.p.kern("Bank of Valletta Plc")
        self.assertTrue(self.p.passt(k, self.p.kern("Bank of Valletta - Head Office")))

    def test_two_different_institutions_do_not_match(self):
        """Die wichtigste Negativprobe. Passte hier etwas, wäre die ganze
        Messung wertlos — sie zählte Verwechslungen als Treffer."""
        a = self.p.kern("Bank of Valletta Plc")
        b = self.p.kern("Lombard Bank Malta plc")
        self.assertFalse(self.p.passt(a, b))
        self.assertFalse(self.p.passt(b, a))
        self.assertFalse(self.p.passt(self.p.kern("APS BANK P.L.C."),
                                      self.p.kern("BNF Bank plc")))

    def test_a_generic_name_cannot_absorb_a_specific_one(self):
        """Der teuerste Fehlertreffer der Messung: `Banco de Portugal` — die
        portugiesische ZENTRALBANK — schrumpfte auf `banco de` und war damit in
        `banco de investimento global` enthalten. 36 Zentralbank-POIs zählten
        als Filialen einer Investmentbank.

        Der Fehler sass nicht in der Enthaltungsregel, sondern darin, dass ein
        Kern aus lauter generischen Wörtern überhaupt entstehen konnte."""
        self.assertEqual(self.p.kern("Banco de Portugal"), "")
        self.assertFalse(self.p.passt(self.p.kern("BANCO DE INVESTIMENTO GLOBAL S.A"),
                                      self.p.kern("Banco de Portugal")))

    def test_a_long_legal_prefix_does_not_break_a_real_hit(self):
        """Die Gegenprobe zum Fix. Eine blosse Längenschranke hätte die
        Zentralbank auch gefangen — und dabei `Citadele` gegen `Akciju
        sabiedrība "Citadele banka"` zerstört, einen echten Treffer."""
        self.assertTrue(self.p.passt(self.p.kern('Akciju sabiedrība "Citadele banka"'),
                                     self.p.kern("Citadele")))

    def test_shared_brands_are_not_counted_as_hits(self):
        """Sparkassen, Raiffeisen und Crédit Agricole teilen eine Marke über
        rechtlich eigenständige Institute. Ein Treffer darauf sagt nicht,
        WELCHES Haus — und zählt deshalb gar nicht, statt falsch zu zählen."""
        for name in ("Kreissparkasse Köln", "Raiffeisenbank Tirol",
                     "Crédit Agricole Italia S.p.A."):
            with self.subTest(name=name):
                self.assertTrue(self.p.ist_verbund(name))
        self.assertFalse(self.p.ist_verbund("Bank of Valletta Plc"))

    def test_all_three_tags_are_searched(self):
        """Das Issue nennt `operator`. Gemessen trägt das Tag nur rund ein
        Drittel der POIs, `name` über 90 % — wer nur `operator` abgleicht,
        misst die Tagging-Disziplin und nennt es Trefferquote."""
        src = (ROOT / "scripts" / "probe_osm_branches.py").read_text(encoding="utf-8")
        self.assertIn('("operator", "name", "brand")', src)

    def test_a_failed_fetch_is_not_a_missing_hit(self):
        """Ein Netzfehler darf nicht als „keine Filialen gefunden" in die Quote
        eingehen. Sonst sinkt sie mit der Verbindungsqualität, und die
        Abbruchempfehlung des Issues hinge am Proxy."""
        src = (ROOT / "scripts" / "probe_osm_branches.py").read_text(encoding="utf-8")
        self.assertIn("NICHT als 'keine Treffer' gewertet", src)


class ErgebnisTest(unittest.TestCase):
    def setUp(self):
        if not PROBE.exists():
            self.skipTest("osm_probe.csv nicht erhoben (braucht Netz)")
        with PROBE.open(encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))
        with LAND.open(encoding="utf-8") as fh:
            self.land = list(csv.DictReader(fh))

    def test_the_sample_spans_more_than_one_country(self):
        """Eine Messung nur in dicht gemappten Ländern beantwortet die Frage
        des Issues nicht — dort ist OSM gut, und daran hängt gerade die
        Verallgemeinerbarkeit."""
        self.assertGreaterEqual(len(self.land), 3)

    def test_the_mapping_density_differs_between_countries(self):
        """Der Vorbehalt aus dem Issue, gemessen: die `operator`-Abdeckung
        schwankt zwischen den Ländern erheblich. Ein Filialzahlvergleich ohne
        diese Bezugsgrösse misst die Mapping-Dichte."""
        anteile = [int(z["n_operator"]) / max(int(z["n_poi"]), 1) for z in self.land]
        self.assertGreater(max(anteile) - min(anteile), 0.3)

    def test_every_institution_gets_a_verdict(self):
        for r in self.rows:
            self.assertIn(r["urteil"],
                          ("treffer", "kein_treffer", "verbundmarke", "zu_kurz"))

    def test_a_hit_names_its_evidence(self):
        """Eine Trefferquote ohne nachprüfbare Einzelzeile ist eine Behauptung.
        Jeder Treffer nennt den OSM-Namen und das Tag, über das er lief."""
        for r in self.rows:
            if r["urteil"] == "treffer":
                self.assertTrue(r["beispiel_osm"])
                self.assertIn(r["feld"], ("operator", "name", "brand"))

    def test_the_order_is_stable(self):
        k = [(r["land"], r["lei"]) for r in self.rows]
        self.assertEqual(k, sorted(k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
