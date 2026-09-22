# Project status

**As of 2026-09-22** · holdings from pipeline run #15 (2026-09-21, green
through publish)

This file describes *where the project stands*. Open work is tracked as
[GitHub issues](https://github.com/Tobias-Run/P3DH/issues); closed findings live
in `BACKLOG.md` as a decision history. The session logs that used to sit here
are in this file's git history.

> The figures below are a **dated snapshot**. They change with every pipeline
> run that finds new submissions, which is why the README does not repeat them.

## Holdings

| | |
|---|---|
| Reports | **882** (institution × scope of consolidation × reference date) |
| Facts | **2,295,224** |
| Institutions | **474** in the holdings · 476 in the catalogue filing XBRL-CSV |
| Countries | 30 |
| Reference dates | 2025-06-30 · 2025-09-30 · 2025-10-31 · 2025-12-31 · 2026-03-31 |
| Reporting framework | RF 4.1: 2,231,690 facts · RF 4.2: 63,534 |
| Unplaceable | **35** facts (0.0015 %) — without any axis value |

The holdings have not changed since run #13: runs #14 and #15 found no new
submissions, which matches the EBA's quarterly publication rhythm. A run that
changes nothing is the normal case between reference dates, not a fault.

**Coverage is complete, not a sample.** The catalogue counts 4,278 submissions
and 489 institutions, but most entries are resubmissions and corrections of the
same report ("latest wins", working principle 5). Of the 489 institutions, 476
file XBRL-CSV — **474 of them are in the holdings**. The remaining 13 publish
only qualitative PDF packages (`*DISDOCS`), which are out of scope for branch B
and analysed separately in
[#38](https://github.com/Tobias-Run/P3DH/issues/38).

The difference of 2 between catalogue (476) and holdings (474) has been
**evidenced rather than assumed** since
[#7](https://github.com/Tobias-Run/P3DH/issues/7), and it consists of two
different things:

- one institution is [#28](https://github.com/Tobias-Run/P3DH/issues/28): the
  submission was downloaded, parsed and declares templates in the coverage
  matrix, but carries not a single placeable cell;
- for the other, **all** catalogue rows are dead EDAP links (checked by HEAD:
  404 — a catalogue row without a published file).

`processed/catalogue_coverage.csv` tracks this per report. At report level,
**882 of 925** are loaded (95.4 %); the 43 gaps are 40 PDF-only institutions,
one #28 case and two dead links — **not a single open, loadable report**.

## Phases

| Phase | Status | State |
|---|---|---|
| 0 — scoping & access | ✅ | `docs/phase0_decision_memo.md` |
| 1 — ingestion | ✅ | full catalogue harvester (Power-BI `query`), wave-wise download, harvest diff with classification and shrink gate |
| 2 — parsing & DPM join | ✅ | 9,775/9,775 datapoints resolved, `codebook/dpm_codebook.csv` (14,221 rows), template titles via the EBA layout |
| 2.5 — open axes | ✅ | the dimension value becomes the row (CCyB1 → ISO country); without an axis value the row stays empty rather than guessed |
| 3 — multi-module | ✅ | CODIS · ESGDIS · FINDIS · GSIIDIS · IRRBBDIS · MRELTLACDIS · REMDIS; only `*DISDOCS` (PDF) excluded from branch B |
| 3b — bridge RF 4.1↔4.2 | ✅ | observation-based: 5,277 cells, of which 5,091 stable, 63 rebound, 123 ambiguous ([#70](https://github.com/Tobias-Run/P3DH/issues/70), all in LIQ2) |
| 4A — branch A (viewer) | ✅ | JSON viewer as the default, shards lazy, ready for the full load |
| 4B — branch B (parquet) | ✅ | `p3dh_long.parquet`, self-contained, feeds branch A |
| 4 — explorations | ✅ | eight benchmark profiles, percentile bands, plausibility profile, footprint, peer clustering, and the cross-corpus analyses listed below |

## Quality commitments in the execution path

None of these is a claim in the README — each either aborts the pipeline or
produces an artefact:

| Check | Against | State at run #15 |
|---|---|---|
| `check_branch_parity.py` | viewer figures ≠ long form, including the **unit** | 2,295,189 cells · 41,902 currency pairs · green |
| `check_fact_placement.py` | silent fact loss through unknown dp codes | unknown dp codes: **0** |
| `check_reference_data.py` | FX/metadata do not cover the facts | 42/42 rates · 474/474 institutions · 0 monetary facts without a EUR value |
| Sanity gate | shrinking holdings through a merge error | reports in either mode, aborts when incremental |
| `determinism.py` | non-reproducible outputs | in the execution path, not only in a test |
| Codebook fingerprint | a codebook change must affect new facts only | decides before the download ([#57](https://github.com/Tobias-Run/P3DH/issues/57)) |
| `check_pipeline_order.py` | a step that reads an artefact produced later | 48 steps, topology valid |

Test suite: **1,442** tests as of this date; the live count is on the Tests
badge in the README. The suite runs in **two passes** — a fast one without
holdings, and a second one with the branch-A artefacts built, so that the tests
which need them actually run. A skipped test in the second pass fails the job
([#69](https://github.com/Tobias-Run/P3DH/issues/69), closed): a check that
declares itself satisfied in the absence of its subject is exactly the failure
mode this project hunts.

## Analyses as a product

These steps deliberately do **not** abort: their findings concern the
submissions, not our pipeline.

- **Plausibility** ([#17](https://github.com/Tobias-Run/P3DH/issues/17), [#36](https://github.com/Tobias-Run/P3DH/issues/36)): 10,942 findings in 474 of 882 reports (3,867 high · 6,235 medium · 840 low) from four rule families — 5,816 cell outliers, 214 remuneration corridor, 4,870 time jumps, 42 structural breaks. The time comparison measures an institution against itself and needs neither peers nor a currency assumption.
- **Footprint** ([#12](https://github.com/Tobias-Run/P3DH/issues/12)): 377 reports, 271 institutions; median domesticity 82.3 %, 149 institutions more than 90 % home-centred.
- **Risk-taker share** ([#40](https://github.com/Tobias-Run/P3DH/issues/40)): REM1 against the Wikidata headcount, 83 reports. Raw, the ratio measures **size** (r² = 0.755 against log10 headcount); what is reported is therefore the residual against the size expectation — p10 0.48 · median 1.03 · p90 1.87.
- **Negative set** ([#42](https://github.com/Tobias-Run/P3DH/issues/42)): of 2,863 supervised entities, **one** significant institution leaves no trace at all. Eleven more file under an identifier other than the ECB LEI — suspicion reported, coverage not claimed.
- **Catalogue coverage** ([#7](https://github.com/Tobias-Run/P3DH/issues/7)): 882 of 925 catalogue reports loaded; the 43 gaps are separated by cause, **none** of them open and loadable.
- **Credit-deterioration chain** ([#16](https://github.com/Tobias-Run/P3DH/issues/16)): performing → forborne → non-performing across three templates that EDAP never joins. 392 reports; median NPL ratio 2.33 %, median coverage ratio 41.0 %. Also a benchmark profile in the viewer, cross-checked value by value against the artefact.
- **Correction direction** ([#31](https://github.com/Tobias-Run/P3DH/issues/31)): do institutions present themselves more favourably through corrections? **No systematic direction** — 8 versus 5 at pair level. The larger finding is that not every resubmission is a correction: of 202 pairs, only 91 change a reported value at all, and 60 change no fact whatsoever.
- **Report volume against disclosure breadth** ([#38](https://github.com/Tobias-Run/P3DH/issues/38)): all 1,073 qualitative PDF packages measured. Report length has almost nothing to do with institution size (r² = 0.005) but does track what is disclosed (r² = 0.283). English is 43.9 % of the corpus — a single-language analysis would reach less than half of it.

## Operations

- **Pipeline:** `.github/workflows/pipeline.yml`, weekly by `schedule` (Mondays 04:00 UTC) and at any time manually via `workflow_dispatch`, stateless — `raw/` starts empty, the holdings come from the `data` branch. The order of the 48 steps has been verified as a graph since [#8](https://github.com/Tobias-Run/P3DH/issues/8) (`check_pipeline_order.py`, run in `tests.yml`). Run #14 fired 5 h 21 late (GitHub's scheduler is explicitly best-effort) and failed on a false positive in the parity check; run #15 went green through publish.
- **Monitoring, two watchers for two different failures:**
  - *Failed runs* — if **two scheduled runs fail in a row**, the `melden` job opens an issue and assigns it to the owner (`scripts/check_run_streak.py`). A single red run triggers nothing: EDAP is occasionally away, a runner fails, Wikidata throttles; that usually heals by the next week. Manually started failures do not count, because somebody is watching. If the run history cannot be retrieved, it **reports rather than stays silent**.
  - *Absent runs* — `.github/workflows/cron_watch.yml` asks daily whether a scheduled run happened **at all** (`scripts/check_run_absence.py`). The watcher above counts failed runs and therefore depends on a run having taken place; a schedule that dies silently is invisible to it. GitHub disables scheduled workflows in repositories with no activity for 60 days, without notice. This watcher deliberately lives outside `pipeline.yml`, so that it does not share the fate it monitors.
- **DISDOCS corpus:** `.github/workflows/disdocs.yml`, monthly, incremental — roughly 2 GB per full run, which is why it is not in the main chain.
- **Tests:** `.github/workflows/tests.yml`, on every push, in two passes.
- **Delivery:** orphan branch `data` → jsDelivr. **The branch is force-pushed and carries exactly one commit** — it has no history; every run replaces the previous state entirely.
- **Development:** feature branch → PR → merge into `main`.

## Hardware (local development)

M1 / 8 GB: `access-parser` reads the 755 MB DPM database table by table;
Playwright headless and sequential; HTTP download with at most 4 workers.
