"""Hängen Bankattribute an Kennzahlen des Heimatlandes? (#11)

Ausgabe: processed/country_effect.csv

## Die These und warum sie so nicht geprüft werden kann

#11 will den Datensatz um BIP- und EURIBOR-Zeitreihen anreichern und dann
Zusammenhänge zwischen Heimatland-Indikatoren und Bankattributen suchen,
kontrolliert auf den nationalen Fussabdruck.

Der EURIBOR-Teil ist schon in #15 daran gescheitert, dass EURIBOR zu einem
Stichtag für ALLE Banken denselben Wert hat — null Varianz auf der
Regressorseite, unabhängig von der Stichprobengrösse. Dieses Skript prüft die
verbleibende Hälfte, und zwar in der Reihenfolge, die eine Korrelation erst
interpretierbar macht: **zuerst die Obergrenze, dann der Regressor.**

## Die Obergrenze: wie viel kann ein Länderindikator überhaupt erklären?

Eine Kennzahl des Heimatlandes ist für alle Institute desselben Landes
identisch. Sie kann deshalb nur den Teil der Streuung erklären, der ZWISCHEN
Ländern liegt — die Streuung innerhalb eines Landes ist für sie unsichtbar.
Diese Zerlegung ist keine Schätzung, sondern eine Identität:

    Varianz gesamt = Varianz zwischen Ländern + Varianz innerhalb

Gemessen an der Domestizitätsquote über 243 Institute in 30 Ländern:

    zwischen    31,8 %
    innerhalb   68,2 %      <- für jeden Länderindikator unerreichbar

**R² ≤ 0,318 für jede denkbare Länderkennzahl**, ob BIP, Zins, Inflation oder
Bevölkerung. Wer diese Zahl nicht zuerst bestimmt, kann ein r² von 0,05 weder
als „schwach" noch als „so gut wie möglich" einordnen.

## Das Ergebnis: das BIP erreicht 0,3 % des Erreichbaren

    log10(BIP Heimatland)        r = +0,036   r² = 0,001
    log10(Exposure des Landes)   r = −0,056   r² = 0,003
    log10(Exposure / BIP)        r = −0,212   r² = 0,045

Das BIP erklärt **0,3 % dessen, was ein Länderindikator überhaupt erklären
könnte.** Die These trägt nicht, und zwar nicht knapp.

## Der Ländereffekt ist trotzdem gross — er ist nur kein Makroeffekt

Die Mediane je Land reichen von 0,061 (Irland) bis 0,993 (Norwegen). Da ist
etwas, es hängt nur nicht an der Volkswirtschaft:

    Irland       Median 0,061    Exposure/BIP 0,45
    Frankreich   Median 0,923    Exposure/BIP 1,68

Genau umgekehrt zur Finanzplatz-Hypothese, die sich hier aufdrängt — Irland
liegt bei Exposure/BIP am unteren Ende und bei der Domestizität trotzdem ganz
unten. Diese zweite Erklärung ist damit ebenfalls widerlegt, und das gehört
dazugesagt: sie war der naheliegende Rettungsversuch.

Was übrig bleibt, ist eine **Zusammensetzungsfrage**: welche Art von Institut
dort ihren Sitz hat. Irlands sieben belastbare Institute sind zu sechst
`Large highest EEA` — Europazentralen amerikanischer und britischer Häuser,
deren Geschäft naturgemäss ausserhalb Irlands liegt. Aber auch das erklärt es
nicht vollständig: INNERHALB von `Large highest EEA` reicht die Spanne weiter
von 0,062 (Irland) bis 0,920 (Italien).

## Was daraus für #11 folgt

Die Frage „hängt die Bank am Heimatland" ist mit diesen Daten beantwortbar und
die Antwort lautet **nein, jedenfalls nicht an seiner Makroökonomie**. Eine
Anreicherung um weitere Länderzeitreihen würde daran nichts ändern: die
Obergrenze liegt bei 0,318, und sie gilt für alle.

Die Streuung sitzt zu zwei Dritteln INNERHALB der Länder — Deutschland reicht
von 0,075 bis 1,000, Italien von 0,000 bis 1,000. Wer die Domestizität erklären
will, braucht Institutsmerkmale, keine Ländermerkmale. Das ist die Richtung von
#13 und #35, nicht die von #11.

Aufruf: python3 scripts/check_country_effect.py
"""

from pathlib import Path
import collections
import csv
import math
import statistics as st
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

FOOTPRINT = ROOT / "processed" / "footprint.csv"
GDP = ROOT / "codebook" / "country_gdp.csv"
OUT = ROOT / "processed" / "country_effect.csv"

# Attribute, die #11 mit Länderkennzahlen erklären will. Mehrere, damit das
# Ergebnis nicht an einer einzelnen Kennzahl hängt.
ATTRIBUTE = {
    "domestic_share": "Anteil des Heimatlands am Exposure",
    "country_hhi": "Konzentration der Länderverteilung (HHI)",
    "n_countries": "Zahl der Länder mit Exposure",
}

# Unter fünf Instituten trägt ein Ländermittel nicht — dieselbe Schranke wie
# überall sonst im Repo.
MIN_INSTITUTE = 5

FELDER = ["attribut", "attribut_label", "regressor", "n_institute", "n_laender",
          "varianz_gesamt", "varianz_zwischen", "anteil_zwischen",
          "r", "r_quadrat", "anteil_des_erreichbaren"]


def korrelation(paare):
    """Pearson-r über (x, y)-Paare, oder None.

    None bei weniger als drei Paaren oder wenn eine Seite konstant ist — und
    der zweite Fall ist hier der wichtige: **EURIBOR ist zu einem Stichtag für
    alle Banken identisch.** Eine Korrelation darauf ist nicht klein, sie ist
    undefiniert, und das muss sichtbar bleiben statt als 0,0 durchzugehen.
    """
    if len(paare) < 3:
        return None
    xs = [p[0] for p in paare]
    ys = [p[1] for p in paare]
    sx, sy = st.pstdev(xs), st.pstdev(ys)
    if sx < 1e-12 or sy < 1e-12:
        return None
    mx, my = st.mean(xs), st.mean(ys)
    return sum((x - mx) * (y - my) for x, y in paare) / (len(paare) * sx * sy)


def varianzzerlegung(werte_je_gruppe):
    """(gesamt, zwischen, anteil_zwischen) — die Obergrenze für Gruppenvariablen.

    `werte_je_gruppe`: {Gruppe: [Werte]}.

    Die Zerlegung ist eine Identität, keine Schätzung: eine Kennzahl, die für
    alle Mitglieder einer Gruppe denselben Wert hat, kann höchstens den Anteil
    ZWISCHEN den Gruppen erklären. `anteil_zwischen` ist damit die harte
    Obergrenze für R² jeder denkbaren Länderkennzahl — auch solcher, die noch
    niemand erhoben hat.

    Ohne diese Zahl ist ein gemessenes r² nicht einzuordnen: 0,05 kann
    „praktisch nichts" heissen oder „fast alles, was geht".
    """
    alle = [w for v in werte_je_gruppe.values() for w in v]
    n = len(alle)
    if n < 2:
        return None
    gesamt = st.pvariance(alle)
    if gesamt < 1e-15:
        return None
    gm = st.mean(alle)
    zwischen = sum(len(v) * (st.mean(v) - gm) ** 2 for v in werte_je_gruppe.values()) / n
    return gesamt, zwischen, zwischen / gesamt


def ein_institut_je_lei(zeilen):
    """Eine Zeile je Institut, nicht je Report.

    `footprint.csv` führt 335 belastbare Zeilen über 243 Institute — ein
    Institut mit vier Stichtagen zählte sonst viermal, und zwar mit fast
    identischem Wert. Das bläht n auf, ohne Information hinzuzufügen, und lässt
    jede Korrelation belastbarer aussehen als sie ist.

    Genommen wird die erste Zeile in stabiler Sortierung, nicht die „beste" —
    eine Auswahl nach dem Wert wäre eine Vorentscheidung über das Ergebnis.
    """
    je = {}
    for z in sorted(zeilen, key=lambda z: (z["lei"], z["scope"], z["refPeriod"])):
        je.setdefault(z["lei"], z)
    return list(je.values())


def lade():
    """(Institute, {Land: BIP}) — nur belastbare Footprint-Zeilen.

    `reliable = false` heisst: kein Heimatland, zu hoher Residualanteil oder
    ein Skalenbefund aus #83. Solche Zeilen in eine Korrelation zu nehmen hiesse,
    über Werte zu rechnen, die wir selbst als unbrauchbar ausgewiesen haben.
    """
    if not FOOTPRINT.exists() or not GDP.exists():
        return [], {}
    with FOOTPRINT.open(encoding="utf-8") as fh:
        zeilen = [z for z in csv.DictReader(fh) if z.get("reliable") == "true"]
    with GDP.open(encoding="utf-8") as fh:
        bip = {z["country"]: float(z["gdp_usd"]) for z in csv.DictReader(fh)
               if z.get("gdp_usd")}
    return ein_institut_je_lei(zeilen), bip


def regressoren(institute, bip):
    """{Name: {Land: Wert}} — die Länderkennzahlen, die geprüft werden.

    `exposure_je_bip` ist der naheliegende zweite Versuch („Finanzplatz"), und
    er steht hier, WEIL er scheitert: ohne ihn läse sich das Ergebnis als
    „BIP war die falsche Kennzahl", statt als „Länderkennzahlen tragen hier
    nicht".
    """
    expo = collections.defaultdict(float)
    for z in institute:
        land = z["home_country"]
        if land in bip and z["total_exposure_eur"]:
            expo[land] += float(z["total_exposure_eur"])
    return {
        "log10_bip": {k: math.log10(v) for k, v in bip.items() if v > 0},
        "log10_exposure_land": {k: math.log10(v) for k, v in expo.items() if v > 0},
        "log10_exposure_je_bip": {k: math.log10(v / bip[k]) for k, v in expo.items()
                                  if v > 0 and bip.get(k, 0) > 0},
    }


def auswerten(institute, bip):
    reg = regressoren(institute, bip)
    aus = []
    for attr, label in sorted(ATTRIBUTE.items()):
        je_land = collections.defaultdict(list)
        for z in institute:
            land = z["home_country"]
            if land in bip and z.get(attr):
                je_land[land].append(float(z[attr]))
        zerlegung = varianzzerlegung(je_land)
        if zerlegung is None:
            continue
        gesamt, zwischen, anteil = zerlegung
        n_inst = sum(len(v) for v in je_land.values())
        for name in sorted(reg):
            paare = [(reg[name][land], w) for land, werte in je_land.items()
                     if land in reg[name] for w in werte]
            r = korrelation(paare)
            aus.append({
                "attribut": attr, "attribut_label": label, "regressor": name,
                "n_institute": n_inst, "n_laender": len(je_land),
                "varianz_gesamt": f"{gesamt:.6f}",
                "varianz_zwischen": f"{zwischen:.6f}",
                "anteil_zwischen": f"{anteil:.4f}",
                "r": "" if r is None else f"{r:+.4f}",
                "r_quadrat": "" if r is None else f"{r*r:.4f}",
                # Erst dieser Quotient macht das r² lesbar: wie viel von dem,
                # was ÜBERHAUPT erklärbar ist, erklärt dieser Regressor?
                "anteil_des_erreichbaren": ("" if r is None or anteil <= 0
                                            else f"{r*r/anteil:.4f}"),
            })
    return aus


def build():
    institute, bip = lade()
    if not institute:
        print("ERROR: footprint.csv oder country_gdp.csv fehlt")
        return []
    aus = auswerten(institute, bip)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(aus)

    print(f"✓ {OUT}  ({len(aus)} Zeilen)")
    for s in bericht(aus, institute, bip):
        print("  " + s)
    return aus


def bericht(aus, institute, bip):
    zeilen = [f"Institute (eine Zeile je LEI): {len(institute)}"]
    for attr in sorted(ATTRIBUTE):
        teil = [a for a in aus if a["attribut"] == attr]
        if not teil:
            continue
        anteil = float(teil[0]["anteil_zwischen"])
        zeilen.append("")
        zeilen.append(f"{ATTRIBUTE[attr]} — Varianz zwischen Ländern: "
                      f"{anteil:.1%} von {teil[0]['n_laender']} Ländern")
        zeilen.append(f"  Obergrenze für JEDE Länderkennzahl: R² <= {anteil:.3f}")
        for a in sorted(teil, key=lambda a: -float(a["r_quadrat"] or 0)):
            erreicht = a["anteil_des_erreichbaren"]
            zeilen.append(f"    {a['regressor']:24s} r={a['r'] or '  n/a':>8s}  "
                          f"r²={a['r_quadrat'] or 'n/a':>7s}  "
                          f"davon erreicht: {float(erreicht):.1%}" if erreicht
                          else f"    {a['regressor']:24s} r=n/a (konstant)")

    # Der Ländereffekt IST da — er hängt nur nicht am BIP. Ohne diese Zahlen
    # läse sich das Ergebnis als „Länder spielen keine Rolle".
    je = collections.defaultdict(list)
    for z in institute:
        if z.get("domestic_share"):
            je[z["home_country"]].append(float(z["domestic_share"]))
    gross = sorted(((k, st.median(v), len(v)) for k, v in je.items()
                    if len(v) >= MIN_INSTITUTE), key=lambda t: t[1])
    if gross:
        zeilen.append("")
        zeilen.append(f"Gegenprobe — der Ländereffekt ist gross, nur kein Makroeffekt "
                      f"({len(gross)} Länder mit n >= {MIN_INSTITUTE}):")
        for k, m, n in gross[:3] + gross[-3:]:
            b = bip.get(k, 0) / 1e9
            zeilen.append(f"    {k[:20]:22s} n={n:3d}  Median {m:.3f}   "
                          f"BIP {b:7.0f} Mrd USD")
        zeilen.append("  Und die Streuung INNERHALB der grossen Länder:")
        for k, v in sorted(je.items(), key=lambda kv: -len(kv[1]))[:4]:
            s = sorted(v)
            zeilen.append(f"    {k[:20]:22s} n={len(s):3d}  "
                          f"{s[0]:.3f} … {s[len(s)//2]:.3f} … {s[-1]:.3f}")
    return zeilen


if __name__ == "__main__":
    build()
