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


def _get(url, versuche=6):
    """(status, payload). 404 ist eine Antwort, kein Fehler.

    Sechs Versuche mit Backoff, nicht drei: der erste Vollabruf starb nach rund
    1.000 Anfragen an `Connection reset by peer`. Bei 1.500 Abrufen am Stück ist
    ein zurückgesetzter Verbindungsaufbau normal, kein Ausnahmefall.

    Eine fehlende Kante sieht aus wie Eigenständigkeit — deshalb wird hier
    hartnäckig wiederholt statt stillschweigend weiterzugehen.
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


def _schreibe(zeilen):
    zeilen = sorted(zeilen, key=lambda r: r["lei"])
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(zeilen)


def build(refresh=False, pause=0.05, checkpoint=25):
    """Der Abruf schreibt UNTERWEGS, nicht erst am Ende.

    Der erste Vollabruf lief rund 30 Minuten und starb dann an einem
    zurückgesetzten Verbindungsaufbau — ohne eine einzige Zeile Ergebnis. Die
    Zusage „idempotent, holt nur Neuzugänge" trägt nur, wenn Teilergebnisse den
    Abbruch überleben. Jetzt steht nach spätestens `checkpoint` Instituten der
    Zwischenstand auf der Platte, und ein neuer Aufruf setzt dort fort.
    """
    with META.open(encoding="utf-8") as fh:
        leis = sorted({r["lei"] for r in csv.DictReader(fh) if r["lei"]})
    schon = {} if refresh else vorhandene()
    zeilen = [schon[l] for l in leis if l in schon]
    offen = [l for l in leis if l not in schon]
    if schon:
        print(f"  {len(schon)} bereits abgerufen, {len(offen)} offen")
    neu = 0

    try:
        for lei in offen:
            dp, dps, dpr = beziehung(lei, "direct")
            up, ups, upr = beziehung(lei, "ultimate")
            zeilen.append({"lei": lei,
                           "direct_parent_lei": dp, "direct_parent_status": dps,
                           "direct_parent_reason": dpr,
                           "ultimate_parent_lei": up, "ultimate_parent_status": ups,
                           "ultimate_parent_reason": upr})
            neu += 1
            if neu % checkpoint == 0:
                _schreibe(zeilen)
                print(f"  … {len(zeilen)}/{len(leis)} gesichert")
            time.sleep(pause)
    except Exception as e:
        _schreibe(zeilen)
        print(f"⚠ abgebrochen nach {len(zeilen)}/{len(leis)}: {e}")
        print(f"  Zwischenstand gesichert — erneuter Aufruf setzt fort.")
        raise

    _schreibe(zeilen)

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
