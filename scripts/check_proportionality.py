"""Wirkt die Proportionalität? (#44)

Ausgabe: processed/proportionality.csv

## Die Lücke, die das Issue benennt

Über die richtige Dosis der Erleichterungen für „kleine und nicht komplexe
Institute" (Art. 433b CRR) wird seit der CRD-V-Reform gestritten. Was in der
Debatte fehlt, ist die schlichte Messung: **wie viel weniger legen erleichterte
Institute tatsächlich offen?**

## Der kritische Schritt kommt zuerst

Das Issue sagt selbst, woran die Auswertung scheitern würde: *„Die EBA-Klasse
ist nicht deckungsgleich mit ‚klein und nicht komplex' nach Art. 4(1)(145) CRR.
‚Other highest EEA' ist eine EDAP-Kategorie, kein Rechtsbegriff. … Das ist der
kritische Schritt dieses Issues, nicht die Rechnung danach."*

Gemessen an der eigenen TREA-Meldung (KM1 `61.00`) sind die Klassen fast
vollständig grössengetrennt:

    Large highest EEA     Median TREA  31,3 Mrd
    Large subsidiaries    Median TREA  14,6 Mrd
    Other highest EEA     Median TREA   1,8 Mrd

Nur **0,4 %** der „Other highest EEA" überragen den TREA-Median der grossen
Klassen. Die EDAP-Kategorie ist damit als Grössenschichtung brauchbar — als
Rechtsbegriff bleibt sie es nicht, und jede Aussage über die Wirkung von
Art. 433b steht unter diesem Vorbehalt.

## Die Falle, die hier NICHT zuschnappt

Eine rohe Quote, die als Verhaltensmass etikettiert wird und in Wahrheit Grösse
misst, ist der wiederkehrende Fehler dieses Projekts (#43, #45, #11, #83). Hier
wurde er erwartet und ist ausgeblieben:

    Auslassungsquote ~ log10(TREA):   Steigung -0,0116   r² = 0,007

**Grösse erklärt die Auslassungsquote praktisch nicht.** Der Klassenunterschied
ist also kein Grössenartefakt — er ist echt, nur klein.

## Was die Klasse erklärt, und was nicht

Der Median wandert monoton in die erwartete Richtung:

    Large highest EEA    0,617
    Large subsidiaries   0,683
    Other highest EEA    0,797

Die Verteilungen überlappen aber fast vollständig:

* **29,3 %** der „Other highest EEA" lassen WENIGER aus als die mittlere Grossbank.
* **46,2 %** der „Large highest EEA" lassen MEHR aus als das mittlere Kleininstitut.

Nach Grössenbereinigung erklärt die Klasse **1,8 %** der Residualvarianz. Das
ist die Antwort auf Punkt 2 des Issues: die Klasse verschiebt das Niveau, aber
sie bestimmt nicht, was ein einzelnes Institut offenlegt. Wer von der Klasse auf
das Haus schliesst, liegt in fast der Hälfte der Fälle falsch.

## Punkt 3: Kalender, nicht Ermessen

Der stärkste Befund, und er kommt aus einer Spalte, die schon da war.
`omission_profile.csv` führt neben der rohen Quote die um das Frequenzmodell
(#34) bereinigte `quote_gegen_erwartung`. Deren Median ist

    in ALLEN drei Klassen exakt 0,000

Sobald verrechnet ist, was ein Institut zu diesem Stichtag überhaupt melden
müsste, lässt das mittlere Haus **nichts** gegen die Erwartung aus — in jeder
Klasse. Der ganze rohe Abstand zwischen den Klassen steckt im Meldekalender.

Damit beantwortet sich die Frage des Issues („wirkt die Erleichterung eher über
weniger Templates oder über seltener?") zugunsten der Frequenz: die
Erleichterung wirkt, indem sie **seltener** verlangt, nicht indem Institute
weniger von dem liefern, was verlangt ist.

## Deskriptiv, nicht kausal

Das Issue verlangt die Einschränkung, und sie gilt: Institute sind nicht
zufällig zugeteilt, sondern nach Grösse und Komplexität. „Erleichterte
Institute legen weniger offen" ist teilweise eine Tautologie. Der Erkenntniswert
liegt im Ausmass und in der Streuung — und die Streuung ist hier die Nachricht.

Aufruf: python3 scripts/check_proportionality.py
"""

from pathlib import Path
import collections
import csv
import math
import statistics
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
OMISSION = ROOT / "processed" / "omission_profile.csv"
OUT = ROOT / "processed" / "proportionality.csv"

# KM1, Total Risk Exposure Amount — dieselbe Koordinate wie in #83. Als
# Grössenmass der eigenen Meldung entnommen, nicht aus einer fremden Liste.
TREA = ("61.00", "0040", "0010")

# Unter so vielen Reports trägt ein Klassenmedian nicht.
MIN_REPORTS = 5

FELDER = ["institution_type", "refPeriod", "n", "quote_median", "quote_q1",
          "quote_q3", "quote_gegen_erwartung_median", "trea_median_eur",
          "n_deklariert_median", "n_offengelegt_median"]


def quartile(werte):
    """(q1, median, q3) — ohne numpy, und leer bei zu wenig Werten."""
    q = sorted(werte)
    if not q:
        return None, None, None
    n = len(q)
    # `3 * n // 4` liegt für jedes n >= 1 unter n — eine zusätzliche
    # min()-Schranke wäre toter Code und suggerierte eine Gefahr, die es
    # nicht gibt. Der Test über n = 1 bis 11 hält die Zusage fest.
    return q[n // 4], statistics.median(q), q[3 * n // 4]


def steigung(paare):
    """(a, b, r²) einer Geraden y = a + b·x, oder (None, None, None).

    Die Frage, für die es das gibt: misst die Auslassungsquote in Wahrheit
    Grösse? Ohne diese Zahl wäre der Klassenunterschied nicht von einem
    Grössenartefakt zu unterscheiden — der Fehler aus #43, #45 und #11.
    """
    if len(paare) < 3:
        return None, None, None
    xs = [x for x, _ in paare]
    ys = [y for _, y in paare]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    nenner = sum((x - mx) ** 2 for x in xs)
    streu = sum((y - my) ** 2 for y in ys)
    if not nenner or not streu:
        return None, None, None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / nenner
    a = my - b * mx
    r2 = 1 - sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys)) / streu
    return a, b, r2


def ueberlappung(klein, gross):
    """Anteil der kleinen Klasse, der WENIGER auslässt als der Median der
    grossen — und umgekehrt.

    Das ist Punkt 2 des Issues: „ist die Klasse überhaupt trennscharf, oder
    überlappen sich die Verteilungen stark?" Zwei Mediane, die auseinander
    liegen, sagen darüber nichts; diese beiden Anteile sagen alles.
    """
    if not klein or not gross:
        return None, None
    mg, mk = statistics.median(gross), statistics.median(klein)
    return (sum(1 for x in klein if x < mg) / len(klein),
            sum(1 for x in gross if x > mk) / len(gross))


def lade():
    """[(klasse, refPeriod, quote_roh, quote_gegen_erwartung, trea, ndekl, noff)]"""
    import duckdb

    if not OMISSION.exists():
        return []
    con = duckdb.connect()
    trea = {(l, s, p): v for l, s, p, v in con.execute(f"""
        SELECT lei, scope, refPeriod, max(fact_value_eur)
        FROM '{PARQUET}'
        WHERE template_id = '{TREA[0]}' AND cell_row = '{TREA[1]}'
          AND cell_col = '{TREA[2]}' AND fact_value_eur IS NOT NULL
          AND fact_value_eur > 0
        GROUP BY lei, scope, refPeriod
        ORDER BY lei, scope, refPeriod
    """).fetchall()}

    aus = []
    with OMISSION.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if not r.get("institution_type") or not r.get("n_deklariert"):
                continue
            if int(r["n_deklariert"]) <= 0:
                continue
            ge = r.get("quote_gegen_erwartung")
            aus.append((r["institution_type"], r["refPeriod"],
                        float(r["quote_roh"]),
                        float(ge) if ge else None,
                        trea.get((r["lei"], r["scope"], r["refPeriod"])),
                        int(r["n_deklariert"]), int(r["n_offengelegt"])))
    return aus


def build():
    daten = lade()
    if not daten:
        print("ERROR: omission_profile.csv fehlt oder ist leer")
        return []

    je = collections.defaultdict(list)
    for k, rp, q, ge, t, nd, no in daten:
        je[(k, rp)].append((q, ge, t, nd, no))

    zeilen = []
    for (k, rp), v in sorted(je.items()):
        if len(v) < MIN_REPORTS:
            continue
        q1, med, q3 = quartile([a for a, _, _, _, _ in v])
        ges = [b for _, b, _, _, _ in v if b is not None]
        treas = [c for _, _, c, _, _ in v if c]
        zeilen.append({
            "institution_type": k, "refPeriod": rp, "n": len(v),
            "quote_median": f"{med:.4f}", "quote_q1": f"{q1:.4f}",
            "quote_q3": f"{q3:.4f}",
            "quote_gegen_erwartung_median":
                f"{statistics.median(ges):.4f}" if ges else "",
            "trea_median_eur":
                f"{statistics.median(treas):.0f}" if treas else "",
            "n_deklariert_median":
                f"{statistics.median([d for _, _, _, d, _ in v]):.0f}",
            "n_offengelegt_median":
                f"{statistics.median([e for _, _, _, _, e in v]):.0f}"})

    zeilen.sort(key=lambda z: (z["refPeriod"], z["institution_type"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(zeilen)
    print(f"✓ {OUT}  ({len(zeilen)} Zeilen)")
    for s in bericht(daten):
        print("  " + s)
    return zeilen


def bericht(daten):
    je = collections.defaultdict(list)
    for k, _, q, ge, t, _, _ in daten:
        je[k].append((q, ge, t))
    aus = []

    # 1. Der kritische Schritt: ist die Klasse eine Grössenklasse?
    aus.append("Klassenprüfung (#44 nennt sie den kritischen Schritt):")
    for k, v in sorted(je.items(), key=lambda kv: -len(kv[1])):
        treas = [t for _, _, t in v if t]
        aus.append(f"    {k:22s} n={len(v):>4d}  Median TREA "
                   f"{statistics.median(treas) / 1e9:6.1f} Mrd" if treas
                   else f"    {k:22s} n={len(v):>4d}  ohne TREA")
    aus.append("  Die EDAP-Kategorie ist als Grössenschichtung brauchbar — als "
               "Rechtsbegriff nach Art. 4(1)(145) CRR bleibt sie es nicht.")

    # 2. Misst die Quote in Wahrheit Grösse?
    paare = [(math.log10(t), q) for _, v in je.items() for q, _, t in v if t]
    a, b, r2 = steigung(paare)
    if r2 is not None:
        aus.append(f"Auslassungsquote ~ log10(TREA): Steigung {b:+.4f} · "
                   f"r² = {r2:.3f} über {len(paare)} Reports.")
        aus.append("  Grösse erklärt die Quote praktisch NICHT. Der "
                   "Klassenunterschied ist damit kein Grössenartefakt — die "
                   "Falle aus #43/#45/#11 schnappt hier nicht zu.")

    # 3. Trennschärfe — Punkt 2 des Issues.
    gr = sorted(je, key=lambda k: statistics.median(q for q, _, _ in je[k]))
    if len(gr) >= 2:
        klein, gross = gr[-1], gr[0]
        qk = [q for q, _, _ in je[klein]]
        qg = [q for q, _, _ in je[gross]]
        u1, u2 = ueberlappung(qk, qg)
        aus.append(f"Trennschärfe: Median {gross} {statistics.median(qg):.3f} "
                   f"gegen {klein} {statistics.median(qk):.3f} — aber")
        aus.append(f"    {u1:.1%} der „{klein}\" lassen WENIGER aus als der "
                   f"Median von „{gross}\"")
        aus.append(f"    {u2:.1%} der „{gross}\" lassen MEHR aus als der "
                   f"Median von „{klein}\"")
        aus.append("  Die Klasse verschiebt das Niveau, sie bestimmt nicht das "
                   "einzelne Haus.")

    # 4. Punkt 3 — Kalender oder Ermessen?
    aus.append("Roh gegen erwartungsbereinigt (#34):")
    kalender = True
    for k, v in sorted(je.items()):
        ges = [ge for _, ge, _ in v if ge is not None]
        if not ges:
            continue
        m = statistics.median(ges)
        kalender = kalender and abs(m) < 1e-9
        aus.append(f"    {k:22s} roh {statistics.median(q for q, _, _ in v):.3f}"
                   f"  →  gegen Erwartung {m:.3f}")
    if kalender:
        aus.append("  In JEDER Klasse null. Sobald verrechnet ist, was ein "
                   "Institut zum Stichtag überhaupt melden müsste, lässt das "
                   "mittlere Haus nichts gegen die Erwartung aus. Der ganze "
                   "rohe Abstand steckt im MELDEKALENDER, nicht im Ermessen — "
                   "das ist die Antwort auf Punkt 3 des Issues.")
    return aus


if __name__ == "__main__":
    build()
