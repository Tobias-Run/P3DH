"""Ehrlicher Extraktionstest für den DISDOCS-Korpus (#38).

Das Issue verlangt diese Reihenfolge ausdrücklich: **Textausbeute je PDF
messen, BEVOR irgendeine Auswertung gebaut wird.** Gescannte Berichte ohne
Textebene liefern nichts, und eine Auswertung darauf wäre eine Auswertung über
die Teilmenge, die zufällig maschinenlesbar ist — mit einer Verzerrung, die
niemand beziffern könnte.

## Warum eine Stichprobe und nicht alles

Gemessen über 25 zufällige Pakete: Median 0,56 MB, Mittel 4,01 MB, Maximum
75 MB. Hochgerechnet sind das **rund 4,3 GB** — der gesamte XBRL-Bestand liegt
bei 13 MB, Faktor 330. Der Korpus gehört deshalb nicht ins Repo (wie `raw/`),
und vor einem Vollabruf will man wissen, ob er sich überhaupt lohnt.

## Was gemessen wird

    seiten           Seitenzahl laut PDF
    zeichen          extrahierte Zeichen gesamt
    zeichen_pro_seite  die eigentliche Kennzahl: unter ~200 ist ein Dokument
                     faktisch ohne Textebene (gescannt), egal wie dick es ist
    sprache          aus dem PDF-Feld /Lang, sonst leer

Sprache wird NICHT geraten. Eine Stichwortheuristik über 31 Länder träfe
systematisch die Institute, die auf Englisch berichten — genau die Verzerrung,
vor der das Issue warnt. Was das PDF selbst angibt, wird übernommen; der Rest
bleibt leer und damit sichtbar unbekannt.

## Ergebnis der ersten Stichprobe (n=30, Seed 20260912)

    PDFs gelesen            33 von 34 Zeilen
    mit Textebene           32   (97 %)
    ohne verwertbaren Text   1   gescannt
    Zeichen je Seite        Median 2.658  (min 0, max 4.182)
    Seiten                  Median 20     (max 249)
    kein PDF im Paket        1

**Der Korpus ist erschliessbar** — das war vorher offen und ist die Bedingung
für alles Weitere.

**Die Sprache aber ist es nicht.** Kein einziges PDF der Stichprobe gibt ein
`/Lang` an. Die Sprachverteilung, die das Issue vor jeder inhaltlichen Aussage
verlangt, lässt sich aus den Metadaten also nicht messen — sie braucht einen
anderen Weg (Spracherkennung auf dem extrahierten Text, mit eigener Fehlerquote,
die dann ihrerseits zu beziffern wäre). Solange das offen ist, wird hier keine
inhaltliche Auswertung gebaut.

Ausgabe: interim/disdocs_probe.csv
Aufruf:  python3 scripts/probe_disdocs.py [--n 30] [--seed 20260912]
"""

from pathlib import Path
import argparse
import csv
import io
import random
import sys
import urllib.error
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "interim" / "disdocs_manifest.csv"
OUT = ROOT / "interim" / "disdocs_probe.csv"

# Unter dieser Dichte ist ein PDF faktisch ohne Textebene. Eine Seite Fliesstext
# trägt 1.500–3.000 Zeichen; 200 ist grosszügig und trifft nur Dokumente, aus
# denen nichts Verwertbares herausfällt.
MIN_ZEICHEN_JE_SEITE = 200

FELDER = ["lei", "country", "refdate", "paket_bytes", "datei", "seiten",
          "zeichen", "zeichen_pro_seite", "sprache", "status"]


def _hole(url, timeout=120):
    with urllib.request.urlopen(url, timeout=timeout) as h:
        return h.read()


def _pdfs(rohdaten):
    """DISDOCS-Pakete sind ZIPs. Liefert (name, bytes) je enthaltenem PDF."""
    try:
        z = zipfile.ZipFile(io.BytesIO(rohdaten))
    except zipfile.BadZipFile:
        return []
    return [(n, z.read(n)) for n in sorted(z.namelist())
            if n.lower().endswith(".pdf")]


def messe_pdf(daten):
    """(seiten, zeichen, sprache, status)."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return 0, 0, "", "pypdf fehlt"
    try:
        leser = PdfReader(io.BytesIO(daten))
        if leser.is_encrypted:
            try:
                leser.decrypt("")
            except Exception:
                return 0, 0, "", "verschluesselt"
        seiten = len(leser.pages)
        text = []
        for s in leser.pages:
            try:
                text.append(s.extract_text() or "")
            except Exception:
                pass
        sprache = ""
        try:
            sprache = (leser.metadata or {}).get("/Lang", "") or ""
        except Exception:
            pass
        n = sum(len(t) for t in text)
        return seiten, n, str(sprache), "ok"
    except Exception as e:
        return 0, 0, "", f"{type(e).__name__}"


def probe(n=30, seed=20260912):
    with MANIFEST.open(encoding="utf-8") as fh:
        zeilen = list(csv.DictReader(fh))
    random.seed(seed)
    stichprobe = random.sample(zeilen, min(n, len(zeilen)))

    aus = []
    for i, r in enumerate(stichprobe, 1):
        print(f"  [{i}/{len(stichprobe)}] {r['lei']} {r['refdate']} …", flush=True)
        basis = {"lei": r["lei"], "country": r["country"], "refdate": r["refdate"],
                 "paket_bytes": 0, "datei": "", "seiten": 0, "zeichen": 0,
                 "zeichen_pro_seite": 0, "sprache": ""}
        try:
            roh = _hole(r["url"])
        except urllib.error.HTTPError as e:
            aus.append({**basis, "status": f"HTTP {e.code}"})
            continue
        except Exception as e:
            aus.append({**basis, "status": type(e).__name__})
            continue
        basis["paket_bytes"] = len(roh)
        pdfs = _pdfs(roh)
        if not pdfs:
            # Kein PDF im Paket ist ein BEFUND, kein Fehler: dann trägt der
            # Korpus dort nichts Auswertbares.
            aus.append({**basis, "status": "kein PDF im Paket"})
            continue
        for name, daten in pdfs:
            seiten, zeichen, sprache, status = messe_pdf(daten)
            aus.append({**basis, "datei": name, "seiten": seiten,
                        "zeichen": zeichen,
                        "zeichen_pro_seite": round(zeichen / seiten) if seiten else 0,
                        "sprache": sprache, "status": status})

    aus.sort(key=lambda z: (z["lei"], z["refdate"], z["datei"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(aus)
    print(f"\n✓ {OUT}  ({len(aus)} Zeilen aus {len(stichprobe)} Paketen)")
    for zeile in bericht(aus):
        print("  " + zeile)
    return aus


def bericht(zeilen):
    import collections
    import statistics as st
    ok = [z for z in zeilen if z["status"] == "ok"]
    lesbar = [z for z in ok if int(z["zeichen_pro_seite"]) >= MIN_ZEICHEN_JE_SEITE]
    leer = [z for z in ok if int(z["zeichen_pro_seite"]) < MIN_ZEICHEN_JE_SEITE]
    aus = [f"PDFs gelesen            : {len(ok)} von {len(zeilen)} Zeilen",
           f"mit Textebene           : {len(lesbar)}",
           f"ohne verwertbaren Text  : {len(leer)}  <- gescannt oder bildbasiert"]
    if ok:
        d = sorted(int(z["zeichen_pro_seite"]) for z in ok)
        aus.append(f"Zeichen/Seite: median {st.median(d):.0f}  "
                   f"min {d[0]}  max {d[-1]}")
        s = sorted(int(z["seiten"]) for z in ok)
        aus.append(f"Seiten       : median {st.median(s):.0f}  max {s[-1]}")
    spr = collections.Counter(z["sprache"] for z in ok if z["sprache"])
    aus.append("Sprache laut PDF: " + (", ".join(f"{k} {v}" for k, v in spr.most_common())
                                       if spr else "von keinem einzigen PDF angegeben"))
    fehler = collections.Counter(z["status"] for z in zeilen if z["status"] != "ok")
    if fehler:
        aus.append("nicht lesbar: " + ", ".join(f"{k} ({v})" for k, v in fehler.most_common()))
    return aus


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20260912)
    a = ap.parse_args()
    probe(a.n, a.seed)
