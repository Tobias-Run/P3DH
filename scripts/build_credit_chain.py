"""Die Kreditverschlechterungs-Kette über Templates hinweg (#16)

Ausgabe: processed/credit_chain.csv

## Warum das EDAP strukturell nicht kann

Kreditrisiko ist keine Zustandsgrösse, sondern eine Kette:

    performing → forborne (gestundet) → non-performing → ausgefallen

Jede Stufe steht in einem **anderen Template**. EDAP liefert ein ZIP je
Institut; Zähler und Nenner einer solchen Kennzahl liegen dort prinzipiell in
verschiedenen Dateien, die nie zusammengeführt werden. Wir haben die Population
in einer Fläche.

Drei Templates, alle drei bis dahin ungenutzt:

    82.00.A  CQ3  r0020 c0010/c0040   performing / non-performing
    80.00.A  CQ1  r0020 c0010/c0020   performing / non-performing forborne
    21.01.D  CR1  r0020 c0040         Wertberichtigung auf NPE

## Der Prototyp des Issues reproduziert

Nachgerechnet zum 31.12.2025, Zeile „Loans and advances":

    verknüpfbare Reports   347   (Issue: 340)
    Median NPL-Quote      2,33 % (Issue: 2,36 %)
    Median Vorstufe       0,59 % (Issue: 0,63 %)

Auch die vier namentlich genannten Institute stimmen. Das ist erwähnenswert,
weil es in diesem Projekt nicht selbstverständlich ist — bei #31 und #44 haben
die Ausgangszahlen der Issues nicht gehalten.

## Der Frühwarn-Indikator und seine eingebaute Falle

Das Issue schlägt das „Verhältnis Vorstufe↔NPL" als Frühwarnung vor: wer wenig
notleidende, aber viele gestundete Kredite hat, trägt ein Problem, das die
NPL-Quote noch nicht zeigt.

Roh gerechnet führt die Liste **Agence France Locale mit dem 377-fachen** an —
bei einer NPL-Quote von 0,00 % und einer Vorstufe von 0,75 %. Das ist keine
Frühwarnung, sondern eine Division durch fast nichts, dieselbe Falle wie der
AIB-Fall in `check_plausibility` (0,0008 EUR gegen 5·10⁻²³).

`MIN_VORSTUFE` verlangt deshalb, dass die Vorstufe **absolut** etwas bedeutet.
Mit einem Prozent des Kreditbuchs bleiben von 338 Instituten acht übrig — und
darunter sind IKB und Bank Handlowy, die das Issue selbst nennt.

## Die Wertberichtigung hat kein einheitliches Vorzeichen

344 Reports melden sie negativ (sie mindert das Exposure), **20 melden sie
positiv**. Für die Deckungsquote wird der Betrag genommen, aber die Konvention
steht als `wb_vorzeichen` in der Zeile: ein positiver Wert kann eine andere
Konvention sein oder ein Vorzeichenfehler, und das zu verschweigen hiesse, sich
für eine der beiden Lesarten zu entscheiden.

## Was hier NICHT gemischt wird

**CON und IND.** Das Issue verlangt es, und `DISCLAIMER.md` auch: die beiden
sind nicht dasselbe Institut. Der Peer-Median, gegen den die Frühwarnung
misst, wird deshalb je (scope, refPeriod) gebildet.

Und die Vergleichbarkeitsgrenze bleibt: Rechnungslegung und nationale Optionen
unterscheiden sich, eine NPL-Quote ist zwischen zwei Aufsichtsräumen nur
bedingt vergleichbar.

Aufruf: python3 scripts/build_credit_chain.py
"""

from pathlib import Path
import collections
import csv
import statistics
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
META = ROOT / "processed" / "entity_meta.csv"
OUT = ROOT / "processed" / "credit_chain.csv"

# Zeile „Loans and advances" — in allen drei Templates dieselbe Koordinate.
ZEILE = "0020"

# Ab welchem Anteil des Kreditbuchs die Vorstufe überhaupt etwas bedeutet.
# Ohne diesen Boden führt Agence France Locale die Liste mit dem 377-fachen an,
# weil ihre NPL-Quote 0,00 % beträgt — eine Division durch fast nichts, kein
# Befund. Gemessen bleiben mit 1 % acht Institute übrig, mit 0,5 % fünfzehn.
MIN_VORSTUFE = 0.01

# Ab welchem Verhältnis Vorstufe/NPL das Muster auffällig ist. Der Median liegt
# bei 0,28, das dritte Quartil bei 0,51 — 1,5 ist deutlich darüber und trifft
# die Fälle, die das Issue nennt (IKB 2,12; Bank Handlowy 2,34).
MIN_VERHAELTNIS = 1.5

FELDER = ["lei", "scope", "refPeriod", "bank_name", "country",
          "institution_type", "kredite_eur", "npe_eur", "npl_quote",
          "forborne_performing_eur", "vorstufe_quote",
          "forborne_non_performing_eur", "npf_quote",
          "vorstufe_verhaeltnis", "wb_npe_eur", "wb_vorzeichen",
          "deckungsquote", "npl_unter_median", "fruehwarnung"]


def quote(zaehler, nenner):
    """Anteil, oder None — nie 0 bei fehlendem Nenner.

    Eine Null wäre hier eine Aussage („kein notleidendes Exposure"), wo in
    Wahrheit keine vorliegt.
    """
    if zaehler is None or not nenner or nenner <= 0:
        return None
    return zaehler / nenner


def vorzeichen(wert):
    """`negativ`, `positiv` oder `` — die Konvention der Wertberichtigung.

    344 Reports melden sie negativ, 20 positiv. Welche Lesart richtig ist,
    entscheidet dieses Skript nicht; es rechnet mit dem Betrag und schreibt
    die Konvention daneben.
    """
    if wert is None:
        return ""
    if wert < 0:
        return "negativ"
    return "positiv" if wert > 0 else "null"


def verhaeltnis(vorstufe_quote, npl_quote):
    """Vorstufe geteilt durch NPL — der Indikator aus dem Issue, oder None.

    None bei fehlender oder verschwindender NPL-Quote. Das ist die Stelle, an
    der die Kennzahl explodiert, und ein Wert wie 377 ist dort kein grosses
    Signal, sondern gar keines.
    """
    if vorstufe_quote is None or not npl_quote or npl_quote <= 0:
        return None
    return vorstufe_quote / npl_quote


def fruehwarnung_von(vorstufe_quote, verh, unter_median,
                     min_vorstufe=MIN_VORSTUFE,
                     min_verhaeltnis=MIN_VERHAELTNIS):
    """Trägt dieses Haus ein Problem, das die NPL-Quote noch nicht zeigt?

    Drei Bedingungen, und alle drei sind nötig:

    * die Vorstufe ist **absolut** wesentlich — sonst ist das Verhältnis ein
      Divisionsartefakt;
    * das Verhältnis liegt deutlich über dem Üblichen;
    * die NPL-Quote liegt **unter** dem Peer-Median — denn genau das macht die
      Aussage: das Problem ist in der etablierten Kennzahl noch nicht sichtbar.

    Ohne die dritte Bedingung stünden dort auch Institute, deren Schwierigkeiten
    längst in der NPL-Quote stehen. Das wäre keine Frühwarnung, sondern eine
    Spätmeldung.
    """
    if vorstufe_quote is None or verh is None:
        return "nein"
    if vorstufe_quote < min_vorstufe:
        return "nein"
    if verh < min_verhaeltnis:
        return "nein"
    return "ja" if unter_median else "nein"


def lade(con):
    """[(lei, scope, refPeriod, bank, land, perf, npe, pf, npf, wb)]"""
    from determinism import ordered_query as ordered

    def hole(template, spalten):
        aus = collections.defaultdict(dict)
        for lei, sc, rp, bank, land, col, v in ordered(con, f"""
            SELECT lei, scope, refPeriod, max(bank_name), max(country),
                   cell_col, max(fact_value_eur)
            FROM '{PARQUET}'
            WHERE template_id = '{template}' AND cell_row = '{ZEILE}'
              AND cell_col IN ({",".join(f"'{c}'" for c in spalten)})
              AND fact_value_eur IS NOT NULL
            GROUP BY lei, scope, refPeriod, cell_col
            ORDER BY lei, scope, refPeriod, cell_col
        """, template):
            d = aus[(lei, sc, rp)]
            d[col] = v
            d["bank"], d["land"] = bank or "", land or ""
        return aus

    cq3 = hole("82.00.A", ("0010", "0040"))
    cq1 = hole("80.00.A", ("0010", "0020"))
    cr1 = hole("21.01.D", ("0040",))

    aus = []
    for k in sorted(cq3):
        c3 = cq3[k]
        perf, npe = c3.get("0010"), c3.get("0040")
        if perf is None or npe is None or perf + npe <= 0:
            continue
        c1, r1 = cq1.get(k, {}), cr1.get(k, {})
        aus.append((*k, c3["bank"], c3["land"], perf, npe,
                    c1.get("0010"), c1.get("0020"), r1.get("0040")))
    return aus


def build():
    import duckdb

    if not PARQUET.exists():
        print(f"ERROR: {PARQUET} fehlt — erst scripts/build_zweig_b.py")
        return []

    itype = {}
    if META.exists():
        with META.open(encoding="utf-8") as fh:
            itype = {r["lei"]: r.get("institution_type", "")
                     for r in csv.DictReader(fh)}

    con = duckdb.connect()
    roh = lade(con)
    print(f"Reports mit CQ3 (Kreditbuch): {len(roh)}")

    # Peer-Median der NPL-Quote je (scope, refPeriod). CON und IND NICHT
    # mischen — das verlangt das Issue und DISCLAIMER.md.
    je_gruppe = collections.defaultdict(list)
    for lei, sc, rp, _b, _l, perf, npe, *_ in roh:
        q = quote(npe, perf + npe)
        if q is not None:
            je_gruppe[(sc, rp)].append(q)
    median = {k: statistics.median(v) for k, v in je_gruppe.items() if v}

    zeilen = []
    for lei, sc, rp, bank, land, perf, npe, pf, npf, wb in roh:
        kredite = perf + npe
        nplq = quote(npe, kredite)
        pfq = quote(pf, kredite)
        verh = verhaeltnis(pfq, nplq)
        unter = nplq is not None and nplq < median.get((sc, rp), float("inf"))
        zeilen.append({
            "lei": lei, "scope": sc, "refPeriod": rp, "bank_name": bank,
            "country": land, "institution_type": itype.get(lei, ""),
            "kredite_eur": f"{kredite:.2f}", "npe_eur": f"{npe:.2f}",
            "npl_quote": "" if nplq is None else f"{nplq:.6f}",
            "forborne_performing_eur": "" if pf is None else f"{pf:.2f}",
            "vorstufe_quote": "" if pfq is None else f"{pfq:.6f}",
            "forborne_non_performing_eur": "" if npf is None else f"{npf:.2f}",
            "npf_quote": (lambda q: "" if q is None else f"{q:.6f}")(
                quote(npf, kredite)),
            "vorstufe_verhaeltnis": "" if verh is None else f"{verh:.4f}",
            "wb_npe_eur": "" if wb is None else f"{wb:.2f}",
            "wb_vorzeichen": vorzeichen(wb),
            "deckungsquote": (lambda q: "" if q is None else f"{q:.6f}")(
                quote(abs(wb) if wb is not None else None, npe)),
            "npl_unter_median": "ja" if unter else "nein",
            "fruehwarnung": fruehwarnung_von(pfq, verh, unter)})

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
    if not zeilen:
        return ["Keine verknüpfbaren Reports — die Kette GREIFT nicht."]
    jung = collections.Counter(z["refPeriod"] for z in zeilen).most_common(1)[0][0]
    akt = [z for z in zeilen if z["refPeriod"] == jung]
    aus = [f"Stichtag {jung} (der besetzteste): {len(akt)} Reports"]

    for feld, name in (("npl_quote", "NPL-Quote"),
                       ("vorstufe_quote", "Vorstufe (performing forborne)"),
                       ("deckungsquote", "NPL-Deckungsquote")):
        v = sorted(float(z[feld]) for z in akt if z[feld])
        if v:
            aus.append(f"    {name:34s} Median {statistics.median(v):7.2%} · "
                       f"Q1 {v[len(v) // 4]:6.2%} · Q3 {v[3 * len(v) // 4]:6.2%} "
                       f"(n={len(v)})")

    # Der Peer-Median wird je Konsolidierungskreis gebildet, und das ist
    # keine Formsache: die beiden liegen messbar auseinander.
    je_scope = collections.defaultdict(list)
    for z in akt:
        if z["npl_quote"]:
            je_scope[z["scope"]].append(float(z["npl_quote"]))
    aus.append("  NPL-Median je Konsolidierungskreis — deshalb wird nicht "
               "gemischt: "
               + " · ".join(f"{k} {statistics.median(v):.2%} (n={len(v)})"
                            for k, v in sorted(je_scope.items())))

    vz = collections.Counter(z["wb_vorzeichen"] for z in akt if z["wb_vorzeichen"])
    aus.append("  Vorzeichen der Wertberichtigung: "
               + "  ".join(f"{k}={v}" for k, v in vz.most_common()))
    if vz.get("positiv"):
        aus.append(f"    ⚠ {vz['positiv']} Reports melden sie POSITIV. Gerechnet "
                   f"wird mit dem Betrag; ob das eine andere Konvention ist oder "
                   f"ein Vorzeichenfehler, entscheidet dieses Skript nicht.")

    ohne_wb = [z for z in akt if z["deckungsquote"]
               and float(z["deckungsquote"]) == 0
               and float(z["npe_eur"]) > 0]
    if ohne_wb:
        aus.append(f"  {len(ohne_wb)} Report(s) mit notleidenden Krediten und "
                   f"KEINER Wertberichtigung darauf: "
                   + ", ".join(f"{z['bank_name'][:26]} "
                               f"({float(z['npe_eur']) / 1e6:.1f} Mio)"
                               for z in ohne_wb[:3]))

    warn = [z for z in akt if z["fruehwarnung"] == "ja"]
    aus.append(f"→ Frühwarnmuster bei {len(warn)} von {len(akt)} Reports: "
               f"Vorstufe über {MIN_VORSTUFE:.0%} des Kreditbuchs, Verhältnis "
               f"über {MIN_VERHAELTNIS}, NPL-Quote UNTER dem Peer-Median.")
    for z in sorted(warn, key=lambda z: -float(z["vorstufe_verhaeltnis"])):
        aus.append(f"    {float(z['vorstufe_verhaeltnis']):5.2f}×  "
                   f"NPL {float(z['npl_quote']):5.2%}  "
                   f"Vorstufe {float(z['vorstufe_quote']):5.2%}  "
                   f"{z['bank_name'][:32]:34s} {z['country'][:10]:12s} {z['scope']}")
    aus.append("  Ohne den Wesentlichkeitsboden führte Agence France Locale "
               "diese Liste mit dem 377-fachen an — bei einer NPL-Quote von "
               "0,00 %. Das wäre eine Division durch fast nichts, keine "
               "Frühwarnung.")
    aus.append("Vergleichbarkeit: Rechnungslegung und nationale Optionen "
               "unterscheiden sich; CON und IND sind nicht dasselbe Institut "
               "und werden nirgends gemischt.")
    return aus


if __name__ == "__main__":
    build()
