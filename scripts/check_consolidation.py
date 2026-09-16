"""Tochter gegen Mutter: hält sich der Konsolidierungskreis? (#32 Punkt 4)

Ausgabe: processed/consolidation_check.csv

## Die Prüfung, die es ohne LEI-Verknüpfung nicht gibt

#32 Punkt 4: *„Der CON-Report der Mutter muss sich zu den IND-Reports ihrer
Töchter plausibel verhalten — das Exposure einer Tochter kann nicht grösser
sein als das der Gruppe, das Länderprofil der Gruppe muss die Töchter
enthalten."*

Beides ist eine Aussage über **zwei verschiedene Meldungen**, und genau deshalb
sieht sie niemand: EDAP liefert je Institut ein Paket, und die Verbindung
zwischen ihnen steht in keiner der beiden Dateien.

## Warum das bis jetzt nicht ging

#83 hat es blockiert, und mit Grund. Die Machbarkeitsprobe fand

    Addiko Bank d.d. (IND)   1,4 Mrd  >  Addiko Bank AG (CON)  4.296 EUR

Das sieht aus wie ein Konsolidierungsfehler und ist ein **Skalenfehler**: der
CON-Report ist um Grössenordnungen zu klein gemeldet. Wer solche Paare nicht
aussortiert, veröffentlicht eine Liste von Verstössen, die keine sind.

Seit #83 trägt `footprint.csv` dafür `vorbehalt`. Reports mit `skala` oder
`unter_trea` fliegen hier raus — nicht weil sie uninteressant wären, sondern
weil sie eine ANDERE Frage beantworten und diese hier unbeantwortbar machen.

## Was ein Befund NICHT ist

Ein Verstoss ist nicht automatisch ein Meldefehler. Der aufsichtliche
Konsolidierungskreis nach CRR ist nicht deckungsgleich mit dem rechtlichen
Eigentum, das GLEIF abbildet (#32 sagt das ausdrücklich): eine Tochter kann
rechtlich dazugehören und aufsichtlich ausserhalb stehen. Die Spalte heisst
deshalb `urteil` und nicht `verstoss`.

Aufruf: python3 scripts/check_consolidation.py
"""

from pathlib import Path
import collections
import csv

ROOT = Path(__file__).resolve().parent.parent
FOOTPRINT = ROOT / "processed" / "footprint.csv"
RELATIONS = ROOT / "processed" / "lei_relations.csv"
OUT = ROOT / "processed" / "consolidation_check.csv"

# Wie viel grösser die Tochter sein darf, bevor es ein Befund ist. Nicht 1,0:
# CCyB1 erfasst nur kreditrisikorelevante Positionen, und Stichtagseffekte
# zwischen zwei Meldungen desselben Konzerns sind normal. 1,05 lässt fünf
# Prozent Luft und trifft nur, was deutlich daneben liegt.
TOLERANZ = 1.05

# Anteil der Tochter-Länder, die im Mutterprofil fehlen dürfen. CCyB1 meldet
# nur Länder oberhalb einer Wesentlichkeitsschwelle; ein Land, das bei der
# Tochter wesentlich ist und im Konzern untergeht, fehlt dort zu Recht.
LAENDER_TOLERANZ = 0.34

FELDER = ["refPeriod", "kind_lei", "kind_name", "mutter_lei", "mutter_name",
          "beziehung", "kind_exposure_eur", "mutter_exposure_eur", "quote",
          "kind_laender", "mutter_laender", "mutter_x28", "fehlende_laender",
          "urteil", "grund"]


def lade_footprint(pfad=None):
    """{(lei, scope, refPeriod): Zeile} aus footprint.csv."""
    pfad = Path(pfad or FOOTPRINT)
    if not pfad.exists():
        return {}
    with pfad.open(encoding="utf-8") as fh:
        return {(r["lei"], r["scope"], r["refPeriod"]): r
                for r in csv.DictReader(fh)}


def lade_kanten(pfad=None):
    """{kind_lei: {(mutter_lei, beziehung)}} — nur BELEGTE Kanten.

    Ein fehlender Parent ist kein Beleg für Eigenständigkeit (#32,
    Arbeitsprinzip 3): GLEIF kennt Reporting Exceptions, und ein Institut ohne
    hinterlegte Mutter kann sehr wohl zu einer Gruppe gehören. Hier zählt nur,
    was positiv gemeldet ist.
    """
    pfad = Path(pfad or RELATIONS)
    if not pfad.exists():
        return {}
    # Je (Kind, Mutter) EINE Kante. Direkte und oberste Mutter sind bei allen
    # 16 heutigen Paaren dieselbe LEI; getrennt gefuehrt stuende jedes Paar
    # zweimal in der Ausgabe, und eine doppelte Zeile ist keine zweite
    # Beobachtung — sie sieht nur so aus.
    aus = collections.defaultdict(lambda: collections.defaultdict(set))
    with pfad.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            for feld, art in (("direct_parent_lei", "direkt"),
                              ("ultimate_parent_lei", "oberste")):
                p = (r.get(feld) or "").strip()
                if p and p != r["lei"]:
                    aus[r["lei"]][p].add(art)
    return {k: {m: "|".join(sorted(a)) for m, a in v.items()}
            for k, v in aus.items()}


def brauchbar(zeile):
    """Taugt diese Footprint-Zeile für einen Grössenvergleich?

    `skala` und `unter_trea` bedeuten: die QUOTEN stimmen, der absolute Betrag
    nicht. Ein Vergleich absoluter Beträge ist damit sinnlos — und wäre er
    erlaubt, produzierte er genau die Scheinverstösse, an denen #83 hängt.

    `residual` und `kein_heimatland` stören den Betrag NICHT: dort geht es um
    die Länderzuordnung, und die Summe bleibt gültig.
    """
    if not zeile:
        return False, "keine Zeile"
    vb = set((zeile.get("vorbehalt") or "").split("|")) - {""}
    stoerend = vb & {"skala", "unter_trea"}
    if stoerend:
        return False, "skalenvorbehalt: " + "|".join(sorted(stoerend))
    return True, ""


def vergleiche(kind, mutter, kind_laender, mutter_laender,
               toleranz=TOLERANZ, laender_toleranz=LAENDER_TOLERANZ):
    """(urteil, grund, quote, fehlende_laender) für EIN Paar.

    Urteile:
      `stimmig`        Tochter kleiner als die Gruppe, Länder enthalten
      `groesser`       die Tochter meldet mehr Exposure als ihre Gruppe
      `laender_fehlen` die Gruppe kennt Länder der Tochter nicht
      `nicht_pruefbar` einer der beiden Reports trägt einen Skalenvorbehalt
    """
    ok_k, grund_k = brauchbar(kind)
    ok_m, grund_m = brauchbar(mutter)
    if not (ok_k and ok_m):
        wer = "Tochter" if not ok_k else "Mutter"
        return "nicht_pruefbar", f"{wer}: {grund_k or grund_m}", None, []

    ke = float(kind["total_exposure_eur"])
    me = float(mutter["total_exposure_eur"])
    if me <= 0:
        return "nicht_pruefbar", "Mutter ohne Exposure", None, []
    quote = ke / me

    fehlend = sorted(kind_laender - mutter_laender)
    anteil = len(fehlend) / len(kind_laender) if kind_laender else 0.0

    if quote > toleranz:
        return ("groesser",
                f"Tochter meldet {quote:.2f}× das Exposure der Gruppe",
                quote, fehlend)
    if anteil > laender_toleranz:
        return ("laender_fehlen",
                f"{len(fehlend)} von {len(kind_laender)} Ländern der Tochter "
                f"fehlen im Gruppenprofil", quote, fehlend)
    return "stimmig", "", quote, fehlend


def build():
    import duckdb

    fp = lade_footprint()
    kanten = lade_kanten()
    if not fp or not kanten:
        print("ERROR: footprint.csv oder lei_relations.csv fehlt")
        return []

    con = duckdb.connect()
    laender = collections.defaultdict(set)
    for lei, scope, rp, land in con.execute(f"""
        SELECT DISTINCT lei, scope, refPeriod, open_axis_country
        FROM '{ROOT / "processed" / "long" / "p3dh_long.parquet"}'
        WHERE template_id = '67.01.A' AND cell_col = '0060'
          AND open_axis_country IS NOT NULL AND cell_row <> 'x1'
    """).fetchall():
        laender[(lei, scope, rp)].add(land)

    zeilen = []
    for (lei, scope, rp), kind in sorted(fp.items()):
        if scope != "IND":
            continue
        for mutter_lei, art in sorted(kanten.get(lei, {}).items()):
            mutter = fp.get((mutter_lei, "CON", rp))
            if not mutter:
                continue
            urteil, grund, quote, fehlend = vergleiche(
                kind, mutter, laender.get((lei, scope, rp), set()),
                laender.get((mutter_lei, "CON", rp), set()))
            zeilen.append({
                "refPeriod": rp, "kind_lei": lei,
                "kind_name": kind["bank_name"], "mutter_lei": mutter_lei,
                "mutter_name": mutter["bank_name"], "beziehung": art,
                "kind_exposure_eur": kind["total_exposure_eur"],
                "mutter_exposure_eur": mutter["total_exposure_eur"],
                "quote": "" if quote is None else f"{quote:.4f}",
                "kind_laender": len(laender.get((lei, scope, rp), set())),
                "mutter_laender": len(laender.get((mutter_lei, "CON", rp), set())),
                # Der naheliegende Einwand gegen jeden Laenderbefund: das Land
                # koennte im Residualbucket der Mutter stecken (CCyB1 erlaubt,
                # unwesentliche Laender zusammenzufassen). Die Spalte macht das
                # nachpruefbar — bei allen heutigen Befunden liegt sie nahe
                # null, der Einwand traegt dort also nicht.
                "mutter_x28": mutter.get("x28_share", ""),
                "fehlende_laender": "|".join(fehlend[:8]),
                "urteil": urteil, "grund": grund})

    zeilen.sort(key=lambda z: (z["refPeriod"], z["kind_lei"], z["mutter_lei"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(zeilen)
    print(f"✓ {OUT}  ({len(zeilen)} Paare)")
    for s in bericht(zeilen):
        print("  " + s)
    return zeilen


def bericht(zeilen):
    u = collections.Counter(z["urteil"] for z in zeilen)
    aus = ["Urteile: " + ("  ".join(f"{k}={v}" for k, v in u.most_common())
                          or "keine Paare")]
    if not zeilen:
        aus.append("Keine Tochter-IND/Mutter-CON-Paare im Bestand — der "
                   "Abgleich GREIFT nicht, er findet nur nichts.")
        return aus
    for z in zeilen:
        if z["urteil"] in ("groesser", "laender_fehlen"):
            aus.append(f"  ⚠ {z['kind_name'][:30]:32s} ⊂ "
                       f"{z['mutter_name'][:28]:30s} {z['grund']}")
    if u["nicht_pruefbar"]:
        aus.append(f"  {u['nicht_pruefbar']} Paare nicht prüfbar — ein Report "
                   f"trägt einen Skalenvorbehalt (#83). Ohne diesen Filter "
                   f"stünden sie als Verstösse da, die keine sind.")
    aus.append("Ein Befund ist KEIN Meldefehler: der aufsichtliche "
               "Konsolidierungskreis nach CRR ist nicht deckungsgleich mit dem "
               "rechtlichen Eigentum, das GLEIF abbildet.")
    return aus


if __name__ == "__main__":
    build()
