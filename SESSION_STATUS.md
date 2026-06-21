# Session Status — 2026-06-21

## Completed

**Phase 0: Analysis & Procurement** ✅
- EDAP access method (Power BI embed + public HTTP URLs)
- XBRL-CSV format inspected, DPM 2.0 procured, Git/GitHub set up

**Phase 1: Ingestion** ✅
- `harvest_catalog.py` → 20 report URLs
- `download_raw_reports.py` → 20 `.zip` in `/raw/`
- `extract_manifest_metadata.py` → extended manifest (11 EUR, 8 SEK, 1 DKK)

**Phase 2: Parsing + DPM Resolution** ✅ (core), 🔧 (refinement open)
- `xbrl_csv_parser.py` → `processed/long_form_raw.csv` (**19,048 records**)
- Filing-indicator join **fixed** (was always False — K_ prefix + sub-letter mismatch)
- **DPM Access DB now readable on M1** via pure-python `access-parser` (no pyodbc/mdbtools/brew)
- **DPM 2.0 v4.2 DB** downloaded (755 MB, cumulative — covers RF 4.0/4.1/4.2)
- `build_codebook.py` → `codebook/dpm_codebook.csv`: resolves **3206/3206 (100%)**
  datapoints to `{template, row, col}` via `Variable → VariableVersion → TableVersionCell.CellCode`
- CellCode memo field decoded (4.2 DB stores it byte-pair-swapped after a BOM)
- Long-form now carries real cell coordinates: **82% of records resolved** to row/col

## Open Refinement (Phase 2.5)

~18% of records (templates **64.01/64.02, 66.02, 67.01, 29.0x**) don't resolve via the
simple `(datapoint, K_template)` join. Two causes:
1. **Open Z-axis / sheet dimension** — CellCode carries an extra `s*` token; the shared
   variable maps to multiple tables (incl. COREP `C_*`), join picks the wrong one.
2. **Sub-letter offset** — report files `67.01.A` but DPM table code is `K_67.01.b`
   (template-specific, not a uniform shift).
Fix: resolve via the relational `Table`/`TableVersion` codes instead of guessing the
filename sub-letter, and key the sheet dimension explicitly.

## Next Actions

```bash
cd /Users/tobibi/P3dh
# Phase 2.5: handle sheet dimension + Table-code join for remaining 18%
# Phase 4 Zweig A: render long_form_raw.csv back into KM1/OV1 template grids
```

## Key Milestones

| Phase | Status | Deliverable |
|-------|--------|-------------|
| 0 | ✅ | Decision memo, format specs, DPM procured |
| 1 | ✅ | `/raw/*.zip` (20) + extended manifest |
| 2 | ✅ core | Long-form (19,048 rows), DPM codebook (100% dp resolved, 82% cells) |
| 2.5 | 🔧 | Sheet-dimension + Table-code join for remaining 18% |
| 3 | ⬜ | RF 4.1 ↔ 4.2 mapping for time series |
| 4 | ⬜ | Zweig A (template rendering) + Zweig B (analytics) |

## Hardware Note

M1/8GB: `access-parser` reads the 755 MB DPM DB table-by-table — works, but heavy
tables (VariableVersion, TableVersionCell) load fully into memory.

## DPM Resolution Chain (reference)

```
dp<n>  ==  Variable.VariableID
       ->  VariableVersion (VariableID -> VariableVID)
       ->  TableVersionCell.CellCode  ==  "{Template, rNNNN, cNNNN[, s*]}"
```

## Repository

- GitHub: https://github.com/Tobias-Run/P3DH
- `.gitignore` excludes both `.accdb` (4.0 + 4.2) and raw downloads

---

**Git commits:**
1. `0486206` — Phase 0 complete
2. `9d90188` / `9e1bc02` — Phase 1 ingestion
3. `d17bf6d` — Phase 2 interim (parser, placeholder labels)
4. _(this session)_ — Filing-indicator fix + DPM resolution via access-parser (82% cells)
