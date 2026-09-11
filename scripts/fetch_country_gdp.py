"""BIP je Land als deskriptive Kontextspalte (#14).

## Wofür — und wofür ausdrücklich nicht

NICHT als Korrelations-Regressor. Das Issue begründet es: der Regressor wäre auf
Länderebene konstant, die effektive Stichprobe also ~30 statt ~450, und Länder
mit hohem BIP haben strukturell andere Bankensysteme. Ein Befund „hohes BIP ↔
höhere Kapitalquote" wäre vermutlich ein Größenklassen-Effekt.

Sondern zur **Normierung**: ein Länderexposure von 5 Mrd EUR bedeutet in Malta
etwas anderes als in Deutschland. Erst am BIP relativiert werden Exposures über
unterschiedlich große Volkswirtschaften vergleichbar.

## Join über ISO-Code, nicht über den Namen

Das Issue warnt vor der Alias-Falle („Czech" vs „Czechia"). Sie wird hier gar
nicht erst betreten: die Weltbank liefert ISO-2 mit, und `codebook/geo_names.csv`
führt dieselben Codes. Verglichen werden Codes, nicht Zeichenketten.

## Jüngstes verfügbares Jahr, nicht ein festes

Ein festes Jahr verliert jedes Land, das für dieses Jahr noch nicht gemeldet hat.
Stattdessen je Land der jüngste vorhandene Wert — mit dem Jahr in der Zeile,
damit sichtbar bleibt, worauf sich die Zahl bezieht.

Quelle: Weltbank, Indikator NY.GDP.MKTP.CD (BIP zu laufenden US-Dollar).
Ausgabe: codebook/country_gdp.csv — statisch, einmal abgerufen.

Aufruf:  python3 scripts/fetch_country_gdp.py
"""

from pathlib import Path
import csv
import json
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
GEO = ROOT / "codebook" / "geo_names.csv"
OUT = ROOT / "codebook" / "country_gdp.csv"

INDIKATOR = "NY.GDP.MKTP.CD"
JAHRE = "2015:2025"
API = ("https://api.worldbank.org/v2/country/all/indicator/"
       f"{INDIKATOR}?format=json&per_page=20000&date={JAHRE}")


def unsere_codes():
    """ISO-2 -> Name, so wie der Bestand die Länder führt."""
    with GEO.open(encoding="utf-8") as fh:
        return {r["code"].upper(): r["name"] for r in csv.DictReader(fh)}


def hole(url=API):
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.load(r)


def juengste_werte(rows, erlaubt):
    """Je ISO-2 der jüngste Jahreswert.

    Gefiltert wird über `erlaubt` — die Codes aus `geo_names.csv`. Das schliesst
    die Aggregate der Weltbank ('Arab World', 'Euro area') von selbst aus: sie
    tragen Pseudo-Codes wie `1A` oder `Z4`, die dort nicht vorkommen. Ein
    Regionsfeld, an dem man sie erkennen könnte, liefert dieser Endpunkt nicht
    — der erste Versuch filterte danach und warf ALLES weg.
    """
    best = {}
    for r in rows:
        code = ((r.get("country") or {}).get("id") or "").upper()
        if r.get("value") is None or code not in erlaubt:
            continue
        jahr = int(r["date"])
        if code not in best or jahr > best[code][0]:
            best[code] = (jahr, float(r["value"]), r["country"]["value"])
    return best


def build():
    geo = unsere_codes()
    daten = hole()
    if not isinstance(daten, list) or len(daten) < 2:
        raise SystemExit(f"unerwartete Antwort der Weltbank: {str(daten)[:200]}")
    meta, rows = daten[0], daten[1]
    if meta.get("pages", 1) > 1:
        raise SystemExit(f"Antwort ist auf {meta['pages']} Seiten verteilt — "
                         f"per_page erhöhen, sonst fehlen Länder")

    best = juengste_werte(rows, set(geo))
    zeilen = []
    for code, name in sorted(geo.items()):
        if code in best:
            jahr, wert, wb_name = best[code]
            zeilen.append({"iso2": code, "country": name, "year": jahr,
                           "gdp_usd": f"{wert:.0f}", "worldbank_name": wb_name})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, ["iso2", "country", "year", "gdp_usd",
                                "worldbank_name"])
        w.writeheader()
        w.writerows(zeilen)

    fehlend = sorted(set(geo) - set(best))
    print(f"✓ {OUT}")
    print(f"  {len(zeilen)} von {len(geo)} Ländern mit BIP")
    print(f"  Jahre: {min(z['year'] for z in zeilen)}–{max(z['year'] for z in zeilen)}")
    if fehlend:
        print(f"  ohne Wert ({len(fehlend)}): "
              + ", ".join(f"{c} {geo[c]}" for c in fehlend[:12])
              + (" …" if len(fehlend) > 12 else ""))
    return zeilen


if __name__ == "__main__":
    build()
