"""IRB-Risikogewichte je PD-Band (#45, Punkt 3).

Ausgabe: processed/irb_risk_weights.csv

## Was die EBA-Übung strukturell nicht liefert

Die EBA-Benchmarking-Übung misst die Streuung der Risikogewichte zwischen
Banken — aber sie deckt nur IRB-Institute ab und veröffentlicht **nicht auf
Institutsebene**. CR6 (`26.00.A`) trägt genau diese Zahlen offen: je Institut,
Forderungsklasse und PD-Band das Exposure, die ausfallgewichtete PD, die LGD und
den Risikogewichtsbetrag. 91 Institute melden es.

Der Beitrag ist damit nicht das bessere Modell, sondern die **nachvollziehbare
Einzelzeile**: bei gleicher Ausfallwahrscheinlichkeit und gleicher
Forderungsklasse unterscheiden sich die Risikogewichte zwischen Instituten um
einen Faktor, den bislang niemand institutsgenau nachlesen kann.

## Drei Fallen, und jede einzelne zerstört die Auswertung

### 1. Die PD-Spalte heisst „(%)" und ist meistens keine

`c0050` trägt das Label *„Exposure weighted average PD (%)"*. Gemessen liegen
15.638 der 15.997 Werte bei <= 1 — also als Bruch gemeldet, nicht in Prozent.

Geraten werden muss das nicht: **die Zeilenbeschriftung nennt das Band**
(`0.25 to <0.50`, in Prozent), und damit lässt sich für jeden Wert prüfen,
welche Lesart hineinpasst. Über 11.177 Werte in benannten Bändern:

    nur als Bruch passend      9.179   82,1 %
    beide Lesarten passend     1.338   12,0 %
    nur als Prozent passend      362    3,2 %
    keine Lesart passend         298    2,7 %

Die Einheit ist eine Eigenschaft des REPORTS, nicht der Zelle. Sie wird deshalb
je Report aus den eindeutigen Zellen bestimmt und dann auf alle angewandt —
auch auf die mehrdeutigen. 124 der 143 Reports melden eindeutig als Bruch,
4 eindeutig in Prozent.

### 2. Die Bänder überlappen sich

`r0010` (0.00–0.15) ENTHÄLT `r0020` (0.00–0.10) und `r0030` (0.10–0.15). Ebenso
`r0070 = r0080 + r0090`, `r0100 = r0110 + r0120`, `r0130 = r0140 + r0150 +
r0160`. Wer alle 18 Zeilen summiert, zählt das Exposure doppelt.

Nachgemessen ist die Hierarchie exakt — Medianabweichung 0,00000, und
`r0180` (Subtotal) = `r0010 + r0040 + r0050 + r0060 + r0070 + r0100 + r0130 +
r0170` bei 652 von 657 Kombinationen auf 1 % genau. Die Spalte `ebene` trennt
deshalb `grob` (8 Bänder, summieren zum Subtotal) von `fein` (13 Bänder) und
`summe`. **Nie über Ebenen hinweg aggregieren.**

### 3. Die Forderungsklasse ist nicht auflösbar

CR6 führt sie als offene Achse (`qEEA=eba_qAE:qx2012`), und für `26.00` liegt
im Codebook keine Achsenauflösung. Der Code bleibt deshalb roh in der Spalte
`klasse_code` stehen. Für den Vergleich reicht das — er läuft INNERHALB einer
Klasse, und die Codes sind institutsübergreifend dieselben —, aber ohne
Klartextnamen ist die Zeile nicht fachlich einzuordnen. Das ist eine Lücke im
Codebook (#3), keine dieser Auswertung.

## Eine Gegenprobe, die der Datensatz sich selbst gibt

`c0100` („Density of risk weighted exposure amounts") ist unabhängig gemeldet
und muss `c0090 / c0040` entsprechen. Über 12.671 Paare: **Medianabweichung
0,0000**, und zwar als BRUCH — die Dichtespalte ist trotz ihres Namens keine
Prozentangabe. Gerechnet wird trotzdem aus Zähler und Nenner; die gemeldete
Dichte steht als Kontrollspalte daneben.

Aufruf: python3 scripts/build_irb_risk_weights.py
"""

from pathlib import Path
import collections
import csv
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
OUT = ROOT / "processed" / "irb_risk_weights.csv"

TEMPLATE = "26.00.A"

# PD-Bänder aus den Zeilenbeschriftungen, in PROZENT. Sie sind der Massstab, an
# dem die Meldeeinheit gemessen wird — deshalb stehen sie hier als Daten und
# nicht als Kommentar.
BAND = {
    "0010": (0.00, 0.15, "grob"), "0020": (0.00, 0.10, "fein"),
    "0030": (0.10, 0.15, "fein"), "0040": (0.15, 0.25, "beide"),
    "0050": (0.25, 0.50, "beide"), "0060": (0.50, 0.75, "beide"),
    "0070": (0.75, 2.50, "grob"), "0080": (0.75, 1.75, "fein"),
    "0090": (1.75, 2.50, "fein"), "0100": (2.50, 10.0, "grob"),
    "0110": (2.50, 5.00, "fein"), "0120": (5.00, 10.0, "fein"),
    "0130": (10.0, 100.0, "grob"), "0140": (10.0, 20.0, "fein"),
    "0150": (20.0, 30.0, "fein"), "0160": (30.0, 100.0, "fein"),
    "0170": (100.0, 100.0, "beide"),
}
SUMME = "0180"

# Korridor für das Defaultband. Gemeldet wird dort 100 % — mal exakt, mal als
# 99,99 oder 100,0000001. Der Korridor fängt die Rundung, ohne die Schranke
# aufzugeben, dass eine Wahrscheinlichkeit nicht über 100 % liegen kann.
DEFAULT_TOLERANZ = (99.0, 101.0)

SPALTEN = {"expo": "0040", "pd": "0050", "lgd": "0070",
           "rwea": "0090", "dichte": "0100"}

# Ab welchem Übergewicht gilt eine Lesart als die des Reports. Nordea meldet 82
# eindeutige Bruch-Zellen gegen 2 Prozent-Zellen — das ist kein Einheitenwechsel
# mitten im Report, das sind zwei auffällige Zellen. Eine Regel ohne Übergewicht
# erklärte 14 Reports für widersprüchlich und verlöre sie.
EINHEIT_UEBERGEWICHT = 4

# Wesentlichkeitsschwelle für die STREUUNGSSTATISTIK — nicht für die Datei.
#
# CR6 ist ein volles Gitter, und viele Zellen tragen Kleinstbeträge. Bei einem
# Exposure von 87.671 EUR und einem RWEA von 699 EUR ist das Risikogewicht
# 0,008 — intern konsistent, die gemeldete Dichte bestätigt es, und trotzdem
# sagt die Zahl nichts über Modellierung, sondern über Rundung auf ganze Euro.
# Eine erste Fassung dieser Auswertung meldete deshalb einen Streuungsfaktor
# von 278 für ein Band, in dem die grossen Melder zwischen 0,66 und 2,23 liegen.
#
# Gemessen: Zellen unter 10 Mio EUR sind 1.713 von 8.839 (19 %) und tragen
# 0,017 % des gesamten Exposures. Sie fliegen aus der Statistik und bleiben in
# der Datei — markiert, nicht versteckt.
MIN_EXPOSURE = 1e7

FELDER = ["lei", "scope", "refPeriod", "bank_name", "country", "institution_type",
          "klasse_code", "cell_row", "pd_band_von", "pd_band_bis", "ebene",
          "pd_einheit", "pd_pct", "pd_im_band", "lgd_pct", "exposure_eur",
          "rwea_eur", "risikogewicht", "wesentlich", "dichte_gemeldet",
          "dichte_stimmt"]


def lade(con):
    """Eine Zeile je (Report, Forderungsklasse, PD-Band) mit allen Spalten."""
    from determinism import ordered_query as ordered

    spalten = ",".join(f"'{c}'" for c in SPALTEN.values())
    return ordered(con, f"""
        SELECT lei, scope, CAST(refPeriod AS VARCHAR) AS refPeriod,
               max(bank_name) AS bank_name, max(country) AS country,
               max(institution_type) AS institution_type,
               coalesce(open_axis_dims, '') AS klasse_code, cell_row,
               max(CASE WHEN cell_col='{SPALTEN["expo"]}'   THEN fact_value_eur END) AS expo,
               max(CASE WHEN cell_col='{SPALTEN["pd"]}'     THEN fact_value END)     AS pd,
               max(CASE WHEN cell_col='{SPALTEN["lgd"]}'    THEN fact_value END)     AS lgd,
               max(CASE WHEN cell_col='{SPALTEN["rwea"]}'   THEN fact_value_eur END) AS rwea,
               max(CASE WHEN cell_col='{SPALTEN["dichte"]}' THEN fact_value END)     AS dichte
        FROM '{PARQUET}'
        WHERE template_id = '{TEMPLATE}' AND cell_col IN ({spalten})
        GROUP BY lei, scope, refPeriod, klasse_code, cell_row
        ORDER BY lei, scope, refPeriod, klasse_code, cell_row
    """, "CR6-Zellen")


def lesart(wert, cell_row):
    """Passt dieser PD-Wert als Bruch, als Prozent, als beides oder als keins?

    Der Massstab ist das Band aus der eigenen Zeilenbeschriftung. Das ist der
    entscheidende Punkt dieser Auswertung: die Einheit muss nicht geraten
    werden, der Meldebogen nennt sie implizit selbst.
    """
    b = BAND.get(cell_row)
    if b is None or wert is None or wert <= 0:
        return None
    lo, hi = b[0], b[1]
    # Das Defaultband (100 %) ist ein Punkt, kein Intervall — und es ist nach
    # OBEN geschlossen, weil eine Wahrscheinlichkeit 100 % nicht überschreiten
    # kann. Ohne diese Schranke passte 100,0 auch als Bruch (= 10.000 %), und
    # jede Defaultzeile wäre „mehrdeutig" statt entschieden.
    drin = ((lambda v: DEFAULT_TOLERANZ[0] <= v <= DEFAULT_TOLERANZ[1])
            if lo == hi else (lambda v: lo <= v < hi))
    p, f = drin(wert), drin(wert * 100)
    if f and not p:
        return "bruch"
    if p and not f:
        return "prozent"
    return "beides" if p else "keins"


def einheit_je_report(zeilen):
    """{(lei, scope, refPeriod): 'bruch'|'prozent'|'unklar'}.

    Die Einheit gehört dem Report, nicht der Zelle. Eine Minderheit
    abweichender Zellen ist ein Befund ÜBER diese Zellen — kein Beleg, dass der
    Report mitten im Meldebogen die Einheit wechselt.
    """
    stimmen = collections.defaultdict(collections.Counter)
    for z in zeilen:
        art = lesart(z["pd"], z["cell_row"])
        if art in ("bruch", "prozent"):
            stimmen[(z["lei"], z["scope"], z["refPeriod"])][art] += 1
    aus = {}
    for k, c in stimmen.items():
        b, p = c["bruch"], c["prozent"]
        if b >= max(1, p * EINHEIT_UEBERGEWICHT):
            aus[k] = "bruch"
        elif p >= max(1, b * EINHEIT_UEBERGEWICHT):
            aus[k] = "prozent"
        else:
            aus[k] = "unklar"
    return aus


def pd_in_prozent(wert, einheit):
    """Auf Prozent normieren — oder None, wenn die Einheit unklar ist.

    Bei `unklar` wird NICHT geraten. Ein normierter Wert aus einer unbekannten
    Einheit sieht aus wie ein gemessener und ist keiner.
    """
    if wert is None or einheit == "unklar":
        return None
    return wert * 100 if einheit == "bruch" else wert


def build():
    import duckdb

    con = duckdb.connect()
    roh = lade(con)
    zeilen = [dict(zip(("lei", "scope", "refPeriod", "bank_name", "country",
                        "institution_type", "klasse_code", "cell_row",
                        "expo", "pd", "lgd", "rwea", "dichte"), r)) for r in roh]

    einheiten = einheit_je_report(zeilen)

    aus = []
    for z in zeilen:
        b = BAND.get(z["cell_row"])
        ebene = "summe" if z["cell_row"] == SUMME else (b[2] if b else "")
        if not ebene:
            continue                       # Zeile ausserhalb des Bänderschemas
        k = (z["lei"], z["scope"], z["refPeriod"])
        einheit = einheiten.get(k, "unklar")
        pd_pct = pd_in_prozent(z["pd"], einheit)
        # Die LGD trägt dieselbe Einheitenfrage, hat aber KEIN Band, an dem sie
        # sich messen liesse. Sie erbt deshalb die am PD gemessene Einheit des
        # Reports — eine Annahme, und sie steht als solche in der Spalte
        # `pd_einheit` daneben.
        lgd_pct = pd_in_prozent(z["lgd"], einheit)
        expo, rwea = z["expo"], z["rwea"]
        rw = rwea / expo if (expo and rwea is not None and expo > 0) else None
        stimmt = ""
        if rw is not None and z["dichte"] is not None:
            stimmt = "ja" if abs(rw - z["dichte"]) <= 0.01 else "nein"
        aus.append({
            "lei": z["lei"], "scope": z["scope"], "refPeriod": z["refPeriod"],
            "bank_name": z["bank_name"] or "", "country": z["country"] or "",
            "institution_type": z["institution_type"] or "",
            "klasse_code": z["klasse_code"], "cell_row": z["cell_row"],
            "pd_band_von": b[0] if b else "", "pd_band_bis": b[1] if b else "",
            "ebene": ebene, "pd_einheit": einheit,
            "pd_pct": round(pd_pct, 6) if pd_pct is not None else "",
            # Leere Zellen tragen keine Aussage. CR6 ist ein VOLLES Gitter aus
            # Forderungsklasse x PD-Band, und die meisten Institute besetzen nur
            # einen Teil davon: 2.736 Zellen führen PD = 0 UND Exposure = 0.
            # Eine erste Fassung wertete jede davon als „PD unterhalb ihres
            # Bandes" und meldete 3.016 Verstösse statt 230 — die Prüfung mass
            # die Belegung des Gitters, nicht die Meldung.
            "pd_im_band": ("" if pd_pct is None or not b or not pd_pct
                           or not expo else
                           ("ja" if (pd_pct >= b[0] if b[0] == b[1]
                                     else b[0] <= pd_pct < b[1]) else "nein")),
            "lgd_pct": round(lgd_pct, 4) if lgd_pct is not None else "",
            "exposure_eur": round(expo, 2) if expo is not None else "",
            "rwea_eur": round(rwea, 2) if rwea is not None else "",
            "risikogewicht": round(rw, 6) if rw is not None else "",
            "wesentlich": "ja" if (expo or 0) >= MIN_EXPOSURE else "nein",
            "dichte_gemeldet": z["dichte"] if z["dichte"] is not None else "",
            "dichte_stimmt": stimmt,
        })

    aus.sort(key=lambda z: (z["lei"], z["scope"], z["refPeriod"],
                            z["klasse_code"], z["cell_row"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(aus)

    print(f"✓ {OUT}  ({len(aus)} Zeilen)")
    for s in bericht(aus, einheiten):
        print("  " + s)
    return aus


def bericht(aus, einheiten):
    import statistics as st

    z = ["Reports: %d · Institute: %d" % (
        len(einheiten), len({k[0] for k in einheiten}))]
    z.append("PD-Einheit je Report: " + "  ".join(
        f"{k}={v}" for k, v in sorted(collections.Counter(einheiten.values()).items())))
    z.append("Ebenen: " + "  ".join(
        f"{k}={v}" for k, v in sorted(collections.Counter(x["ebene"] for x in aus).items())))

    d = collections.Counter(x["dichte_stimmt"] for x in aus if x["dichte_stimmt"])
    z.append(f"Gegenprobe gemeldete Dichte gegen RWEA/Exposure: "
             f"ja={d['ja']} nein={d['nein']}")

    ausserhalb = [x for x in aus if x["pd_im_band"] == "nein"]
    z.append(f"PD ausserhalb des eigenen Bandes: {len(ausserhalb)} von "
             f"{sum(1 for x in aus if x['pd_im_band'])}")

    # Der eigentliche Befund: Streuung des Risikogewichts INNERHALB eines Bandes
    # und einer Forderungsklasse. Nur auf der feinen Ebene, damit nichts
    # doppelt zaehlt.
    je = collections.defaultdict(list)
    for x in aus:
        # `exposure_eur` ist eine gerundete Zahl, keine Zeichenkette: ein Test
        # gegen ("", 0) lässt "0.0" durch und zog damit unbesetzte Zellen in die
        # Streuung. Sichtbar wurde es an einem Risikogewicht von 0,008 bei 20 %
        # Ausfallwahrscheinlichkeit — eine Zahl, die es nicht geben kann.
        if x["ebene"] not in ("fein", "beide") or x["risikogewicht"] == "":
            continue
        if x["wesentlich"] != "ja":
            continue
        je[(x["klasse_code"], x["cell_row"])].append(float(x["risikogewicht"]))
    gross = [(k, sorted(v)) for k, v in je.items() if len(v) >= 20]
    z.append(f"Band x Forderungsklasse mit >= 20 Instituten: {len(gross)}")
    if gross:
        spannen = []
        for k, v in gross:
            p10, p90 = v[int(0.1 * (len(v) - 1))], v[int(0.9 * (len(v) - 1))]
            if p10 > 0:
                spannen.append((p90 / p10, k, len(v), p10, st.median(v), p90))
        spannen.sort(reverse=True)
        z.append("groesste Streuung (p90/p10 des Risikogewichts):")
        for f, k, n, lo, med, hi in spannen[:6]:
            band = BAND.get(k[1], (0, 0, ""))
            z.append(f"  PD {band[0]:>5}–{band[1]:<5} {k[0][-8:]:>8s}  n={n:3d}  "
                     f"p10 {lo:.3f} · median {med:.3f} · p90 {hi:.3f}  → Faktor {f:.1f}")
    return z


if __name__ == "__main__":
    build()
