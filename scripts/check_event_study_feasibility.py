"""Trägt der Bestand eine Ereignisstudie? (#39)

Ausgabe: processed/event_study_feasibility.csv

## Was hier entschieden wird — und was nicht

#39 fragt, ob der Markt auf Pillar-3-Offenlegung reagiert. Das Issue setzt die
Machbarkeit selbst an den Anfang: *„Erst die Machbarkeit klären (Marktdatenquelle,
Anzahl isolierter Ereignisse), dann entscheiden. Wenn die isolierte Stichprobe zu
klein ausfällt, ist das ein legitimer Abbruchgrund — besser als eine Studie mit
20 Ereignissen."*

Dieses Skript beantwortet die **eine Hälfte, die aus unseren Daten beantwortbar
ist**: wie viele verwertbare Ereignisse es gibt. Die andere Hälfte — Kursdaten —
kann es nicht beantworten und behauptet es auch nicht.

## Ein Ereignis ist nicht eine Einreichung

Ein Institut reicht mehrere Module am selben Tag ein. Wer Einreichungen zählt,
zählt dasselbe Ereignis mehrfach und hält die Stichprobe für doppelt so gross,
wie sie ist. Verdichtet wird deshalb auf **(Institut, Tag)**.

## Isolation ist die eigentliche Hürde

Eine Einreichung, neben der zwei Tage später die nächste liegt, trägt kein
sauberes Ereignisfenster: der Kurseffekt lässt sich nicht zuordnen. Gezählt wird
deshalb, wie viele Ereignisse **allein** in ihrem Fenster stehen.

Das Issue nennt eine zweite Konfundierung, die dieses Skript NICHT auflösen
kann: Pillar-3-Offenlegung fällt oft mit dem Geschäftsbericht zusammen, und
dessen Datum liegt uns nicht vor. Die hier gezählten Zahlen sind deshalb eine
**obere Schranke** der verwertbaren Ereignisse, keine Schätzung.

## Und die Selektion ist messbar statt vermutet

Das Issue befürchtet, ein Aktien-Ereignisfenster decke nur börsennotierte
Institute ab. Seit #40 steht die Börsennotierung im Codebook, und die Befürchtung
ist beziffert: von 489 Instituten sind **69 belegt notiert** — und 257 tragen
gar keinen Wikidata-Eintrag, ihr Status ist damit **unbekannt und nicht
„nicht notiert"** (Arbeitsprinzip 3).

Aufruf: python3 scripts/check_event_study_feasibility.py
"""

from datetime import datetime
from pathlib import Path
import collections
import csv

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "interim" / "edap_recon" / "manifest_full.csv"
WIKIDATA = ROOT / "codebook" / "wikidata_entities.csv"
FINDINGS = ROOT / "interim" / "plausibility_findings.csv"
OUT = ROOT / "processed" / "event_study_feasibility.csv"

# Fenster in Kalendertagen um ein Ereignis. ±3 ist das engste, das ein
# übliches (-1,+1)-Handelstagsfenster noch trägt; ±10 ist streng.
FENSTER = (3, 5, 10, 21)

# Unter so vielen isolierten Ereignissen lohnt der Aufwand nicht. Das Issue
# nennt 20 als Beispiel für zu klein; 100 ist die Schwelle, ab der ein
# Mittelwert abnormaler Renditen überhaupt eine Chance auf Trennschärfe hat.
MIN_EREIGNISSE = 100

FELDER = ["fenster_tage", "ereignisse_gesamt", "isoliert", "isoliert_anteil",
          "isoliert_boersennotiert", "isoliert_mit_hoch_befund", "urteil"]


def tag_von(ts):
    """Der Kalendertag aus dem EDAP-Zeitstempel (`YYYYMMDDHHMMSSmmm`)."""
    try:
        return datetime.strptime(str(ts)[:8], "%Y%m%d").date()
    except (ValueError, TypeError):
        return None


def ereignisse_je_institut(zeilen):
    """{lei: {Tag}} — mehrere Module am selben Tag sind EIN Ereignis.

    Wer Einreichungen zählt statt Ereignisse, hält die Stichprobe für doppelt
    so gross: gemessen verdichten sich 4.278 Einreichungen auf 1.964 Tage.
    """
    aus = collections.defaultdict(set)
    for r in zeilen:
        t = tag_von(r.get("submission_ts"))
        lei = (r.get("lei") or "").strip()
        if t and lei:
            aus[lei].add(t)
    return aus


def isolierte(tage, fenster):
    """Die Tage, neben denen im Fenster kein weiterer desselben Instituts liegt."""
    s = sorted(tage)
    return [t for i, t in enumerate(s)
            if not any(abs((o - t).days) <= fenster
                       for j, o in enumerate(s) if j != i)]


def boersennotierte(pfad=None):
    """{lei} mit BELEGTER Börsennotierung.

    Wer keinen Wikidata-Eintrag hat, ist nicht „nicht notiert", sondern
    unbekannt — die Menge ist eine untere Schranke.
    """
    pfad = Path(pfad or WIKIDATA)
    if not pfad.exists():
        return set(), set()
    bekannt, notiert = set(), set()
    with pfad.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            lei = (r.get("lei") or "").strip()
            if not lei:
                continue
            bekannt.add(lei)
            if (r.get("boersennotiert") or "").strip().lower() == "ja":
                notiert.add(lei)
    return notiert, bekannt


def mit_hoch_befund(pfad=None):
    """{lei} mit mindestens einem `hoch`-Befund aus #17.

    Das ist die Behandlungsgruppe der schärferen Frage aus #39: reagiert der
    Markt STÄRKER, wenn die Offenlegung etwas Unangenehmes enthält?
    """
    pfad = Path(pfad or FINDINGS)
    if not pfad.exists():
        return set()
    with pfad.open(encoding="utf-8") as fh:
        return {r["lei"] for r in csv.DictReader(fh)
                if (r.get("severity") or "").strip().lower() == "hoch"}


def urteil_von(n_isoliert_notiert, schwelle=MIN_EREIGNISSE):
    """Die Entscheidung, die #39 verlangt — an EINER Zahl.

    Gewertet wird die Schnittmenge aus isoliert UND belegt börsennotiert: das
    ist die Stichprobe, die eine Aktien-Ereignisstudie wirklich hätte. Die
    Gesamtzahl der Ereignisse ist dafür irreführend, weil vier von fünf
    Instituten keine handelbare Aktie haben.
    """
    if n_isoliert_notiert >= schwelle:
        return "tragfaehig"
    if n_isoliert_notiert >= schwelle // 4:
        return "grenzwertig"
    return "zu klein"


def build():
    if not MANIFEST.exists():
        print(f"ERROR: {MANIFEST} fehlt")
        return []
    with MANIFEST.open(encoding="utf-8") as fh:
        zeilen = list(csv.DictReader(fh))
    je_institut = ereignisse_je_institut(zeilen)
    notiert, bekannt = boersennotierte()
    hoch = mit_hoch_befund()

    aus = []
    for f in FENSTER:
        iso = {l: isolierte(t, f) for l, t in je_institut.items()}
        ges = sum(len(t) for t in je_institut.values())
        n_iso = sum(len(v) for v in iso.values())
        n_bn = sum(len(v) for l, v in iso.items() if l in notiert)
        n_hb = sum(len(v) for l, v in iso.items() if l in notiert and l in hoch)
        aus.append({"fenster_tage": f, "ereignisse_gesamt": ges,
                    "isoliert": n_iso,
                    "isoliert_anteil": f"{n_iso / max(ges, 1):.3f}",
                    "isoliert_boersennotiert": n_bn,
                    "isoliert_mit_hoch_befund": n_hb,
                    "urteil": urteil_von(n_bn)})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(aus)

    print(f"✓ {OUT}  ({len(aus)} Fenster)")
    for s in bericht(aus, zeilen, je_institut, notiert, bekannt):
        print("  " + s)
    return aus


def bericht(aus, zeilen, je_institut, notiert, bekannt):
    leis = set(je_institut)
    ges = sum(len(t) for t in je_institut.values())
    b = [f"Einreichungen: {len(zeilen)} · verdichtet auf (Institut, Tag): {ges}",
         f"Institute: {len(leis)} · davon in Wikidata: {len(leis & bekannt)} · "
         f"belegt börsennotiert: {len(leis & notiert)}",
         f"⚠ {len(leis - bekannt)} Institute ohne Wikidata-Eintrag — ihr "
         f"Notierungsstatus ist UNBEKANNT, nicht „nicht notiert\".",
         "",
         f"{'Fenster':>8}  {'isoliert':>9}  {'Anteil':>7}  {'notiert':>8}  "
         f"{'+Befund':>8}  Urteil"]
    for r in aus:
        b.append(f"{'±' + str(r['fenster_tage']) + 'd':>8}  "
                 f"{r['isoliert']:>9}  {float(r['isoliert_anteil']) * 100:>6.0f} %  "
                 f"{r['isoliert_boersennotiert']:>8}  "
                 f"{r['isoliert_mit_hoch_befund']:>8}  {r['urteil']}")
    b += ["",
          "Die Spalte `notiert` ist die Stichprobe, die eine Aktien-Ereignis-",
          "studie hätte — nicht `isoliert`. Vier von fünf Instituten dieses",
          "Bestands haben keine handelbare Aktie (Sparkassen, Genossenschafts-",
          "und Förderbanken).",
          "",
          "⚠ OBERE SCHRANKE, keine Schätzung. Die zweite Konfundierung aus #39",
          "  ist damit NICHT aufgelöst: Pillar-3-Offenlegung fällt oft mit dem",
          "  Geschäftsbericht zusammen, und dessen Datum liegt uns nicht vor.",
          "  Jedes solche Ereignis fällt später zusätzlich heraus.",
          "",
          "⚠ Kursdaten sind keine offene Quelle. Diese Prüfung sagt, ob sich",
          "  die Beschaffung LOHNEN würde — sie ersetzt sie nicht."]
    return b


if __name__ == "__main__":
    build()
