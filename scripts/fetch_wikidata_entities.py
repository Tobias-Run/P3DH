"""Wikidata über die LEI verknüpfen (#40).

Ausgabe: codebook/wikidata_entities.csv
Cache:   interim/wikidata_cache/ (gitignored)

## Was hier geholt wird und warum

Wikidata führt die LEI als Property `P1278`. Damit lassen sich unsere Institute
mit Merkmalen verbinden, die in keiner Aufsichtsquelle stehen — vor allem der
**Gesamtbelegschaft** (`P1128`). Erst sie macht die Kennzahl möglich, um die es
in #40 geht: der Anteil der „identified staff" aus REM1 an allen Mitarbeitern.

Geholt werden ausserdem Gründungsjahr (`P571`), Rechtsform (`P1454`) und
Börsennotierung (`P414`) — unabhängige Merkmale für die Peer-Schichtung, die
heute nur Grössenklasse × Konsolidierung kennt.

## Die Mitarbeiterzahl ist nicht EINE Zahl

ABN AMRO liefert in derselben Abfrage 18.830 und 20.872. Das ist kein Fehler:
`P1128` trägt mehrere Aussagen mit verschiedenen Stichtagen (`P585`), und
Wikidata gibt alle zurück. Wer die erstbeste nimmt, bekommt eine beliebige.

Deshalb wird auf STATEMENT-Ebene abgefragt (`p:`/`ps:`/`pq:`) und die Zahl mit
dem JÜNGSTEN Stichtag behalten; Aussagen ohne Stichtag verlieren gegen solche
mit. `mitarbeiter_stand` führt das Datum mit, damit ein Leser sieht, worauf sich
der Quotient bezieht.

## Trefferquote, gemessen statt geschätzt

#40 nennt 65 % aus einer Stichprobe von 40. Über alle 474 Institute abgefragt
liegt sie niedriger, und die entscheidende Zahl ist noch einmal deutlich
kleiner: nur ein Teil der gefundenen Einträge trägt überhaupt eine
Mitarbeiterzahl. Beide Quoten stehen im Bericht — die zweite ist die, die für
die Kennzahl zählt.

⚠️ **Die Lücke ist nicht zufällig verteilt.** Grosse und bekannte Institute sind
in Wikidata besser erfasst als kleine Regionalbanken. Jede Auswertung auf dieser
Teilmenge hat einen Grössenbias; `build_risk_taker_share.py` misst ihn und weist
ihn aus, statt ihn zu erwähnen.

Aufruf: python3 scripts/fetch_wikidata_entities.py
        python3 scripts/fetch_wikidata_entities.py --limit 40   (Stichprobe)
"""

from pathlib import Path
import csv
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
OUT = ROOT / "codebook" / "wikidata_entities.csv"
CACHE = ROOT / "interim" / "wikidata_cache"

ENDPOINT = "https://query.wikidata.org/sparql"
# Wikidata bittet ausdrücklich um einen aussagekräftigen User-Agent mit
# Kontaktmöglichkeit. Ein anonymer Abruf ist unhöflich und wird gedrosselt.
AGENT = "P3DH-research/1.0 (https://github.com/Tobias-Run/P3DH)"

# LEIs je Abfrage. Ein VALUES-Block mit 150 Einträgen läuft zuverlässig unter
# dem 60-Sekunden-Limit des öffentlichen Endpunkts; bei 474 sind das vier
# Abfragen statt 474.
BLOCK = 150
PAUSE = 1.5          # Sekunden zwischen Abfragen

FELDER = ["lei", "wikidata_id", "name", "mitarbeiter", "mitarbeiter_stand",
          "gruendung", "rechtsform", "boersennotiert"]

# Auf Statement-Ebene, damit der Stichtag (P585) mitkommt. Ohne ihn ist bei
# mehreren P1128-Aussagen nicht entscheidbar, welche gilt.
QUERY = """
SELECT ?lei ?item ?itemLabel ?employees ?empDate ?inception ?legalFormLabel ?exchange
WHERE {
  VALUES ?lei { %s }
  ?item wdt:P1278 ?lei .
  OPTIONAL {
    ?item p:P1128 ?empSt .
    ?empSt ps:P1128 ?employees .
    OPTIONAL { ?empSt pq:P585 ?empDate }
  }
  OPTIONAL { ?item wdt:P571 ?inception }
  OPTIONAL { ?item wdt:P1454 ?legalForm }
  OPTIONAL { ?item wdt:P414 ?exchange }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "de,en" }
}
"""


def lade_leis(pfad=None):
    """Die LEIs des Bestands, sortiert — der Cache soll stabil sein."""
    import duckdb

    pfad = pfad or PARQUET
    con = duckdb.connect()
    return sorted(x[0] for x in con.execute(
        f"SELECT DISTINCT lei FROM '{pfad}' WHERE lei IS NOT NULL AND lei <> ''"
    ).fetchall())


def frage_ab(leis, cache=None, pause=PAUSE):
    """Ein Block LEIs gegen den SPARQL-Endpunkt, mit Cache auf der Platte.

    Der Cache ist nach dem INHALT des Blocks benannt, nicht nach seiner
    Nummer: verschiebt sich die LEI-Liste um einen Eintrag, wäre sonst jeder
    Block neu zu holen — und ein höflicher Abruf ist einer, der nicht
    wiederholt, was er schon weiss.
    """
    cache = Path(cache or CACHE)
    cache.mkdir(parents=True, exist_ok=True)
    schluessel = hashlib.sha256("|".join(leis).encode()).hexdigest()[:16]
    datei = cache / f"{schluessel}.json"
    if datei.exists():
        return json.loads(datei.read_text(encoding="utf-8"))

    q = QUERY % " ".join('"%s"' % l.replace('"', "") for l in leis)
    url = f"{ENDPOINT}?format=json&query=" + urllib.parse.quote(q)
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=120) as fh:
        daten = json.load(fh)
    datei.write_text(json.dumps(daten), encoding="utf-8")
    time.sleep(pause)
    return daten


def juengste_zahl(aussagen):
    """Aus mehreren (Wert, Stichtag) die mit dem jüngsten Stichtag.

    ABN AMRO trägt 18.830 und 20.872. Ohne diese Auswahl entschiede die
    Reihenfolge, die der Endpunkt zufällig liefert — und der Quotient in
    #40 hinge an einer Zufälligkeit.

    Aussagen OHNE Stichtag verlieren gegen solche mit: eine datierte Zahl ist
    nachprüfbar, eine undatierte nicht. Gibt es nur undatierte, gewinnt die
    grösste — nicht, weil sie richtiger wäre, sondern damit die Auswahl
    deterministisch ist und nicht von der Abfragereihenfolge abhängt.
    """
    if not aussagen:
        return None, ""
    datiert = [(d, v) for v, d in aussagen if d]
    if datiert:
        d, v = max(datiert)
        return v, d[:10]
    return max(v for v, _ in aussagen), ""


def sammle(bindings):
    """SPARQL-Zeilen -> {lei: Datensatz}. Mehrere Zeilen je LEI sind die Regel."""
    roh = {}
    for b in bindings:
        lei = b["lei"]["value"]
        e = roh.setdefault(lei, {"item": "", "name": "", "emp": [],
                                 "inception": "", "form": "", "boerse": False})
        e["item"] = b.get("item", {}).get("value", "").rsplit("/", 1)[-1]
        e["name"] = e["name"] or b.get("itemLabel", {}).get("value", "")
        if "employees" in b:
            try:
                wert = int(float(b["employees"]["value"]))
            except (ValueError, TypeError):
                wert = None
            if wert is not None:
                e["emp"].append((wert, b.get("empDate", {}).get("value", "")))
        e["inception"] = e["inception"] or b.get("inception", {}).get("value", "")[:4]
        e["form"] = e["form"] or b.get("legalFormLabel", {}).get("value", "")
        if "exchange" in b:
            e["boerse"] = True
    return roh


def vorhandene_zeilen(pfad=None):
    """Wie viele Treffer die Datei auf der Platte schon trägt."""
    pfad = Path(pfad or OUT)
    if not pfad.exists():
        return 0
    with pfad.open(encoding="utf-8") as fh:
        return sum(1 for _ in csv.DictReader(fh))


def darf_schreiben(neu, alt, fehlgeschlagen):
    """Darf dieses Ergebnis den vorhandenen Stand ersetzen?

    Ein vollständiger Lauf ersetzt immer — auch wenn Wikidata Einträge verloren
    hat, denn das ist dann die Wahrheit der Quelle.

    Nach einem FEHLGESCHLAGENEN Block aber ist ein kleineres Ergebnis kein
    Befund über Wikidata, sondern über das Netz. Es zu schreiben hiesse, eine
    gepflegte Zuordnung durch eine halbe zu ersetzen — und der nächste Schritt
    rechnete stillschweigend auf einer geschrumpften Stichprobe weiter. Genau
    die Sorte Ausfall, die sich als Erfolg meldet.
    """
    return not fehlgeschlagen or neu >= alt


def build(limit=None):
    leis = lade_leis()
    if limit:
        leis = leis[:limit]
    print(f"LEIs im Bestand: {len(leis)}")

    bindings, fehlgeschlagen = [], 0
    for i in range(0, len(leis), BLOCK):
        block = leis[i:i + BLOCK]
        try:
            daten = frage_ab(block)
        except Exception as e:                      # noqa: BLE001
            # Ein fehlgeschlagener Block darf den Lauf nicht kippen, aber er
            # darf auch nicht still verschwinden: sonst sieht eine halbe
            # Antwort aus wie eine ganze.
            print(f"  ⚠ Block {i//BLOCK + 1} fehlgeschlagen: {e}")
            fehlgeschlagen += 1
            continue
        bindings.extend(daten["results"]["bindings"])
        print(f"  Block {i//BLOCK + 1}: {len(block)} LEIs abgefragt")

    roh = sammle(bindings)
    zeilen = []
    for lei in leis:
        e = roh.get(lei)
        if not e:
            continue
        mit, stand = juengste_zahl(e["emp"])
        zeilen.append({
            "lei": lei, "wikidata_id": e["item"], "name": e["name"],
            "mitarbeiter": "" if mit is None else mit,
            "mitarbeiter_stand": stand,
            "gruendung": e["inception"], "rechtsform": e["form"],
            "boersennotiert": "ja" if e["boerse"] else "nein",
        })

    alt = vorhandene_zeilen()
    if not darf_schreiben(len(zeilen), alt, fehlgeschlagen):
        print(f"✗ {fehlgeschlagen} Block(e) fehlgeschlagen und nur "
              f"{len(zeilen)} statt {alt} Treffer — {OUT} bleibt unverändert. "
              f"Ein Netzausfall darf keinen Bestand schrumpfen lassen.")
        return []

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(zeilen)

    print(f"✓ {OUT}  ({len(zeilen)} Treffer)")
    for s in bericht(zeilen, leis):
        print("  " + s)
    return zeilen


def bericht(zeilen, leis):
    mit = [z for z in zeilen if z["mitarbeiter"] != ""]
    aus = [f"Trefferquote LEI: {len(zeilen)}/{len(leis)} "
           f"({100*len(zeilen)/max(len(leis),1):.0f} %)",
           f"davon MIT Mitarbeiterzahl: {len(mit)} "
           f"({100*len(mit)/max(len(leis),1):.0f} % des Bestands) "
           f"— das ist die Quote, die für #40 zählt",
           f"mit datiertem Stand: {sum(1 for z in mit if z['mitarbeiter_stand'])}"]
    if mit:
        werte = sorted(int(z["mitarbeiter"]) for z in mit)
        aus.append(f"Mitarbeiterzahlen: Median {werte[len(werte)//2]:,} · "
                   f"min {werte[0]:,} · max {werte[-1]:,}")
    aus.append(f"börsennotiert: {sum(1 for z in zeilen if z['boersennotiert']=='ja')} "
               f"· mit Gründungsjahr: {sum(1 for z in zeilen if z['gruendung'])}")
    return aus


if __name__ == "__main__":
    grenze = None
    if "--limit" in sys.argv:
        grenze = int(sys.argv[sys.argv.index("--limit") + 1])
    build(grenze)
