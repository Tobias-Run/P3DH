"""Die Identität einer Einreichung (#88).

Der Fehler, gegen den diese Datei geschrieben ist, hatte drei Eigenschaften, die
ihn teuer machten: er war **still** (keine Ausnahme, kein Fehlschlag), er sah
nach korrekter Arbeit aus (eine plausible Deduplikationszahl), und die richtige
Fassung derselben Regel stand daneben im selben Repo.

`resolve_latest_submissions.py` gruppierte nach der Spalte `module` — die aber
nur den numerischen PILLAR3-Code trägt (`020000` = RF 4.1), nicht den Modultyp.
CODIS, ESGDIS und FINDIS desselben Instituts zum selben Stichtag fielen damit
zusammen, und „latest wins" verwarf zwei von dreien als überholt: **1.746 statt
2.829 Einreichungen, 38 % weg.**

Gemessen je Modul: FINDIS 617 → 127, ESGDIS 289 → 53, IRRBBDIS 381 → 90.
"""

from pathlib import Path
import csv
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KATALOG = ROOT / "interim" / "edap_recon" / "manifest_full.csv"

URL = ("https://errp.eba.europa.eu/public-documents/{t}/input/"
       "{lei}.{k}_{land}_PILLAR3{m}_{t}_{d}_{ts}.zip")


def zeile(lei="AAA", k="CON", land="DE", m="020000", t="CODIS",
          d="2025-12-31", ts="20260101000000000"):
    return {"url": URL.format(lei=lei, k=k, land=land, m=m, t=t, d=d, ts=ts),
            "lei": lei, "consolidation": k, "country": land, "module": m,
            "refdate": d, "submission_ts": ts}


class RegelTest(unittest.TestCase):
    def setUp(self):
        import submissions as s
        self.s = s

    def test_the_module_type_comes_from_the_filename(self):
        self.assertEqual(self.s.report_type(zeile(t="FINDIS")["url"]), "FINDIS")
        self.assertEqual(self.s.report_type(zeile(t="MRELTLACDIS")["url"]),
                         "MRELTLACDIS")

    def test_an_unparsable_name_gets_no_default_type(self):
        """Ein Fallback wäre hier gefährlich: er verschmölze fremde Dateinamen
        still zu einer gemeinsamen Gruppe — also genau der Fehler, gegen den
        dieses Modul gebaut ist, nur an anderer Stelle."""
        self.assertEqual(self.s.report_type("https://example.org/kaputt.zip"), "")

    def test_different_modules_are_not_corrections_of_each_other(self):
        """Der Kern von #88. Drei Module desselben Instituts zum selben
        Stichtag — alle drei müssen überleben."""
        rows = [zeile(t="CODIS", ts="1"), zeile(t="ESGDIS", ts="2"),
                zeile(t="FINDIS", ts="3")]
        self.assertEqual(len(self.s.latest_wins(rows)), 3)

    def test_the_newest_version_of_one_submission_wins(self):
        rows = [zeile(ts="20260101000000000"), zeile(ts="20260301000000000"),
                zeile(ts="20260201000000000")]
        behalten = self.s.latest_wins(rows)
        self.assertEqual(len(behalten), 1)
        self.assertEqual(behalten[0]["submission_ts"], "20260301000000000")

    def test_the_country_is_not_part_of_the_identity(self):
        """So naheliegend es aussieht: zwei Institute haben zuerst unter
        falschem Ländercode eingereicht und dann korrigiert (UniCredit Banka
        Slovenija als `FR` statt `SI`, Sparkasse Malta als `FR` statt `MT`).
        Mit `country` im Schlüssel zählte jede dieser Meldungen doppelt."""
        rows = [zeile(land="FR", ts="1"), zeile(land="SI", ts="2")]
        behalten = self.s.latest_wins(rows)
        self.assertEqual(len(behalten), 1)
        self.assertEqual(behalten[0]["country"], "SI")

    def test_the_framework_version_is_part_of_the_identity(self):
        """`020000` (RF 4.1) und `020100` (RF 4.2) sind verschiedene Meldungen,
        keine Korrekturfassungen — und sie treffen im Bestand aufeinander, weil
        RF 4.2 ausschliesslich am 2026-03-31 gilt."""
        rows = [zeile(m="020000", ts="1"), zeile(m="020100", ts="2")]
        self.assertEqual(len(self.s.latest_wins(rows)), 2)

    def test_the_order_of_input_does_not_matter(self):
        rows = [zeile(ts="2"), zeile(t="FINDIS", ts="1"), zeile(ts="3")]
        a = self.s.latest_wins(rows)
        b = self.s.latest_wins(list(reversed(rows)))
        self.assertEqual([r["url"] for r in a], [r["url"] for r in b])


class KopplungTest(unittest.TestCase):
    """Eine Regel, eine Implementierung — und der Beleg, dass es so bleibt."""

    def test_both_consumers_use_the_shared_rule(self):
        """Der eigentliche Schutz. Nicht „die Regel ist richtig", sondern
        „es gibt nur eine". Zwei Implementierungen derselben Regel, von denen
        eine still abweicht, ist die Fehlerklasse aus #88."""
        for name in ("build_parse_manifest.py", "resolve_latest_submissions.py"):
            with self.subTest(skript=name):
                src = (ROOT / "scripts" / name).read_text(encoding="utf-8")
                self.assertIn("from submissions import latest_wins", src)
                self.assertNotIn("def latest_wins", src,
                                 "eigene Implementierung neben der gemeinsamen")

    def test_no_consumer_defaults_to_the_derived_manifest(self):
        """`manifest_latest.csv` stammt aus `manifest_urls.csv`, und das ist nur
        ein Ausschnitt des Katalogs. Als Default lud und parste es einen
        Bruchteil des Bestands — ohne dass irgendetwas fehlschlug."""
        for name in ("download_raw_reports.py", "xbrl_csv_parser.py"):
            with self.subTest(skript=name):
                src = (ROOT / "scripts" / name).read_text(encoding="utf-8")
                zeilen = [z for z in src.splitlines()
                          if "manifest_latest.csv" in z and not z.strip().startswith("#")]
                self.assertEqual(zeilen, [], f"{name} greift noch darauf zurück")

    def test_the_documentation_does_not_lead_back_into_the_trap(self):
        """Der Defekt aus #88 hatte zwei Oberflächen, und die Defaults waren
        die kleinere. Die grössere ist `docs/phase1_ingestion.md`: das Issue
        nennt sie wörtlich — „Betroffen ist, wer die Skripte von Hand aufruft,
        und genau das zeigt `docs/phase1_ingestion.md`."

        Die Doku wies bis September 2026 an, `manifest_latest.csv` zu
        konsumieren, und nannte den alten Gruppenschlüssel INKLUSIVE `country`.
        Wer ihr folgte, bekam 1.746 statt 2.829 Einreichungen — lautlos.

        Erlaubt bleibt die Datei nur als ausgewiesene Warnung (Zeilen, die mit
        `>` beginnen). Als Anweisung darf sie nicht wieder auftauchen.
        """
        doc = (ROOT / "docs" / "phase1_ingestion.md").read_text(encoding="utf-8")
        anweisung = [z for z in doc.splitlines()
                     if "manifest_latest.csv" in z and not z.lstrip().startswith(">")]
        self.assertEqual(anweisung, [],
                         "die Doku schickt Leser wieder auf das verkürzte Manifest")
        self.assertIn("manifest_parse.csv", doc,
                      "die Doku nennt das richtige Manifest gar nicht")
        # Und der Schlüssel, der dort steht, muss der produktive sein.
        self.assertNotIn("(lei, consolidation, country, module, refdate)", doc,
                         "der alte Schlüssel mit `country` steht wieder in der Doku")

    def test_a_missing_parse_manifest_is_an_error_not_a_fallback(self):
        """Fehlt das Parse-Manifest, ist die Kette unvollständig — und das
        gehört gesagt, nicht umgangen."""
        src = (ROOT / "scripts" / "xbrl_csv_parser.py").read_text(encoding="utf-8")
        self.assertIn("erst scripts/build_parse_manifest.py", src)


class BestandTest(unittest.TestCase):
    """Gegen den echten Katalog — die Zahlen aus #88."""

    def setUp(self):
        if not KATALOG.exists():
            self.skipTest("manifest_full.csv nicht vorhanden")
        with KATALOG.open(encoding="utf-8") as fh:
            self.rows = [r for r in csv.DictReader(fh) if "DISDOCS" not in r["url"]]
        import submissions
        self.s = submissions

    def test_the_broken_key_would_lose_a_third_of_the_catalogue(self):
        """Der Regressionstest zum Defekt. Er prüft nicht nur, dass die richtige
        Regel richtig zählt, sondern dass die FALSCHE messbar anders zählt —
        sonst wäre der Test gegen eine Rückkehr des Fehlers blind."""
        richtig = self.s.latest_wins(self.rows)

        ohne_typ = {}
        for r in self.rows:
            k = tuple(r[x] for x in ("lei", "consolidation", "country",
                                     "module", "refdate"))
            if k not in ohne_typ or r["submission_ts"] > ohne_typ[k]["submission_ts"]:
                ohne_typ[k] = r

        self.assertGreater(len(richtig), 2500)
        self.assertLess(len(ohne_typ), len(richtig) * 0.7,
                        "der alte Schlüssel verliert nichts mehr — dann prüft "
                        "dieser Test den Defekt nicht")

    def test_every_module_survives(self):
        """Je Modul, weil der Defekt sie unterschiedlich hart traf: CODIS
        verlor die Hälfte, FINDIS und ESGDIS rund 80 %."""
        import collections
        vorher = collections.Counter(self.s.report_type(r["url"]) for r in self.rows)
        nachher = collections.Counter(self.s.report_type(r["url"])
                                      for r in self.s.latest_wins(self.rows))
        for modul in ("CODIS", "FINDIS", "ESGDIS", "IRRBBDIS",
                      "MRELTLACDIS", "REMDIS", "GSIIDIS"):
            with self.subTest(modul=modul):
                self.assertGreater(nachher[modul], 0.5 * vorher[modul],
                                   f"{modul}: {vorher[modul]} -> {nachher[modul]}")

    def test_the_production_manifest_matches_the_rule(self):
        """Die committete Datei gegen die Regel, aus der sie entstanden ist.
        Weicht sie ab, ist sie von Hand entstanden oder veraltet."""
        pfad = ROOT / "interim" / "edap_recon" / "manifest_parse.csv"
        if not pfad.exists():
            self.skipTest("manifest_parse.csv nicht vorhanden")
        with pfad.open(encoding="utf-8") as fh:
            ist = {r["url"] for r in csv.DictReader(fh)}
        soll = {r["url"] for r in self.s.latest_wins(self.rows)}
        self.assertEqual(len(ist - soll), 0,
                         "im Parse-Manifest stehen überholte Fassungen")


if __name__ == "__main__":
    unittest.main(verbosity=2)
