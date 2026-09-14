"""Die Identität einer Einreichung — an EINER Stelle (#88).

Was eine Einreichung von einer Korrekturfassung derselben Einreichung
unterscheidet, entscheidet jede Auswertung über den Katalog. Die Regel stand
zweimal im Repo, und eine der beiden Fassungen war falsch:

    build_parse_manifest.py       richtig — mit dem Modultyp aus dem Dateinamen
    resolve_latest_submissions.py falsch  — ohne ihn

Die falsche verlor 38 % der Einreichungen (FINDIS 617 -> 127, ESGDIS 289 -> 53),
und zwar lautlos: sie meldete eine plausible Deduplikationszahl.

## Die Falle

Die Spalte `module` im Katalog trägt **nicht** den Modultyp, sondern den
numerischen PILLAR3-Code:

    020000  Reporting Framework 4.1
    010000  ebenso, anderer Meldebereich
    020100  Reporting Framework 4.2

Unter EINEM Code liegen CODIS, ESGDIS, FINDIS, REMDIS, IRRBBDIS, MRELTLACDIS und
GSIIDIS als fachlich eigenständige Meldungen desselben Instituts zum selben
Stichtag. Belegt am Katalog: (0W2PZJM8XOY22M4GG883, CON, 020000, 2025-06-30)
enthält CODIS, ESGDIS und FINDIS als drei getrennte Einreichungen. Ohne den Typ
im Schlüssel verwirft „latest wins" zwei davon als überholte Resubmissions.

Der Typ steht nur im Dateinamen:

    <LEI>.<CON|IND>_<LAND>_PILLAR3<modul>_<TYP>_<stichtag>_<ts>.zip

## Und die Falle daneben

`country` gehört ausdrücklich NICHT in den Schlüssel, so naheliegend es aussieht.
Zwei Institute haben ihre Meldung zuerst unter falschem Ländercode eingereicht
und dann korrigiert — UniCredit Banka Slovenija als `FR` statt `SI`, Sparkasse
Malta als `FR` statt `MT`. Mit `country` im Schlüssel zählen beide Fassungen als
getrennte Reports, also doppelt.

Die Regel lautet damit: **ein Institut, ein Konsolidierungskreis, ein
Meldebereich, ein Modultyp, ein Stichtag.** Das Land ist eine Eigenschaft der
Einreichung, kein Teil ihrer Identität.
"""

# `country` fehlt hier mit Absicht — siehe Modul-Docstring.
GROUP_KEYS = ("lei", "consolidation", "module", "refdate")


def report_type(url):
    """CODIS / FINDIS / ESGDIS / IRRBBDIS / REMDIS / … aus dem Dateinamen.

    Liefert "" für alles, was nicht dem Schema folgt — der Aufrufer entscheidet,
    ob das ein Fehler ist. Ein Fallback auf einen Default wäre hier gefährlich:
    er würde fremde Dateinamen still zu einer gemeinsamen Gruppe verschmelzen,
    also genau den Fehler wiederholen, gegen den dieses Modul gebaut ist.
    """
    teile = url.rsplit("/", 1)[-1].split("_")
    return teile[3] if len(teile) > 3 else ""


def identitaet(row):
    """Der vollständige Schlüssel einer Einreichung."""
    return tuple(row[k] for k in GROUP_KEYS) + (report_type(row["url"]),)


def latest_wins(rows):
    """Eine Zeile je Einreichung — die mit dem höchsten `submission_ts`.

    Reine Funktion, Eingabereihenfolge egal, Ausgabe nach `url` sortiert.
    """
    best = {}
    for r in rows:
        k = identitaet(r)
        if k not in best or r["submission_ts"] > best[k]["submission_ts"]:
            best[k] = r
    return sorted(best.values(), key=lambda r: r["url"])
