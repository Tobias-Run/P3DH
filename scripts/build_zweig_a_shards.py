"""Zweig A (JSON): emit per-report JSON shards for the lazy-loading viewer,
DERIVED SOLELY FROM ZWEIG B (processed/long/p3dh_long.parquet) — the one joined truth.

Zweig B already joins facts + DPM labels/types/titles + entity metadata + FX into a
single table, so this script performs NO joins of its own: it only reshapes that table
into lazy-loadable JSON. Zweig B is thus the sole transformation stage; the viewer and
the analytics layer share one source and cannot drift.

Outputs under processed/zweig_a/data/ (sized to scale toward the full catalog):
  index.json          SLIM: per-report metadata (entityID/date/currency/framework/nt/
                      shard-file) + meta/names/fx lookup maps + stats.  This is the only
                      up-front payload — it stays small even at thousands of reports.
  benchmark.json      per-report head templates (KM1 61.00, OV1 60.00.A) — the cross-report
                      data the benchmark and time-series need.  Loaded LAZILY (first time
                      the benchmark tab or a time-series is shown), not on boot.
  codebook.json       {cb, titles} trimmed to the cells that actually occur.
  reports/<key>.json  {tpl:{template_id:[[row,col,val],...]}} — the full grid of ONE
                      report, fetched lazily when the user opens it.  Written INCREMENTALLY:
                      only shards whose bytes changed are rewritten; vanished reports are
                      pruned — so a re-run after a delta load touches only what moved.

Values come from fact_value_raw (original strings) so the ~1.3 % non-numeric facts
(text narratives, enum codes) survive intact.

Run:  python3 scripts/build_zweig_b.py && python3 scripts/build_zweig_a_shards.py
"""

from pathlib import Path
import csv
import json
import gzip
import re
import sys
import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from determinism import ordered_query as ordered  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
OUT = ROOT / "processed" / "zweig_a" / "data"
SHARDS = OUT / "reports"

# Templates, deren Zellen report-übergreifend in benchmark.json landen (Benchmark
# + Zeitreihe, lazy geladen). Wert = None -> alle Spalten; sonst nur die genannten.
#
# Die Spalten-Allowlist ist der Grund, warum weitere Templates hier überhaupt
# tragbar sind: 41.00 hat 97k Zellen, davon braucht das ESG-Profil 3 Spalten.
# Ohne Filter würde benchmark.json um ein Vielfaches wachsen — die Datei wird
# zwar lazy geladen, aber nicht geshardet.
HEAD_TEMPLATES = {
    "61.00":   None,                      # KM1  — Kennzahlen + Zeitreihen-Basis
    "60.00.A": None,                      # OV1  — Risikoprofil (Anteile an TREA)
    "82.00.A": {"0010", "0040"},          # CQ3  — performing / non-performing
    # ESG: Bezugsgröße + die "davon"-Spalten. Nur Quotienten daraus sind
    # vergleichbar — die absoluten Beträge nicht, siehe Kommentar im Viewer.
    "41.00":   {"0010", "0020", "0030", "0040", "0050"},
}


def dpm_code(tid):
    """Mirror the viewer's dpmCode(): 'K_' + template, trailing single letter lowercased."""
    p = tid.split(".")
    if p and len(p[-1]) == 1 and p[-1].isalpha() and p[-1].isupper():
        p[-1] = p[-1].lower()
    return "K_" + ".".join(p)


def safe_name(s):
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)


def write_if_changed(path, text):
    """Write only when bytes differ — keeps git diffs (and full-load rebuilds) minimal."""
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


SUBLETTER_RE = re.compile(r"\.[A-Z]$")


def base_tid(tid):
    """'60.00.A' -> '60.00'. Filing indicators are declared per BASE template."""
    return SUBLETTER_RE.sub("", tid)


def load_coverage_map(root: Path | None = None):
    """Map report key -> template_id -> reported (True/False) from filing_indicators.csv.

    Straight read of the declarations, no normalisation — resolve_coverage()
    does the mapping onto the templates the viewer renders.
    """
    root = root or ROOT
    cov_path = root / "processed" / "filing_indicators.csv"
    if not cov_path.exists():
        return {}
    mapping = {}
    with cov_path.open("r", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            entity = (row.get("entityID") or "").strip()
            period = (row.get("refPeriod") or "").strip()
            tid = (row.get("template_id") or "").strip()
            if not entity or not period or not tid:
                continue
            rep = mapping.setdefault(f"{entity}|{period}", {})
            rep[tid] = str(row.get("reported", "")).strip().lower() == "true"
    return mapping


def cell_discriminator(country, dims, dp):
    """Was unterscheidet zwei Fakten auf DERSELBEN (template,row,col)?

    Reihenfolge nach Lesbarkeit: aufgelöster Ländername vor roher Dimension
    vor dp-Code. Der dp-Code ist die Rückfallebene für Fälle, in denen unser
    Codebook die Unterscheidung nicht kennt — bei LIQ1 (`74.00.C`) etwa liegen
    vier dp-Codes auf r0150/c0050 mit identischen Labels; die unterscheidende
    Achse (vermutlich das Quartal des 12-Monats-Durchschnitts) steht im DPM,
    aber nicht in `dpm_codebook.csv`. Gleiche Lückenklasse wie #3 und #29.
    """
    return country or dims or dp or ""


def collapse_cells(rows):
    """rows: Liste von (row, col, val, discriminator) EINES Templates.

    Liefert die Shard-Darstellung: `[row, col, val]` für eindeutige Zellen,
    `[row, col, val, disc]` für Koordinaten, die MEHRFACH belegt sind.

    Hintergrund (#52): 88.155 der 1.540.802 Zellkoordinaten (5,7 %) tragen je
    Report mehr als einen Fakt, 74.905 davon mit verschiedenen Werten. Der
    Viewer baute daraus eine Map und behielt willkürlich einen Wert. Der
    Diskriminator wird nur dort mitgeschrieben, wo er gebraucht wird — sonst
    würde die Shard-Größe für 94 % unnötig wachsen.
    """
    seen = {}
    for r, c, val, disc in rows:
        seen[(r, c)] = seen.get((r, c), 0) + 1
    out = []
    for r, c, val, disc in rows:
        out.append([r, c, val, disc] if seen[(r, c)] > 1 else [r, c, val])
    return out


def load_quality_profile(root: Path | None = None):
    """Plausibilitäts-Befunde je Report (Issue #17) -> {report_key: {...}}.

    Der Viewer soll Ausreißer einordnen können, ohne sie zu verstecken (#48):
    die Benchmark-Rangliste führte bisher mit Werten wie 387 % CET1 an, ohne
    Hinweis darauf, dass wir sie selbst als auffällig einstufen.

    Landet im INDEX, nicht im Shard: die Benchmark-Tabelle braucht die Angabe
    für alle Zeilen gleichzeitig, ein Shard wird aber nur für den geöffneten
    Report geladen. Der Aufschlag ist klein — nur Reports MIT Befunden stehen
    drin (326 von 882), je Eintrag vier Zahlen.

    Report-Key ist 'entityID|refPeriod' wie im Index; entityID wird aus
    (lei, scope) rekonstruiert, weil quality_profile.csv beide getrennt führt.
    """
    root = root or ROOT
    path = root / "processed" / "quality_profile.csv"
    if not path.exists():
        return {}
    out = {}
    with path.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            lei, scope, rp = r.get("lei"), r.get("scope"), r.get("refPeriod")
            if not (lei and scope and rp):
                continue
            out[f"rs:{lei}.{scope}|{rp}"] = {
                "n": int(r["n_findings"] or 0),
                "h": int(r["n_hoch"] or 0),
                "m": int(r["n_mittel"] or 0),
                "d": round(float(r["max_deviation_orders"] or 0), 1),
                # Betroffene Templates: der Viewer markiert template-GENAU, nicht
                # pauschal. Der Schweregrad allein trägt das nicht — er ist auf
                # Einheiten-Verwechslungen geeicht (6 Größenordnungen = "hoch")
                # und stuft deshalb einen statistisch extremen Ausreißer in einer
                # engen Quotenzelle als "niedrig" ein: Kommuninvest liegt bei
                # KM1 r0050 mit robustem z = 10,3 weit außerhalb, aber nur 1,3
                # Größenordnungen über dem Median. Siehe #53.
                "t": [t for t in (r.get("templates") or "").split("|") if t],
            }
    return out


def resolve_coverage(declared, data_tids):
    """Project the filing-indicator declarations of ONE report onto the template
    ids the viewer actually renders.

    `declared`:  {template_id: reported_bool} as filed by the institution.
    `data_tids`: template ids that carry placeable facts in this report.

    Institutions declare per BASE template ('01.00') while the data carries
    sub-lettered variants ('01.00.A', '01.00.B') — hence exact-match-first,
    then base. (14 of 114 declared ids DO carry a sub-letter, so the exact
    match has to win; with this rule all 191 data templates / 1.545.856 facts
    resolve and none is left over.)

    Returns {template_id: state} with state in:
      'reported'      — declared as disclosed, facts present
      'not-reported'  — declared as NOT disclosed (deliberate omission, Art. 432)
      'reported-empty'— declared as disclosed, but we hold no placeable cells.
                        That is OUR gap (open axes / missing dp codes, #3),
                        not an omission by the institution — never label it as
                        one.
    Templates without ANY declaration are deliberately ABSENT from the result;
    the viewer has to show them as 'unknown'. Absence of a declaration is not
    evidence of anything (Arbeitsprinzip 3, "Fehlt != Null").
    """
    out = {}
    consumed = set()
    for tid in data_tids:
        if tid in declared:
            key = tid
        elif base_tid(tid) in declared:
            key = base_tid(tid)
        else:
            continue          # no declaration -> viewer shows 'unknown'
        out[tid] = "reported" if declared[key] else "not-reported"
        consumed.add(key)
    # Declared templates that produced no placeable cells at all. A base id
    # whose sub-lettered variants carry data is already consumed above and
    # must NOT resurface here (that was the phantom-section bug).
    for tid, reported in declared.items():
        if tid in consumed or tid in out:
            continue
        out[tid] = "reported-empty" if reported else "not-reported"
    return out


def main():
    if not PARQUET.exists():
        sys.exit(f"missing {PARQUET} — run scripts/build_zweig_b.py first")
    SHARDS.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    con.execute(f"CREATE VIEW p AS SELECT * FROM '{PARQUET}'")
    coverage = load_coverage_map(ROOT)
    quality = load_quality_profile(ROOT)

    # --- pass 1: group placeable cells into reports (raw string values) ---
    reports = {}
    for eid, rp, cur, fw, tid, r, c, val, oc, od, dp in ordered(con, """
        SELECT entityID, refPeriod, currency, framework_version,
               template_id, cell_row, cell_col, fact_value_raw,
               open_axis_country, open_axis_dims, datapoint_code
        FROM p
        WHERE cell_row IS NOT NULL AND cell_row <> ''
        -- Die Sortierung deckt die GESAMTE Projektion ab, nicht nur die
        -- Gruppierung: sonst entscheidet die Zufallsreihenfolge (DuckDB
        -- sortiert parallel), welcher Wert in der Ausgabe landet.
        --   template..cell_col  : die fachliche Ordnung im Shard
        --   fact_value_raw + oc/od/dp : 74.905 Koordinaten sind je Report
        --     MEHRFACH belegt (#52) — ohne diese Schlüssel wandert der Wert
        --   currency/framework  : ZULETZT, damit sie die Zellordnung nicht
        --     antasten; sie werden je Report aus der ersten Zeile gezogen und
        --     wären ohne Sortierung bei 12 Reports mit zwei Währungen zufällig
        ORDER BY entityID, refPeriod, template_id, cell_row, cell_col,
                 fact_value_raw, open_axis_country, open_axis_dims, datapoint_code,
                 currency, framework_version
    """, "pass 1 / Zellen"):
        key = eid + "|" + rp
        rep = reports.get(key)
        if rep is None:
            rep = reports[key] = {"entityID": eid, "refPeriod": rp,
                                  "baseCurrency": cur or "", "framework": fw,
                                  "tpl": {}}
        rep["tpl"].setdefault(tid, []).append(
            (r, c, "" if val is None else val, cell_discriminator(oc, od, dp)))

    # --- coverage ("Fehlt != Null"): resolve declarations against the templates
    # that actually carry cells. Done AFTER pass 1 so data_tids is complete, and
    # per report so nothing aliases the shared declaration dict.
    for key, rep in reports.items():
        rep["coverage"] = resolve_coverage(coverage.get(key, {}), set(rep["tpl"]))
        # Diskriminator nur an mehrfach belegten Koordinaten behalten (#52)
        rep["tpl"] = {t: collapse_cells(rows) for t, rows in rep["tpl"].items()}

    # --- codebook (labels/titles/types), trimmed to the cells that occur ---
    cb, titles = {}, {}
    for tid, r, c, rl, cl, dt, tt in ordered(con, """
        SELECT template_id, cell_row, cell_col,
               max(row_label), max(col_label), max(data_type), max(template_title)
        FROM p WHERE cell_row IS NOT NULL AND cell_row <> ''
        GROUP BY template_id, cell_row, cell_col      -- one deterministic row per cell
        ORDER BY template_id, cell_row, cell_col
    """, "codebook"):
        kc = dpm_code(tid)
        cb[kc + "|" + r + "|" + c] = [rl or "", cl or "", dt or ""]
        if tt:
            titles[kc] = tt
    # --- Achsenbeschriftung für offene Zeilenachsen (#56) ---
    # Bei diesen Templates IST die Zeile der Achsenwert: CCyB1 führt 250 Zeilen,
    # eine je Staat, und der Shard trägt dort den ISO-Code ('NL'). Ohne
    # Auflösung liest der Nutzer 'AD, AE, AF, AG, AI, AL …' und muss selbst
    # wissen, dass AD Andorra ist.
    #
    # Nur was in den Daten steht (open_axis_country), nichts Erfundenes: 'x1'
    # (Summenzeile), 'x28' (übrige Länder) und 'qx2014' haben keinen
    # Ländernamen und bleiben als Code stehen — der Nutzer sieht damit auch,
    # dass sie keine Staaten sind. 15 KB für 8 Templates.
    axis = {}
    for tid, r, nm in ordered(con, """
        SELECT template_id, cell_row, max(open_axis_country)
        FROM p
        WHERE open_axis_country IS NOT NULL AND open_axis_country <> ''
          AND cell_row IS NOT NULL AND cell_row <> ''
        GROUP BY template_id, cell_row
        ORDER BY template_id, cell_row
    """, "Achsenbeschriftung"):
        axis.setdefault(dpm_code(tid), {})[r] = nm

    codebook = {"cb": cb, "titles": titles, "axis": axis}

    # --- lookup maps, all straight from the same parquet ---
    # Diese drei Maps werden je Schlüssel ÜBERSCHRIEBEN — bei mehreren Zeilen je
    # LEI gewinnt also die letzte. Heute liefert build_entity_meta.py genau eine
    # Zeile je LEI (geprüft: 0 mehrdeutige), aber das ist eine Eigenschaft der
    # Daten, keine Zusage. Die vollständige Sortierung macht das Ergebnis auch
    # dann reproduzierbar, wenn sich das ändert.
    meta = {}
    for lei, country, itype, gsii in ordered(con, """
        SELECT DISTINCT lei, country, institution_type, files_gsii_module
        FROM p WHERE lei IS NOT NULL AND lei <> ''
        ORDER BY lei, country, institution_type, files_gsii_module
    """, "meta"):
        meta[lei] = {"country": country or "", "institution_type": itype or "",
                     "is_gsii": "true" if gsii else "false"}
    names = {}
    for lei, nm, country in ordered(con, """
        SELECT DISTINCT lei, bank_name, country
        FROM p WHERE lei IS NOT NULL AND lei <> ''
        ORDER BY lei, bank_name, country
    """, "names"):
        names[lei] = {"name": nm or lei, "jur": country or ""}
    fx = {}
    for cur, rp, rate in ordered(con, """
        SELECT DISTINCT currency, refPeriod, fx_rate
        FROM p WHERE fx_rate IS NOT NULL AND currency <> 'EUR'
        ORDER BY currency, refPeriod, fx_rate
    """, "fx"):
        fx[cur + "|" + rp] = rate

    # --- pass 2: shards (incremental) + slim index + benchmark aggregate ---
    index_reports, benchmark = [], {}
    n_facts = written = skipped = 0
    current = set()
    for key, rep in reports.items():
        fname = safe_name(rep["entityID"]) + "__" + rep["refPeriod"] + ".json"
        current.add(fname)
        # Deterministisch serialisieren: resolve_coverage() iteriert über ein
        # set(), dessen Reihenfolge zwischen Läufen schwankt (String-Hash-
        # Randomisierung). Ohne sort_keys schrieb jeder Lauf ~830 der 882
        # Shards neu, obwohl sich inhaltlich nichts geändert hatte.
        #
        # Der Schaden ist NICHT der data-Branch — der wird als frisches
        # Orphan-Commit force-gepusht, dort ist Churn folgenlos (eine frühere
        # Fassung dieses Kommentars behauptete das Gegenteil). Er ist:
        #   1. `written/skipped` verliert seinen Aussagewert — bei 830 von 882
        #      erkennt niemand mehr, ob wirklich neue Daten da sind;
        #   2. eine Pipeline, die auf gleichen Eingaben verschiedene Bytes
        #      liefert, ist nicht reproduzierbar — und genau das behauptet das
        #      README. Man kann eine Ausgabe dann gegen nichts prüfen.
        payload = json.dumps({"tpl": rep["tpl"], "coverage": rep.get("coverage", {})},
                             ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        if write_if_changed(SHARDS / fname, payload):
            written += 1
        else:
            skipped += 1
        n_facts += sum(len(v) for v in rep["tpl"].values())
        head = {}
        for t, cols in HEAD_TEMPLATES.items():
            cells = rep["tpl"].get(t)
            if not cells:
                continue
            if cols is not None:
                cells = [c for c in cells if c[1] in cols]
                if not cells:
                    continue
            head[t] = cells
        if head:
            benchmark[key] = head
        entry = {
            "k": key, "entityID": rep["entityID"], "refPeriod": rep["refPeriod"],
            "baseCurrency": rep["baseCurrency"], "framework": rep["framework"],
            "nt": len(rep["tpl"]), "f": fname,
        }
        q = quality.get(key)
        if q:                       # nur Reports MIT Befunden tragen das Feld
            entry["q"] = q
        index_reports.append(entry)

    removed = 0
    for old in SHARDS.glob("*.json"):        # prune shards of reports that vanished
        if old.name not in current:
            old.unlink()
            removed += 1

    index = {"stats": {"reports": len(index_reports), "facts": n_facts},
             "reports": index_reports, "meta": meta, "names": names, "fx": fx}
    write_if_changed(OUT / "index.json", json.dumps(index, ensure_ascii=False, separators=(",", ":")))
    write_if_changed(OUT / "benchmark.json", json.dumps(benchmark, ensure_ascii=False, separators=(",", ":")))
    write_if_changed(OUT / "codebook.json", json.dumps(codebook, ensure_ascii=False, separators=(",", ":")))

    # --- sizes (raw + gzip, since Pages serves gzip) ---
    def sz(name):
        b = (OUT / name).read_bytes()
        return len(b) / 1e6, len(gzip.compress(b, 6)) / 1e6

    shard_files = list(SHARDS.glob("*.json"))
    shard_raw = sum(p.stat().st_size for p in shard_files) / 1e6
    shard_gz = sorted(len(gzip.compress(p.read_bytes(), 6)) for p in shard_files)
    idx_r, idx_g = sz("index.json")
    bm_r, bm_g = sz("benchmark.json")
    cb_r, cb_g = sz("codebook.json")

    print(f"✓ {OUT.relative_to(ROOT)}/  (Quelle: Zweig-B-Parquet)")
    print(f"  index.json     {idx_r:6.2f} MB raw · {idx_g:5.2f} MB gzip   ← UPFRONT (slim)")
    print(f"  benchmark.json {bm_r:6.2f} MB raw · {bm_g:5.2f} MB gzip   ← lazy (Benchmark/Zeitreihe)")
    print(f"  codebook.json  {cb_r:6.2f} MB raw · {cb_g:5.2f} MB gzip   ← lazy? (Detail/Vergleich)")
    print(f"  reports/       {len(shard_files)} shards · {shard_raw:.2f} MB raw · "
          f"geschrieben {written} / unverändert {skipped} / entfernt {removed}")
    if shard_files:
        print(f"                 per shard gzip: median {shard_gz[len(shard_gz)//2]/1e3:.1f} KB · "
              f"max {shard_gz[-1]/1e3:.1f} KB")
    print(f"\n  Upfront (index, gzip): {idx_g:.2f} MB · Reports: {len(index_reports)} · Facts: {n_facts:,}")
    if index_reports:
        per = idx_g / len(index_reports) * 1e6
        print(f"  Projektion Voll-Load (4.278 Reports): index ≈ {per*4278/1e6:.1f} MB gzip upfront")


if __name__ == "__main__":
    main()
