"""Phase 3b: Framework-Brücke 4.1 ↔ 4.2 (Zell-Ebene).

Beim RF-Wechsel (ab Stichtag 2026-03-31) bleiben Templates und Zell-Layout weit-
gehend stabil, aber ein Teil der Zellen wird im DPM auf NEUE datapoint-Codes
umgebunden (beobachtet z. B. KM1 r0260 Leverage-Puffer, Teile von 63.01, 71.00).
Ein naiver Join über den dp-Code verliert genau diese Zeitreihen still.

Dieses Skript leitet aus dem Zweig-B-Parquet die Brücke ab: je Zelle
(template, row, col), die unter BEIDEN Framework-Versionen beobachtet wurde,
der dp-Code je Version und der Status:
  stable   — gleicher dp-Code in 4.1 und 4.2 (direkter Join ok)
  rebound  — dp-Code geändert (Zeitreihe NUR über diese Brücke verknüpfbar)
  ambiguous— mehrere dp-Codes je Version beobachtet (manuell prüfen)

Die Brücke ist beobachtungsbasiert: sie wächst mit jeder neuen 4.2-Welle
(einfach neu laufen lassen). Zellen, die bisher nur in einer Version vorkommen,
stehen bewusst NICHT drin — Abwesenheit ist bei Offenlegungsdaten kein Beleg
für Taxonomie-Änderung (Frequenz/Anwendbarkeit!).

Lauf:  python3 scripts/build_framework_bridge.py
Out:   codebook/framework_bridge.csv
"""

from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parent.parent
PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
OUT = ROOT / "codebook" / "framework_bridge.csv"


def build_bridge(rows):
    """rows: Iterable von (fw, template_id, cell_row, cell_col, dp, row_label, col_label).

    Liefert sortierte Brücken-Records für Zellen, die in beiden Versionen
    beobachtet wurden."""
    cells = {}
    for fw, tmpl, r, c, dp, rl, cl in rows:
        key = (tmpl, r, c)
        entry = cells.setdefault(key, {"4.1": set(), "4.2": set(), "rl": rl, "cl": cl})
        if fw in entry:
            entry[fw].add(dp)
        # Labels: erstbeste nicht-leere Variante behalten
        if not entry["rl"] and rl:
            entry["rl"] = rl
        if not entry["cl"] and cl:
            entry["cl"] = cl

    bridge = []
    for (tmpl, r, c), e in cells.items():
        dp41, dp42 = e["4.1"], e["4.2"]
        if not dp41 or not dp42:
            continue  # nur in einer Version beobachtet — keine Brücken-Aussage
        if len(dp41) > 1 or len(dp42) > 1:
            status = "ambiguous"
        elif dp41 == dp42:
            status = "stable"
        else:
            status = "rebound"
        bridge.append({
            "template_id": tmpl,
            "cell_row": r,
            "cell_col": c,
            "row_label": e["rl"] or "",
            "col_label": e["cl"] or "",
            "dp_41": "|".join(sorted(dp41)),
            "dp_42": "|".join(sorted(dp42)),
            "status": status,
        })
    bridge.sort(key=lambda x: (x["template_id"], x["cell_row"], x["cell_col"]))
    return bridge


def main():
    import duckdb

    if not PARQUET.exists():
        print(f"ERROR: {PARQUET} fehlt — erst scripts/fetch_state.sh (oder build_zweig_b.py)")
        return

    con = duckdb.connect()
    rows = con.execute(f"""
        SELECT DISTINCT framework_version, template_id, cell_row, cell_col,
                        datapoint_code, row_label, col_label
        FROM '{PARQUET}'
        WHERE cell_row <> '' AND cell_col <> ''
          AND framework_version IN ('4.1', '4.2')
    """).fetchall()

    bridge = build_bridge(rows)

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(bridge[0].keys()))
        writer.writeheader()
        writer.writerows(bridge)

    n = {"stable": 0, "rebound": 0, "ambiguous": 0}
    for b in bridge:
        n[b["status"]] += 1
    print(f"✓ {OUT.name}: {len(bridge)} Zellen in beiden RF-Versionen beobachtet")
    print(f"  stable {n['stable']} / rebound {n['rebound']} / ambiguous {n['ambiguous']}")
    if n["rebound"]:
        print("\n  Umgebundene Zellen (Zeitreihe nur über die Brücke!):")
        for b in bridge:
            if b["status"] == "rebound":
                print(f"    {b['template_id']:10s} r{b['cell_row']} c{b['cell_col']}"
                      f"  {b['dp_41']} -> {b['dp_42']}  ({b['row_label'][:40]})")


if __name__ == "__main__":
    main()
