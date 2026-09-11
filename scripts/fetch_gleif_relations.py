"""Konzernbeziehungen je LEI aus GLEIF (#32).

## Warum das die Voraussetzung für jedes Populationsaggregat ist

Der Bestand meldet 325 Institute nur konsolidiert (CON) und 148 nur auf
Einzelinstitutsebene (IND). Die IND-Melder sind fast alle Töchter von irgendwem
— **von wem, steht nirgends in den Daten.** Wer über alle Institute summiert,
zählt Konzernmutter und Tochter doppelt, ohne dass jemand sagen kann, wie oft.

## „Kein Parent" ist nicht „eigenständig"

Das ist die zentrale Unterscheidung, und GLEIF trägt sie mit. Antwortet der
Parent-Endpunkt mit 404, heisst das nicht, dass keine Mutter existiert — es
heisst, dass keine *hinterlegt* ist. Daneben gibt es die **Reporting Exception**
mit einem Grund, und die Gründe sagen Verschiedenes:

    NO_KNOWN_PERSON          es gibt wirklich keine Mutter  -> eigenständig
    NON_CONSOLIDATING        niemand konsolidiert das Institut -> eigenständig
    NO_LEI                   es GIBT eine Mutter, nur ohne LEI -> NICHT eigenständig
    LEGAL_OBSTACLES          Meldung rechtlich verhindert      -> unbekannt
    BINDING_LEGAL_COMMITMENTS, CONSENT_NOT_OBTAINED, …        -> unbekannt

Deshalb wird der Grund mitgeschrieben, nicht nur „hat/hat keinen Parent". Ein
Graph, der `NO_LEI` wie `NO_KNOWN_PERSON` behandelt, behauptet Eigenständigkeit,
wo die Quelle das Gegenteil sagt (Arbeitsprinzip 3).

## Untere Schranke, kein vollständiges Bild

GLEIF-Meldung ist teils freiwillig. Der Graph darf deshalb nur **positiv belegte
Kanten** behaupten und muss auch so beschriftet werden — er ist eine untere
Schranke der Konzernverflechtung.

Ausserdem sind GLEIF-Beziehungen **rechtliche** Eigentumsverhältnisse. Der
aufsichtliche Konsolidierungskreis nach CRR ist etwas anderes und weicht ab.

Ausgabe: processed/lei_relations.csv
Aufruf:  python3 scripts/fetch_gleif_relations.py [--refresh]
"""

from pathlib import Path
import csv
import json
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
META = ROOT / "processed" / "entity_meta.csv"
OUT = ROOT / "processed" / "lei_relations.csv"

API = "https://api.gleif.org/api/v1/lei-records"
FELDER = ["lei", "direct_parent_lei", "direct_parent_status", "direct_parent_reason",
          "ultimate_parent_lei", "ultimate_parent_status", "ultimate_parent_reason"]

# Gründe, die Eigenständigkeit tatsächlich belegen — alles andere heisst
# „unbekannt", nicht „eigenständig".
EIGENSTAENDIG = {"NO_KNOWN_PERSON", "NON_CONSOLIDATING", "NO_KNOWN_PERSON_ENTITY"}


def _get(url, versuche=3):
    """(status, payload). 404 ist eine Antwort, kein Fehler.

    Wiederholung mit Backoff: von 60 Probeabrufen scheiterten 3 sporadisch.
    Ohne sie fehlten still einzelne Kanten — und eine fehlende Kante sieht aus
    wie Eigenständigkeit.
    """
    for i in range(versuche):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, None
            if e.code in (429, 500, 502, 503, 504) and i < versuche - 1:
                time.sleep(2 ** i)
                continue
            raise
        except Exception:
            if i == versuche - 1:
                raise
            time.sleep(2 ** i)
    raise RuntimeError(f"unerreichbar nach {versuche} Versuchen: {url}")


def beziehung(lei, art):
    """art: 'direct' | 'ultimate'. -> (parent_lei, status, reason)."""
    s, d = _get(f"{API}/{lei}/{art}-parent")
    if s == 200 and (d.get("data") or {}).get("attributes", {}).get("lei"):
        return d["data"]["attributes"]["lei"], "parent", ""
    s, d = _get(f"{API}/{lei}/{art}-parent-reporting-exception")
    if s == 200 and d.get("data"):
        a = d["data"]["attributes"]
        return "", "exception", a.get("reason") or ""
    # Weder Parent noch Exception: GLEIF sagt zu diesem LEI schlicht nichts.
    return "", "nichts_gemeldet", ""


def vorhandene():
    if not OUT.exists():
        return {}
    with OUT.open(encoding="utf-8") as fh:
        return {r["lei"]: r for r in csv.DictReader(fh)}


def build(refresh=False, pause=0.05):
    with META.open(encoding="utf-8") as fh:
        leis = sorted({r["lei"] for r in csv.DictReader(fh) if r["lei"]})
    schon = {} if refresh else vorhandene()
    zeilen, neu = [], 0

    for i, lei in enumerate(leis, 1):
        if lei in schon:
            zeilen.append(schon[lei])
            continue
        dp, dps, dpr = beziehung(lei, "direct")
        up, ups, upr = beziehung(lei, "ultimate")
        zeilen.append({"lei": lei,
                       "direct_parent_lei": dp, "direct_parent_status": dps,
                       "direct_parent_reason": dpr,
                       "ultimate_parent_lei": up, "ultimate_parent_status": ups,
                       "ultimate_parent_reason": upr})
        neu += 1
        if neu % 50 == 0:
            print(f"  … {i}/{len(leis)}")
        time.sleep(pause)

    zeilen.sort(key=lambda r: r["lei"])
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(zeilen)

    bestand = set(leis)
    kanten = [r for r in zeilen if r["direct_parent_lei"] in bestand]
    ukanten = [r for r in zeilen if r["ultimate_parent_lei"] in bestand]
    mit_parent = [r for r in zeilen if r["direct_parent_lei"]]
    belegt_eigen = [r for r in zeilen
                    if r["direct_parent_reason"] in EIGENSTAENDIG]
    unbekannt = [r for r in zeilen if not r["direct_parent_lei"]
                 and r["direct_parent_reason"] not in EIGENSTAENDIG]

    print(f"✓ {OUT}  ({len(zeilen)} Institute, {neu} neu abgerufen)")
    print(f"  mit direkter Mutter (irgendwo) : {len(mit_parent):>4}")
    print(f"  Mutter SELBST im Bestand       : {len(kanten):>4}  <- Doppelzählung")
    print(f"  Ultimate-Mutter im Bestand     : {len(ukanten):>4}")
    print(f"  Eigenständigkeit belegt        : {len(belegt_eigen):>4}")
    print(f"  unbekannt (keine Aussage)      : {len(unbekannt):>4}")
    return zeilen


if __name__ == "__main__":
    build(refresh="--refresh" in sys.argv)
