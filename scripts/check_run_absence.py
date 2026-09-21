"""Ein Lauf, der gar nicht feuert, ist unsichtbar (#8, der blinde Fleck).

`check_run_streak.py` zählt **fehlgeschlagene** geplante Läufe. Sein Job hängt
an `failure() && github.event_name == 'schedule'` — er existiert also nur,
wenn der Lauf stattgefunden hat. Feuert der Cron überhaupt nicht, gibt es
keinen Fehlschlag, keinen Job und keine Meldung.

**Die Überwachung erklärt sich bei Abwesenheit für erfüllt** — genau der
Fehlermodus, gegen den sie gebaut wurde. Aufgefallen ist das am 2026-09-21:
der Montagslauf fehlte um 05:37 UTC noch vollständig, und nichts im Projekt
hätte davon berichtet. (Er kam dann um 09:21, 5 h 21 verspätet — GitHubs
Scheduler ist ausdrücklich „best effort".)

## Wonach dieser Wächter fragt

Nicht „ist ein Lauf rot?", sondern **„wann gab es zuletzt überhaupt einen
geplanten Lauf?"** Liegt der länger zurück als `SCHWELLE_TAGE`, wird gemeldet.

Das ist kein theoretisches Risiko. GitHub **deaktiviert geplante Workflows in
Repositories, in denen 60 Tage lang nichts passiert** — lautlos. Dazu kommen
verschluckte Einzelläufe, ein versehentlich deaktivierter Workflow und ein
Tippfehler im Cron-Ausdruck, der keine Syntaxprüfung auslöst, weil er
syntaktisch gültig ist.

## Die Schwelle

Die Pipeline läuft wöchentlich (montags 04:00 UTC). **9 Tage** lassen einen
Stichtag ausfallen plus zwei Tage Nachsicht für die Verspätung, die der
Scheduler sich regelmässig nimmt. Bei einem ausgefallenen Montag meldet dieser
Wächter am Mittwoch darauf.

## Was er NICHT kann, und das gehört dazu

Er läuft selbst als geplanter Workflow auf derselben Plattform. **Fällt GitHubs
Scheduler vollständig aus, fällt er mit aus.** Ein Wächter im selben System
kann einen Totalausfall dieses Systems nicht melden; er meldet den
realistischen Fall — dass *dieser eine* Zeitplan still stirbt, während der Rest
weiterläuft. Ein Wächter ausserhalb wäre stärker, wäre aber ein zweiter Ort mit
eigenen Zugangsdaten und eigener Pflege.

Dieselbe Falle wie im Streckenwächter gilt auch hier: **ist die Historie nicht
abrufbar, ist sie unbekannt, nicht leer.** Dann wird gemeldet, und die Meldung
sagt, worauf sie beruht.

Aufruf (im Workflow):
    python3 scripts/check_run_absence.py
"""

from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import os
import sys
import urllib.error

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# Die Plattform-Bausteine kommen aus dem Streckenwächter — dieselbe API,
# dieselbe Wiedererkennung offener Meldungen. Verdoppelt wären sie zwei
# Stellen, die auseinanderlaufen können.
from check_run_streak import _hole, offene_meldung as _offene  # noqa: E402

# Wöchentlicher Cron plus zwei Tage Nachsicht für die Verspätung, die sich
# GitHubs Scheduler regelmässig nimmt (am 2026-09-21 waren es 5 h 21).
SCHWELLE_TAGE = 9

MARKE = "Pipeline: seit Tagen kein geplanter Lauf"

EIGNER = "@Tobias-Run"


def zeit(wert):
    """ISO-8601 aus der GitHub-API -> aware datetime. Unlesbar -> None."""
    if not wert:
        return None
    try:
        return datetime.fromisoformat(str(wert).replace("Z", "+00:00"))
    except ValueError:
        return None


def juengster_geplanter(laeufe):
    """Zeitpunkt des letzten GEPLANTEN Laufs — egal mit welchem Ergebnis.

    Ein roter Lauf ist hier ausdrücklich ein Lebenszeichen: er beweist, dass
    der Zeitplan feuert. Ob er *gelingt*, beantwortet der Streckenwächter.
    """
    zeiten = [zeit(l.get("created_at")) for l in laeufe
              if (l.get("event") or "") == "schedule"]
    zeiten = [z for z in zeiten if z]
    return max(zeiten) if zeiten else None


def alter_tage(zeitpunkt, jetzt):
    if zeitpunkt is None:
        return None
    return (jetzt - zeitpunkt).total_seconds() / 86400.0


def soll_melden(laeufe, offen, jetzt, schwelle=SCHWELLE_TAGE,
                historie_bekannt=True):
    """(melden?, Begründung) — die ganze Entscheidung an einer Stelle."""
    if offen:
        return False, (f"Es liegt bereits eine offene Meldung vor (#{offen}) "
                       f"— keine zweite.")
    if not historie_bekannt:
        return True, ("Die Lauf-Historie war nicht abrufbar. Es wird gemeldet, "
                      "weil eine stumme Überwachung schlimmer ist als ein "
                      "überflüssiger Alarm.")
    letzter = juengster_geplanter(laeufe)
    if letzter is None:
        # Der Fall, den es am 2026-09-21 fast gegeben hätte: ein Cron, der
        # noch nie gefeuert hat. Keine Strecke, kein Fehlschlag, kein Alarm.
        return True, ("Es gibt **keinen einzigen** geplanten Lauf in der "
                      "abgefragten Historie. Entweder ist der Zeitplan nie "
                      "gestartet, oder er ist deaktiviert.")
    tage = alter_tage(letzter, jetzt)
    if tage > schwelle:
        return True, (f"Der letzte geplante Lauf liegt **{tage:.1f} Tage** "
                      f"zurück (Schwelle: {schwelle}). Erwartet wäre "
                      f"wöchentlich einer.")
    return False, (f"Letzter geplanter Lauf vor {tage:.1f} Tagen — innerhalb "
                   f"der Schwelle von {schwelle}.")


def meldung(grund, workflow_url="", wer=EIGNER, bestaetigt=True):
    """(Titel, Text). Beides HIER, damit Marke und Titel nicht auseinanderlaufen.

    Stünde der Titel im Workflow und die Marke im Skript, entstünde bei einer
    Abweichung kein Fehler, sondern **täglich ein neues Issue**.
    """
    if bestaetigt:
        kopf = (f"{wer} — der wöchentliche Pipeline-Lauf hat **nicht "
                f"stattgefunden**.")
    else:
        kopf = (f"{wer} — **ob** der wöchentliche Pipeline-Lauf stattgefunden "
                f"hat, liess sich nicht feststellen: die Lauf-Historie war "
                f"nicht abrufbar. Diese Meldung entsteht vorsorglich.")
    zeilen = [
        kopf,
        "",
        "Diese Meldung kommt von einem anderen Wächter als die über "
        "fehlgeschlagene Läufe. Der zählt rote Läufe und hängt damit daran, "
        "dass überhaupt einer stattgefunden hat. Ein Zeitplan, der still "
        "stirbt, ist für ihn unsichtbar — dieser hier fragt deshalb nach "
        "**Abwesenheit**.",
        "",
        f"**Befund:** {grund}",
        "",
        "Die häufigsten Ursachen, in dieser Reihenfolge:",
        "",
        "1. GitHub deaktiviert geplante Workflows in Repositories, in denen "
        "**60 Tage** lang nichts passiert — ohne Hinweis. Ein Commit "
        "reaktiviert sie.",
        "2. Der Workflow wurde in der Actions-Oberfläche deaktiviert.",
        "3. Der Cron-Ausdruck wurde geändert und ist syntaktisch gültig, "
        "trifft aber nicht mehr den gemeinten Zeitpunkt.",
        "4. Ein einzelner verschluckter Lauf. GitHubs Scheduler ist "
        "ausdrücklich „best effort\" — Verspätungen von Stunden sind normal, "
        "ein Ausfall über mehr als eine Woche ist es nicht.",
        "",
    ]
    if workflow_url:
        zeilen.append(f"- Alle Läufe: {workflow_url}")
    zeilen += [
        "",
        "Solange diese Meldung offen ist, wird keine zweite angelegt. Nach dem "
        "Beheben schliessen.",
    ]
    return MARKE, "\n".join(zeilen)


def lade_geplante(repo, workflow, token, limit=30):
    """Geplante Läufe, **ohne** Statusfilter.

    `check_run_streak.lade_laeufe` fragt `status=completed` ab — richtig für
    die Frage „ist er rot?". Hier wäre es falsch: ein gerade laufender Lauf ist
    das beste Lebenszeichen, das es gibt, und fiele sonst heraus.
    """
    d = _hole(f"/repos/{repo}/actions/workflows/{workflow}/runs"
              f"?per_page={limit}&event=schedule", token)
    return [{"event": r.get("event"), "conclusion": r.get("conclusion"),
             "status": r.get("status"), "created_at": r.get("created_at"),
             "url": r.get("html_url")} for r in d.get("workflow_runs", [])]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    p.add_argument("--workflow", default="pipeline.yml")
    p.add_argument("--schwelle", type=float, default=SCHWELLE_TAGE)
    p.add_argument("--titel-datei", default="interim/meldung_titel.txt")
    p.add_argument("--text-datei", default="interim/meldung.md")
    args = p.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "")
    jetzt = datetime.now(timezone.utc)
    laeufe, historie_bekannt, offen = [], True, None
    try:
        laeufe = lade_geplante(args.repo, args.workflow, token)
        offen = _offene(args.repo, token, marke=MARKE)
    except (urllib.error.URLError, json.JSONDecodeError, OSError, KeyError) as e:
        historie_bekannt = False
        print(f"historie_fehler={str(e)[:80]}")

    melden, grund = soll_melden(laeufe, offen, jetzt, args.schwelle,
                                historie_bekannt)
    if melden:
        titel, text = meldung(
            grund,
            workflow_url=f"https://github.com/{args.repo}/actions/workflows/"
                         f"{args.workflow}",
            bestaetigt=historie_bekannt)
        Path(args.titel_datei).parent.mkdir(parents=True, exist_ok=True)
        Path(args.titel_datei).write_text(titel + "\n", encoding="utf-8")
        Path(args.text_datei).write_text(text + "\n", encoding="utf-8")

    print(f"entscheidung={'ja' if melden else 'nein'}")
    print(f"grund={grund}")


if __name__ == "__main__":
    main()
