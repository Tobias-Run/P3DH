"""Rechtzeitigkeit der Offenlegung je Institut (#33).

Abstand zwischen Stichtag und Einreichung, aus `submission_ts` im
Harvest-Manifest. Ergebnis: processed/disclosure_lag.csv

## Warum die ERSTE Einreichung zählt

66 % aller (Institut, Stichtag, Modul)-Kombinationen haben mehr als eine
Einreichung — 1.141 von 1.739. Der Abstand zwischen erster und letzter
beträgt im Median 4 Tage, im Extremfall 423.

Rechtzeitigkeit ist die Frage „wann lag die Offenlegung erstmals vor". Wer
stattdessen die letzte Einreichung misst, misst Korrekturverhalten (#31) —
und bestraft ausgerechnet die Institute, die einen Fehler später
nachbessern. Beide Zeitstempel stehen in der Ausgabe, aber die Kennzahl
hängt an `lag_days` (erste), nicht an `lag_days_last`.

## Warum nur INNERHALB der Klasse verglichen wird

CRR Art. 433a–c geben grossen, anderen sowie kleinen und nicht komplexen
Instituten **verschiedene Fristen und Frequenzen**. Ein roher Vergleich über
alle Institute misst die Proportionalitätsklasse, nicht die Sorgfalt.

Die Klasse muss nicht erst modelliert werden (#34) — `entity_meta.csv` führt
sie bereits als `institution_type`: „Large highest EEA" (142), „Large
subsidiaries" (109), „Other highest EEA" (253). Das Perzentil wird deshalb
je (Stichtag, institution_type) gebildet, nie darüber hinweg.

## Was diese Kennzahl NICHT sagt

Der Hub ging am 26.01.2026 live; die vier älteren Stichtage wurden
nachgereicht. Ihre Lags (Median 252 / 162 / 144 / 135 Tage) sind
**Nachreichungs-Artefakte und keine Verspätung**. Belastbar ist allein
2026-03-31 (Median 59).

Und dort meldet fast ausschliesslich eine Klasse: 168 „Large highest EEA",
79 „Large subsidiaries" — aber nur **ein** „Other highest EEA". Für rund die
Hälfte des Bestands ist Rechtzeitigkeit am eingeschwungenen Stichtag damit
schlicht nicht messbar. Das ist keine Lücke im Skript, sondern die
Quartalspflicht aus CRR Art. 433a: andere Institute legen gar nicht
quartalsweise offen. Die Spalte `belastbar` hält das fest.

Aufruf: python3 scripts/build_disclosure_lag.py
"""

from datetime import datetime
from pathlib import Path
import collections
import csv
import statistics as st

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "interim" / "edap_recon" / "manifest_full.csv"
META = ROOT / "processed" / "entity_meta.csv"
OUT = ROOT / "processed" / "disclosure_lag.csv"

# Der Hub ging am 26.01.2026 live. Alles davor wurde nachgereicht; der
# gemessene Abstand ist dort eine Eigenschaft des Hub-Starts, nicht des
# Instituts.
HUB_START = datetime(2026, 1, 26)

# Unter dieser Besetzung wird kein Perzentil ausgewiesen — dieselbe Schwelle
# wie in der Peer-Logik des Viewers. Lieber nichts als eine Scheinaussage.
MIN_KLASSE = 5

FELDER = ["lei", "bank_name", "country", "institution_type", "refdate", "module",
          "lag_days", "lag_days_last", "n_submissions", "submitted_at",
          "klasse_n", "klasse_median", "percentile", "belastbar"]


def _lag(refdate, ts):
    return (datetime.strptime(ts[:14], "%Y%m%d%H%M%S")
            - datetime.strptime(refdate, "%Y-%m-%d")).days


def _nachgereicht(refdate):
    """Lag dieser Stichtag vor dem Hub-Start?

    Dann konnte seine Offenlegung dort gar nicht rechtzeitig erscheinen — der
    gemessene Abstand ist eine Eigenschaft des Hub-Starts, nicht des Instituts.
    Gemessen schlägt das durch: 252 / 162 / 144 / 135 Tage für die vier älteren
    Stichtage gegen 59 für den ersten, der nach dem Start liegt.

    Bewusst diese schlichte Regel und keine Schätzung der Fristen: eine
    hergeleitete Grenze wäre eine Annahme, die wie eine Messung aussieht.
    """
    return datetime.strptime(refdate, "%Y-%m-%d") < HUB_START


def einreichungen(manifest_rows):
    """Je (LEI, Stichtag, Modul) die erste und die letzte Einreichung."""
    g = collections.defaultdict(list)
    for r in manifest_rows:
        if not (r["lei"] and r["refdate"] and r["submission_ts"]):
            continue
        g[(r["lei"], r["refdate"], r["module"])].append(r["submission_ts"])
    aus = {}
    for k, ts in g.items():
        ts = sorted(ts)
        aus[k] = (ts[0], ts[-1], len(ts))
    return aus


def perzentil(wert, werte):
    """Anteil der Klasse, der SPÄTER dran war — 0 = früheste, 100 = späteste.

    Aufsteigend nach Lag: ein kleines Perzentil heisst früh offengelegt.
    """
    kleiner = sum(1 for w in werte if w < wert)
    gleich = sum(1 for w in werte if w == wert)
    return round(100.0 * (kleiner + 0.5 * gleich) / len(werte), 1)


def build():
    with MANIFEST.open(encoding="utf-8") as fh:
        man = list(csv.DictReader(fh))
    with META.open(encoding="utf-8") as fh:
        meta = {r["lei"]: r for r in csv.DictReader(fh)}

    erste = einreichungen(man)

    zeilen = []
    for (lei, refdate, modul), (ts0, ts1, n) in erste.items():
        m = meta.get(lei, {})
        zeilen.append({
            "lei": lei,
            "bank_name": m.get("name", ""),
            "country": m.get("country", ""),
            "institution_type": m.get("institution_type", ""),
            "refdate": refdate,
            "module": modul,
            "lag_days": _lag(refdate, ts0),
            "lag_days_last": _lag(refdate, ts1),
            "n_submissions": n,
            "submitted_at": ts0[:8],
            "belastbar": "false" if _nachgereicht(refdate) else "true",
        })

    # Perzentil je (Stichtag, Institutstyp) — niemals darüber hinweg.
    klassen = collections.defaultdict(list)
    for z in zeilen:
        klassen[(z["refdate"], z["institution_type"])].append(z["lag_days"])

    for z in zeilen:
        werte = klassen[(z["refdate"], z["institution_type"])]
        z["klasse_n"] = len(werte)
        if len(werte) >= MIN_KLASSE and z["institution_type"]:
            z["klasse_median"] = round(st.median(werte), 1)
            z["percentile"] = perzentil(z["lag_days"], werte)
        else:
            # Zu dünn besetzt: die Klasse steht da, das Urteil nicht.
            z["klasse_median"] = ""
            z["percentile"] = ""

    zeilen.sort(key=lambda z: (z["lei"], z["refdate"], z["module"]))
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(zeilen)

    print(f"✓ {OUT}  ({len(zeilen)} Einreichungs-Kombinationen)")
    for zeile in bericht(zeilen):
        print("  " + zeile)
    return zeilen


def bericht(zeilen):
    aus = []
    belastbar = [z for z in zeilen if z["belastbar"] == "true"]
    aus.append(f"belastbar (nach Hub-Start faellig): {len(belastbar)} von {len(zeilen)}")
    je = collections.defaultdict(list)
    for z in zeilen:
        je[z["refdate"]].append(z["lag_days"])
    aus.append("Median-Lag je Stichtag (erste Einreichung):")
    for d in sorted(je):
        mark = "" if any(z["refdate"] == d and z["belastbar"] == "true" for z in zeilen) \
            else "   <- nachgereicht, keine Verspaetung"
        aus.append(f"  {d}  n={len(je[d]):>4}  median={st.median(je[d]):>5.0f}{mark}")
    typ = collections.defaultdict(list)
    for z in belastbar:
        typ[z["institution_type"] or "(ohne Klasse)"].append(z["lag_days"])
    if typ:
        aus.append("Am belastbaren Stichtag je Institutstyp:")
        for t, v in sorted(typ.items(), key=lambda x: -len(x[1])):
            aus.append(f"  {t:22} n={len(v):>4}  median={st.median(v):>4.0f}")
    nach = [z for z in zeilen if z["n_submissions"] > 1]
    aus.append(f"mit Wiedereinreichung: {len(nach)} "
               f"({100 * len(nach) / max(len(zeilen), 1):.0f} %) — "
               f"deshalb zaehlt die erste, nicht die letzte")
    return aus


if __name__ == "__main__":
    build()
