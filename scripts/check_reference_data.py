"""Guard: Referenzdaten decken die geladenen Fakten nicht mehr ab.

Die Pipeline aktualisiert Fakten, aber die Referenzdaten (EZB-Kurse,
Institutsmetadaten) kommen aus eigenen Feedern. Beide werden in Zweig B per
LEFT JOIN angehängt (`build_zweig_b.py`) — fehlt eine Zeile, gibt es **kein
Fehler, nur NULL**:

  * fehlender FX-Kurs   -> `fact_value_eur` leer -> Fakt fällt aus jedem
                           EUR-normierten Peer-Vergleich, ohne Spur
  * fehlendes entity_meta -> `bank_name`/`institution_type` leer -> Institut
                           taucht in Filtern und Peer-Schichtung nicht auf

Dieser Guard prüft die Abdeckung **auf der Konsumentenseite** (dem fertigen
Parquet) und bricht ab, wenn sie unvollständig ist. Er läuft im Workflow nach
`build_zweig_b.py` und vor Publish, damit unvollständige Daten gar nicht erst
veröffentlicht werden.

Anders als `check_fact_placement.py` gibt es hier **keine Baseline**: eine
Lücke ist immer behebbar, indem der zuständige Feeder läuft
(`fetch_fx_rates.py` bzw. `build_entity_meta.py`). Deshalb harter Abbruch.

Lauf:  python3 scripts/check_reference_data.py
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
FX = ROOT / "processed" / "fx_rates.csv"
ENTITY_META = ROOT / "processed" / "entity_meta.csv"


def missing_keys(needed, available):
    """Schlüssel, die in den Fakten vorkommen, aber in der Referenztabelle fehlen.

    `needed` ist eine Sequenz von (key, n_facts)-Paaren, `available` eine Menge
    von Schlüsseln. Rückgabe absteigend nach betroffenen Fakten — das Schlimmste
    zuerst. Reine Funktion, damit sie ohne DuckDB testbar bleibt.
    """
    miss = [(key, n) for key, n in needed if key not in available]
    miss.sort(key=lambda kv: -kv[1])
    return miss


def _rel(path):
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def main():
    import duckdb

    for p, hint in ((PARQUET, "erst build_zweig_b.py (oder scripts/fetch_state.sh)"),
                    (FX, "erst fetch_fx_rates.py"),
                    (ENTITY_META, "erst build_entity_meta.py")):
        if not p.exists():
            print(f"ERROR: {_rel(p)} fehlt — {hint}")
            return 2

    con = duckdb.connect()
    con.execute(f"SET file_search_path='{ROOT}'")

    # --- FX-Abdeckung -----------------------------------------------------
    fx_needed = con.execute(f"""
        SELECT currency, refPeriod, COUNT(*) FROM '{PARQUET}'
        WHERE currency IS NOT NULL AND currency <> ''
        GROUP BY 1, 2
    """).fetchall()
    fx_have = {(c, d) for c, d in con.execute(
        "SELECT currency, refdate FROM read_csv_auto('processed/fx_rates.csv', all_varchar=true)"
    ).fetchall()}
    fx_missing = missing_keys([((c, d), n) for c, d, n in fx_needed], fx_have)

    # --- entity_meta-Abdeckung -------------------------------------------
    ent_needed = con.execute(f"""
        SELECT lei, COUNT(*) FROM '{PARQUET}'
        WHERE lei IS NOT NULL AND lei <> ''
        GROUP BY 1
    """).fetchall()
    ent_have = {r[0] for r in con.execute(
        "SELECT lei FROM read_csv_auto('processed/entity_meta.csv', all_varchar=true)"
    ).fetchall()}
    ent_missing = missing_keys([(lei, n) for lei, n in ent_needed], ent_have)

    # --- Folgeschaden: monetäre Fakten ohne EUR-Wert ----------------------
    mon_total, mon_no_eur = con.execute(f"""
        SELECT COUNT(*), SUM(CASE WHEN fact_value_eur IS NULL THEN 1 ELSE 0 END)
        FROM '{PARQUET}'
        WHERE data_type = 'monetary' AND fact_value IS NOT NULL
    """).fetchone()
    mon_no_eur = mon_no_eur or 0

    print("Referenzdaten-Abdeckung:")
    print(f"  FX-Kurse:     {len(fx_needed) - len(fx_missing)}/{len(fx_needed)} "
          f"(Währung, Stichtag)-Paare")
    print(f"  entity_meta:  {len(ent_needed) - len(ent_missing)}/{len(ent_needed)} Institute")
    print(f"  monetäre Fakten ohne fact_value_eur: {mon_no_eur} von {mon_total}")

    problems = []
    if fx_missing:
        problems.append(f"{len(fx_missing)} (Währung, Stichtag)-Paar(e) ohne EZB-Kurs")
        for (cur, date), n in fx_missing[:10]:
            print(f"    ✗ kein Kurs: {cur} {date} — {n} Fakten betroffen")
    if ent_missing:
        problems.append(f"{len(ent_missing)} Institut(e) ohne entity_meta")
        for lei, n in ent_missing[:10]:
            print(f"    ✗ kein entity_meta: {lei} — {n} Fakten betroffen")
    if mon_no_eur:
        problems.append(f"{mon_no_eur} monetäre Fakten ohne fact_value_eur")

    if problems:
        print("\n✗ Guard schlägt an — Referenzdaten decken die Fakten nicht ab:")
        for p in problems:
            print(f"    - {p}")
        print("\n  Beheben, indem der zuständige Feeder läuft (braucht Netz):")
        if fx_missing or mon_no_eur:
            print("    python3 scripts/fetch_fx_rates.py")
        if ent_missing:
            print("    python3 scripts/build_entity_meta.py   # setzt einen Harvest voraus")
        print("    danach: python3 scripts/build_zweig_b.py")
        return 1

    print("\n✓ Guard grün — Referenzdaten decken alle geladenen Fakten ab")
    return 0


if __name__ == "__main__":
    sys.exit(main())
