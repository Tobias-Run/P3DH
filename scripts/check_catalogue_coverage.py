"""Ist die Stichtagswelle geladen — und wenn nicht, warum nicht? (#7)

Ausgabe: processed/catalogue_coverage.csv

## Die Frage, die ohne dieses Skript nicht zu beantworten war

#7 fragt, ob der Bestand vollständig ist. Bisher liess sich das nur von Hand
ermitteln, und die Antwort veraltete mit dem nächsten Lauf. Vor allem aber gab
die naheliegende Rechnung — Katalogzeilen gegen geladene Reports — eine
alarmierende Zahl aus, die fast nur aus Fällen besteht, die gar keine Lücke sind.

## Eine fehlende Zeile ist vier verschiedene Dinge

Gemessen fehlen 43 von 925 Katalog-Reports. Davon sind:

    nur DISDOCS (PDF, kein XBRL-CSV)                  40
    geparst, aber keine platzierbaren Fakten (#28)     1
    tote EDAP-Links (404, Katalogzeile ohne Datei)     2
    offen und ladbar                                   0

**Nur die letzte Zeile ist eine Lücke dieser Pipeline.** Die ersten 40 sind
Institute, die ihren Pillar-3-Bericht ausschliesslich als PDF veröffentlichen —
`build_parse_manifest.py` schliesst DISDOCS bewusst aus, weil dort kein XBRL-CSV
drinsteht. Sie als Rückstand zu zählen hiesse, eine Eigenschaft der Quelle als
eigenes Versäumnis zu buchen.

Die zwei toten Links sind Katalogzeilen, zu denen die EBA nie eine Datei
publiziert hat (per HEAD geprüft: 404). Sie stehen dauerhaft in
`manifest_todo.csv` und werden nie verschwinden.

Der eine #28-Fall ist der heikelste: die Einreichung wurde heruntergeladen und
geparst, steht in der Coverage-Matrix und trägt trotzdem keinen einzigen
platzierbaren Fakt. Im Parquet fehlt sie deshalb — sichtbar nur, wenn man die
Coverage-Matrix gegen die Long-Form hält, und das tut sonst niemand.

## Warum das Skript OHNE Netz auskommt

Die Einstufung „toter Link" braucht eigentlich einen HTTP-Abruf. Sie ist hier
aber ableitbar: was in `manifest_todo.csv` steht, wurde von
`download_raw_reports.py` versucht und ist nicht in `raw/` gelandet. Mit
`--probe` lässt sich die Einstufung gegen EDAP nachprüfen; ohne die Option
läuft der Schritt in jeder Pipeline mit.

Aufruf: python3 scripts/check_catalogue_coverage.py
        python3 scripts/check_catalogue_coverage.py --probe   (mit Netz)
"""

from pathlib import Path
import collections
import csv
import sys

ROOT = Path(__file__).resolve().parent.parent
RECON = ROOT / "interim" / "edap_recon"
PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
FILING = ROOT / "processed" / "filing_indicators.csv"
OUT = ROOT / "processed" / "catalogue_coverage.csv"

FULL = RECON / "manifest_full.csv"
PARSE = RECON / "manifest_parse.csv"
TODO = RECON / "manifest_todo.csv"

FELDER = ["lei", "consolidation", "refdate", "status", "grund"]

# Die vier Einstufungen, in der Reihenfolge ihrer Schwere. `offen` ist die
# einzige, die diese Pipeline noch einholen kann.
GELADEN = "geladen"
NUR_PDF = "nur_pdf"
OHNE_FAKTEN = "ohne_platzierbare_fakten"
TOTER_LINK = "toter_link"
OFFEN = "offen"

GRUND = {
    GELADEN: "im Parquet",
    NUR_PDF: "veröffentlicht nur DISDOCS (PDF), kein XBRL-CSV",
    OHNE_FAKTEN: "geparst und in der Coverage-Matrix, aber kein platzierbarer "
                 "Fakt (#28)",
    TOTER_LINK: "Katalogzeile ohne publizierte Datei (EDAP 404)",
    OFFEN: "ladbar und noch nicht geladen",
}


def lese(pfad):
    pfad = Path(pfad)
    if not pfad.exists():
        return []
    with pfad.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def schluessel(zeile):
    return (zeile["lei"], zeile["consolidation"], zeile["refdate"])


def dateiname(url):
    return url.rsplit("/", 1)[-1]


def geladene_reports(pfad=None):
    """{(lei, scope, refPeriod)} aus dem Parquet — was wirklich Fakten trägt."""
    import duckdb

    pfad = pfad or PARQUET
    if not Path(pfad).exists():
        return set()
    con = duckdb.connect()
    return {tuple(r) for r in con.execute(
        f"SELECT DISTINCT lei, scope, refPeriod FROM '{pfad}'").fetchall()}


def verarbeitete_dateien(pfad=None):
    """Quelldateien, die es bis in die Coverage-Matrix geschafft haben.

    Die Matrix ist das Hauptbuch: eine Einreichung kann sauber parsen und
    trotzdem keinen platzierbaren Fakt liefern — dann steht sie hier und fehlt
    im Parquet. Genau dieser Unterschied trennt #28 von einer echten Lücke.
    """
    return {r["source_file"] for r in lese(pfad or FILING) if r.get("source_file")}


def einstufen(kat, parse, todo, geladen, verarbeitet):
    """Jeder Katalog-Report bekommt genau eine Einstufung.

    `kat` ist der volle Katalog, `parse` das auf XBRL-CSV gefilterte Manifest.
    Ein Report, der im Katalog steht, aber nicht im Parse-Manifest, hat kein
    XBRL — er ist kein Rückstand, sondern eine PDF-Veröffentlichung.
    """
    aus = {}
    parse_urls = collections.defaultdict(list)
    for r in parse:
        parse_urls[schluessel(r)].append(r["url"])

    for k in sorted({schluessel(r) for r in kat}):
        if k in geladen:
            aus[k] = GELADEN
        elif k not in parse_urls:
            aus[k] = NUR_PDF
        elif any(dateiname(u) in verarbeitet for u in parse_urls[k]):
            aus[k] = OHNE_FAKTEN
        elif any(u in todo for u in parse_urls[k]):
            aus[k] = TOTER_LINK
        else:
            aus[k] = OFFEN
    return aus


def probe(urls, timeout=45):
    """HEAD gegen EDAP — prüft die Einstufung `toter_link` nach. Braucht Netz."""
    import urllib.request

    stat = collections.Counter()
    for u in urls:
        req = urllib.request.Request(
            u, method="HEAD", headers={"User-Agent": "P3DH-research/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as fh:
                stat[fh.status] += 1
        except Exception as e:                        # noqa: BLE001
            stat[getattr(e, "code", type(e).__name__)] += 1
    return stat


def build(mit_probe=False):
    kat, parse = lese(FULL), lese(PARSE)
    if not kat:
        print(f"ERROR: {FULL} fehlt — erst scripts/harvest_catalog_query.py")
        return []
    todo = {r["url"] for r in lese(TODO)}
    urteil = einstufen(kat, parse, todo, geladene_reports(),
                       verarbeitete_dateien())

    zeilen = [{"lei": l, "consolidation": c, "refdate": d, "status": s,
               "grund": GRUND[s]}
              for (l, c, d), s in sorted(urteil.items())]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(zeilen)

    print(f"✓ {OUT}  ({len(zeilen)} Katalog-Reports)")
    for s in bericht(urteil):
        print("  " + s)

    if mit_probe:
        urls = [r["url"] for r in parse
                if urteil.get(schluessel(r)) in (TOTER_LINK, OFFEN)]
        print(f"  HEAD auf {len(urls)} Kandidaten …")
        print(f"    {dict(probe(urls))}")
    return zeilen


def bericht(urteil):
    z = collections.Counter(urteil.values())
    n = len(urteil)
    aus = [f"Katalog-Reports: {n} · geladen: {z[GELADEN]} "
           f"({100 * z[GELADEN] / max(n, 1):.1f} %)"]
    for s in (NUR_PDF, OHNE_FAKTEN, TOTER_LINK, OFFEN):
        if z[s]:
            aus.append(f"  {s:26s} {z[s]:4d}   {GRUND[s]}")
    # Die einzige Zahl, die eine Aufgabe beschreibt. Ohne diesen Satz läse
    # jemand die 43 als Rückstand — und 40 davon sind gar keiner.
    aus.append(f"→ tatsächlich offen und ladbar: {z[OFFEN]}. Alles andere ist "
               f"eine Eigenschaft der Quelle, kein Rückstand dieser Pipeline.")
    return aus


if __name__ == "__main__":
    build("--probe" in sys.argv)
