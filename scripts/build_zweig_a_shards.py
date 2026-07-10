"""Zweig A (JSON): emit per-report JSON shards for the lazy-loading viewer,
DERIVED SOLELY FROM ZWEIG B (processed/long/p3dh_long.parquet) — the one joined truth.

Zweig B already joins facts + DPM labels/types/titles + entity metadata + FX into a
single table, so this script performs NO joins of its own: it only reshapes that table
into lazy-loadable JSON. Zweig B is thus the sole transformation stage; the viewer and
the analytics layer share one source and cannot drift.

Outputs under processed/zweig_a/data/:
  index.json          report metadata + head templates (KM1 61.00, OV1 60.00.A)
                      + meta/names/fx lookup maps + global stats.  Everything the
                      report list, filters, benchmark and time-series need WITHOUT
                      touching a shard.
  codebook.json       {cb, titles} trimmed to the cells that actually occur.
  reports/<key>.json  {tpl:{template_id:[[row,col,val],...]}} — the full grid of
                      ONE report, fetched lazily when the user opens it.

Values come from fact_value_raw (original strings) so the ~1.3 % non-numeric facts
(text narratives, enum codes) survive intact.

Run:  python3 scripts/build_zweig_b.py && python3 scripts/build_zweig_a_shards.py
"""

from pathlib import Path
import json
import gzip
import re
import sys
import duckdb

ROOT = Path(__file__).resolve().parent.parent
PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
OUT = ROOT / "processed" / "zweig_a" / "data"
SHARDS = OUT / "reports"

HEAD_TEMPLATES = {"61.00", "60.00.A"}   # KM1 + OV1: needed cross-report by benchmark/time-series


def dpm_code(tid):
    """Mirror the viewer's dpmCode(): 'K_' + template, trailing single letter lowercased."""
    p = tid.split(".")
    if p and len(p[-1]) == 1 and p[-1].isalpha() and p[-1].isupper():
        p[-1] = p[-1].lower()
    return "K_" + ".".join(p)


def safe_name(s):
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)


def main():
    if not PARQUET.exists():
        sys.exit(f"missing {PARQUET} — run scripts/build_zweig_b.py first")
    SHARDS.mkdir(parents=True, exist_ok=True)
    for old in SHARDS.glob("*.json"):        # clear stale shards (renamed/removed reports)
        old.unlink()

    con = duckdb.connect()
    con.execute(f"CREATE VIEW p AS SELECT * FROM '{PARQUET}'")

    # --- pass 1: group placeable cells into reports (raw string values) ---
    reports = {}
    used_cells, used_tpls = set(), set()
    for eid, rp, cur, fw, tid, r, c, val in con.execute("""
        SELECT entityID, refPeriod, currency, framework_version,
               template_id, cell_row, cell_col, fact_value_raw
        FROM p
        WHERE cell_row IS NOT NULL AND cell_row <> ''
        ORDER BY entityID, refPeriod, template_id, cell_row, cell_col
    """).fetchall():
        key = eid + "|" + rp
        rep = reports.get(key)
        if rep is None:
            rep = reports[key] = {"entityID": eid, "refPeriod": rp,
                                  "baseCurrency": cur or "", "framework": fw, "tpl": {}}
        rep["tpl"].setdefault(tid, []).append([r, c, "" if val is None else val])
        kc = dpm_code(tid)
        used_tpls.add(kc)
        used_cells.add(kc + "|" + r + "|" + c)

    # --- codebook (labels/titles/types), trimmed to the cells that occur ---
    cb, titles = {}, {}
    for tid, r, c, rl, cl, dt, tt in con.execute("""
        SELECT template_id, cell_row, cell_col,
               max(row_label), max(col_label), max(data_type), max(template_title)
        FROM p WHERE cell_row IS NOT NULL AND cell_row <> ''
        GROUP BY template_id, cell_row, cell_col      -- one deterministic row per cell
        ORDER BY template_id, cell_row, cell_col
    """).fetchall():
        kc = dpm_code(tid)
        cb[kc + "|" + r + "|" + c] = [rl or "", cl or "", dt or ""]
        if tt:
            titles[kc] = tt
    codebook = {"cb": cb, "titles": titles}

    # --- lookup maps, all straight from the same parquet ---
    meta = {}
    for lei, country, itype, gsii in con.execute("""
        SELECT DISTINCT lei, country, institution_type, files_gsii_module
        FROM p WHERE lei IS NOT NULL AND lei <> ''
        ORDER BY lei
    """).fetchall():
        meta[lei] = {"country": country or "", "institution_type": itype or "",
                     "is_gsii": "true" if gsii else "false"}
    names = {}
    for lei, nm, country in con.execute("""
        SELECT DISTINCT lei, bank_name, country
        FROM p WHERE lei IS NOT NULL AND lei <> ''
        ORDER BY lei
    """).fetchall():
        names[lei] = {"name": nm or lei, "jur": country or ""}
    fx = {}
    for cur, rp, rate in con.execute("""
        SELECT DISTINCT currency, refPeriod, fx_rate
        FROM p WHERE fx_rate IS NOT NULL AND currency <> 'EUR'
        ORDER BY currency, refPeriod
    """).fetchall():
        fx[cur + "|" + rp] = rate

    # --- pass 2: one shard per report, build the index ---
    index_reports, n_facts = [], 0
    for key, rep in reports.items():
        fname = safe_name(rep["entityID"]) + "__" + rep["refPeriod"] + ".json"
        with open(SHARDS / fname, "w", encoding="utf-8") as f:
            json.dump({"tpl": rep["tpl"]}, f, ensure_ascii=False, separators=(",", ":"))
        tids = sorted(rep["tpl"].keys())
        n_facts += sum(len(v) for v in rep["tpl"].values())
        head = {t: rep["tpl"][t] for t in HEAD_TEMPLATES if t in rep["tpl"]}
        index_reports.append({
            "k": key, "entityID": rep["entityID"], "refPeriod": rep["refPeriod"],
            "baseCurrency": rep["baseCurrency"], "framework": rep["framework"],
            "nt": len(tids), "tids": tids, "head": head, "f": fname,
        })

    index = {"stats": {"reports": len(index_reports), "facts": n_facts},
             "reports": index_reports, "meta": meta, "names": names, "fx": fx}
    with open(OUT / "index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))
    with open(OUT / "codebook.json", "w", encoding="utf-8") as f:
        json.dump(codebook, f, ensure_ascii=False, separators=(",", ":"))

    # --- sizes (raw + gzip, since Pages serves gzip) ---
    def sz(path):
        return path.stat().st_size, len(gzip.compress(path.read_bytes(), 6))

    shard_files = list(SHARDS.glob("*.json"))
    shard_raw = sum(p.stat().st_size for p in shard_files)
    shard_gz = sorted(len(gzip.compress(p.read_bytes(), 6)) for p in shard_files)
    idx_raw, idx_gz = sz(OUT / "index.json")
    cb_raw, cb_gz = sz(OUT / "codebook.json")

    print(f"✓ {OUT.relative_to(ROOT)}/  (Quelle: Zweig-B-Parquet)")
    print(f"  index.json     {idx_raw/1e6:6.2f} MB raw · {idx_gz/1e6:5.2f} MB gzip")
    print(f"  codebook.json  {cb_raw/1e6:6.2f} MB raw · {cb_gz/1e6:5.2f} MB gzip")
    print(f"  reports/       {len(shard_files)} shards · {shard_raw/1e6:6.2f} MB raw total")
    if shard_files:
        med = shard_gz[len(shard_gz) // 2]
        print(f"                 per shard gzip: median {med/1e3:.1f} KB · max {shard_gz[-1]/1e3:.1f} KB")
    print(f"\n  Upfront (index+codebook, gzip): {(idx_gz+cb_gz)/1e6:.2f} MB")
    print(f"  Reports: {len(index_reports)} · Facts: {n_facts:,}")


if __name__ == "__main__":
    main()
