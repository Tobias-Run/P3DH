"""Offenlegungsfrequenz je Template, gemessen statt aus der CRR abgeschrieben (#34).

Ausgabe: processed/disclosure_frequency.csv

## Warum das gebraucht wird

Fast jede Auswertung über Stichtage hinweg stolpert sonst über den Meldekalender.
Ein Template, das halbjährlich offengelegt wird, „verschwindet" zwischen den
Quartalen — und sieht dabei aus wie eine Auslassung (#43) oder wie ein Sprung
(#36). Ohne dieses Modell ist beides nicht zu unterscheiden.

Die Frequenz steht in Art. 433a–c CRR. Sie hier aus dem Gesetzestext zu kodieren
wäre möglich, aber schwächer: gemessen wird, was Institute TUN, und Abweichungen
davon sind selbst ein Befund.

## Die Konstruktion: Muster je Institut, nicht Quote je Population

Die naheliegende Messung — der Anteil der Melder je (Template, Stichtag) — ist
unbrauchbar, und zwar aus demselben Grund wie in #43: **ein Drittel der Quoten
liegt im mehrdeutigen Mittelfeld** (32 % zwischen 20 und 80 %). Eine Schwelle
darauf erfände eine Trennung, die die Zahlen nicht hergeben.

Gemessen wird deshalb das MUSTER eines einzelnen Instituts über die vier
Stichtage — eine Vierer-Kette aus Ja/Nein, in der Reihenfolge

    2025-06-30 · 2025-09-30 · 2025-12-31 · 2026-03-31

Das ist scharf. Über 4.407 (Institut, Template)-Paare mit allen vier Stichtagen
fallen **96,5 % in genau vier Muster**:

    1010   36,2 %   halbjährlich     (Halbjahr und Jahresende)
    0000   33,6 %   nie              (Template trifft dieses Institut nicht)
    0010   15,6 %   jährlich         (nur Jahresende)
    1111   11,1 %   vierteljährlich
    Rest    3,5 %   uneinheitlich

Ein Anteil, den eine gemittelte Quote nie gezeigt hätte.

## Drei Vorbehalte, und der erste ist der grösste

**1. Nur 82 der 476 Institute tragen überhaupt ein Muster bei.** Ein Muster
braucht alle vier Stichtage — und wer nur zum Jahresende meldet, hat keines.
Das ist keine Stichprobe, sondern eine Auswahl nach genau der Eigenschaft, die
gemessen wird. Für `Other highest EEA` bleiben ganze **8 Paare** übrig; für
diese Klasse sagt die Datei nichts.

**2. Vier Stichtage unterscheiden „jährlich" nicht von „einmalig".** Ein
Template, das nur am 2025-12-31 erscheint, kann jährlich gemeldet werden — oder
einmalig. Das entscheidet erst die nächste Welle.

**3. Ein Muster ist keine Pflicht.** `0000` heisst „dieses Institut legt das
Template nie offen", nicht „es müsste nicht". Die Trennung von Nichtanwendbarkeit
und Ermessen ist und bleibt offen (#43).

## Was ausdrücklich GEPRÜFT und nicht angenommen ist

Der Stichtag 2026-03-31 ist zugleich der einzige mit Reporting Framework 4.2 —
beide Effekte sind im Bestand nicht trennbar (`docs/datensatz.md`). Für diese
Messung wäre das fatal, wenn der Meldebogen sich geändert hätte: ein Template,
das in 4.2 anders heisst, sähe aus wie eines, das im ersten Quartal nicht mehr
gemeldet wird.

Nachgemessen trägt der Filing-Indicator-Bogen an **allen** Stichtagen dieselben
114 Templates, keines fällt weg, keines kommt dazu. Der Meldewerkswechsel
verzerrt die Frequenz damit nicht.

Aufruf: python3 scripts/build_disclosure_frequency.py
"""

from pathlib import Path
import collections
import csv
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
INDICATORS = ROOT / "processed" / "filing_indicators.csv"
OUT = ROOT / "processed" / "disclosure_frequency.csv"

# Die vier Stichtage in fester Reihenfolge — sie IST das Muster. 2025-10-31
# fehlt bewusst: drei Reports, ein Sonderstichtag, kein Quartalsraster.
STICHTAGE = ("2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31")

# Muster -> Frequenz. Nur die vier, die 96,5 % der Paare abdecken; alles andere
# heisst `uneinheitlich` und wird NICHT in eine der vier hineingezwungen.
MUSTER = {
    "1111": "vierteljaehrlich",
    "1010": "halbjaehrlich",
    "0010": "jaehrlich",
    "0000": "nie",
}

# Ab welchem Anteil das Modalmuster als die Frequenz einer Koordinate gilt.
# Darunter sagt die Koordinate nichts — die Institute sind sich uneinig, und
# eine knappe Mehrheit ist keine Regel.
MODAL_ANTEIL = 0.6

# Unter so vielen Instituten trägt ein Modalmuster nichts. Gleiche Begründung
# wie MIN_PEER in build_omission_profile.py.
MIN_INSTITUTE = 5

FELDER = ["institution_type", "template_id", "template_title", "n_institute",
          "frequenz", "muster_modal", "anteil_modal", "eindeutig",
          "n_vierteljaehrlich", "n_halbjaehrlich", "n_jaehrlich", "n_nie",
          "n_uneinheitlich"]


def muster_von(belegung):
    """{Stichtag: bool} -> '1010'. None, wenn nicht alle vier Stichtage da sind.

    Die Unvollständigkeit ist kein Randfall, sondern der Normalfall: nur 4.407
    von 38.907 Paaren haben alle vier. Ein Muster aus zwei Stichtagen zu bilden
    hiesse, `10` als „halbjährlich" zu lesen — es könnte genauso gut ein
    vierteljährliches Template sein, dessen andere Stichtage fehlen.
    """
    if any(d not in belegung for d in STICHTAGE):
        return None
    return "".join("1" if belegung[d] else "0" for d in STICHTAGE)


def frequenz_von(muster):
    """Muster -> Frequenzname. Unbekannte Muster bleiben `uneinheitlich`."""
    return MUSTER.get(muster, "uneinheitlich")


def koordinate(muster_liste):
    """Alle Muster einer (Klasse, Template)-Koordinate -> Urteil.

    Liefert (frequenz, modalmuster, anteil, eindeutig).
    """
    if not muster_liste:
        return ("", "", 0.0, False)
    zaehl = collections.Counter(muster_liste)
    modal, n = zaehl.most_common(1)[0]
    anteil = n / len(muster_liste)
    eindeutig = len(muster_liste) >= MIN_INSTITUTE and anteil >= MODAL_ANTEIL
    # Ohne Eindeutigkeit KEINE Frequenz. Eine Koordinate, in der sich die
    # Institute nicht einig sind, trägt keine — und ein Modalmuster von 40 %
    # als Frequenz auszugeben wäre eine erfundene Regel.
    return (frequenz_von(modal) if eindeutig else "uneinheitlich",
            modal, round(anteil, 3), eindeutig)


def lade(con):
    """(entityID, Klasse, Template, Stichtag, reported) für die vier Stichtage."""
    from determinism import ordered_query as ordered

    tage = ",".join(f"'{d}'" for d in STICHTAGE)
    return ordered(con, f"""
        WITH meta AS (
          SELECT DISTINCT entityID, institution_type FROM '{PARQUET}'
          WHERE institution_type IS NOT NULL
        ),
        titel AS (
          SELECT template_id, max(template_title) AS t FROM '{PARQUET}'
          WHERE template_title IS NOT NULL GROUP BY template_id
        )
        SELECT f.entityID, m.institution_type, f.template_id,
               CAST(f.refPeriod AS VARCHAR) AS refPeriod, f.reported,
               max(t.t) AS titel
        FROM '{INDICATORS}' f
        JOIN meta m ON m.entityID = f.entityID
        LEFT JOIN titel t ON t.template_id = f.template_id
                          OR t.template_id LIKE f.template_id || '.%'
        WHERE CAST(f.refPeriod AS VARCHAR) IN ({tage})
        GROUP BY f.entityID, m.institution_type, f.template_id, f.refPeriod, f.reported
        ORDER BY f.entityID, m.institution_type, f.template_id, f.refPeriod, f.reported
    """, "Filing-Indicators je Stichtag")


def build():
    import duckdb

    con = duckdb.connect()
    belegung = collections.defaultdict(dict)
    klasse, titel = {}, {}
    for eid, it, tid, rp, rep, t in lade(con):
        belegung[(eid, tid)][rp] = bool(rep)
        klasse[(eid, tid)] = it
        if t and tid not in titel:
            titel[tid] = t

    je_koordinate = collections.defaultdict(list)
    for k, b in belegung.items():
        m = muster_von(b)
        if m is None:
            continue                      # nicht alle vier Stichtage
        je_koordinate[(klasse[k], k[1])].append(m)

    aus = []
    for (it, tid), muster in sorted(je_koordinate.items()):
        freq, modal, anteil, eindeutig = koordinate(muster)
        zaehl = collections.Counter(frequenz_von(m) for m in muster)
        aus.append({
            "institution_type": it, "template_id": tid,
            "template_title": titel.get(tid, ""),
            "n_institute": len(muster), "frequenz": freq,
            "muster_modal": modal, "anteil_modal": anteil,
            "eindeutig": "ja" if eindeutig else "nein",
            "n_vierteljaehrlich": zaehl["vierteljaehrlich"],
            "n_halbjaehrlich": zaehl["halbjaehrlich"],
            "n_jaehrlich": zaehl["jaehrlich"],
            "n_nie": zaehl["nie"],
            "n_uneinheitlich": zaehl["uneinheitlich"],
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(aus)

    print(f"✓ {OUT}  ({len(aus)} Koordinaten)")
    for s in bericht(aus, belegung, je_koordinate):
        print("  " + s)
    return aus


def bericht(aus, belegung, je_koordinate):
    z = []
    voll = sum(1 for b in belegung.values() if muster_von(b) is not None)
    z.append(f"(Institut,Template)-Paare: {len(belegung):,} · mit allen vier "
             f"Stichtagen: {voll:,} ({100*voll/max(len(belegung),1):.1f} %)")

    alle = [m for lst in je_koordinate.values() for m in lst]
    mv = collections.Counter(alle)
    z.append("häufigste Muster (06-30 · 09-30 · 12-31 · 03-31):")
    for m, n in mv.most_common(5):
        z.append(f"  {m}  {n:5d}  {100*n/len(alle):5.1f} %  {frequenz_von(m)}")
    bekannt = sum(n for m, n in mv.items() if m in MUSTER)
    z.append(f"  in einem der vier bekannten Muster: {100*bekannt/len(alle):.1f} %")

    f = collections.Counter(a["frequenz"] for a in aus)
    z.append("Koordinaten je Frequenz: " + "  ".join(
        f"{k}={v}" for k, v in sorted(f.items())))
    e = sum(1 for a in aus if a["eindeutig"] == "ja")
    z.append(f"eindeutig (>= {MIN_INSTITUTE} Institute, Modalanteil "
             f">= {MODAL_ANTEIL:.0%}): {e} von {len(aus)}")

    je_kl = collections.defaultdict(collections.Counter)
    for a in aus:
        je_kl[a["institution_type"]][a["frequenz"]] += 1
    z.append("je Grössenklasse:")
    for kl in sorted(je_kl):
        n = sum(je_kl[kl].values())
        z.append(f"  {kl[:24]:26s} {n:3d} Koordinaten  " + "  ".join(
            f"{k}={v}" for k, v in sorted(je_kl[kl].items())))

    beispiele = [a for a in aus if a["eindeutig"] == "ja"
                 and a["frequenz"] in ("vierteljaehrlich", "halbjaehrlich", "jaehrlich")]
    if beispiele:
        z.append("Beispiele (eindeutige Koordinaten):")
        for a in sorted(beispiele, key=lambda x: (x["frequenz"], x["template_id"]))[:8]:
            z.append(f"  {a['template_id']:8s} {a['institution_type'][:18]:20s} "
                     f"{a['frequenz']:16s} {a['anteil_modal']:.0%} von "
                     f"{a['n_institute']:3d}  {str(a['template_title'])[:34]}")
    return z


if __name__ == "__main__":
    build()
