"""Was eine Harvest-Runde am Katalog verändert hat (#6).

## Warum das ein eigenes Modul ist

Der Diff selbst lief seit `9a198be` — er war nie „nicht scharf geschaltet", wie
das Issue vermutete. Er hatte nur kein Gedächtnis und keinen Leser:

* `harvest_log.csv` ist **append-only** angelegt; der Sinn ist die Historie.
  Sie entstand auf einem Wegwerf-Runner und war nach jedem CI-Harvest weg —
  beim nächsten Lauf begann der Log wieder bei null, mit genau einer Zeile.
  Ein Vorher/Nachher-Log, das kein Vorher kennt.
* Gelesen wurde `manifest_delta.csv` von niemandem.

Die Rechenlogik steckte außerdem in `harvest_catalog_query.py`, das Playwright
auf Modulebene importiert — sie war damit nicht prüfbar, ohne einen Browser zu
starten. Hier steht sie als reine Funktion über Strings, ohne jede Abhängigkeit.

## Was der Diff unterscheidet

`neu` und `weg` genügen nicht. EDAP führt zu einem Meldeplatz mehrere
Einreichungen (gemessen: 372 der 3.812 Plätze im Katalog), und die überholten
bleiben in aller Regel **stehen**. Verschwindet eine Zeile trotzdem, ist das
etwas anderes als eine Neueinreichung:

    neu            erster Eintrag für diesen Meldeplatz
    resubmission   neue Fassung eines Platzes, den der Katalog schon kannte
    ueberholt      verschwunden, aber der Platz ist weiter belegt
    zurueckgezogen verschwunden und der Platz ist leer

Nur die letzte Kategorie ist ein echter Verlust — das ist die Klasse, in der
die 17 belegten toten EDAP-Links sichtbar werden.

## Das Schrumpf-Gate

Der Harvest ist der fragilste Teil der Kette (headless Power-BI-Embed mit
DSR-Pagination). Bricht die Pagination in der Mitte ab, liefert der Lauf
*weniger* Zeilen — und schrieb sie bisher ungeprüft über `manifest_full.csv`.
Das Gate muss deshalb **vor** dem Überschreiben greifen: danach ist die
Vergleichsgrundlage weg, und der nächste Lauf misst gegen den bereits
beschädigten Katalog. Genau so verschwindet ein Bestandsverlust lautlos.

Toleranz: 2 %. Der Katalog wächst; legitime Abgänge sind selten (17 tote Links
auf 4.278 Zeilen ≈ 0,4 %). Ein echter Masseneinzug wird mit `--allow-shrink`
durchgelassen, dann aber bewusst.
"""

from pathlib import Path
import csv
import re

RECON = Path(__file__).resolve().parent.parent / "interim" / "edap_recon"
MANIFEST = RECON / "manifest_full.csv"
LOG = RECON / "harvest_log.csv"
DELTA = RECON / "manifest_delta.csv"

# Dateiname: <LEI>.<CON|IND>_<LAND>_PILLAR3<modul>_<TYP>_<stichtag>_<ts>.zip
# Der Meldeplatz ist alles davor — der Zeitstempel unterscheidet die Fassungen.
_TS_SUFFIX = re.compile(r"_[0-9]+\.zip$")

LOG_FIELDS = ["harvested_at", "total", "institutions",
              "neu", "resubmission", "ueberholt", "zurueckgezogen"]
DELTA_FIELDS = ["change", "slot", "url"]

SHRINK_TOLERANCE = 0.02


def slot_of(url):
    """Der Meldeplatz einer Einreichung: Dateiname ohne Einreichungs-Zeitstempel.

    Der Typ (CODIS/FINDIS/ESGDIS/…) bleibt bewusst drin. Ohne ihn fielen unter
    einem Modulcode fachlich verschiedene Meldungen zusammen — derselbe Fehler,
    vor dem `build_parse_manifest.report_type()` warnt.
    """
    return _TS_SUFFIX.sub("", url.rsplit("/", 1)[-1])


def classify(prev_urls, cur_urls):
    """Reine Funktion: zwei URL-Mengen -> Änderungszeilen, sortiert.

    Reihenfolge der Eingabe ist egal; die Ausgabe ist deterministisch nach
    (Änderungsart, URL) sortiert — sonst rauscht `manifest_delta.csv` im Diff.
    """
    prev_urls, cur_urls = set(prev_urls), set(cur_urls)
    prev_slots = {slot_of(u) for u in prev_urls}
    cur_slots = {slot_of(u) for u in cur_urls}
    rows = []
    for u in cur_urls - prev_urls:
        rows.append({"change": "resubmission" if slot_of(u) in prev_slots else "neu",
                     "slot": slot_of(u), "url": u})
    for u in prev_urls - cur_urls:
        rows.append({"change": "ueberholt" if slot_of(u) in cur_slots else "zurueckgezogen",
                     "slot": slot_of(u), "url": u})
    return sorted(rows, key=lambda r: (r["change"], r["url"]))


def counts(rows):
    """Änderungsart -> Anzahl, immer alle vier Schlüssel."""
    out = {"neu": 0, "resubmission": 0, "ueberholt": 0, "zurueckgezogen": 0}
    for r in rows:
        out[r["change"]] = out.get(r["change"], 0) + 1
    return out


def shrink_verdict(prev_total, new_total, tolerance=SHRINK_TOLERANCE):
    """None, wenn der Harvest plausibel ist — sonst der Grund als Text.

    Getrennt von der Aktion, damit die Schwelle prüfbar ist, ohne einen
    Katalog zu schreiben.
    """
    if new_total == 0:
        return "Harvest lieferte 0 Zeilen"
    if prev_total == 0:
        return None                      # erster Lauf: es gibt nichts zu schützen
    floor = prev_total * (1 - tolerance)
    if new_total < floor:
        lost = prev_total - new_total
        return (f"Katalog geschrumpft: {prev_total} → {new_total} "
                f"({lost} Zeilen, {lost / prev_total:.1%}) — mehr als die "
                f"{tolerance:.0%} Toleranz. Wahrscheinlich eine abgebrochene "
                f"DSR-Pagination, nicht ein Masseneinzug bei EDAP.")
    return None


def read_urls(path):
    """URL-Spalte eines Manifests; leere Menge, wenn es die Datei nicht gibt."""
    if not Path(path).exists():
        return set()
    with open(path, encoding="utf-8") as fh:
        return {r["url"] for r in csv.DictReader(fh) if r.get("url")}


def write_delta(rows, path=DELTA):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=DELTA_FIELDS)
        w.writeheader()
        w.writerows(rows)


def append_log(harvested_at, total, institutions, rows, path=LOG):
    """Eine Zeile je Harvest-Lauf. Append-only — die Historie IST das Produkt."""
    path = Path(path)
    new = not path.exists()
    if not new:
        # Ein Log mit anderem Kopf würde ab hier spaltenversetzt weitergeführt —
        # lesbar bliebe er, richtig nicht mehr. Lieber laut abbrechen: die
        # Historie ist der ganze Zweck der Datei.
        with open(path, encoding="utf-8") as fh:
            head = (fh.readline().strip() or "").split(",")
        if head != LOG_FIELDS:
            raise SystemExit(
                f"{path} hat einen anderen Spaltenkopf ({head}). Das Format hat "
                f"sich mit #6 geändert; die alte Datei wurde nie committet. "
                f"Entfernen und den Log neu beginnen lassen.")
    with open(path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LOG_FIELDS)
        if new:
            w.writeheader()
        w.writerow({"harvested_at": harvested_at, "total": total,
                    "institutions": institutions, **counts(rows)})


def render_summary(log_path=LOG, delta_path=DELTA, max_rows=15):
    """Markdown für die Lauf-Zusammenfassung — der Leser, den der Diff nie hatte.

    Bewusst knapp: Zahlen aus dem Log, und namentlich nur die zurückgezogenen
    Einreichungen. Die sind der einzige echte Verlust und deshalb das einzige,
    was man Zeile für Zeile sehen will.
    """
    out = ["## Harvest-Delta"]
    log = []
    if Path(log_path).exists():
        with open(log_path, encoding="utf-8") as fh:
            log = list(csv.DictReader(fh))
    if not log:
        return "\n".join(out + ["", "_Kein Harvest-Log — dieser Lauf hat nicht geerntet._"])

    last = log[-1]
    out += ["", f"- Katalog: **{last['total']}** Einreichungen · "
                f"{last['institutions']} Institute",
            f"- Neu: **{last['neu']}** · Resubmissions: {last['resubmission']} · "
            f"überholt: {last['ueberholt']} · zurückgezogen: "
            f"**{last['zurueckgezogen']}**",
            f"- Läufe im Log: {len(log)} (seit {log[0]['harvested_at']})"]

    rows = []
    if Path(delta_path).exists():
        with open(delta_path, encoding="utf-8") as fh:
            rows = [r for r in csv.DictReader(fh) if r["change"] == "zurueckgezogen"]
    if rows:
        out += ["", "### Zurückgezogen (Meldeplatz jetzt leer)", ""]
        out += [f"- `{r['slot']}`" for r in rows[:max_rows]]
        if len(rows) > max_rows:
            out.append(f"- … und {len(rows) - max_rows} weitere")
    return "\n".join(out)


if __name__ == "__main__":
    print(render_summary())
