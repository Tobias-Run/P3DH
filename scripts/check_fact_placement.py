"""Guard: stiller Fact-Verlust durch unbekannte Datapoint-Codes.

Hintergrund: `cell_row`/`cell_col` entstehen erst durch einen dp-Lookup im Parser
(`xbrl_csv_parser.py`, gegen `codebook/dpm_codebook.csv`). Kennt das Codebook einen
dp-Code nicht, bleiben die Koordinaten leer — und der Fakt wird in
`build_zweig_a_shards.py` (`WHERE cell_row <> ''`) **stillschweigend weggefiltert**.
Niemand merkt es; die Zahl der Reports stimmt, nur die Fakten fehlen.

Der Guard klassifiziert jeden Fakt in genau eine Klasse:

  placed      — Koordinate vorhanden (alles gut)
  open_axis   — keine Koordinate, aber `open_axis_dims` gesetzt. Erwartet: offene
                Tabellen haben im DPM keine statische (row, col). KEIN Alarm.
  unplaceable — weder Koordinate noch Dimension → der stille Verlust.

Verglichen wird gegen `interim/placement_baseline.json` (der akzeptierte Ist-Stand).
Abbruch mit Exit-Code 1, sobald es *schlechter* wird — gleiche Philosophie wie das
Sanity-Gate im Workflow, das bei schrumpfendem Bestand abbricht:

  * mehr unplatzierbare Fakten als in der Baseline, oder
  * ein NEUER dem Codebook unbekannter dp-Code, oder
  * eine `rebound`-Zelle der Framework-Brücke, deren dp-Code dem Codebook fehlt
    (dann verlöre genau diese Zelle beim Versionswechsel ihre Koordinaten).

Lauf:  python3 scripts/check_fact_placement.py
       python3 scripts/check_fact_placement.py --update-baseline   # bewusst anheben
"""

from pathlib import Path
import argparse
import csv
import json
import sys
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
LONG_FORM = ROOT / "processed" / "long_form_raw.csv"
CODEBOOK = ROOT / "codebook" / "dpm_codebook.csv"
BRIDGE = ROOT / "codebook" / "framework_bridge.csv"
BASELINE = ROOT / "interim" / "placement_baseline.json"
REPORT = ROOT / "interim" / "placement_report.csv"

# CSV-Feld-Limit: fact_value_raw kann lange Narrative tragen.
csv.field_size_limit(10_000_000)


def _rel(path):
    """Pfad repo-relativ anzeigen, sonst unverändert (Tests nutzen Temp-Pfade)."""
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def classify(rows, known_dps):
    """Klassifiziert Fakten in placed / open_axis / unplaceable.

    rows: Iterable von Dicts mit framework_version, template_id, cell_row,
          cell_col, open_axis_dims, datapoint_code.
    known_dps: Menge der dem DPM-Codebook bekannten dp-Codes.

    Reine Funktion (streaming-fähig) — der Aufrufer entscheidet, woher die Zeilen
    kommen. Gibt ein Summary-Dict zurück.
    """
    by_fw = {}
    unplaceable_by_template = Counter()
    unknown_dps = set()

    for row in rows:
        fw = row.get("framework_version", "") or "?"
        bucket = by_fw.setdefault(fw, Counter())

        has_cell = bool((row.get("cell_row") or "").strip()
                        and (row.get("cell_col") or "").strip())
        has_dim = bool((row.get("open_axis_dims") or "").strip())

        if has_cell:
            klass = "placed"
        elif has_dim:
            klass = "open_axis"
        else:
            klass = "unplaceable"
            unplaceable_by_template[row.get("template_id", "?")] += 1

        bucket[klass] += 1
        bucket["total"] += 1

        dp = (row.get("datapoint_code") or "").strip()
        if dp and dp not in known_dps:
            unknown_dps.add(dp)

    return {
        "by_framework": {fw: dict(c) for fw, c in sorted(by_fw.items())},
        "unplaceable_by_template": dict(unplaceable_by_template.most_common()),
        "unplaceable_total": sum(c.get("unplaceable", 0) for c in by_fw.values()),
        "unknown_dps": sorted(unknown_dps),
    }


def check_bridge_dps(bridge_rows, known_dps):
    """rebound-Zellen, deren dp-Code dem Codebook fehlt.

    Eine solche Zelle verlöre beim Versionswechsel ihre Koordinaten — genau der
    Fall, für den die Brücke die Wackelkandidaten benennt. Pipe-getrennte Mengen
    (status='ambiguous') werden aufgesplittet.
    """
    broken = []
    for row in bridge_rows:
        if row.get("status") != "rebound":
            continue
        missing = [dp for field in ("dp_41", "dp_42")
                   for dp in (row.get(field) or "").split("|")
                   if dp and dp not in known_dps]
        if missing:
            broken.append({
                "template_id": row.get("template_id", ""),
                "cell_row": row.get("cell_row", ""),
                "cell_col": row.get("cell_col", ""),
                "missing": sorted(set(missing)),
            })
    return broken


def _load_known_dps(path):
    with open(path, encoding="utf-8") as f:
        return {r["datapoint_code"] for r in csv.DictReader(f) if r.get("datapoint_code")}


def _iter_long_form(path):
    with open(path, encoding="utf-8") as f:
        yield from csv.DictReader(f)


def _write_report(summary, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scope", "key", "metric", "value"])
        for fw, counts in summary["by_framework"].items():
            for metric, value in sorted(counts.items()):
                w.writerow(["framework", fw, metric, value])
        for tid, n in summary["unplaceable_by_template"].items():
            w.writerow(["template", tid, "unplaceable", n])
        w.writerow(["global", "-", "unknown_dp_count", len(summary["unknown_dps"])])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--update-baseline", action="store_true",
                    help="Ist-Stand als neue Baseline festschreiben (bewusster Schritt)")
    args = ap.parse_args()

    for p, hint in ((LONG_FORM, "erst xbrl_csv_parser.py bzw. scripts/fetch_state.sh"),
                    (CODEBOOK, "erst build_codebook.py")):
        if not p.exists():
            print(f"ERROR: {p} fehlt — {hint}")
            return 2

    known_dps = _load_known_dps(CODEBOOK)
    summary = classify(_iter_long_form(LONG_FORM), known_dps)

    bridge_broken = []
    if BRIDGE.exists():
        with open(BRIDGE, encoding="utf-8") as f:   # csv-Modul: row_label kann \n enthalten
            bridge_broken = check_bridge_dps(list(csv.DictReader(f)), known_dps)

    _write_report(summary, REPORT)

    print("Fact-Platzierung je Framework:")
    for fw, c in summary["by_framework"].items():
        print(f"  fw {fw}: platziert {c.get('placed', 0):9d} · offene Achse "
              f"{c.get('open_axis', 0):8d} · UNPLATZIERBAR {c.get('unplaceable', 0):7d}"
              f"  (gesamt {c.get('total', 0)})")
    print(f"\ndem Codebook unbekannte dp-Codes: {len(summary['unknown_dps'])}")
    top = list(summary["unplaceable_by_template"].items())[:5]
    if top:
        print("Top-Templates mit unplatzierbaren Fakten:")
        for tid, n in top:
            print(f"  {tid:12s} {n:7d}")
    print(f"→ Report: {_rel(REPORT)}")

    current = {
        "unplaceable_by_framework": {fw: c.get("unplaceable", 0)
                                     for fw, c in summary["by_framework"].items()},
        "accepted_unknown_dps": summary["unknown_dps"],
    }

    if args.update_baseline or not BASELINE.exists():
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        with open(BASELINE, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, sort_keys=True)
            f.write("\n")
        action = "aktualisiert" if args.update_baseline else "angelegt"
        print(f"\n✓ Baseline {action}: {_rel(BASELINE)}")
        return 0

    with open(BASELINE, encoding="utf-8") as f:
        base = json.load(f)

    problems = []
    base_unpl = base.get("unplaceable_by_framework", {})
    for fw, n in current["unplaceable_by_framework"].items():
        allowed = base_unpl.get(fw, 0)
        if n > allowed:
            problems.append(f"fw {fw}: unplatzierbare Fakten {allowed} → {n} (+{n - allowed})")

    new_dps = sorted(set(current["accepted_unknown_dps"]) - set(base.get("accepted_unknown_dps", [])))
    if new_dps:
        problems.append(f"{len(new_dps)} NEUE unbekannte dp-Codes, z. B. {new_dps[:5]}")

    for b in bridge_broken:
        problems.append(f"rebound-Zelle {b['template_id']} r{b['cell_row']} c{b['cell_col']}: "
                        f"dp fehlt im Codebook {b['missing']}")

    if problems:
        print("\n✗ Guard schlägt an — stiller Fact-Verlust wächst:")
        for p in problems:
            print(f"    - {p}")
        print("\n  Ursache prüfen (fehlt eine Taxonomie im dpm_codebook.csv?).")
        print("  Wenn der Zuwachs geprüft und akzeptiert ist:")
        print("    python3 scripts/check_fact_placement.py --update-baseline")
        return 1

    print("\n✓ Guard grün — kein zusätzlicher Fact-Verlust gegenüber der Baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
