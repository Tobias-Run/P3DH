"""Zwei geplante Läufe hintereinander rot? Dann muss es jemand erfahren.

Ausgabe: Exit 0 und eine Entscheidung auf stdout; die Meldung selbst erzeugt
der Workflow-Schritt.

## Wozu

Seit #8 läuft die Pipeline montags ohne Aufsicht. Ein roter Lauf fällt damit
niemandem auf — und genau das ist der Zustand, den dieses Projekt sonst überall
bekämpft: ein Ausfall, der sich als Stille meldet.

Ein EINZELNER roter Lauf ist dabei kein Alarm wert. EDAP ist zeitweise nicht
erreichbar, ein Runner kann ausfallen, Wikidata drosselt. Solche Läufe heilen
sich in der Woche darauf von selbst. **Zwei hintereinander tun das nicht** —
dann liegt es an der Kette, nicht am Wetter.

## Nur GEPLANTE Läufe zählen

Ein manuell gestarteter Lauf, der fehlschlägt, ist kein unbemerkter Ausfall:
jemand hat ihn gestartet und sieht das Ergebnis. Er zählt deshalb nicht in die
Strecke — sonst löste ein Experiment am Freitag eine Meldung aus, die niemand
braucht, und die echte Meldung ginge im Rauschen unter.

## Die Falle, gegen die das hier geschrieben ist

Wenn die Abfrage der Lauf-Historie scheitert, ist die Strecke **unbekannt** —
nicht null. Ein `except: return False` hiesse: die Überwachung fällt aus und
meldet sich als „alles in Ordnung". Bei unbekannter Historie wird deshalb
gemeldet, und die Meldung sagt selbst, dass sie auf unvollständiger Kenntnis
beruht. Ein überflüssiger Alarm kostet eine Minute; ein ausgefallener Alarm
kostet Wochen.

Aufruf (im Workflow):
    python3 scripts/check_run_streak.py --conclusion failure
"""

from pathlib import Path
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent

# So viele geplante Fehlläufe hintereinander, bevor gemeldet wird. Zwei, weil
# die Pipeline wöchentlich läuft: gemeint sind zwei Wochen nacheinander.
SCHWELLE = 2

# Woran eine offene Meldung wiedererkannt wird. Bewusst über den Titel und
# nicht über ein Label: ein Label muss im Repository existieren, sonst schlägt
# das Anlegen fehl — und zwar an der Stelle, die gerade melden soll.
MARKE = "Pipeline: zwei geplante Läufe hintereinander fehlgeschlagen"

# Wer die Meldung bekommt. Als Zuweisung UND als Erwähnung im Text: die
# Zuweisung erzeugt die Benachrichtigung zuverlässig, die Erwähnung macht beim
# Lesen sofort klar, an wen sie gerichtet ist.
EIGNER = "@Tobias-Run"

# `cancelled` ist KEIN Fehlschlag: jemand hat abgebrochen, das ist eine
# Entscheidung. `timed_out` und `startup_failure` sind welche.
FEHLSCHLAG = {"failure", "timed_out", "startup_failure"}

API = "https://api.github.com"


def ist_fehlschlag(conclusion):
    return (conclusion or "").lower() in FEHLSCHLAG


def geplante(laeufe):
    """Nur die Läufe, die der Zeitplan gestartet hat — neueste zuerst."""
    return [l for l in laeufe if (l.get("event") or "") == "schedule"]


def strecke(laeufe):
    """Wie viele geplante Läufe am Stück zuletzt rot waren.

    `laeufe` kommt neueste-zuerst. Gezählt wird ab vorn bis zum ersten Lauf,
    der nicht fehlgeschlagen ist. Noch laufende Einträge (ohne `conclusion`)
    beenden die Zählung ebenfalls — ein Lauf ohne Ergebnis ist kein Beleg.
    """
    n = 0
    for l in geplante(laeufe):
        if not ist_fehlschlag(l.get("conclusion")):
            break
        n += 1
    return n


def soll_melden(laeufe, offene_meldung, schwelle=SCHWELLE, historie_bekannt=True):
    """(melden?, Begründung) — die ganze Entscheidung an einer Stelle.

    Eine bereits offene Meldung verhindert eine zweite: sonst stünde nach einem
    Monat viermal dasselbe im Issue-Tracker und die Meldung verlöre genau die
    Dringlichkeit, für die sie da ist.
    """
    if offene_meldung:
        return False, ("Es liegt bereits eine offene Meldung vor "
                       f"(#{offene_meldung}) — keine zweite.")
    if not historie_bekannt:
        # Siehe Modul-Docstring: unbekannt ist nicht null.
        return True, ("Die Lauf-Historie war nicht abrufbar. Es wird gemeldet, "
                      "weil eine stumme Überwachung schlimmer ist als ein "
                      "überflüssiger Alarm.")
    n = strecke(laeufe)
    if n >= schwelle:
        return True, (f"{n} geplante Läufe hintereinander fehlgeschlagen "
                      f"(Schwelle: {schwelle}).")
    return False, (f"{n} geplanter Fehllauf am Stück — unter der Schwelle von "
                   f"{schwelle}. Ein einzelner roter Lauf heilt sich oft in "
                   f"der Woche darauf.")


def meldung(grund, lauf_url="", workflow_url="", wer=EIGNER, bestaetigt=True):
    """(Titel, Text) der Meldung — beides HIER, nicht im Workflow.

    Der Titel muss mit `MARKE` beginnen, weil die Suche nach einer bereits
    offenen Meldung darüber läuft. Stünde er im Workflow und die Marke hier,
    könnten beide auseinanderlaufen — und das Ergebnis wäre kein Fehler,
    sondern jede Woche ein neues Issue. Aus einer Quelle erzeugt, ist das
    konstruktiv ausgeschlossen.

    `bestaetigt=False` heisst: gemeldet wird, weil die Historie nicht abrufbar
    war. Dann darf der Text die Strecke NICHT behaupten. Eine Meldung, die mehr
    weiss als ihre Grundlage hergibt, ist derselbe Fehler wie eine Kennzahl,
    die mehr misst als sie sagt — nur schlimmer, weil sie jemanden losschickt.
    """
    if bestaetigt:
        kopf = (f"{wer} — der wöchentliche Pipeline-Lauf ist **zweimal "
                f"hintereinander** fehlgeschlagen.")
    else:
        kopf = (f"{wer} — der wöchentliche Pipeline-Lauf ist fehlgeschlagen, "
                f"und **ob es der zweite in Folge war, liess sich nicht "
                f"feststellen**: die Lauf-Historie war nicht abrufbar. Diese "
                f"Meldung entsteht vorsorglich.")
    zeilen = [
        kopf,
        "",
        "Ein einzelner roter Lauf wird bewusst nicht gemeldet: EDAP ist zeitweise "
        "nicht erreichbar, ein Runner kann ausfallen, Wikidata drosselt. Solche "
        "Läufe heilen sich in der Woche darauf. Zwei hintereinander tun das "
        "nicht — dann liegt es an der Kette.",
        "",
        f"**Befund:** {grund}",
        "",
    ]
    if lauf_url:
        zeilen.append(f"- Dieser Lauf: {lauf_url}")
    if workflow_url:
        zeilen.append(f"- Alle Läufe: {workflow_url}")
    zeilen += [
        "",
        "Solange diese Meldung offen ist, wird keine zweite angelegt. Nach dem "
        "Beheben schliessen — schlägt es danach erneut zweimal fehl, entsteht "
        "eine neue.",
    ]
    return MARKE, "\n".join(zeilen)


# --- alles ab hier redet mit GitHub -----------------------------------------

def _hole(pfad, token):
    req = urllib.request.Request(
        API + pfad, headers={"Accept": "application/vnd.github+json",
                             "User-Agent": "p3dh-monitor",
                             **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=45) as fh:
        return json.load(fh)


def lade_laeufe(repo, workflow, token, limit=20):
    d = _hole(f"/repos/{repo}/actions/workflows/{workflow}/runs"
              f"?per_page={limit}&status=completed", token)
    return [{"event": r.get("event"), "conclusion": r.get("conclusion"),
             "id": r.get("id"), "created_at": r.get("created_at"),
             "url": r.get("html_url")} for r in d.get("workflow_runs", [])]


def offene_meldung(repo, token, marke=MARKE):
    """Nummer einer bereits offenen Meldung, sonst None."""
    d = _hole(f"/repos/{repo}/issues?state=open&per_page=100", token)
    for i in d:
        if i.get("pull_request"):
            continue
        if (i.get("title") or "").startswith(marke):
            return i.get("number")
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--conclusion", required=True,
                   help="Ergebnis des LAUFENDEN Laufs (failure/success/…)")
    p.add_argument("--event", default=os.environ.get("GITHUB_EVENT_NAME", ""),
                   help="Auslöser des laufenden Laufs")
    p.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    p.add_argument("--workflow", default="pipeline.yml")
    p.add_argument("--titel-datei", default="interim/meldung_titel.txt")
    p.add_argument("--text-datei", default="interim/meldung.md")
    args = p.parse_args()

    if args.event != "schedule":
        print("entscheidung=nein")
        print("grund=Kein geplanter Lauf — ein manuell gestarteter Fehlschlag "
              "ist kein unbemerkter Ausfall.")
        return 0

    token = os.environ.get("GITHUB_TOKEN", "")
    historie_bekannt, laeufe, offen = True, [], None
    try:
        laeufe = lade_laeufe(args.repo, args.workflow, token)
        offen = offene_meldung(args.repo, token)
    except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
        historie_bekannt = False
        print(f"warnung=Lauf-Historie nicht abrufbar: {e}", file=sys.stderr)

    # Der laufende Lauf steht noch nicht (oder nicht mit Ergebnis) in der
    # Historie — er wird vorn angestellt, sonst zählte die Strecke ihn nicht.
    aktuell = [{"event": "schedule", "conclusion": args.conclusion}]
    melden, grund = soll_melden(aktuell + laeufe, offen,
                                historie_bekannt=historie_bekannt)

    if melden:
        server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
        run_id = os.environ.get("GITHUB_RUN_ID", "")
        titel, text = meldung(
            grund,
            lauf_url=f"{server}/{args.repo}/actions/runs/{run_id}" if run_id else "",
            workflow_url=f"{server}/{args.repo}/actions/workflows/{args.workflow}",
            bestaetigt=historie_bekannt)
        for pfad, inhalt in ((args.titel_datei, titel), (args.text_datei, text)):
            ziel = Path(pfad)
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_text(inhalt, encoding="utf-8")

    # Als GITHUB_OUTPUT-Zeilen: der Workflow liest `entscheidung` direkt.
    print(f"entscheidung={'ja' if melden else 'nein'}")
    print(f"grund={grund}")
    print(f"strecke={strecke(aktuell + laeufe) if historie_bekannt else 'unbekannt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
