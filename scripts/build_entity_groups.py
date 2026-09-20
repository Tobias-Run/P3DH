"""Wer gehört zu wem — und wo das eine Auswertung verzerrt (#32 Punkte 3 und 5)

Ausgabe: processed/entity_groups.csv

## Die beiden offenen Punkte des Issues

**Punkt 5** verlangt eine belastbare Konzernzuordnung als Nebenprodukt,
„nützlich für die Peer-Schichtung (#4), die heute nur Grössenklasse ×
Konsolidierung kennt". **Punkt 3** verlangt, die Doppelzählungswarnung dort zu
verdrahten, wo über Institute aggregiert wird — für die Länderaggregate ist das
mit #19 geschehen, für die Benchmark-Aggregate nicht.

Beides ist dieselbe Frage, einmal je Institut und einmal je Peer-Gruppe.
Deshalb ein Artefakt statt zwei.

## Warum nicht in entity_meta.csv

`build_entity_meta.py` läuft nur im `harvest`-Zweig der Pipeline — die
Institutsmetadaten fallen aus der Power-BI-Query. Eine Spalte dort
materialisierte sich erst beim nächsten Harvest, und bis dahin läse sie
niemand. Dieses Skript läuft in jedem Lauf.

## Zwei Graphen, und keiner ersetzt den anderen

GLEIF (`lei_relations.csv`, #32) sagt, wem ein Institut rechtlich gehört; die
EZB-Hierarchie (`coverage_gap.csv`, #42) sagt, wer die beaufsichtigte Gruppe
führt. Für „gehören die zusammen" zählt beides, und wo beide etwas sagen,
stimmen sie überein — 67 identisch, 0 Konflikte (`group_graph_check.csv`).

Die Spalte `kopf_quelle` hält fest, welcher Graph geantwortet hat. Ein Kopf aus
nur einer Quelle ist schwächer belegt als einer aus beiden, und das soll man
sehen können.

## „Kein Mutterunternehmen gemeldet" heisst nicht „eigenständig"

Arbeitsprinzip 3, und #32 sagt es selbst: „Ein fehlender Parent ist kein Beleg
für Eigenständigkeit." GLEIF unterscheidet sauber zwischen `NO_KNOWN_PERSON` /
`NON_CONSOLIDATING` / `NATURAL_PERSONS` („es gibt keine") und `NO_LEI` /
`NON_PUBLIC` („wir kennen sie nicht"). Nur das erste ist eine Auskunft.

## Was Punkt 3 für die Benchmark-Aggregate wirklich bedeutet

Die erste Messung zählte nur Mutter-Tochter-Paare und fand sieben in vier
Gruppen — ein Randeffekt. Das war zu eng: **Geschwister** unter demselben Kopf
sind derselbe Konzern, der zweimal in der Verteilung steht, auch wenn keiner
die Mutter des anderen ist.

Richtig gezählt trifft es **155 Reports in 10 von 26 Peer-Gruppen**, und der
Effekt ist auf eine Klasse konzentriert:

    Peer-Gruppe                          Reports  effektiv  Verlust
    Large subsidiaries | CON | 2025-12-31     71        26    63,4 %
    Large subsidiaries | CON | 2025-06-30     54        24    55,6 %
    Large subsidiaries | CON | 2025-09-30     31        16    48,4 %
    Large highest EEA  | CON | 2025-12-31    101       101     0,0 %
    Other highest EEA  | CON | 2025-12-31    118       117     0,8 %

Im Nachhinein ist das offensichtlich: die Klasse heisst „Large **subsidiaries**"
— Töchter grosser Gruppen. Dass viele davon Geschwister sind, ist keine
Anomalie, sondern die Definition der Klasse. Zum 31.12.2025 stehen dort 71
Reports für **26 unabhängige Bankengruppen**.

`peer_effektiv` führt diese Zahl mit. Sie ist dasselbe Problem wie in #14 und
#11: **die effektive Stichprobe ist kleiner als die gezählte**, und ein
Perzentil, das 71 Beobachtungen behauptet, wo 26 unabhängige stehen, ist zu
schmal — nicht falsch, aber sicherer, als die Daten hergeben.

## Warum trotzdem markiert und nicht korrigiert wird

Der Benchmark bildet Perzentile, keine Summen — eine Tochter doppelt gezählt
verschiebt einen Rang, sie verdoppelt keinen Betrag. Wer die Geschwister aus
der Verteilung würfe, müsste entscheiden, welches von vierzehn ING- oder
BNP-Häusern bleibt, und verlöre echte Meldungen für einen Effekt, der sich
sauber ausweisen lässt. Die Markierung überlässt die Deutung dem Leser und
behauptet nichts.

Aufruf: python3 scripts/build_entity_groups.py
"""

from pathlib import Path
import collections
import csv
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
META = ROOT / "processed" / "entity_meta.csv"
RELATIONS = ROOT / "processed" / "lei_relations.csv"
COVERAGE = ROOT / "processed" / "coverage_gap.csv"
OUT = ROOT / "processed" / "entity_groups.csv"

# Dieselben GLEIF-Gründe wie in build_peer_clusters: hier ist positiv erklärt,
# dass es keine konsolidierende Mutter gibt.
BELEGT_EIGEN = {"NO_KNOWN_PERSON", "NON_CONSOLIDATING", "NATURAL_PERSONS"}

FELDER = ["lei", "scope", "refPeriod", "bank_name", "country",
          "institution_type", "konzern_kopf", "kopf_name", "kopf_quelle",
          "peer_gruppe", "peer_n", "peer_effektiv",
          "peer_konzernueberschneidung", "peer_verwandte"]


def lade_gleif(pfad=None):
    """{lei: (art, kopf)} aus GLEIF — `konzern`, `eigen` oder `unbekannt`."""
    pfad = Path(pfad or RELATIONS)
    if not pfad.exists():
        return {}
    aus = {}
    with pfad.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            lei = r["lei"]
            mutter = (r.get("ultimate_parent_lei") or "").strip()
            grund = (r.get("ultimate_parent_reason") or "").strip()
            if mutter and mutter != lei:
                aus[lei] = ("konzern", mutter)
            elif grund in BELEGT_EIGEN:
                aus[lei] = ("eigen", lei)
            else:
                aus[lei] = ("unbekannt", "")
    return aus


def lade_ezb(pfad=None):
    """{lei: (kopf_lei, kopf_name)} aus der EZB-Hierarchie (#42)."""
    pfad = Path(pfad or COVERAGE)
    if not pfad.exists():
        return {}
    aus = {}
    with pfad.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r.get("lei") and r.get("gruppenkopf_lei"):
                aus[r["lei"]] = (r["gruppenkopf_lei"],
                                 r.get("gruppenkopf_name", ""))
    return aus


def kopf_von(lei, gleif, ezb):
    """(kopf, quelle) — die Konzernzuordnung aus beiden Graphen.

    `quelle` ist `beide`, `gleif`, `ezb`, `eigen` oder `unbekannt`.

    `unbekannt` und `eigen` sind ZWEI Antworten, nicht eine. `eigen` heisst:
    GLEIF erklärt, dass es keine Mutter gibt. `unbekannt` heisst: es gibt
    vielleicht eine, wir kennen sie nicht — und diese beiden zu verschmelzen
    wäre genau der Fehler, vor dem #32 warnt.
    """
    art, g = gleif.get(lei, ("unbekannt", ""))
    e = ezb.get(lei, ("", ""))[0]
    if art == "konzern" and e:
        # Wo beide antworten, stimmen sie überein (group_graph_check.csv:
        # 67 identisch, 0 Konflikte). Weichen sie doch ab, gewinnt GLEIF —
        # es ist die feinere Zuordnung; die Abweichung ist dann die
        # Perimetergrenze des SSM, kein Widerspruch.
        return g, "beide" if g == e else "gleif"
    if art == "konzern":
        return g, "gleif"
    if e:
        return e, "ezb"
    if art == "eigen":
        return lei, "eigen"
    return "", "unbekannt"


def peer_schluessel(institution_type, scope, refperiod):
    """Dieselbe Peer-Gruppe wie `peerKeyOf()` im Viewer und `peer_stats()` im
    Shard-Bau. Zwei Peer-Begriffe im selben Produkt wären der sichere Weg zu
    zwei Antworten auf dieselbe Frage."""
    return f"{institution_type or '?'}|{scope}|{refperiod}"


def ueberschneidungen(zeilen):
    """Setzt `peer_konzernueberschneidung` und `peer_verwandte`.

    Die Frage aus #32 Punkt 3, auf die Benchmark-Aggregate angewandt: steht in
    meiner Peer-Gruppe noch ein Institut, das zu demselben Konzern gehört?

    Ein Institut ohne belegten Kopf kann hier nicht überschneiden — nicht weil
    es eigenständig wäre, sondern weil wir es nicht wissen. Die Spalte zählt
    also eine UNTERE Schranke, wie der ganze Graph (#32: „untere Schranke der
    Konzernverflechtung, kein vollständiges Bild").
    """
    je_gruppe = collections.defaultdict(list)
    for z in zeilen:
        je_gruppe[z["peer_gruppe"]].append(z)

    for gruppe, zs in je_gruppe.items():
        nach_kopf = collections.defaultdict(list)
        for z in zs:
            if z["konzern_kopf"]:
                nach_kopf[z["konzern_kopf"]].append(z)
        # Die effektive Stichprobe: verschiedene Konzernköpfe plus jeder
        # Report ohne belegten Kopf als eigene Einheit. Ein unbekannter Kopf
        # wird NICHT mit den anderen unbekannten verschmolzen — das behauptete
        # eine Verwandtschaft, für die es keinen Beleg gibt.
        effektiv = len(nach_kopf) + sum(1 for z in zs if not z["konzern_kopf"])
        for z in zs:
            z["peer_n"] = len(zs)
            z["peer_effektiv"] = effektiv
            verwandte = [a for a in nach_kopf.get(z["konzern_kopf"], [])
                         if a["lei"] != z["lei"]] if z["konzern_kopf"] else []
            z["peer_konzernueberschneidung"] = "ja" if verwandte else "nein"
            z["peer_verwandte"] = "|".join(
                sorted(a["bank_name"][:28] for a in verwandte)[:3])
    return zeilen


def build():
    import duckdb
    from determinism import ordered_query as ordered

    if not PARQUET.exists():
        print(f"ERROR: {PARQUET} fehlt — erst scripts/build_zweig_b.py")
        return []

    gleif, ezb = lade_gleif(), lade_ezb()
    itype, name_meta = {}, {}
    if META.exists():
        with META.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                itype[r["lei"]] = r.get("institution_type") or ""
                name_meta[r["lei"]] = r.get("name") or ""

    con = duckdb.connect()
    zeilen = []
    for lei, scope, rp, bank, land in ordered(con, f"""
        SELECT DISTINCT lei, scope, refPeriod, max(bank_name), max(country)
        FROM '{PARQUET}'
        GROUP BY lei, scope, refPeriod
        ORDER BY lei, scope, refPeriod
    """, "Institute je Stichtag"):
        kopf, quelle = kopf_von(lei, gleif, ezb)
        zeilen.append({
            "lei": lei, "scope": scope, "refPeriod": rp,
            "bank_name": bank or name_meta.get(lei, ""),
            "country": land or "",
            "institution_type": itype.get(lei, ""),
            "konzern_kopf": kopf,
            "kopf_name": ezb.get(lei, ("", ""))[1] if quelle in ("ezb", "beide")
                         else name_meta.get(kopf, ""),
            "kopf_quelle": quelle,
            "peer_gruppe": peer_schluessel(itype.get(lei, ""), scope, rp),
            "peer_n": 0, "peer_effektiv": 0,
            "peer_konzernueberschneidung": "nein",
            "peer_verwandte": ""})

    ueberschneidungen(zeilen)
    zeilen.sort(key=lambda z: (z["refPeriod"], z["lei"], z["scope"]))
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
    q = collections.Counter(z["kopf_quelle"] for z in zeilen)
    aus = ["Konzernzuordnung (#32 Punkt 5): "
           + "  ".join(f"{k}={v}" for k, v in q.most_common())]
    belegt = sum(v for k, v in q.items() if k != "unbekannt")
    aus.append(f"  {belegt} von {len(zeilen)} Reports mit belegtem Kopf. "
               f"`unbekannt` heisst NICHT eigenständig — #32: der Graph ist "
               f"eine untere Schranke der Konzernverflechtung.")

    treffer = [z for z in zeilen if z["peer_konzernueberschneidung"] == "ja"]
    gruppen = {z["peer_gruppe"] for z in treffer}
    alle = {z["peer_gruppe"] for z in zeilen}
    aus.append(f"Peer-Überschneidung (#32 Punkt 3): {len(treffer)} Reports in "
               f"{len(gruppen)} von {len(alle)} Peer-Gruppen haben einen "
               f"Konzernverwandten in derselben Gruppe.")
    for z in sorted(treffer, key=lambda z: z["peer_gruppe"])[:6]:
        aus.append(f"    {z['bank_name'][:30]:32s} {z['peer_gruppe'][:38]:40s} "
                   f"↔ {z['peer_verwandte'][:34]}")
    aus.append("  Das ist KEINE Doppelzählung — der Benchmark bildet "
               "Perzentile, keine Summen. Es ist etwas anderes: die effektive "
               "Stichprobe ist kleiner als die gezählte.")
    eng = sorted({(z["peer_gruppe"], z["peer_n"], z["peer_effektiv"])
                  for z in zeilen if z["peer_n"] and
                  z["peer_effektiv"] < z["peer_n"] * 0.8},
                 key=lambda t: t[2] / t[1])
    for gruppe, n, eff in eng[:4]:
        aus.append(f"    {gruppe[:40]:42s} {n:>4} Reports → {eff:>3} "
                   f"unabhängige Gruppen ({1 - eff / n:.0%} Verlust)")
    if eng:
        aus.append("  Der Effekt sitzt in „Large subsidiaries\" — Töchter "
                   "grosser Gruppen, von denen viele Geschwister sind. Das ist "
                   "die Definition der Klasse, keine Anomalie; ein Perzentil "
                   "dort ist schmaler, als die Reportzahl verspricht.")
    return aus


if __name__ == "__main__":
    build()
