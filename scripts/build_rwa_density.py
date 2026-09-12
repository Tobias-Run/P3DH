"""RWA-Dichte über die volle Population, mit Zerlegung nach Risikomix (#45).

Ausgabe: processed/rwa_density.csv

## Was das über die EBA-Übung hinaus liefert

Die Streuung der Risikogewichte ist eines der meistuntersuchten Themen der
Bankenregulierung. Die EBA-Benchmarking-Übung deckt aber nur **IRB-Institute**
ab und veröffentlicht **nicht auf Institutsebene**. Unser Beitrag ist nicht das
bessere Modell, sondern die breitere Grundgesamtheit: alle Melder, inklusive
Standardansatz-Häuser, je Institut nachvollziehbar.

## Zähler und Nenner — und warum der Name irreführt

    RWA-Dichte := TREA (KM1 61.00 r0040) / Gesamtrisikopositionsmessgröße
                  der Verschuldungsquote (KM1 61.00 r0210)

Das ist **nicht** TREA/Bilanzsumme. Die LR-Messgröße enthält ausserbilanzielle
Positionen und folgt aufsichtlichen Anrechnungsregeln; wer die Zahl gegen
Literatur hält, die TREA/Total Assets rechnet, vergleicht Verschiedenes.

Genommen wird jeweils Spalte `c0010` — KM1 führt in `c0020`–`c0050` die vier
Vorquartale mit. Eine Zeitreihe im Report ist etwas anderes als der Stichtag.

## Die Gegenprobe, die es umsonst gibt

OV1 (`60.00.A` r0380) trägt dieselbe Gesamtsumme noch einmal. Gemessen über 704
Paare: **Median-Abweichung 0,0000 %**, nur 16 liegen über 1 % auseinander. Zwei
unabhängig gemeldete Templates, dieselbe Zahl — das validiert die Kette vom
Parser bis zur EUR-Normierung besser als jeder interne Guard. Die Spalte
`ov1_abweichung` führt es je Zeile mit.

## Skalenverdacht: belegt, nicht geraten

Sechs Institute melden ihren Nenner an einem Stichtag um Faktor 10³ bis 10⁶
neben ihren eigenen anderen Stichtagen:

    Deutsche Pfandbriefbank AG    4,1e4 · 4,2e4 · 3,72e10 · 3,74e10
    National Bank of Greece       8,01e4 · 8,15e10 · 8,6e10
    Banca Transilvania            4,23e7 · 4,33e10
    First Investment Bank         8,91e6 · 9,29e6 · 9,99e9 · 1,1e10
    EXIM Banca Romaneasca         5,51e9 · 6,33e6
    AB Artea bankas               6,14e6 · 6,18e9

Der Beleg ist die **eigene Zeitreihe**, nicht eine Schwelle auf der Dichte. Das
ist der entscheidende Unterschied: eine Dichte von 0,031 sieht genauso
unplausibel aus — **ist aber echt.** Kommuninvest finanziert schwedische
Kommunen, Risikogewicht 0 %, und meldet an drei Stichtagen stabil um 0,03. Ein
pauschaler Ausreisserfilter hätte Kommuninvest genauso weggeworfen wie Athen
und damit die interessanteste Beobachtung des Datensatzes gelöscht.

Korrigiert wird **nichts**. Wie bei der Sperrliste in #9: wer eine
Grössenordnung stillschweigend geraderückt, erfindet Daten, falls die Vermutung
falsch ist. Die Spalte `skalenverdacht` markiert, `plausibel` fasst zusammen,
die Werte bleiben unverändert stehen.

Institute mit nur EINEM Stichtag bekommen `skalenverdacht = unbekannt`, nicht
`false` — es fehlt schlicht die Vergleichsgrundlage („Fehlt ≠ Null").

Aufruf: python3 scripts/build_rwa_density.py
"""

from pathlib import Path
import collections
import csv
import statistics as st
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
META = ROOT / "processed" / "entity_meta.csv"
OUT = ROOT / "processed" / "rwa_density.csv"

# Ab diesem Faktor gegenüber dem eigenen Median ist der Nenner kein
# Geschäftsvorgang mehr. Gemessen springen die Fälle um 10^3 bis 10^6; 100 liegt
# weit darüber, was ein Institut zwischen zwei Quartalen bewegt.
SKALEN_FAKTOR = 100

# Oberhalb dieser Dichte ist der Nenner kaputt, nicht das Portfolio besonders.
# Bewusst NICHT bei 1: die Entwicklungsbank FMO meldet 1,16 und Brown Brothers
# Harriman 2,31 — hohe, aber denkbare Werte. Die belegten Skalenfehler liegen
# bei 410, 437, 462 und 475.096.
DICHTE_ABSURD = 10

# OV1-Zeilen: Risikoart -> Zeilencode. „Davon"-Zeilen getrennt, weil sie sich
# NICHT zur Gesamtsumme addieren, sondern in r0010 bzw. r0070 enthalten sind.
OV1 = {"kredit": "0010", "ccr": "0070", "cva": "0120", "settlement": "0200",
       "verbriefung": "0210", "grosskredite": "0300", "umwidmung": "0310",
       "markt": "0260", "operationell": "0320", "gesamt": "0380"}

# Die Zeilen, die sich zur Gesamtsumme ADDIEREN. Empirisch bestimmt, nicht
# angenommen: mit dieser Menge stimmen 646 von 746 Reports exakt (Median-
# Abweichung 0,0000 %). Nimmt man r0340 („Amounts below the thresholds for
# deduction, subject to 250% risk weight") hinzu, sind es nur noch 196 — die
# Zeile ist eine NACHRICHTENZEILE und steckt bereits im Kreditrisiko.
OV1_SUMMANDEN = ["0010", "0070", "0120", "0200", "0210", "0260", "0300",
                 "0310", "0320"]
OV1_ANSATZ = {"sa": "0020", "f_irb": "0030", "a_irb": "0060"}

FELDER = ["lei", "scope", "refPeriod", "bank_name", "country", "institution_type",
          "trea_eur", "lr_exposure_eur", "rwa_density",
          "ov1_total_eur", "ov1_abweichung",
          "ov1_teile_summe", "ov1_teile_stimmt",
          "anteil_kredit", "anteil_ccr", "anteil_markt", "anteil_operationell",
          "kredit_sa_anteil", "kredit_irb_anteil", "ansatz",
          "skalenverdacht", "plausibel"]


def _zellen(con, template, zeilen):
    """{(entityID, refPeriod): {zeile: wert}} für Spalte c0010."""
    from determinism import ordered_query as ordered
    liste = ",".join(f"'{z}'" for z in sorted(zeilen))
    roh = ordered(con, f"""
        SELECT entityID, refPeriod, cell_row,
               max(COALESCE(fact_value_eur, TRY_CAST(fact_value AS DOUBLE))) AS v
        FROM p
        WHERE template_id='{template}' AND cell_col='0010' AND cell_row IN ({liste})
        GROUP BY entityID, refPeriod, cell_row
        ORDER BY entityID, refPeriod, cell_row
    """, f"{template} / Zellen")
    out = {}
    for eid, rp, row, v in roh:
        if v is not None:
            out.setdefault((eid, rp), {})[row] = v
    return out


def _anteil(zaehler, nenner):
    if not nenner or zaehler is None:
        return ""
    return round(zaehler / nenner, 4)


def skalenverdacht(lr_je_institut, dichte_je=None):
    """{entityID: {refPeriod: 'true'|'false'|'unbekannt'}}.

    ## Zwei unabhängige Signale, und warum es beide braucht

    **(a) Gegen das MAXIMUM der eigenen Zeitreihe.** Der Skalenfehler macht den
    Nenner immer zu KLEIN (durch 10^3 oder 10^6 geteilt). Ist ein Wert um
    `SKALEN_FAKTOR` kleiner als der grösste andere Stichtag desselben Instituts,
    ist er der kaputte.

    Gegen den Median zu prüfen war der erste Versuch und er war falsch: bei der
    Deutschen Pfandbriefbank (4,1e4 · 4,2e4 · 3,72e10 · 3,74e10) liegt der
    Median zwischen den Welten, und die Regel markierte **beide Seiten des
    Sprungs** — auch die beiden korrekten Stichtage. Sie erkannte, dass das
    Institut inkonsistent ist, aber nicht, welcher Wert es ist.

    **(b) Gegen die Dichte selbst, bei absurder Höhe.** Ein Institut mit nur
    EINEM Stichtag hat keine Zeitreihe. Banque Banorient France meldet dort eine
    Dichte von 410 — und fiel durch (a) glatt hindurch. Oberhalb von
    `DICHTE_ABSURD` ist das keine Portfolioeigenschaft mehr.

    Die Schwelle liegt bei 10 und nicht bei 1: die Entwicklungsbank FMO meldet
    1,16 und Brown Brothers Harriman 2,31. Das sind hohe, aber denkbare Werte
    für Häuser mit hohen Risikogewichten — sie als Fehler zu markieren wäre
    dieselbe Anmassung wie ein Ausreisserfilter, der Kommuninvest löscht.
    """
    dichte_je = dichte_je or {}
    out = {}
    for eid, werte in lr_je_institut.items():
        out[eid] = {}
        gueltig = [x for x in werte.values() if x]
        groesster = max(gueltig) if gueltig else 0
        for rp, v in werte.items():
            d = dichte_je.get((eid, rp))
            if d is not None and d > DICHTE_ABSURD:
                out[eid][rp] = "true"          # (b)
                continue
            if len(gueltig) < 2 or not v:
                out[eid][rp] = "unbekannt"
                continue
            out[eid][rp] = "true" if groesster / v >= SKALEN_FAKTOR else "false"   # (a)
    return out


def build():
    import duckdb
    con = duckdb.connect()
    con.execute(f"CREATE VIEW p AS SELECT * FROM '{PARQUET.as_posix()}'")

    km = _zellen(con, "61.00", ["0040", "0210"])
    ov = _zellen(con, "60.00.A", list(OV1.values()) + list(OV1_ANSATZ.values()))

    with META.open(encoding="utf-8") as fh:
        meta = {r["lei"]: r for r in csv.DictReader(fh)}

    lr_je = collections.defaultdict(dict)
    for (eid, rp), z in km.items():
        if z.get("0210"):
            lr_je[eid][rp] = z["0210"]
    dichte_je = {(eid, rp): z["0040"] / z["0210"]
                 for (eid, rp), z in km.items() if z.get("0040") and z.get("0210")}
    verdacht = skalenverdacht(lr_je, dichte_je)

    zeilen = []
    for (eid, rp), z in km.items():
        trea, lr = z.get("0040"), z.get("0210")
        if not trea or not lr:
            continue           # ohne beide Seiten gibt es keine Dichte
        lei, _, scope = eid.partition("rs:")[2].rpartition(".")
        m = meta.get(lei, {})
        o = ov.get((eid, rp), {})
        gesamt = o.get(OV1["gesamt"])
        kredit = o.get(OV1["kredit"])
        teilsumme = sum(o.get(z) or 0 for z in OV1_SUMMANDEN)
        sv = verdacht.get(eid, {}).get(rp, "unbekannt")
        zeilen.append({
            "lei": lei, "scope": scope, "refPeriod": rp,
            "bank_name": m.get("name", ""), "country": m.get("country", ""),
            "institution_type": m.get("institution_type", ""),
            "trea_eur": round(trea, 2), "lr_exposure_eur": round(lr, 2),
            "rwa_density": round(trea / lr, 4),
            "ov1_total_eur": round(gesamt, 2) if gesamt else "",
            "ov1_abweichung": round(abs(gesamt - trea) / trea, 6) if gesamt else "",
            "ov1_teile_summe": round(teilsumme, 2) if gesamt else "",
            "ov1_teile_stimmt": ("" if not gesamt else
                                 "true" if abs(teilsumme - gesamt) <= 0.001 * gesamt
                                 else "false"),
            "anteil_kredit": _anteil(kredit, gesamt),
            "anteil_ccr": _anteil(o.get(OV1["ccr"]), gesamt),
            "anteil_markt": _anteil(o.get(OV1["markt"]), gesamt),
            "anteil_operationell": _anteil(o.get(OV1["operationell"]), gesamt),
            "kredit_sa_anteil": _anteil(o.get(OV1_ANSATZ["sa"]), kredit),
            "kredit_irb_anteil": _anteil(
                (o.get(OV1_ANSATZ["f_irb"]) or 0) + (o.get(OV1_ANSATZ["a_irb"]) or 0)
                if (o.get(OV1_ANSATZ["f_irb"]) or o.get(OV1_ANSATZ["a_irb"])) else None,
                kredit),
            "ansatz": "",          # unten gesetzt, sobald die Anteile stehen
            "skalenverdacht": sv,
            "plausibel": "false" if sv == "true" else "true",
        })

    for z in zeilen:
        z["ansatz"] = ansatz_von(z["kredit_sa_anteil"], z["kredit_irb_anteil"])

    zeilen.sort(key=lambda z: (z["lei"], z["scope"], z["refPeriod"]))
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(zeilen)

    print(f"✓ {OUT}  ({len(zeilen)} Zeilen)")
    for zeile in bericht(zeilen):
        print("  " + zeile)
    return zeilen


def ansatz_von(sa, irb):
    """SA / IRB / gemischt — aus den OV1-„davon"-Zeilen, nicht geraten.

    Schwelle 90 %: darunter meldet das Institut in beiden Welten, und das
    zusammenzufassen verwischt genau den Unterschied, um den es in #45 geht.
    """
    if sa == "" and irb == "":
        return "unbekannt"
    s, i = float(sa or 0), float(irb or 0)
    if s >= 0.9:
        return "SA"
    if i >= 0.9:
        return "IRB"
    return "gemischt"


def bericht(zeilen):
    gut = [z for z in zeilen if z["plausibel"] == "true"]
    d = sorted(float(z["rwa_density"]) for z in gut)

    def p(q):
        return d[int(q * len(d))] if d else 0

    aus = [f"Institute: {len({z['lei'] for z in zeilen})} · Zeilen mit beiden Seiten: {len(zeilen)}",
           f"RWA-Dichte (ohne Skalenverdacht, n={len(d)}): "
           f"Median {st.median(d):.3f}  p10 {p(.10):.3f}  p90 {p(.90):.3f}"]
    sv = collections.Counter(z["skalenverdacht"] for z in zeilen)
    aus.append("Skalenverdacht: " + "  ".join(f"{k}={v}" for k, v in sorted(sv.items())))
    an = collections.Counter(z["ansatz"] for z in gut)
    aus.append("Ansatz: " + "  ".join(f"{k}={v}" for k, v in sorted(an.items())))
    for a in ("SA", "IRB", "gemischt"):
        teil = sorted(float(z["rwa_density"]) for z in gut if z["ansatz"] == a)
        if len(teil) >= 5:
            aus.append(f"  {a:9} n={len(teil):>4}  Median {st.median(teil):.3f}")
    abw = [float(z["ov1_abweichung"]) for z in zeilen if z["ov1_abweichung"] != ""]
    if abw:
        aus.append(f"OV1 gegen KM1: n={len(abw)}  Median {st.median(abw)*100:.4f} %  "
                   f"über 1 %: {sum(1 for a in abw if a > 0.01)}")
    ts = collections.Counter(z["ov1_teile_stimmt"] for z in zeilen if z["ov1_teile_stimmt"])
    if ts:
        aus.append(f"OV1-Teile summieren sich zur Gesamtzeile: "
                   f"{ts.get('true', 0)} von {sum(ts.values())}")
    return aus


if __name__ == "__main__":
    build()
