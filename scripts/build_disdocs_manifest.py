"""DISDOCS-Manifest: die Pakete, die der Parser heute verwirft (#38).

`build_parse_manifest.py` schliesst sie aus — zu Recht, es sind PDF-Berichte
und kein XBRL-CSV:

    if "DISDOCS" in r["url"] or r["url"] in seen:
        continue

Der Grund war richtig, der Umfang war uns nicht klar. Es sind die
**qualitativen Säule-3-Berichte**: der Fliesstext, mit dem die Institute ihre
Zahlen einordnen. Wir haben die URLs; wir sind die Einzigen, die beide Korpora
über (LEI, Stichtag) verknüpfen können.

Dieses Skript erzeugt nur das Manifest. Es lädt nichts herunter — das tut
`probe_disdocs.py`, und zwar erst stichprobenartig, weil vorher niemand sagen
kann, ob aus den PDFs überhaupt Text herausfällt.

Ausgabe: interim/disdocs_manifest.csv
Aufruf:  python3 scripts/build_disdocs_manifest.py
"""

from pathlib import Path
import collections
import csv

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "interim" / "edap_recon" / "manifest_full.csv"
META = ROOT / "processed" / "entity_meta.csv"
OUT = ROOT / "interim" / "disdocs_manifest.csv"

FELDER = ["lei", "bank_name", "country", "consolidation", "refdate",
          "submission_ts", "im_xbrl_bestand", "url"]


def ist_disdocs(url):
    return "DISDOCS" in url


def build():
    with MANIFEST.open(encoding="utf-8") as fh:
        alle = list(csv.DictReader(fh))
    meta = {}
    if META.exists():
        with META.open(encoding="utf-8") as fh:
            meta = {r["lei"]: r for r in csv.DictReader(fh)}

    # Welche Institute liefern auch XBRL? Das ist die Verknüpfung, um die es
    # in #38 geht — Text gegen Zahl. Ein DISDOCS-Bericht eines Instituts ohne
    # XBRL-Meldung lässt sich gegen nichts halten.
    mit_xbrl = {r["lei"] for r in alle if not ist_disdocs(r["url"])}

    zeilen = []
    for r in alle:
        if not ist_disdocs(r["url"]):
            continue
        zeilen.append({
            "lei": r["lei"],
            "bank_name": meta.get(r["lei"], {}).get("name", ""),
            "country": r["country"],
            "consolidation": r["consolidation"],
            "refdate": r["refdate"],
            "submission_ts": r["submission_ts"],
            "im_xbrl_bestand": "true" if r["lei"] in mit_xbrl else "false",
            "url": r["url"],
        })
    zeilen.sort(key=lambda z: (z["lei"], z["refdate"], z["submission_ts"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(zeilen)

    print(f"✓ {OUT}  ({len(zeilen)} Pakete)")
    for zeile in bericht(zeilen, alle):
        print("  " + zeile)
    return zeilen


def bericht(zeilen, alle):
    leis = {z["lei"] for z in zeilen}
    ohne = [z for z in zeilen if z["im_xbrl_bestand"] == "false"]
    je_datum = collections.Counter(z["refdate"] for z in zeilen)
    aus = [
        f"Institute mit mindestens einem Bericht: {len(leis)}",
        f"Länder                                : {len({z['country'] for z in zeilen})}",
        f"Anteil am Katalog                     : {len(zeilen)} von {len(alle)}",
        f"OHNE XBRL-Meldung (nichts zum Halten) : {len(ohne)}",
        "je Stichtag: " + "  ".join(f"{d} {n}" for d, n in sorted(je_datum.items())),
    ]
    return aus


if __name__ == "__main__":
    build()
