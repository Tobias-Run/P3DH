#!/usr/bin/env python3
"""Zweig A gegen die Long-Form: tragen die Shards dieselben Werte?

## Warum es das gibt

Der README behauptet seit Monaten:

    Zweig A wird immer aus Zweig B abgeleitet, nie parallel geparst
    (Werte byte-identisch verifiziert).

Geprüft hat das niemand. Der einzige Mechanismus war der CSV-Viewer — ein
zweiter Renderpfad, der die Long-Form direkt im Browser joint und daneben
gehalten werden konnte. Der ist bei 413 MB und 2,3 Mio. Fakten nicht mehr
lauffähig (der Tab stirbt am Speicher), war seit dem 7. Juli nicht mehr
gepflegt und kannte weder die offene Zeilenachse (#56) noch den
Zell-Diskriminator (#52) noch die Coverage-Zustände. Eine Gegenprobe, die
planmäßig abweicht, ist keine.

Diese Prüfung macht dasselbe ohne Browser — und sie prüft schärfer, weil sie
nicht die Anzeige vergleicht, sondern die Werte.

## Was verglichen wird

    processed/long_form_raw.csv          (die geparste Wahrheit)
              │
              ▼  build_zweig_b.py  →  Parquet  →  build_zweig_a_shards.py
              ▼
    processed/zweig_a/data/reports/*.json

Je (Report, Template) wird die **Multimenge** aller `(Zeile, Spalte, Wert)`
gebildet und beidseitig verglichen. Multimenge, nicht Menge: 88.155
Koordinaten tragen je Report mehr als einen Fakt (#52), und ein verlorenes
Duplikat wäre genau die Art Fehler, die eine Mengenprüfung durchwinkt.

Der Wert wird als **Zeichenkette** verglichen, nicht als Zahl. `fact_value_raw`
im Parquet ist eine VARCHAR-Kopie der CSV-Spalte; ein Vergleich über `float()`
würde eine Formatierungsänderung (`1.0` vs `1`) verschlucken, und genau die
wäre ein Drift.

## Und die Währung je Template (#55)

Die Wertprüfung oben war strukturell blind für den Fehler, der sie am meisten
gebraucht hätte. Sie vergleicht **Rohwerte**, und die stimmten: `104.236.671.752`
stand im Shard wie in der Long-Form. Falsch war die **Einheit** — der Index
behauptete für dieses Template SEK, gemeldet war EUR. Der Viewer rechnete daraus
441.335 statt 4.775.833 EUR Vorstandsvergütung pro Kopf, und die Parität blieb
grün. Über den ganzen Bestand: 9.086 monetäre Fakten mit dem falschen Kurs, ohne
dass eine Prüfung anschlug.

Die EUR-Umrechnung selbst lässt sich hier nicht vergleichen — sie entsteht erst
im Browser und steht nirgends als Wert. Ihre **Eingabe** aber schon: für jedes
(Report, Template) muss die Währung, die der Viewer benutzen würde
(`cur[tid]` sonst `baseCurrency` aus `index.json`), die sein, die die Long-Form
für dieses Template führt. Genau diese Gleichung war verletzt.

Nicht verglichen werden Labels und Datentypen: die entstehen erst im Parquet und
haben in der Long-Form keine Entsprechung. Diese Prüfung beantwortet „stehen
dieselben Zahlen in derselben Einheit da", nicht „sind sie richtig beschriftet".

## Bekannte, erlaubte Abweichung

Zellen ohne `cell_row` landen nicht im Shard (so gebaut) und werden hier
beidseitig ausgefiltert. Ein Report, dessen Fakten *alle* unplatzierbar sind,
bekommt gar keinen Shard — das ist #28 und wird gemeldet, nicht als Fehler
gewertet. Ein Shard OHNE Gegenstück in der Long-Form ist dagegen immer ein
Fehler: er behauptet Daten, die es nicht gibt.
"""

from pathlib import Path
import argparse
import collections
import json
import sys

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from determinism import ordered_query as ordered  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LONG_FORM = ROOT / "processed" / "long_form_raw.csv"
SHARDS = ROOT / "processed" / "zweig_a" / "data" / "reports"
MAX_REPORTED = 12       # so viele Abweichungen werden im Detail ausgegeben


def long_form_cells(con, path, sample=None):
    """{report_key: {template: Counter((row, col, value))}} aus der Long-Form.

    Die Sortierung deckt die gesamte Projektion ab — die Regel aus
    docs/reproduzierbarkeit.md gilt auch für eine Prüfung. Sie ist hier zwar
    nicht ergebnisrelevant (Counter ist ordnungsunabhängig), aber eine
    Ausnahme wäre die erste Stelle, an der die Regel bröckelt.
    """
    rows = ordered(con, f"""
        SELECT entityID, refPeriod, template_id, cell_row, cell_col, fact_value
        FROM read_csv_auto('{path}', all_varchar=true)
        WHERE cell_row IS NOT NULL AND cell_row <> ''
        ORDER BY entityID, refPeriod, template_id, cell_row, cell_col, fact_value
    """, "Long-Form-Zellen")
    out = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    for eid, rp, tid, r, c, val in rows:
        key = f"{eid}|{rp}"
        if sample is not None and key not in sample:
            continue
        out[key][tid][(r, c, "" if val is None else val)] += 1
    return out


def shard_cells(path):
    """{template: Counter((row, col, value))} eines Shards.

    Der vierte Eintrag einer Zelle ist der Diskriminator (#52) — er stammt aus
    dem Parquet und hat in der Long-Form keine Entsprechung; er bleibt hier
    also außen vor. Verglichen werden die ersten drei Stellen.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for tid, cells in (data.get("tpl") or {}).items():
        cnt = collections.Counter()
        for cell in cells:
            cnt[(cell[0], cell[1], cell[2])] += 1
        out[tid] = cnt
    return out


def long_form_currencies(con, path, sample=None):
    """{report_key: {template: {währung: n}}} aus der Long-Form (#55).

    `baseCurrency` steht dort JE FAKT — die Spalte heißt nur so wie das Feld,
    das im Index je Report steht. Genau diese Namensgleichheit hat den Fehler
    getarnt: der Shard-Builder zog eine Spalte, die je Fakt gilt, und schrieb
    sie als Report-Eigenschaft fest.
    """
    rows = ordered(con, f"""
        SELECT entityID, refPeriod, template_id, baseCurrency, count(*)
        FROM read_csv_auto('{path}', all_varchar=true)
        WHERE cell_row IS NOT NULL AND cell_row <> ''
          AND baseCurrency IS NOT NULL AND baseCurrency <> ''
        GROUP BY 1, 2, 3, 4
        ORDER BY 1, 2, 3, 4
    """, "Long-Form-Währungen")
    out = collections.defaultdict(lambda: collections.defaultdict(dict))
    for eid, rp, tid, cur, n in rows:
        key = f"{eid}|{rp}"
        if sample is not None and key not in sample:
            continue
        out[key][tid][cur.replace("iso4217:", "")] = n
    return out


def viewer_currency(entry, tid):
    """Die Währung, die der Viewer für dieses Template benutzen würde.

    Spiegel von `curOf(rep, tid)` im Viewer. Ein Spiegel ist immer eine zweite
    Wahrheit — hier ist er eine Zeile lang und steht neben dem Original im
    Test, was billiger ist, als die Umrechnung selbst zu vergleichen (sie
    entsteht erst im Browser).
    """
    ov = (entry.get("cur") or {}).get(tid)
    return (ov or entry.get("baseCurrency") or "").replace("iso4217:", "")


def currency_problems(index_reports, lf_cur, keys):
    """Reine Funktion: wo weicht die Viewer-Währung von der gemeldeten ab?"""
    by_key = {r["entityID"] + "|" + r["refPeriod"]: r for r in index_reports}
    out = []
    for key in sorted(keys):
        entry = by_key.get(key)
        if entry is None:
            continue                      # Index/Shard-Abgleich macht main()
        for tid, counts in sorted(lf_cur.get(key, {}).items()):
            if len(counts) > 1:
                # Das Modell kennt eine Währung je Template. Träfe das nicht
                # mehr zu, wäre die Ausnahmeliste selbst zu grob — dann muss
                # sie auf Zellebene, nicht stillschweigend eine Währung wählen.
                out.append(f"{key} {tid}: mehrere Währungen im selben Template "
                           f"({', '.join(sorted(counts))}) — die Ausnahmeliste "
                           f"je Template kann das nicht ausdrücken")
                continue
            reported = next(iter(counts))
            used = viewer_currency(entry, tid)
            if used != reported:
                out.append(f"{key} {tid}: gemeldet in {reported}, der Viewer "
                           f"rechnet mit {used or '(keine)'} — "
                           f"{counts[reported]} Fakten mit falschem Kurs")
    return out


def shard_key(path):
    """'rs_LEI.CON__2025-12-31.json' -> 'rs:LEI.CON|2025-12-31'.

    Spiegelt safe_name() im Shard-Builder. Der Trenner ist '__', der Doppelpunkt
    im entityID wurde zu '_'; deshalb wird nur das erste '_' zurückgedreht.
    """
    stem = path.stem
    if "__" not in stem:
        return None
    eid, _, refperiod = stem.rpartition("__")
    return eid.replace("_", ":", 1) + "|" + refperiod


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sample", type=int, metavar="N",
                    help="nur die N ersten Reports prüfen (Reihenfolge: Dateiname)")
    args = ap.parse_args()

    if not LONG_FORM.exists():
        sys.exit(f"fehlt: {LONG_FORM} — erst scripts/fetch_state.sh laufen lassen")
    if not SHARDS.is_dir():
        sys.exit(f"fehlt: {SHARDS} — erst scripts/build_zweig_a_shards.py laufen lassen")

    files = sorted(SHARDS.glob("*.json"))
    if args.sample:
        files = files[:args.sample]
    if not files:
        sys.exit("keine Shards gefunden")

    by_key = {}
    for f in files:
        k = shard_key(f)
        if k is None:
            sys.exit(f"unerwarteter Shard-Name: {f.name}")
        by_key[k] = f

    con = duckdb.connect()
    lf = long_form_cells(con, LONG_FORM, sample=set(by_key) if args.sample else None)

    problems, n_cells, n_reports = [], 0, 0
    only_long_form = sorted(set(lf) - set(by_key))

    for key in sorted(by_key):
        shard = shard_cells(by_key[key])
        truth = lf.get(key)
        if truth is None:
            problems.append(f"{key}: Shard vorhanden, aber in der Long-Form kein einziger "
                            f"platzierbarer Fakt — der Shard behauptet Daten, die es nicht gibt")
            continue
        n_reports += 1
        for tid in sorted(set(shard) | set(truth)):
            a, b = shard.get(tid, collections.Counter()), truth.get(tid, collections.Counter())
            n_cells += sum(b.values())
            if a == b:
                continue
            missing = b - a          # in der Long-Form, nicht im Shard
            extra = a - b            # im Shard, nicht in der Long-Form
            detail = []
            if missing:
                s = list(missing.elements())[:3]
                detail.append(f"{sum(missing.values())} fehlen im Shard, z. B. {s}")
            if extra:
                s = list(extra.elements())[:3]
                detail.append(f"{sum(extra.values())} zusätzlich im Shard, z. B. {s}")
            problems.append(f"{key} · {tid}: " + " · ".join(detail))

    # --- Einheit statt Wert (#55): die Rohwerte oben koennen stimmen und die
    # Zahl im Viewer trotzdem falsch sein, wenn die Waehrung nicht passt.
    lf_cur = long_form_currencies(con, LONG_FORM,
                                  sample=set(by_key) if args.sample else None)
    index_path = SHARDS.parent / "index.json"
    n_cur = 0
    if index_path.exists():
        reports = json.loads(index_path.read_text(encoding="utf-8"))["reports"]
        cur_problems = currency_problems(reports, lf_cur, set(by_key))
        n_cur = sum(len(v) for k, v in lf_cur.items() if k in by_key)
        problems.extend(cur_problems)
    else:
        problems.append(f"{index_path.name} fehlt — die Waehrung je Template "
                        "ist damit ungeprueft (#55)")

    print(f"Zweig-A-Parität gegen {LONG_FORM.name}")
    print(f"  Reports verglichen : {n_reports}")
    print(f"  Zellen verglichen  : {n_cells:,}".replace(",", "."))
    print(f"  Währungen geprüft  : {n_cur:,}".replace(",", ".") + " (Report, Template)")
    if only_long_form:
        # #28: ein Report kann Deklarationen ohne einen einzigen platzierbaren
        # Fakt haben. Dann existiert er hier gar nicht — und das ist richtig so.
        print(f"  ohne Shard         : {len(only_long_form)} "
              f"(Reports ohne platzierbare Zelle, siehe #28)")
        for k in only_long_form[:5]:
            print(f"      {k}")

    if problems:
        print(f"\n✗ {len(problems)} Abweichung(en):")
        for p in problems[:MAX_REPORTED]:
            print(f"    {p}")
        if len(problems) > MAX_REPORTED:
            print(f"    … und {len(problems) - MAX_REPORTED} weitere")
        print("\nZweig A ist gegenüber der Long-Form gedriftet. Der Viewer zeigt damit\n"
              "andere Zahlen als der Bestand — das ist die Zusage aus dem README.")
        sys.exit(1)

    print("\n✓ Jeder Wert im Viewer steht so auch in der Long-Form, in derselben\n"
          "  Währung, und umgekehrt.")


if __name__ == "__main__":
    main()
