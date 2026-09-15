"""Zinssensitivität aus dem IRRBB-Modul, gemessen statt geschätzt (#15).

Ausgabe: processed/irrbb_sensitivity.csv

## Warum das die EURIBOR-Korrelation ersetzt

#11 wollte die Zinssensitivität aus einer EURIBOR-Korrelation gewinnen. Das
geht nicht, und zwar nicht aus Datenmangel, sondern aus Konstruktion: **EURIBOR
hat zu einem Stichtag für alle Banken denselben Wert.** Eine Regression über
Banken hinweg hat auf der Regressorseite null Varianz. Über die Zeitachse zu
retten wäre möglich, aber 266 von 474 Instituten haben genau einen Stichtag,
und das Beobachtungsfenster ist neun Monate mit weitgehend flachem Zins.

Das IRRBB-Modul enthält die Antwort bereits — aufsichtlich vorgeschrieben,
standardisiert und je Institut gemessen: `68.00` (EU IRRBB1) trägt die sechs
Zinsschock-Szenarien mit der Barwertänderung des Eigenkapitals (ΔEVE) und der
Zinsergebnisänderung (ΔNII). 235 Institute melden es, und es war bisher
vollständig ungenutzt.

    c0010  ΔEVE laufende Periode      alle sechs Szenarien
    c0020  ΔEVE Vorperiode
    c0030  ΔNII laufende Periode      NUR Parallel hoch/runter — so sieht es
    c0040  ΔNII Vorperiode            die Meldevorschrift vor

## Der Massstab ist das Kernkapital, nicht der Betrag

Ein ΔEVE von 100 Mio. EUR heisst bei einer Sparkasse etwas anderes als bei der
Deutschen Bank. Der aufsichtliche Bezug ist das Tier-1-Kapital aus KM1
(`61.00` r0020), und er ist nicht frei gewählt: die **Supervisory Outlier
Tests** definieren genau diesen Quotienten.

    SOT_EVE  15 %   CRD Art. 98(5): Barwertverlust über 15 % des Kernkapitals
                    in einem der sechs Szenarien
    SOT_NII   5 %   EBA/GL/2022/14: Rückgang des Zinsergebnisses über 5 % des
                    Kernkapitals unter Parallelverschiebung

Gezählt wird nur der VERLUST. Ein positives ΔEVE ist ein Gewinn und keine
Auffälligkeit — die Prüfung symmetrisch zu führen hiesse, Banken für
Zinsgewinne zu markieren.

## Das Ergebnis: die EVE-Kategorie ist leer, und genau das ist der Befund

    ΔEVE über 1.763 saubere Zeilen:  Median −0,00 · p5 −0,081 · p1 −0,115
                                     grösster Verlust  −14,84 %
    über der 15-%-Schwelle:          0

**Null Überschreitungen — bei einem Maximum von 14,84 %.** Die fünf schwersten
Fälle liegen bei −14,84 · −14,64 · −14,51 · −14,45 · −14,33 %, also allesamt im
letzten Prozentpunkt vor der Schwelle:

    BANK POLSKIEJ SPOLDZIELCZOSCI   PL   −14,84 %
    BANCA IFIS                      IT   −14,64 %
    Advanzia Bank                   LU   −14,51 %
    Hrvatska poštanska banka        HR   −14,45 %
    NOBA Group                      SE   −14,33 %

Eine leere Kategorie sieht aus wie eine Prüfung, die nichts tut. Hier ist sie
das Gegenteil: die Verteilung bricht **unmittelbar vor** der aufsichtlichen
Grenze ab. Das ist keine Eigenschaft der Zinsrisiken, das ist die Grenze als
bindende Nebenbedingung — Institute steuern bis an sie heran und nicht darüber.
Ohne die Randverteilung wäre „0 Überschreitungen" bedeutungslos.

## Bei ΔNII ist die Kategorie nicht leer — und die Treffer haben ein Muster

22 Überschreitungen, und sie verteilen sich nicht zufällig:

    flatexDEGIRO         DE   −25,5 %     Parallel runter
    Nordnet              SE   −25,0 %     Parallel runter
    Clearstream Banking  LU   −21,5 %     Parallel runter
    Avanza               SE   −19,1 %     Parallel runter
    Revolut Holdings     LT   −15,3 %     Parallel runter
    NOBA Group           SE   −14,7 %     Parallel runter

Broker, Neobanken und Verwahrstellen — Häuser, deren Ertrag am Zinsspread auf
gehaltene Kundengelder hängt. Fallen die Zinsen, fällt das Zinsergebnis. Das
ist kein Meldefehler und keine Auffälligkeit im Sinne einer Fehlmeldung,
sondern ein Geschäftsmodell, das der Test genau dafür sichtbar macht.

## Zwei Vorbehalte, und beide stehen als Spalte

**Der Nenner kann kaputt sein.** Die Deutsche Pfandbriefbank meldet ein
Tier-1-Kapital von 2.998 EUR — ihr ganzer Report liegt um 10^6 daneben (#83).
Ungefiltert ergäbe das eine Quote von −42.028, also 126 Zeilen scheinbarer
SOT-Überschreitungen aus einem einzigen Skalenfehler. `scale_flags.csv` nimmt
sie heraus; der Vorbehalt steht in der Spalte, der Report verschwindet nicht.

**Und der Zähler auch.** Citibank Europe meldet ein ΔEVE von −298 Mrd. EUR
gegen 14,4 Mrd. Kernkapital. Ein Barwertverlust, der das gesamte Kernkapital um
das Zwanzigfache übersteigt, ist keine Sensitivität mehr — ein solches Institut
wäre mehrfach insolvent. Ab `QUOTE_UNPLAUSIBEL` wird die Zeile als Artefakt
geführt und nicht als Befund.

Aufruf: python3 scripts/build_irrbb_sensitivity.py
"""

from pathlib import Path
import collections
import csv
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
SCALE_FLAGS = ROOT / "processed" / "scale_flags.csv"
OUT = ROOT / "processed" / "irrbb_sensitivity.csv"

TEMPLATE = "68.00"
KM1 = "61.00"
TIER1_ROW = "0020"          # KM1 r0020 "Tier 1 capital"

# Die sechs aufsichtlichen Zinsschock-Szenarien in der Reihenfolge des
# Templates. Die Bezeichnungen stehen hier und nicht im Code, damit die
# Ausgabe ohne Kenntnis der Zeilennummern lesbar ist.
SZENARIEN = {
    "0010": "Parallelverschiebung hoch",
    "0020": "Parallelverschiebung runter",
    "0030": "Steepener",
    "0040": "Flattener",
    "0050": "kurze Zinsen hoch",
    "0060": "kurze Zinsen runter",
}

# ΔNII wird nur für die beiden Parallelverschiebungen gemeldet — so sieht es
# die Meldevorschrift vor. Für die übrigen vier Szenarien ist die Spalte leer,
# und das ist keine Auslassung ("Fehlt != Null", Arbeitsprinzip 3).
NII_SZENARIEN = ("0010", "0020")

SPALTE_EVE = "0010"          # laufende Periode
SPALTE_NII = "0030"          # laufende Periode

# Die Schwellen sind nicht geeicht, sondern gesetzt — sie stehen im Recht.
SOT_EVE = 0.15               # CRD Art. 98(5)
SOT_NII = 0.05               # EBA/GL/2022/14

# Ab welchem Quotienten die Zeile ein Meldeartefakt ist und kein Befund. Ein
# Barwertverlust grösser als das gesamte Kernkapital beschreibt kein
# Zinsrisiko, sondern ein mehrfach insolventes Institut.
QUOTE_UNPLAUSIBEL = 1.0

FELDER = ["lei", "scope", "refPeriod", "bank_name", "country", "institution_type",
          "szenario", "szenario_label", "delta_eve_eur", "delta_nii_eur",
          "tier1_eur", "quote_eve", "quote_nii", "sot_eve", "sot_nii", "vorbehalt"]


def quote(delta, tier1):
    """ΔEVE bzw. ΔNII im Verhältnis zum Kernkapital, oder None.

    None heisst „nicht berechenbar", nicht „null": ohne Kernkapital gibt es
    keinen aufsichtlichen Bezug, und ein Tier-1 von 0 oder darunter ist keine
    Bezugsgrösse, sondern ein eigener (hier nicht behandelter) Befund.
    """
    if delta is None or not tier1 or tier1 <= 0:
        return None
    return delta / tier1


def sot_urteil(q, schwelle):
    """Überschreitet der VERLUST die aufsichtliche Schwelle?

    Einseitig mit Absicht. Der Supervisory Outlier Test fragt nach dem
    Rückgang; ein positives ΔEVE ist ein Zinsgewinn. Symmetrisch geprüft
    stünden Institute mit Zinsgewinnen in derselben Liste wie solche am
    aufsichtlichen Schwellenwert — zwei Sachverhalte unter einem Etikett.
    """
    if q is None:
        return ""
    return "ja" if q < -schwelle else "nein"


def vorbehalt_von(skaliert, q_eve, q_nii):
    """Trägt diese Zeile überhaupt eine Aussage?

    `skala`        der Report ist laut #83 um einen Faktor zu klein gemeldet.
                   Betroffen ist hier der NENNER: die Pfandbriefbank meldet
                   2.998 EUR Kernkapital, und jede Quote daraus ist Unsinn.
    `unplausibel`  der Quotient übersteigt 1 — der Zähler kann nicht stimmen.
                   Gemessen an zwei Reports (Citibank Europe, Wüstenrot
                   Bausparkasse).

    Die Reihenfolge ist wichtig: ein skalierter Report erzeugt AUCH einen
    unplausiblen Quotienten. Wer `unplausibel` zuerst prüft, schreibt den
    Skalenfehler dem Zähler zu und verliert die Spur zu #83.
    """
    if skaliert:
        return "skala"
    for q in (q_eve, q_nii):
        if q is not None and abs(q) > QUOTE_UNPLAUSIBEL:
            return "unplausibel"
    return ""


def lade_skalenmarken(pfad=None):
    """{(lei, scope, refPeriod)} der Reports mit belegtem Skalenfehler (#83).

    Nur `skaliert`, nicht `verdacht`: ein Verdacht reicht nicht, um eine Zeile
    aus der Auswertung zu nehmen. Fehlt die Datei, wird nichts markiert — dann
    steht der Vorbehalt eben nicht da, statt dass die halbe Auswertung
    stillschweigend verschwindet.
    """
    pfad = Path(pfad or SCALE_FLAGS)
    if not pfad.exists():
        return set()
    with pfad.open(encoding="utf-8") as fh:
        return {(r["lei"], r["scope"], r["refPeriod"]) for r in csv.DictReader(fh)
                if r.get("ebene") == "report" and r.get("urteil") == "skaliert"
                and r.get("lei")}


def lade(con):
    """(Schockwerte, Kernkapital) aus dem Parquet."""
    from determinism import ordered_query as ordered

    schock = {}
    for lei, sc, rp, bank, land, it, row, col, v in ordered(con, f"""
        SELECT lei, scope, refPeriod, max(bank_name), max(country),
               max(institution_type), cell_row, cell_col, min(fact_value_eur)
        FROM '{PARQUET}'
        WHERE template_id = '{TEMPLATE}' AND fact_value_eur IS NOT NULL
          AND cell_col IN ('{SPALTE_EVE}', '{SPALTE_NII}')
        GROUP BY lei, scope, refPeriod, cell_row, cell_col
        ORDER BY lei, scope, refPeriod, cell_row, cell_col
    """, "IRRBB1-Schocks"):
        schock[(lei, sc, rp, row, col)] = (v, bank or "", land or "", it or "")

    tier1 = {}
    for lei, sc, rp, v in ordered(con, f"""
        SELECT lei, scope, refPeriod, max(fact_value_eur)
        FROM '{PARQUET}'
        WHERE template_id = '{KM1}' AND cell_row = '{TIER1_ROW}'
          AND cell_col = '0010' AND fact_value_eur IS NOT NULL
        GROUP BY lei, scope, refPeriod
        ORDER BY lei, scope, refPeriod
    """, "Kernkapital"):
        tier1[(lei, sc, rp)] = v
    return schock, tier1


def build():
    import duckdb

    if not PARQUET.exists():
        print(f"ERROR: {PARQUET} fehlt — erst scripts/build_zweig_b.py")
        return []

    con = duckdb.connect()
    schock, tier1 = lade(con)
    skaliert = lade_skalenmarken()

    reports = sorted({k[:3] for k in schock})
    zeilen = []
    for lei, sc, rp in reports:
        t1 = tier1.get((lei, sc, rp))
        for szen in sorted(SZENARIEN):
            eve = schock.get((lei, sc, rp, szen, SPALTE_EVE))
            nii = schock.get((lei, sc, rp, szen, SPALTE_NII))
            if eve is None and nii is None:
                continue
            meta = eve or nii
            q_eve = quote(eve[0] if eve else None, t1)
            q_nii = quote(nii[0] if nii else None, t1)
            vb = vorbehalt_von((lei, sc, rp) in skaliert, q_eve, q_nii)
            zeilen.append({
                "lei": lei, "scope": sc, "refPeriod": rp,
                "bank_name": meta[1], "country": meta[2], "institution_type": meta[3],
                "szenario": szen, "szenario_label": SZENARIEN[szen],
                "delta_eve_eur": "" if eve is None else f"{eve[0]:.0f}",
                "delta_nii_eur": "" if nii is None else f"{nii[0]:.0f}",
                "tier1_eur": "" if t1 is None else f"{t1:.0f}",
                "quote_eve": "" if q_eve is None else f"{q_eve:.4f}",
                "quote_nii": "" if q_nii is None else f"{q_nii:.4f}",
                # Ein Vorbehalt macht die Zeile nicht falsch, aber ihr Urteil
                # wertlos. Deshalb bleibt das Urteil leer statt „nein" — sonst
                # läse sich ein Skalenfehler als bestandener Test.
                "sot_eve": "" if vb else sot_urteil(q_eve, SOT_EVE),
                "sot_nii": "" if vb else sot_urteil(q_nii, SOT_NII),
                "vorbehalt": vb,
            })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(zeilen)

    print(f"✓ {OUT}  ({len(zeilen)} Zeilen, {len(reports)} Reports)")
    for s in bericht(zeilen):
        print("  " + s)
    return zeilen


def _quoten(zeilen, feld):
    return sorted(float(z[feld]) for z in zeilen if z[feld] and not z["vorbehalt"])


def bericht(zeilen):
    aus = []
    vb = collections.Counter(z["vorbehalt"] for z in zeilen if z["vorbehalt"])
    aus.append(f"Reports mit Kernkapital: "
               f"{len({(z['lei'], z['scope'], z['refPeriod']) for z in zeilen if z['tier1_eur']})}"
               f" · mit Vorbehalt: " + ("  ".join(f"{k}={v}" for k, v in sorted(vb.items())) or "keine"))

    for feld, urteil, schwelle, name in (("quote_eve", "sot_eve", SOT_EVE, "ΔEVE"),
                                         ("quote_nii", "sot_nii", SOT_NII, "ΔNII")):
        q = _quoten(zeilen, feld)
        if not q:
            continue
        n = len(q)
        treffer = [z for z in zeilen if z[urteil] == "ja"]
        aus.append("")
        aus.append(f"{name} / Tier 1 über {n:,} auswertbare Zeilen "
                   f"(SOT-Schwelle {schwelle:.0%}):")
        aus.append(f"  Median {q[n//2]:+.4f} · p5 {q[int(0.05*(n-1))]:+.4f} · "
                   f"p1 {q[int(0.01*(n-1))]:+.4f} · grösster Verlust {q[0]:+.4f}")
        aus.append(f"  über der Schwelle: {len(treffer)}")
        if treffer:
            for z in sorted(treffer, key=lambda z: float(z[feld]))[:6]:
                aus.append(f"    {z['bank_name'][:30]:32s} {z['country'][:12]:14s} "
                           f"{z['refPeriod']}  {z['szenario_label'][:26]:28s} "
                           f"{100*float(z[feld]):7.1f} %")
        else:
            # Ohne die Randverteilung wäre „0 Überschreitungen" bedeutungslos —
            # es könnte heissen, dass gar nicht gemessen wurde.
            nah = [z for z in zeilen if z[feld] and not z["vorbehalt"]
                   and float(z[feld]) < -0.8 * schwelle]
            aus.append(f"    Gegenprobe: {len(nah)} Zeilen liegen im letzten Fünftel "
                       f"VOR der Schwelle — die Verteilung bricht unmittelbar davor ab.")
            for z in sorted(nah, key=lambda z: float(z[feld]))[:5]:
                aus.append(f"    {z['bank_name'][:30]:32s} {z['country'][:12]:14s} "
                           f"{z['refPeriod']}  {z['szenario_label'][:26]:28s} "
                           f"{100*float(z[feld]):7.2f} %")
    return aus


if __name__ == "__main__":
    build()
