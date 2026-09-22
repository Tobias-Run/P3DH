# Backlog

> **Open items have been tracked as GitHub issues since 2026-08-26:**
> https://github.com/Tobias-Run/P3DH/issues
> This file keeps the *closed* findings as a decision history — why something is
> built the way it is. It is no longer a task tracker.

## ✅ DONE: GAR/BTAR facts unplaceable (issue #3, closed)

Made visible by the placement guard (`scripts/check_fact_placement.py`): the
codebook did not know 636 dp codes, and 5,344 facts were therefore filtered out
in `build_zweig_a_shards.py` (`WHERE cell_row <> ''`) — without an error,
without a warning. Concentrated in `47.00.A` (GAR I, 4,700 of 6,197) and
`96.00.B` (TLAC2b creditor ranking, 127 of 132).

**The suspected cause was wrong.** Suspicion fell on a gap in the ESGDIS
templates inside the DPM Access database. In fact the codebook was simply
**out of date**: the refresh step in the workflow is opt-in and did not run
during the full load. The rebuild in the course of #56 resolved 9,775 of 9,775
dp codes (previously 9,068) and thereby covered 14,283 additional facts in
`47.00.A`/`49.01`/`96.00.A` and `96.00.B`.

State after pipeline run #6: **dp codes unknown to the codebook: 0.** Thirty-five
unplaceable facts remain (0.0015 %) — facts without any axis value, where the row
is deliberately left empty rather than invented (working principle 3).

Exactly this failure mode — a codebook change that silently affects new facts
only — was subsequently guarded as #57: the codebook's fingerprint sits next to
the holdings and forces a full reparse.

## ✅ DONE: filing indicators always `False` ("missing ≠ zero")

Fixed (utf-8-sig plus key normalisation to the base ID without the `K_` prefix).
The parser now also writes `processed/filing_indicators.csv` (the coverage
matrix). Regression tests: `tests/test_xbrl_csv_parser.py`
(`test_filing_indicators_not_all_false`, `..._key_normalized_and_values`).

## ✅ DONE: phase 2.5 — missing cell coordinates = open axis

About 16 % of records had no `cell_row`/`cell_col`, 100 % of them in templates
with an **open axis** (67.01 CCyB1 geographical, 66.02 CC2, 64.0x LI2/LI3,
29.0x CR9/CR10; also open-axis cells in 04.00/26.00). Those k files carry a
third, typed dimension column (`RIO` = country, `qADP`/`qABI`/`qEEA` = free text
or enumeration). For open tables the DPM holds **no static (row, col)** — the row
comes into existence at filing time, through the dimension value.

So it was **not a join bug** but data loss: the parser read only
`datapoint`/`factValue` and discarded the dimension column (in CCyB1, the country
of every position was lost). Fix: a new field `open_axis_dims` captures every
column beyond `datapoint`/`factValue` as `col=value;…`. Verified on the sample
report: 370 of 370 coordinate-less records are now identified through
`open_axis_dims`, none remain without an identity. Regression tests:
`test_open_axis_dimension_captured`, `test_open_axis_rows_not_collapsed`.

**✅ Follow-up done (2026-07-05):** the long form was regenerated across all 123
CODIS reports of the 20 % sample — 53,833 records carry `open_axis_dims`.
Optionally still open: resolving `open_axis_dims` against DPM open-axis members
(e.g. `eba_GA:NL` → "Netherlands") for readable open axes in the viewer.

## ✅ DONE: delta pipeline + automation (2026-08-21)

- **The parser is incremental** (`source_file` ledger; `--full` forces a
  rebuild). Two defects found along the way were fixed: (a) the set of valid
  sources came from the ZIPs *on disk* — on a stateless runner the merge would
  have discarded the entire existing holdings; it now comes from the manifest.
  (b) Submissions without placeable facts exist only in the coverage matrix and
  were therefore re-parsed on every run; the coverage matrix is now the
  authoritative ledger. Regression tests: `IncrementalMergeTest` (cross-checked
  against the old logic).
- **Download delta** via `scripts/plan_delta.py` → `manifest_todo.csv` (manifest
  minus what has already been processed), instead of relying on the files present
  in `raw/`.
- **Automation** in place: `.github/workflows/pipeline.yml`, including the sanity
  gate against shrinking holdings.

**Harvest diff** (issue #6) has been closed since 2026-09:
`scripts/harvest_delta.py` classifies every change (new · resubmission ·
superseded · withdrawn), `harvest_log.csv` and `manifest_delta.csv` are
committed — previously the append-only history was created on a throwaway runner
and started afresh on every run — and the run summary reads the diff. Plus a
shrink gate **before** `manifest_full.csv` is overwritten: afterwards the basis
for comparison would be gone. In the workflow the harvest stays deliberately
**opt-in** — it is the most fragile part of the chain (headless Power-BI embed).

## ✅ DONE: the weekly cron is live

Prepared commented-out for a long time, armed with run #13 (2026-09-15), first
fired on 2026-09-21 — 5 h 21 late, because GitHub's scheduler is explicitly
best-effort. That run (#14) failed on a false positive in the parity check: an
institution filing a package with **no data files at all**, every filing
indicator `false`, is making a complete and lawful statement, and the shard
builder deliberately creates an empty shard for it (#28). The guard has since
distinguished the two cases by the shard's content. Run #15 went green through
publish.

The blind spot that surfaced alongside it is closed as well: the failure monitor
counts *failed* scheduled runs and therefore cannot see a schedule that never
fires. `.github/workflows/cron_watch.yml` now asks the other question daily —
see `STATUS.md`, "Operations".
