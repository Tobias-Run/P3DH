"""Ländercode-Verwechslungen über die Zeit (#59)

Ausgabe: processed/country_swap.csv

## Die Prüfklasse, die #17 strukturell nicht erreicht

#59 fand den Fall beim Bau der Footprint-Kennzahlen:

    BBVA, CCyB1 67.01.A
    2025-06-30   grösstes Land Spanien    188,8 Mrd
    2025-12-31   grösstes Land Dänemark   190,6 Mrd,  Spanien nur noch 19,3

BBVA hat in Dänemark kein nennenswertes Geschäft. Der Dänemark-Betrag
entspricht fast dem Spanien-Wert des Vorquartals, und Spanien fällt gleichzeitig
um eine Grössenordnung.

Der Zell-Ausreissertest aus #17 sieht das nicht, und zwar nicht aus Schwäche,
sondern aus Bauart: er vergleicht einen Wert gegen die Population **derselben
Zelle**, und 190 Mrd sind für BBVA völlig plausibel. Falsch ist nur das **Land**
— und das ist die Zeilenkoordinate, keine Grösse.

## Auf Anteilen, nicht auf Beträgen

Sonst schlüge jeder Skalenfehler an (#83) und jede Bilanzausweitung. Ein Tausch
der Koordinate lässt die Summe unverändert und verschiebt nur ihre Verteilung —
in Anteilen gerechnet bleibt genau dieses Muster übrig.

## Die Signatur ist die PAARUNG, nicht die Sprunghöhe

Der naheliegende Test — „ein Land springt stark" — findet vor allem etwas
anderes. Gemessen über 105 Stichtagspaare stehen ganz oben Fälle, in denen das
**Heimatland** von null auf über 90 % springt (Alpha Bank, Kereskedelmi,
Banco de Crédito Social). Dort hat der frühere Report das Heimatland
offensichtlich nicht enthalten; das ist eine Lücke, kein Tausch.

Ein Tausch erkennt man daran, dass die beiden Bewegungen einander **aufheben**:

    Paarung = min(|Δauf|, |Δab|) / max(|Δauf|, |Δab|)

    First Investment Bank   Schweiz  +90,9 %  ←  Bulgarien  −90,9 %   Paarung 100 %
    BBVA                    Dänemark +36,8 %  ←  Spanien    −35,1 %   Paarung  95 %
    Raiffeisen Bank S.A.    Deutschl.+30,6 %  ←  Österreich −28,5 %   Paarung  93 %

Dazu die zweite Bedingung aus dem Issue: das steigende Land muss **neu
auftauchen**. Bei BBVA lag Dänemark vorher bei 0,0 %, bei First Investment Bank
die Schweiz bei 0,4 %.

## Kein Werturteil

Wie bei #17 sagt der Test „passt nicht zum eigenen Vorquartal", nicht „ist
falsch". Eine reale Umgliederung kann dasselbe Muster erzeugen, und der
Konsolidierungskreis kann sich ändern. Die Spalte heisst deshalb `urteil`.

## Eine zweite, unabhängige Quelle

Der Issue-Review hat die Fehlerklasse nebenbei eine Ebene höher belegt: zwei
Institute haben ihre Meldung zuerst unter **falschem Ländercode eingereicht**
und dann korrigiert (UniCredit Banka Slovenija unter `FR` statt `SI`,
Sparkasse Malta unter `FR` statt `MT`). Dass Ländercodes in diesem Meldeprozess
verwechselt werden, ist damit unabhängig von dieser Auswertung belegt.

Aufruf: python3 scripts/check_country_swap.py
"""

from pathlib import Path
import collections
import csv
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
OUT = ROOT / "processed" / "country_swap.csv"

TEMPLATE = "67.01.A"
SPALTE = "0060"

# Wie gross die Bewegung mindestens sein muss, um überhaupt hinzusehen. Zehn
# Prozentpunkte des Gesamtexposures sind für ein Land keine Schwankung mehr.
MIN_SPRUNG = 0.10

# Wie gut Anstieg und Abfall einander aufheben müssen. Darunter ist es eine
# Portfolioverschiebung mit zufällig entgegengesetztem Vorzeichen; ein Tausch
# der Koordinate erhält die Summe und hebt sich deshalb fast exakt auf.
MIN_PAARUNG = 0.80

# Bis zu welchem Voranteil ein Land als „neu aufgetaucht" gilt — die zweite
# Bedingung aus dem Issue. Ein Land, das vorher schon ein Zehntel trug, ist
# gewachsen, nicht erschienen.
MAX_VORHER = 0.05

FELDER = ["lei", "bank_name", "home_country", "scope", "von", "bis",
          "land_auf", "delta_auf", "anteil_vorher", "land_ab", "delta_ab",
          "paarung", "auf_ist_heimatland", "urteil"]


def anteile(betraege):
    """{Land: Betrag} -> {Land: Anteil}, oder {} wenn nichts Positives da ist.

    Negative Beträge fallen heraus: eine Nettoposition ist kein Gewicht.
    """
    positiv = {k: v for k, v in betraege.items() if v and v > 0}
    summe = sum(positiv.values())
    return {k: v / summe for k, v in positiv.items()} if summe else {}


def paarung(auf, ab):
    """Wie gut heben Anstieg und Abfall einander auf? 1,0 heisst exakt.

    Die eigentliche Kennzahl dieses Tests. Eine Sprunghöhe allein trennt
    Tausch und Lücke nicht — erst das Verhältnis der beiden Bewegungen tut es.
    """
    a, b = abs(auf), abs(ab)
    if not a or not b:
        return 0.0
    return min(a, b) / max(a, b)


def urteil_von(delta_auf, delta_ab, vorher, auf_ist_heimat,
               min_sprung=MIN_SPRUNG, min_paarung=MIN_PAARUNG,
               max_vorher=MAX_VORHER):
    """`verdacht_tausch`, `heimatland_ergaenzt`, `verschiebung` oder `""`.

    `heimatland_ergaenzt` ist eine eigene Antwort und ausdrücklich KEIN
    Tauschverdacht: dass das Heimatland eines Instituts von null auf über
    90 % springt, heisst fast immer, dass der frühere Report es nicht enthielt.
    Das als Verwechslung zu melden wäre ein Befund, den es nicht gibt.
    """
    if delta_auf < min_sprung:
        return ""
    p = paarung(delta_auf, delta_ab)
    if auf_ist_heimat:
        return "heimatland_ergaenzt"
    if p >= min_paarung and vorher <= max_vorher:
        return "verdacht_tausch"
    return "verschiebung"


def paare(profile):
    """[(lei, scope, von, bis)] — aufeinanderfolgende Stichtage je Melder.

    Verglichen wird nur ein Institut mit SICH SELBST. Zwischen zwei
    Instituten wäre eine unterschiedliche Länderverteilung keine Auffälligkeit,
    sondern der Normalfall.
    """
    je = collections.defaultdict(list)
    for lei, scope, rp in profile:
        je[(lei, scope)].append(rp)
    aus = []
    for (lei, scope), rps in sorted(je.items()):
        rps = sorted(rps)
        for a, b in zip(rps, rps[1:]):
            aus.append((lei, scope, a, b))
    return aus


def vergleiche(vorher, nachher):
    """(land_auf, delta_auf, anteil_vorher, land_ab, delta_ab) oder None.

    Genommen wird die grösste Auf- und die grösste Abwärtsbewegung. Bei einem
    Koordinatentausch sind das genau die beiden vertauschten Länder.
    """
    laender = set(vorher) | set(nachher)
    delta = {l: nachher.get(l, 0.0) - vorher.get(l, 0.0) for l in laender}
    auf = max(delta.items(), key=lambda kv: (kv[1], kv[0]), default=None)
    ab = min(delta.items(), key=lambda kv: (kv[1], kv[0]), default=None)
    if not auf or not ab or auf[1] <= 0 or ab[1] >= 0:
        return None
    return auf[0], auf[1], vorher.get(auf[0], 0.0), ab[0], ab[1]


def build():
    import duckdb
    from determinism import ordered_query as ordered

    if not PARQUET.exists():
        print(f"ERROR: {PARQUET} fehlt — erst scripts/build_zweig_b.py")
        return []

    con = duckdb.connect()
    roh = collections.defaultdict(dict)
    meta = {}
    for lei, scope, rp, bank, heimat, land, v in ordered(con, f"""
        SELECT lei, scope, refPeriod, max(bank_name), max(country),
               open_axis_country, sum(fact_value_eur)
        FROM '{PARQUET}'
        WHERE template_id = '{TEMPLATE}' AND cell_col = '{SPALTE}'
          AND fact_value_eur IS NOT NULL
          AND open_axis_country IS NOT NULL
        GROUP BY lei, scope, refPeriod, open_axis_country
        ORDER BY lei, scope, refPeriod, open_axis_country
    """, "Länder-Exposure je Stichtag"):
        roh[(lei, scope, rp)][land] = v
        meta[lei] = (bank or "", heimat or "")

    profile = {k: anteile(d) for k, d in roh.items()}
    profile = {k: v for k, v in profile.items() if v}

    zeilen = []
    for lei, scope, a, b in paare(profile):
        v = vergleiche(profile[(lei, scope, a)], profile[(lei, scope, b)])
        if not v:
            continue
        land_auf, d_auf, vorher, land_ab, d_ab = v
        bank, heimat = meta.get(lei, ("", ""))
        ist_heimat = bool(heimat) and land_auf == heimat
        u = urteil_von(d_auf, d_ab, vorher, ist_heimat)
        if not u:
            continue
        zeilen.append({
            "lei": lei, "bank_name": bank, "home_country": heimat,
            "scope": scope, "von": a, "bis": b,
            "land_auf": land_auf, "delta_auf": f"{d_auf:.4f}",
            "anteil_vorher": f"{vorher:.4f}",
            "land_ab": land_ab, "delta_ab": f"{d_ab:.4f}",
            "paarung": f"{paarung(d_auf, d_ab):.4f}",
            "auf_ist_heimatland": "ja" if ist_heimat else "nein",
            "urteil": u})

    zeilen.sort(key=lambda z: (z["von"], z["lei"], z["scope"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(zeilen)
    print(f"✓ {OUT}  ({len(zeilen)} Zeilen aus {len(paare(profile))} "
          f"Stichtagspaaren)")
    for s in bericht(zeilen):
        print("  " + s)
    return zeilen


def bericht(zeilen):
    if not zeilen:
        return ["Keine Bewegung über der Schwelle — der Test GREIFT nicht, "
                "er findet nur nichts."]
    u = collections.Counter(z["urteil"] for z in zeilen)
    aus = ["Urteile: " + "  ".join(f"{k}={v}" for k, v in u.most_common())]
    verdacht = [z for z in zeilen if z["urteil"] == "verdacht_tausch"]
    if verdacht:
        aus.append("Tauschverdacht — Anstieg und Abfall heben einander auf, "
                   "und das steigende Land war vorher praktisch nicht da:")
        for z in sorted(verdacht, key=lambda z: -float(z["paarung"])):
            aus.append(f"    {z['bank_name'][:26]:28s} "
                       f"{z['land_auf'][:14]:16s} {float(z['delta_auf']):+6.1%} "
                       f"← {z['land_ab'][:14]:16s} {float(z['delta_ab']):+6.1%} "
                       f"· Paarung {float(z['paarung']):.0%} · vorher "
                       f"{float(z['anteil_vorher']):.1%} · Heimat "
                       f"{z['home_country'][:12]}")
    heim = [z for z in zeilen if z["urteil"] == "heimatland_ergaenzt"]
    if heim:
        aus.append(f"{len(heim)} Fälle, in denen das HEIMATLAND neu auftaucht "
                   f"— das ist eine Lücke im früheren Report, kein Tausch, und "
                   f"deshalb ein eigenes Urteil.")
    aus.append("Kein Werturteil: der Test sagt „passt nicht zum eigenen "
               "Vorquartal\", nicht „ist falsch\". Eine reale Umgliederung "
               "oder ein geänderter Konsolidierungskreis erzeugt dasselbe "
               "Muster.")
    return aus


if __name__ == "__main__":
    build()
