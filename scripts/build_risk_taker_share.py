"""Wie breit ziehen Institute den Kreis der Risikoträger? (#40)

Ausgabe: processed/risk_taker_share.csv

## Die Kennzahl, die erst durch die Kombination entsteht

REM1 (`30.01` r0010) liefert die Zahl der „identified staff" nach CRD Art. 92 —
also die Mitarbeiter, deren Tätigkeit sich wesentlich auf das Risikoprofil
auswirkt. Wikidata liefert über die LEI die Gesamtbelegschaft (`P1128`). Der
Quotient sagt, **wie breit ein Institut den Kreis zieht**, und das ist ein
Ermessensspielraum, über den es bisher keine vergleichenden Zahlen gibt.

## Roh gerechnet misst die Kennzahl die Grösse

Gemessen über 83 Institute reicht der rohe Anteil von 0,30 % bis 54,67 % —
Faktor 180. Das sieht nach einem gewaltigen Ermessensunterschied aus und ist
zum grössten Teil keiner:

    log10(Belegschaft) gegen log10(Anteil):   r = −0,865   r² = 0,749

    Belegschaft        n    Median-Anteil
    < 500             23        13,83 %
    500–5.000         33         5,60 %
    5.000–50.000      21         1,37 %
    > 50.000           6         0,98 %

**Drei Viertel der Streuung erklärt die Belegschaftsgrösse allein.** Und das ist
kein Artefakt, sondern Sachlogik: eine Grossbank mit 194.000 Beschäftigten hat
Zehntausende im Filialvertrieb, deren Tätigkeit das Risikoprofil nicht wesentlich
beeinflusst. Ein Spezialfinanzierer mit 101 Mitarbeitern hat sie nicht.

Wer die Rohquote als Governance-Aussage veröffentlicht, veröffentlicht eine
Grössenmessung mit einem Governance-Etikett — derselbe Fehler wie die Rohquote
in #43, die RWA-Dichte in #45 und die Ländermittel in #11.

## Gemessen wird deshalb der REST

Erwartet wird der Anteil, den die Belegschaftsgrösse vorhersagt (Regression von
log10(Anteil) auf log10(Belegschaft) über alle auswertbaren Institute). Die
Abweichung davon ist das, was #40 eigentlich sucht:

    `faktor_gegen_erwartung` = tatsächlicher Anteil / erwarteter Anteil

Ein Wert von 2,0 heisst: dieses Institut führt doppelt so viele Risikoträger wie
Häuser seiner Grösse. Das ist eine Aussage über die Auslegung, nicht über die
Grösse.

## Drei Vorbehalte, und alle drei sind gemessen

**1. Die Stichprobe ist gross-lastig.** Nur 24 % der Institute tragen in
Wikidata eine Mitarbeiterzahl, und sie sind nach TREA im Median **2,4-mal
grösser** als die übrigen. Die Verteilung hier ist nicht die des Bestands.

**2. Wikidata ist crowdsourced.** Mitarbeiterzahlen sind unterschiedlich aktuell
und verschieden abgegrenzt (Kopfzahl gegen Vollzeitäquivalente). Der Stichtag
steht in `mitarbeiter_stand`, wo Wikidata ihn führt — und nur dort, wo er steht,
ist der Quotient datiert nachprüfbar.

**3. Beide Seiten der Division brauchen einen Filter.** REM1 ist genau das
Template, in dem #17 die stärksten Ausreisser findet. Reports mit einem
`rem_per_head`-Befund fliegen raus; ihre Kopfzahl ist die eine Hälfte des
Quotienten, den die Plausibilitätsprüfung bereits beanstandet hat.

Aufruf: python3 scripts/build_risk_taker_share.py
"""

from datetime import date
from pathlib import Path
import collections
import csv
import math
import statistics as st
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
WIKIDATA = ROOT / "codebook" / "wikidata_entities.csv"
FINDINGS = ROOT / "interim" / "plausibility_findings.csv"
OUT = ROOT / "processed" / "risk_taker_share.csv"

REM1 = "30.01"
KOPFZAHL_ROW = "0010"        # "Number of identified staff"

# Unter so vielen Instituten trägt die Regression nicht — und ein „erwarteter
# Anteil" aus zehn Punkten wäre eine Zahl mit Nachkommastellen und ohne Inhalt.
MIN_FUER_REGRESSION = 20

FELDER = ["lei", "scope", "refPeriod", "bank_name", "country", "institution_type",
          "identified_staff", "mitarbeiter", "mitarbeiter_stand", "wikidata_id",
          "anteil", "erwarteter_anteil", "faktor_gegen_erwartung", "vorbehalt"]


def lade_wikidata(pfad=None):
    """{lei: (mitarbeiter, stand, wikidata_id)} — nur Einträge MIT Zahl.

    Ohne Mitarbeiterzahl gibt es keinen Quotienten. Ein Eintrag ohne sie ist
    für diese Auswertung dasselbe wie kein Eintrag.
    """
    pfad = Path(pfad or WIKIDATA)
    if not pfad.exists():
        return {}
    aus = {}
    with pfad.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            try:
                n = int(r["mitarbeiter"])
            except (ValueError, KeyError, TypeError):
                continue
            if n > 0:
                aus[r["lei"]] = (n, r.get("mitarbeiter_stand", ""),
                                 r.get("wikidata_id", ""))
    return aus


def lade_rem_befunde(pfad=None):
    """{(lei, scope, refPeriod)} mit einem `rem_per_head`-Befund aus #17.

    Die Kopfzahl aus REM1 ist die eine Hälfte des Quotienten, den die
    Plausibilitätsprüfung dort bereits beanstandet. Sie hier noch einmal zu
    verwenden hiesse, einen bekannten Ausreisser als Governance-Aussage zu
    verkaufen.
    """
    pfad = Path(pfad or FINDINGS)
    if not pfad.exists():
        return set()
    with pfad.open(encoding="utf-8") as fh:
        return {(r["lei"], r["scope"], r["refPeriod"]) for r in csv.DictReader(fh)
                if r.get("rule") == "rem_per_head"}


def regression(punkte):
    """Kleinste Quadrate auf (log10 x, log10 y) -> (steigung, achsenabschnitt).

    Bewusst die einfachste Form: EIN Regressor, und der ist die Grösse. Ein
    reicheres Modell würde mehr erklären und wäre hier falsch — gesucht ist
    nicht die beste Vorhersage, sondern der Teil, den die Grösse NICHT erklärt.

    None bei zu wenigen Punkten oder wenn x keine Streuung hat; im zweiten Fall
    ist die Steigung nicht bestimmbar, und ein Achsenabschnitt allein wäre eine
    Konstante mit dem Anschein eines Modells.
    """
    if len(punkte) < MIN_FUER_REGRESSION:
        return None
    xs = [math.log10(x) for x, _ in punkte]
    ys = [math.log10(y) for _, y in punkte]
    mx, my = st.mean(xs), st.mean(ys)
    nenner = sum((x - mx) ** 2 for x in xs)
    if nenner < 1e-12:
        return None
    steigung = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / nenner
    return steigung, my - steigung * mx


def erwarteter_anteil(modell, mitarbeiter):
    """Was die Belegschaftsgrösse allein vorhersagt."""
    if modell is None or mitarbeiter <= 0:
        return None
    steigung, abschnitt = modell
    return 10 ** (steigung * math.log10(mitarbeiter) + abschnitt)


def vorbehalt_von(staff, mitarbeiter, hat_rem_befund):
    """Warum dieser Quotient nichts trägt — oder "" wenn er trägt.

    Eigene Funktion, weil beide Fälle im aktuellen Bestand NICHT vorkommen:
    `staff_ueber_belegschaft` trifft heute null Zeilen. Ein Test, der über die
    Ausgabe läuft, liefe über nichts und meldete Erfolg — genau der Ausfall,
    der sich als Erfolg meldet. Über die Funktion ist die Regel prüfbar, auch
    wenn der Bestand sie gerade nicht auslöst.
    """
    if hat_rem_befund:
        return "rem_befund"
    if staff > mitarbeiter:
        # Mehr Risikoträger als Mitarbeiter. Eine der beiden Zahlen ist falsch
        # oder meint einen anderen Perimeter — in jedem Fall trägt der
        # Quotient keine Aussage.
        return "staff_ueber_belegschaft"
    return ""


def ein_report_je_institut(zeilen):
    """Je LEI genau ein Report für die Schätzung — CON vor IND.

    Ein Haus mit mehreren Stichtagen zählte sonst mehrfach, mit fast
    identischem Wert (dieselbe Pseudoreplikation wie in #11).

    CON gewinnt, weil Wikidatas `P1128` die Belegschaft der GRUPPE führt. Ein
    IND-Report stellt dieser Gruppenzahl die Risikoträger des Einzelinstituts
    gegenüber und untertreibt den Anteil deshalb systematisch. Wo beide
    vorliegen, ist der konsolidierte der passende.

    Unter gleichem Perimeter gewinnt der JÜNGSTE Stichtag: gesucht ist, wie das
    Haus den Kreis heute zieht.

    Sortiert wird über alle Schlüsselteile. Stünde `scope` nicht darin,
    entschiede bei gleichem Stichtag die Eingangsreihenfolge — und die Ausgabe
    hinge an etwas, das nicht im Schlüssel steht (`scripts/determinism.py`).
    """
    aus = {}
    for z in sorted(zeilen, key=_rang):
        aus.setdefault(z["lei"], z)
    return aus


def schaetze_modell(zeilen):
    """(modell, je_institut) — die Erwartung, gegen die alle gemessen werden.

    Geschätzt wird NUR auf Zeilen ohne Vorbehalt. Ein Wert, den wir selbst als
    unbrauchbar ausweisen, darf die Erwartung nicht verschieben, gegen die alle
    anderen gemessen werden — sonst zieht ein bekannter Ausreisser die Latte zu
    sich hin und macht die übrigen Häuser genau um seinen Fehler auffälliger.

    Auf dem heutigen Bestand verschiebt der Unterschied die Erwartung um 0,8 bis
    4,5 % — klein genug, dass er in keiner Kennzahl auffiele, und das ist der
    Grund, ihn hier festzuhalten statt an der Ausgabe zu messen.
    """
    je_institut = ein_report_je_institut([z for z in zeilen if not z["vorbehalt"]])
    return (regression([(z["mitarbeiter"], z["anteil"])
                        for z in je_institut.values()]), je_institut)


def _rang(z):
    """CON vor IND, dann der jüngste Stichtag, dann `scope` als Letztentscheid."""
    try:
        alter = -date.fromisoformat(z["refPeriod"]).toordinal()
    except (ValueError, TypeError):
        # Ein unlesbarer Stichtag darf nicht gewinnen, aber auch nicht die
        # Sortierung sprengen: er landet hinten und wird über den Text geordnet.
        alter = 0
    return (z["lei"], z["scope"] != "CON", alter, z["refPeriod"], z["scope"])


def lade_kopfzahlen(con):
    """{(lei, scope, refPeriod): (summe, bank, land, institution_type)}.

    Summiert über die Spalten: REM1 führt die Kopfzahl je Funktionsstufe
    (Aufsichtsorgan, Geschäftsleitung, sonstige Risikoträger). Der Kreis der
    Risikoträger ist ihre Summe, nicht eine einzelne Stufe.
    """
    from determinism import ordered_query as ordered

    aus = {}
    for lei, sc, rp, bank, land, it, summe in ordered(con, f"""
        SELECT lei, scope, refPeriod, max(bank_name), max(country),
               max(institution_type), sum(fact_value)
        FROM '{PARQUET}'
        WHERE template_id = '{REM1}' AND cell_row = '{KOPFZAHL_ROW}'
          AND fact_value IS NOT NULL AND fact_value > 0
        GROUP BY lei, scope, refPeriod
        ORDER BY lei, scope, refPeriod
    """, "REM1-Kopfzahlen"):
        aus[(lei, sc, rp)] = (summe, bank or "", land or "", it or "")
    return aus


def build():
    import duckdb

    if not PARQUET.exists():
        print(f"ERROR: {PARQUET} fehlt")
        return []
    wiki = lade_wikidata()
    if not wiki:
        print(f"ERROR: {WIKIDATA} fehlt — erst scripts/fetch_wikidata_entities.py")
        return []

    con = duckdb.connect()
    kopf = lade_kopfzahlen(con)
    rem_befunde = lade_rem_befunde()

    roh = []
    for (lei, sc, rp), (staff, bank, land, it) in sorted(kopf.items()):
        if lei not in wiki:
            continue
        mitarbeiter, stand, wid = wiki[lei]
        vorbehalt = vorbehalt_von(staff, mitarbeiter,
                                  (lei, sc, rp) in rem_befunde)
        roh.append({
            "lei": lei, "scope": sc, "refPeriod": rp, "bank_name": bank,
            "country": land, "institution_type": it,
            "identified_staff": int(staff), "mitarbeiter": mitarbeiter,
            "mitarbeiter_stand": stand, "wikidata_id": wid,
            "anteil": staff / mitarbeiter, "vorbehalt": vorbehalt,
        })

    modell, je_institut = schaetze_modell(roh)

    for z in roh:
        erw = erwarteter_anteil(modell, z["mitarbeiter"])
        z["erwarteter_anteil"] = "" if erw is None else f"{erw:.6f}"
        z["faktor_gegen_erwartung"] = ("" if erw is None or erw <= 0
                                       else f"{z['anteil'] / erw:.3f}")
        z["anteil"] = f"{z['anteil']:.6f}"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(roh)

    print(f"✓ {OUT}  ({len(roh)} Zeilen, {len(je_institut)} Institute im Modell)")
    for s in bericht(roh, je_institut, modell, con, wiki):
        print("  " + s)
    return roh


def bericht(zeilen, je_institut, modell, con, wiki):
    aus = []
    vb = collections.Counter(z["vorbehalt"] for z in zeilen if z["vorbehalt"])
    aus.append(f"Zeilen: {len(zeilen)} · mit Vorbehalt: "
               + ("  ".join(f"{k}={v}" for k, v in sorted(vb.items())) or "keine"))
    if not je_institut:
        return aus

    anteile = sorted(float(z["anteil"]) for z in je_institut.values())
    n = len(anteile)
    aus.append(f"Roher Anteil identified staff (je Institut, n={n}): "
               f"p5 {anteile[int(.05*(n-1))]*100:.2f} % · "
               f"Median {anteile[n//2]*100:.2f} % · "
               f"p95 {anteile[int(.95*(n-1))]*100:.2f} % · "
               f"max {anteile[-1]*100:.2f} %")

    # Der Grund, warum die Rohquote nicht die gesuchte Aussage ist.
    punkte = [(math.log10(z["mitarbeiter"]), math.log10(float(z["anteil"])))
              for z in je_institut.values()]
    mx, my = st.mean(x for x, _ in punkte), st.mean(y for _, y in punkte)
    sx, sy = st.pstdev(x for x, _ in punkte), st.pstdev(y for _, y in punkte)
    r = (sum((x - mx) * (y - my) for x, y in punkte) / (len(punkte) * sx * sy)
         if sx > 0 and sy > 0 else 0)
    aus.append(f"log10(Belegschaft) gegen log10(Anteil): r = {r:+.3f} · "
               f"r² = {r*r:.3f} — so viel erklärt die GRÖSSE allein")
    if modell:
        aus.append(f"  Modell: Anteil ≈ 10^({modell[0]:.3f}·log10(Belegschaft) "
                   f"{modell[1]:+.3f})")

    for lo, hi, lab in ((0, 500, "< 500"), (500, 5000, "500–5.000"),
                        (5000, 50000, "5.000–50.000"), (50000, 10**9, "> 50.000")):
        t = [float(z["anteil"]) for z in je_institut.values()
             if lo <= z["mitarbeiter"] < hi]
        if t:
            aus.append(f"    {lab:14s} n={len(t):3d}  Median {st.median(t)*100:6.2f} %")

    # Und das, was nach Abzug der Grösse übrig bleibt — die eigentliche Aussage.
    fak = sorted((float(z["faktor_gegen_erwartung"]), z["bank_name"])
                 for z in je_institut.values() if z["faktor_gegen_erwartung"])
    if fak:
        aus.append(f"Faktor gegen die Grössenerwartung (n={len(fak)}): "
                   f"p10 {fak[int(.1*(len(fak)-1))][0]:.2f} · "
                   f"Median {fak[len(fak)//2][0]:.2f} · "
                   f"p90 {fak[int(.9*(len(fak)-1))][0]:.2f}")
        aus.append("  Kreis am weitesten gezogen (für ihre Grösse):")
        for f, b in fak[-4:][::-1]:
            aus.append(f"    {b[:36]:38s} {f:5.2f}×")
        aus.append("  Am engsten:")
        for f, b in fak[:4]:
            aus.append(f"    {b[:36]:38s} {f:5.2f}×")

    # Der Perimeter-Test: Wikidata führt die Belegschaft der GRUPPE, ein
    # IND-Report die Risikoträger des Einzelinstituts. Roh muss der Anteil
    # deshalb zwischen CON und IND auseinanderlaufen — nach Abzug der Grösse
    # darf er es nicht mehr, sonst hat das Modell Perimeter mit Grösse
    # verwechselt und der Faktor misst weiter die Konsolidierungsstufe.
    for feld, lab in (("anteil", "roher Anteil"),
                      ("faktor_gegen_erwartung", "Faktor")):
        teil = {s: [float(z[feld]) for z in je_institut.values()
                    if z["scope"] == s and z[feld]] for s in ("CON", "IND")}
        if all(teil.values()):
            aus.append(f"Perimeter, {lab}: CON {st.median(teil['CON']):.3f} "
                       f"(n={len(teil['CON'])}) · IND {st.median(teil['IND']):.3f} "
                       f"(n={len(teil['IND'])})")

    # Der Grössenbias der Stichprobe — gemessen, nicht erwähnt.
    trea = dict(con.execute(f"""
        SELECT lei, max(fact_value_eur) FROM '{PARQUET}'
        WHERE template_id = '61.00' AND cell_row = '0040' AND cell_col = '0010'
          AND fact_value_eur IS NOT NULL GROUP BY 1""").fetchall())
    mit = [v for l, v in trea.items() if l in wiki]
    ohne = [v for l, v in trea.items() if l not in wiki]
    if mit and ohne:
        aus.append(f"⚠ Grössenbias der Stichprobe: Institute MIT "
                   f"Wikidata-Mitarbeiterzahl haben einen Median-TREA von "
                   f"{st.median(mit)/1e9:.1f} Mrd EUR, die übrigen "
                   f"{st.median(ohne)/1e9:.1f} Mrd — Faktor "
                   f"{st.median(mit)/st.median(ohne):.1f}.")
    return aus


if __name__ == "__main__":
    build()
