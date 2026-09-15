"""LEI → Aktien-ISIN → Primärnotierung (#39).

Ausgabe: processed/equity_link.csv

## Was hier fertig wird — und was nicht

#39 hat zwei Hälften. `check_event_study_feasibility.py` hat die eine beantwortet
(243 verwertbare Ereignisse bei ±3 Tagen, die Stichprobe trägt). Dieses Skript
erledigt die zweite Hälfte, soweit sie **ohne fremde Daten** erledigt werden
kann: die Verknüpfung vom Institut zu seinem handelbaren Papier.

Was danach noch fehlt, ist genau eine Sache: **Kursreihen.** Sie sind keine
offene Quelle, und daran ändert dieses Skript nichts.

## Warum nicht GLEIF

Das Issue nennt GLEIF `/isins` als Weg, und der funktioniert — geprüft an 12
Instituten, alle mit Treffern. Er liefert aber den **falschen** Instrumententyp:
Intesa Sanpaolo trägt dort 1.676 ISINs, und das sind ganz überwiegend Anleihen.
Eine Ereignisstudie auf Aktienkursen braucht **die eine** Aktien-ISIN, und
GLEIF unterscheidet den Typ nicht.

Wikidata führt sie als `P946` — gemessen bei 56 der 69 belegt börsennotierten
Institute, Tickersymbole (`P249` am Börsen-Statement) bei 58.

## Die Falle: Wikidata ordnet die Börsen nicht

`P414` listet **alle** Notierungen nebeneinander, ohne Rangfolge. Die erstbeste
zu nehmen geht schief, und zwar sichtbar:

    UniCredit                   -> Frankfurt Stock Exchange, Ticker CRI
    Banca Monte dei Paschi      -> OTC Markets Group,        Ticker BMDPY

BMDPY ist ein **ADR**. Ein Ereignisfenster auf einem dünn gehandelten
Zweitpapier misst Rauschen, nicht Marktreaktion — und es sähe aus wie ein
Ergebnis.

Entschieden wird deshalb über das **Länderpräfix der ISIN**: `IT0005218752`
heisst Italien, also ist die italienische Notierung die primäre. Wo keine
Notierung zum Präfix passt, bleibt das Feld leer und `sicherheit` sagt warum —
geraten wird nicht.

Aufruf: python3 scripts/build_equity_link.py
"""

from pathlib import Path
import collections
import csv
import json
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
WIKIDATA = ROOT / "codebook" / "wikidata_entities.csv"
OUT = ROOT / "processed" / "equity_link.csv"

ENDPOINT = "https://query.wikidata.org/sparql"
AGENT = "P3DH-research/1.0 (https://github.com/Tobias-Run/P3DH)"

FELDER = ["lei", "name", "wikidata_id", "isin", "isin_land",
          "boerse", "boerse_land", "ticker", "sicherheit"]

# ISIN-Präfix -> Land der Primärnotierung. Zwei Präfixe meinen keinen
# Handelsplatz: `XS` ist Euroclear/Clearstream (internationale Anleihen) und
# `EU` die EU selbst. Eine Aktie mit solchem Präfix gibt es nicht — taucht sie
# auf, ist die ISIN keine Aktien-ISIN.
UEBERNATIONAL = {"XS", "EU"}

QUERY = """
SELECT ?item ?isin ?exchange ?exchangeLabel ?iso ?ticker WHERE {
  VALUES ?item { %s }
  ?item wdt:P946 ?isin .
  OPTIONAL {
    ?item p:P414 ?st .
    ?st ps:P414 ?exchange .
    OPTIONAL { ?st pq:P249 ?ticker }
    # P297 ist der ISO-3166-Code. Das Länder-LABEL taugt nicht: "Germany"[:2]
    # ergibt "GE", das ISIN-Präfix ist "DE" — der Vergleich ginge lautlos
    # daneben und träfe dann nie eine Notierung.
    OPTIONAL { ?exchange wdt:P17/wdt:P297 ?iso }
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "de,en" }
}
"""


def isin_land(isin):
    """Die ersten beiden Zeichen einer ISIN sind der Ländercode."""
    isin = (isin or "").strip().upper()
    return isin[:2] if len(isin) >= 2 and isin[:2].isalpha() else ""


def waehle_notierung(isin, notierungen):
    """(boerse, boerse_land, ticker, sicherheit) — die PRIMÄRE Notierung.

    `notierungen`: [(boerse, boerse_land_iso, ticker)] in beliebiger Reihenfolge,
    so wie Wikidata sie liefert.

    Gewählt wird die Notierung, deren Land zum ISIN-Präfix passt. Die erstbeste
    zu nehmen träfe bei Monte dei Paschi das OTC-gehandelte ADR statt der
    Mailänder Aktie — ein Ereignisfenster darauf misst Rauschen.

    Passt keine, bleibt alles leer. Ein Ticker ohne belegte Primärnotierung
    wäre schlimmer als keiner: er sieht benutzbar aus.
    """
    if not (isin or "").strip():
        # Eigener Zustand: "keine ISIN bei Wikidata" ist etwas anderes als
        # "ISIN da, aber unbrauchbar". Beides in einen Topf zu werfen verwischt,
        # ob die Lücke bei der Quelle oder bei der Form liegt.
        return "", "", "", "keine isin"
    land = isin_land(isin)
    if not land:
        return "", "", "", "isin unbrauchbar"
    if land in UEBERNATIONAL:
        return "", "", "", "isin nicht national (kein Aktienpapier)"
    if not notierungen:
        return "", "", "", "keine Notierung bei Wikidata"
    treffer = [n for n in notierungen if (n[1] or "").upper() == land]
    if not treffer:
        return "", "", "", "keine Notierung im ISIN-Land"
    # Mehrere im selben Land (Wikidata führt z. B. Segmente einzeln): die mit
    # Ticker gewinnt, sonst deterministisch die alphabetisch erste.
    treffer.sort(key=lambda n: (not n[2], n[0] or "", n[2] or ""))
    b, bl, t = treffer[0]
    if len(treffer) > 1:
        return b, bl, t, "mehrere im ISIN-Land"
    return b, bl, t, "eindeutig" if t else "ohne ticker"


def lade_notierte(pfad=None):
    """[(lei, datensatz)] der belegt börsennotierten Institute."""
    pfad = Path(pfad or WIKIDATA)
    if not pfad.exists():
        return []
    with pfad.open(encoding="utf-8") as fh:
        return [(r["lei"], r) for r in csv.DictReader(fh)
                if (r.get("boersennotiert") or "").strip().lower() == "ja"
                and (r.get("wikidata_id") or "").strip()]


def sammle(bindings):
    """SPARQL-Zeilen -> {wikidata_id: (isin, [(boerse, land, ticker)])}."""
    aus = {}
    for b in bindings:
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        isin = b.get("isin", {}).get("value", "")
        e = aus.setdefault(qid, [isin, []])
        # Mehrere ISINs je Item kommen vor (Vorzugs-/Stammaktie). Die erste
        # bleibt; welche die "richtige" ist, entscheidet dieses Skript nicht.
        if not e[0]:
            e[0] = isin
        if "exchange" in b:
            e[1].append((b.get("exchangeLabel", {}).get("value", ""),
                         (b.get("iso", {}).get("value", "") or "").upper(),
                         b.get("ticker", {}).get("value", "")))
    return aus


def frage_ab(qids, endpoint=ENDPOINT):
    q = QUERY % " ".join("wd:" + i for i in qids)
    url = f"{endpoint}?format=json&query=" + urllib.parse.quote(q)
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=120) as fh:
        return json.load(fh)["results"]["bindings"]


def build():
    notierte = lade_notierte()
    if not notierte:
        print(f"ERROR: {WIKIDATA} fehlt oder kennt keine notierten Institute")
        return []
    print(f"belegt börsennotierte Institute: {len(notierte)}")
    roh = sammle(frage_ab([r["wikidata_id"] for _, r in notierte]))

    zeilen = []
    for lei, r in sorted(notierte):
        qid = r["wikidata_id"]
        isin, notierungen = roh.get(qid, ("", []))
        b, bl, t, sicher = waehle_notierung(isin, notierungen)
        zeilen.append({"lei": lei, "name": r.get("name", ""),
                       "wikidata_id": qid,
                       "isin": isin, "isin_land": isin_land(isin),
                       "boerse": b, "boerse_land": bl, "ticker": t,
                       "sicherheit": sicher})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(zeilen)
    print(f"✓ {OUT}  ({len(zeilen)} Zeilen)")
    for s in bericht(zeilen):
        print("  " + s)
    return zeilen


def bericht(zeilen):
    z = collections.Counter(x["sicherheit"] for x in zeilen)
    mit_isin = [x for x in zeilen if x["isin"]]
    mit_tick = [x for x in zeilen if x["ticker"]]
    aus = [f"mit Aktien-ISIN (P946): {len(mit_isin)} von {len(zeilen)}",
           f"mit Ticker der Primärnotierung: {len(mit_tick)}",
           "Einstufung: " + "  ".join(f"{k}={v}" for k, v in z.most_common())]
    aus.append(f"→ {len(mit_tick)} Institute sind an eine Kursreihe "
               f"anschliessbar, SOBALD es eine gibt.")
    aus.append("⚠ Kursdaten sind keine offene Quelle. Dieses Blatt schliesst "
               "die Lücke auf UNSERER Seite; die andere bleibt offen.")
    return aus


if __name__ == "__main__":
    build()
