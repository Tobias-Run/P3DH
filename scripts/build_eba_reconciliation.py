"""Bottom-up gegen top-down: unsere Aggregate gegen die EBA-eigenen (#37).

Ausgabe: processed/eba_reconciliation.csv

## Der Test, der nicht schiefgehen kann

Die EBA veröffentlicht aggregierte Kennzahlen je Land; wir haben die
Einzelmeldungen. Niemand prüft, ob beides zusammenpasst — dabei ist das die
naheliegendste Validierung des ganzen Projekts. Jeder Ausgang trägt:

    stimmt überein     externe Bestätigung der Kette, vom Parser bis zur
                       EUR-Normierung. Bisher validieren wir nur intern.
    systematisch ab    eine Aussage über Abdeckung — wer ist in den
                       EBA-Zahlen und nicht im Hub (#42)
    sprunghaft ab      wir haben einen Fehler, und zwar einen lokalisierbaren

## Quelle

EBA Risk Dashboard, Blatt „KRIs by country and EU" des Datenanhangs. Je Zeile
Periode, Land, KRI-Code und Wert; 20 Kennzahlen, 32 Länder, quartalsweise.

Verglichen werden die vier Kapitalkennzahlen, die sich aus KM1 (`61.00`)
vollständig rechnen lassen:

    SVC_3   CET1-Quote        Σ r0010 / Σ r0040
    SVC_1   Tier-1-Quote      Σ r0020 / Σ r0040
    SVC_2   Gesamtkapital     Σ r0030 / Σ r0040
    SVC_13  Verschuldung      Σ r0020 / Σ r0210

## Drei Dinge, ohne die der Vergleich Unsinn misst

**Gewichtet, nicht gemittelt.** Die EBA weist gewichtete Durchschnitte aus:
Summe der Zähler durch Summe der Nenner. Ein naiver Mittelwert über Institute
ist etwas anderes — bei stark unterschiedlichen Bilanzsummen sehr viel anderes.

**Keine Doppelzählung.** Ohne den Konzerngraphen (#32) summieren wir Mutter und
Tochter. Gezählt wird deshalb nur, wessen direkte Mutter NICHT selbst im
Bestand meldet, und nur konsolidierte Meldungen.

**Keine kaputten Nenner.** Reports mit Skalenverdacht (#45, #83) melden ihre
absoluten Grössen um 10^3 bis 10^6 zu klein. In einem Summenaggregat
verschwinden sie nicht, sie verzerren es — sie werden ausgeschlossen und die
Zahl der Ausgeschlossenen steht in der Ausgabe.

## Und die Einschränkung, die bleibt

**Die Grundgesamtheiten sind verschieden, und das ist kein Fehler.** Das EBA
Risk Dashboard beruht auf aufsichtlichem Meldewesen (COREP/FINREP) über eine
definierte Stichprobe; P3DH ist Offenlegung nach CRR Teil 8 mit anderer
Abgrenzung. Eine Abweichung ist deshalb **erwartbar**. Die Spalte `abdeckung`
sagt, auf wie vielen Instituten unsere Seite beruht — ohne sie wäre jede
Differenz uninterpretierbar, und der kleinere Wert wäre fälschlich der „falsche".

Aufruf: python3 scripts/build_eba_reconciliation.py [--xlsx PFAD ...]
"""

from pathlib import Path
import argparse
import collections
import csv
import re
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
META = ROOT / "processed" / "entity_meta.csv"
RELATIONS = ROOT / "processed" / "lei_relations.csv"
DICHTE = ROOT / "processed" / "rwa_density.csv"
GEO = ROOT / "codebook" / "geo_names.csv"
OUT = ROOT / "processed" / "eba_reconciliation.csv"

SEITE = ("https://www.eba.europa.eu/risk-and-data-analysis/risk-analysis/"
         "risk-monitoring/risk-dashboard")
BASIS = "https://www.eba.europa.eu"

# KRI -> (Zähler-Zeile, Nenner-Zeile) in KM1 61.00, Spalte c0010.
KRI = {
    "SVC_3":  ("0010", "0040"),   # CET1-Quote
    "SVC_1":  ("0020", "0040"),   # Tier-1-Quote
    "SVC_2":  ("0030", "0040"),   # Gesamtkapitalquote
    "SVC_13": ("0020", "0210"),   # Verschuldungsquote
}

FELDER = ["kri", "kri_name", "refPeriod", "country_iso", "country",
          "eba_wert", "unser_wert", "differenz_pp",
          "n_institute", "n_ausgeschlossen_gruppe", "n_ausgeschlossen_skala"]


def annex_urls():
    """Die Datenanhänge von der Übersichtsseite lesen, nicht raten."""
    with urllib.request.urlopen(SEITE, timeout=90) as h:
        html = h.read().decode("utf-8", "replace")
    treffer = re.findall(r'href="([^"]*Data%20Annex[^"]*\.xlsx)"', html)
    return [t if t.startswith("http") else BASIS + t for t in treffer]


def lies_annex(pfad):
    """{(kri, YYYYMM, ISO2): (name, wert)} aus dem Blatt „KRIs by country and EU"."""
    import openpyxl
    wb = openpyxl.load_workbook(pfad, read_only=True, data_only=True)
    blatt = next((n for n in wb.sheetnames if n.startswith("KRIs by country")), None)
    if not blatt:
        return {}
    out = {}
    for row in wb[blatt].iter_rows(min_row=2, values_only=True):
        if not row or len(row) < 5 or not row[0]:
            continue
        periode, land, code, name, wert = (str(x) if x is not None else "" for x in row[:5])
        try:
            out[(code, periode, land)] = (name, float(wert))
        except ValueError:
            continue
    return out


def periode_von(refperiod):
    """'2025-12-31' -> '202512'."""
    return refperiod[:4] + refperiod[5:7]


def eigenstaendige(meta):
    """LEIs, deren direkte Mutter NICHT selbst im Bestand meldet.

    Ohne das summiert ein Länderaggregat Mutter UND Tochter — gemessen liegt
    bei 66 der 508 Institute die Mutter selbst im Bestand (#32).
    """
    if not RELATIONS.exists():
        return set(meta)
    with RELATIONS.open(encoding="utf-8") as fh:
        rel = {r["lei"]: r["direct_parent_lei"] for r in csv.DictReader(fh)}
    return {l for l in meta if rel.get(l, "") not in meta or not rel.get(l)}


def verdaechtige():
    """(lei, scope, refPeriod) mit Skalenverdacht aus #45."""
    if not DICHTE.exists():
        return set()
    with DICHTE.open(encoding="utf-8") as fh:
        return {(r["lei"], r["scope"], r["refPeriod"]) for r in csv.DictReader(fh)
                if r["skalenverdacht"] == "true"}


def unsere_aggregate(con, meta, ohne_mutter, kaputt):
    """{(kri, refPeriod, land): (wert, n, n_gruppe, n_skala)} — GEWICHTET."""
    from determinism import ordered_query as ordered
    zeilen = ordered(con, """
        SELECT lei, scope, refPeriod, cell_row,
               max(COALESCE(fact_value_eur, TRY_CAST(fact_value AS DOUBLE))) AS v
        FROM p
        WHERE template_id='61.00' AND cell_col='0010'
          AND cell_row IN ('0010','0020','0030','0040','0210')
          AND scope='CON'
        GROUP BY lei, scope, refPeriod, cell_row
        ORDER BY lei, scope, refPeriod, cell_row
    """, "KM1 / Kapital")
    je = {}
    for lei, scope, rp, row, v in zeilen:
        if v is not None:
            je.setdefault((lei, scope, rp), {})[row] = v

    summen = collections.defaultdict(lambda: [0.0, 0.0, 0, 0, 0])
    for (lei, scope, rp), z in sorted(je.items()):
        land = (meta.get(lei) or {}).get("country", "")
        for kri, (zae, nen) in KRI.items():
            schluessel = (kri, rp, land)
            eintrag = summen[schluessel]
            if lei not in ohne_mutter:
                eintrag[2] += 1            # wegen Konzernmutter ausgeschlossen
                continue
            if (lei, scope, rp) in kaputt:
                eintrag[3] += 1            # wegen Skalenverdacht ausgeschlossen
                continue
            a, b = z.get(zae), z.get(nen)
            if a is None or b is None or b <= 0:
                continue
            eintrag[0] += a
            eintrag[1] += b
            eintrag[4] += 1
    return {k: (v[0] / v[1] if v[1] else None, v[4], v[2], v[3])
            for k, v in summen.items()}


def build(xlsx=None):
    import duckdb
    pfade = [Path(x) for x in (xlsx or [])]
    if not pfade:
        ziel = Path("/tmp")
        for u in annex_urls():
            name = ziel / re.sub(r"[^A-Za-z0-9._-]", "_", u.rsplit("/", 1)[-1])
            print(f"  hole {name.name}")
            with urllib.request.urlopen(u, timeout=300) as h:
                name.write_bytes(h.read())
            pfade.append(name)

    eba = {}
    for p in pfade:
        eba.update(lies_annex(p))
    print(f"  EBA-Anhänge gelesen: {len(pfade)} · {len(eba)} Werte")

    with META.open(encoding="utf-8") as fh:
        meta = {r["lei"]: r for r in csv.DictReader(fh)}
    iso = {}
    if GEO.exists():
        with GEO.open(encoding="utf-8") as fh:
            iso = {r["name"]: r["code"].upper() for r in csv.DictReader(fh)}

    con = duckdb.connect()
    con.execute(f"CREATE VIEW p AS SELECT * FROM '{PARQUET.as_posix()}'")
    unser = unsere_aggregate(con, meta, eigenstaendige(set(meta)), verdaechtige())

    zeilen = []
    for (kri, rp, land), (wert, n, n_gruppe, n_skala) in sorted(unser.items()):
        code = iso.get(land, "")
        if wert is None or not code:
            continue
        e = eba.get((kri, periode_von(rp), code))
        if not e:
            continue
        name, ebawert = e
        zeilen.append({
            "kri": kri, "kri_name": name.replace("\n", " ")[:60],
            "refPeriod": rp, "country_iso": code, "country": land,
            "eba_wert": round(ebawert, 6), "unser_wert": round(wert, 6),
            "differenz_pp": round((wert - ebawert) * 100, 3),
            "n_institute": n, "n_ausgeschlossen_gruppe": n_gruppe,
            "n_ausgeschlossen_skala": n_skala,
        })
    zeilen.sort(key=lambda z: (z["kri"], z["refPeriod"], z["country_iso"]))
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(zeilen)

    print(f"✓ {OUT}  ({len(zeilen)} Vergleichspunkte)")
    for s in bericht(zeilen):
        print("  " + s)
    return zeilen


def bericht(zeilen):
    import statistics as st
    aus = []
    if not zeilen:
        return ["keine Vergleichspunkte — Perioden oder Länder passen nicht"]
    for kri in sorted({z["kri"] for z in zeilen}):
        teil = [z for z in zeilen if z["kri"] == kri]
        d = sorted(abs(z["differenz_pp"]) for z in teil)
        aus.append(f"{kri:7} n={len(teil):>4}  |Differenz| Median {st.median(d):5.2f} pp  "
                   f"p90 {d[int(.9 * len(d))]:6.2f} pp  max {d[-1]:7.2f} pp")
    nah = [z for z in zeilen if abs(z["differenz_pp"]) <= 1.0]
    aus.append(f"innerhalb 1 Prozentpunkt: {len(nah)} von {len(zeilen)} "
               f"({100 * len(nah) / len(zeilen):.0f} %)")
    weit = sorted(zeilen, key=lambda z: -abs(z["differenz_pp"]))[:5]
    aus.append("grösste Abweichungen:")
    for z in weit:
        aus.append(f"  {z['kri']:7} {z['country_iso']} {z['refPeriod']}  "
                   f"EBA {z['eba_wert']:.4f}  wir {z['unser_wert']:.4f}  "
                   f"({z['differenz_pp']:+.2f} pp, n={z['n_institute']})")
    return aus


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", nargs="*", help="lokale Datenanhänge (sonst werden sie geholt)")
    a = ap.parse_args()
    build(a.xlsx)
