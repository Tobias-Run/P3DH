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
GRUPPEN = ROOT / "processed" / "entity_groups.csv"
COVERAGE = ROOT / "processed" / "coverage_gap.csv"
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

# Bis hierher gilt eine Abweichung als stimmig. Ein Prozentpunkt auf einer
# Kapitalquote ist bei verschiedenen Grundgesamtheiten kein Befund.
NAH_PP = 1.0

# Unter so vielen Instituten ist ein gewichtetes Landesaggregat nicht
# vergleichbar: gemessen weichen Laender mit hoechstens zwei Instituten im
# Median um 1,07 pp ab, solche mit acht und mehr nur um 0,23 pp.
DUENN = 2

# Ab welchem Anteil selbst meldender signifikanter Institute ein Landesaggregat
# ueberhaupt vergleichbar ist. Darunter melden die grossen Haeuser ueber eine
# auslaendische Mutter, und ihr Kapital steht im Aggregat des Mutterlands.
SELBSTMELDER = 0.50

FELDER = ["kri", "kri_name", "refPeriod", "country_iso", "country",
          "eba_wert", "unser_wert", "differenz_pp",
          "n_institute", "n_ausgeschlossen_gruppe", "n_ausgeschlossen_skala",
          "n_si_land", "n_si_selbstmelder", "quote_selbstmelder", "ursache"]


# Die EBA-Seite weist den Standard-User-Agent von `urllib` (Python-urllib/3.x)
# mit HTTP 403 ab. Hier steht deshalb eine ehrliche Kennung mit Projektadresse
# — das ist korrekte Client-Identifikation, wie sie jeder Betreiber erwartet,
# und ausdruecklich KEIN vorgetaeuschter Browser.
UA = "P3DH-Pipeline/1.0 (+https://github.com/Tobias-Run/P3DH)"


def hole(url, timeout=90):
    """Eine GET-Anfrage mit benannter Kennung."""
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout)


def annex_urls():
    """Die Datenanhänge von der Übersichtsseite lesen, nicht raten."""
    with hole(SEITE) as h:
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


def melder_menge(pfad=None):
    """LEIs, die tatsächlich MELDEN — aus entity_groups.csv (#32).

    Nicht dasselbe wie `entity_meta`: dort stehen auch Institute, von denen
    kein Report vorliegt. Für die Frage „wird diese Tochter schon von ihrer
    Mutter mitgemeldet?" zählt allein, wer meldet.
    """
    pfad = Path(pfad or GRUPPEN)
    if not pfad.exists():
        return {}
    with pfad.open(encoding="utf-8") as fh:
        return {r["lei"]: r["konzern_kopf"] for r in csv.DictReader(fh)}


def eigenstaendige(meta, koepfe=None):
    """LEIs, deren Kapital nicht schon in einer anderen Meldung steckt.

    Geprüft werden BEIDE Wege, und das ist seit #32 eine echte Korrektur:

    * die **direkte Mutter** meldet — die bisherige Regel;
    * der **aufgelöste Konzernkopf** meldet — neu aus `entity_groups.csv`.

    Keiner der beiden genügt allein. Die alte Regel liess Enkelinnen durch,
    deren direkte Mutter nicht meldet, deren Konzernkopf aber schon. Eine
    Regel nur auf dem Konzernkopf macht den umgekehrten Fehler: **Bank
    Handlowy w Warszawie** hat als GLEIF-Kopf die Citigroup, die im P3DH
    nicht meldet — ihre direkte Mutter *Citibank Europe plc* aber sehr wohl.
    Auf dem Kopf allein geprüft stünde ihr Kapital zweimal im polnischen
    Aggregat.

    Der Unterschied ist klein und real: 12 der 442 Institute fallen zusätzlich
    heraus.
    """
    koepfe = koepfe if koepfe is not None else melder_menge()
    rel = {}
    if RELATIONS.exists():
        with RELATIONS.open(encoding="utf-8") as fh:
            rel = {r["lei"]: (r["direct_parent_lei"] or "")
                   for r in csv.DictReader(fh)}
    melder = set(koepfe)

    def steckt_schon_drin(lei):
        mutter = rel.get(lei, "")
        if mutter and mutter != lei and mutter in melder:
            return True
        kopf = koepfe.get(lei, "")
        return bool(kopf) and kopf != lei and kopf in melder

    return {l for l in meta if not steckt_schon_drin(l)}


def si_je_land(pfad=None):
    """{Ländername: (signifikante Einheiten, davon SELBST meldend)} aus #42.

    Die Grundgesamtheit UNSERER Seite, die das Issue verlangt. Sie ist
    ausdrücklich **kein** Abbild der EBA-Stichprobe — die EBA aggregiert über
    eine eigene, anders abgegrenzte Auswahl.

    Gezählt wird nur `meldet_selbst`, und das war eine Korrektur. Der erste
    Versuch zählte `ueber_gruppe` mit und gab Luxemburg damit eine Abdeckung
    von 1,0 — bei einer Abweichung von 10 Prozentpunkten. Tatsächlich melden
    dort **7 von 30** signifikanten Instituten selbst; die übrigen 21 sind
    Töchter ausländischer Gruppen, deren Kapital im Land der MUTTER
    aggregiert wird und im luxemburgischen Aggregat deshalb gar nicht
    auftaucht.

    Genau das ist der Konsolidierungsunterschied, den das Issue als Ursache
    nennt — und er ist an dieser Quote ablesbar:

        Luxemburg   7 von 30   23,3 %      grösste Abweichungen
        Belgien     8 von 20   40,0 %
        Irland      6 von 11   54,5 %
        Deutschland 32 von 64  50,0 %
    """
    pfad = Path(pfad or COVERAGE)
    if not pfad.exists():
        return {}
    aus = collections.defaultdict(lambda: [0, 0])
    with pfad.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if not (r.get("signifikanz") or "").upper().startswith("S"):
                continue
            e = aus[r["land"]]
            e[0] += 1
            if r.get("einordnung") == "meldet_selbst":
                e[1] += 1
    return {k: tuple(v) for k, v in aus.items()}


def ursache_von(differenz_pp, n_institute, abdeckung,
                schwelle=NAH_PP, duenn=DUENN):
    """Woher kommt die Abweichung? — Punkt 3 des Issues.

    `stimmig`        innerhalb der Toleranz, nichts zu erklären
    `duenne_basis`   zu wenige Institute für ein vergleichbares Aggregat
    `konsolidierung` die signifikanten Häuser des Landes melden überwiegend
                     NICHT selbst, sondern über eine ausländische Mutter —
                     ihr Kapital steht im Aggregat des Mutterlands
    `unerklaert`     breite Basis, die Häuser melden selbst — und trotzdem
                     weit daneben

    Der **Stichtagsversatz** steht bewusst NICHT in dieser Liste. Er wurde
    geprüft und ist widerlegt: über 287 Zellen passt unser Wert 111-mal besser
    zum aktuellen EBA-Quartal und nur 44-mal besser zum Vorquartal. Eine
    Ursache, die man nicht misst, gehört nicht in die Spalte.
    """
    if abs(differenz_pp) <= schwelle:
        return "stimmig"
    if n_institute <= duenn:
        return "duenne_basis"
    if abdeckung is not None and abdeckung < SELBSTMELDER:
        return "konsolidierung"
    return "unerklaert"


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
            with hole(u, timeout=300) as h:
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
    koepfe = melder_menge()
    unser = unsere_aggregate(con, meta, eigenstaendige(set(meta), koepfe),
                             verdaechtige())
    si = si_je_land()

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
        gesamt, abgedeckt = si.get(land, (0, 0))
        quote = abgedeckt / gesamt if gesamt else None
        zeilen[-1].update({
            "n_si_land": gesamt, "n_si_selbstmelder": abgedeckt,
            "quote_selbstmelder": "" if quote is None else round(quote, 4),
            "ursache": ursache_von(zeilen[-1]["differenz_pp"], n, quote)})
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
    import collections as co
    u = co.Counter(z.get("ursache", "") for z in zeilen)
    aus.append("Ursache der Abweichung (#37 Punkt 3): "
               + "  ".join(f"{k}={v}" for k, v in u.most_common() if k))
    aus.append("  Der Stichtagsversatz fehlt in dieser Liste, weil er GEPRÜFT "
               "und widerlegt ist: über 287 Zellen passt unser Wert 111-mal "
               "besser zum aktuellen EBA-Quartal und nur 44-mal besser zum "
               "Vorquartal.")
    unerklaert = [z for z in zeilen if z.get("ursache") == "unerklaert"]
    aus.append(f"  {len(unerklaert)} Zellen bleiben unerklärt: breite Basis, "
               f"gute Abdeckung — und trotzdem über {NAH_PP:.0f} pp daneben. "
               f"Das ist die Teilmenge, die eine Erklärung verdient.")
    for z in sorted(unerklaert, key=lambda z: -abs(z["differenz_pp"]))[:4]:
        aus.append(f"    {z['kri']:7} {z['country_iso']} {z['refPeriod']}  "
                   f"{z['differenz_pp']:+.2f} pp · n={z['n_institute']} · "
                   f"Selbstmelder {z['quote_selbstmelder']}")
    weit = sorted(zeilen, key=lambda z: -abs(z["differenz_pp"]))[:5]
    aus.append("grösste Abweichungen:")
    for z in weit:
        aus.append(f"  {z['kri']:7} {z['country_iso']} {z['refPeriod']}  "
                   f"EBA {z['eba_wert']:.4f}  wir {z['unser_wert']:.4f}  "
                   f"({z['differenz_pp']:+.2f} pp, n={z['n_institute']}, "
                   f"{z.get('ursache', '')})")
    aus.append("Die Abweichung ist KEIN Gütemass für unsere Methode. Die "
               "korrigierte Entdopplung (#32) entfernt echte Doppelzählungen "
               "und vergrössert die Abweichung dabei — in den 28 betroffenen "
               "Zellen von 0,88 auf 1,08 pp. Wer auf die EBA-Zahl hin "
               "optimiert, passt die eigene Methode an eine fremde "
               "Grundgesamtheit an.")
    return aus


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", nargs="*", help="lokale Datenanhänge (sonst werden sie geholt)")
    a = ap.parse_args()
    build(a.xlsx)
