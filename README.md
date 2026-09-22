# EBA Pillar 3 Data Hub (P3DH) — data analysis pipeline

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22666716.svg)](https://doi.org/10.5281/zenodo.22666716)
[![Tests](https://github.com/Tobias-Run/P3DH/actions/workflows/tests.yml/badge.svg)](https://github.com/Tobias-Run/P3DH/actions/workflows/tests.yml)
[![Pipeline](https://github.com/Tobias-Run/P3DH/actions/workflows/pipeline.yml/badge.svg)](https://github.com/Tobias-Run/P3DH/actions/workflows/pipeline.yml)

**Europe's banks disclose everything. Almost nobody can read it.**

The EBA publishes the supervisory disclosures of the large EU and EEA
institutions in one place, machine-readable as XBRL-CSV. That was real
progress — and it solved the wrong half of the problem. The portal hands out
one bank's archive after another. Whether a capital ratio is high, whether a
country exposure looks unusual, or whether a reported figure is plausible at
all, it does not say.

Those questions need the population as a yardstick. So we built it: every
submission parsed, every data point resolved against the DPM, every template
reconstructed with real row and column labels — and then compared across
institutions.

The difference shows up quickly. One report in the holdings states **EUR 11.7
trillion in fixed management-body remuneration for nine people**, roughly three
times German GDP. Read on its own, that is a number. Read against 330
comparable reports whose median is EUR 1.6 million, it is a finding. We do not
correct it — we flag it and say why.

> **Current project status:** see `STATUS.md`, which carries the dated
> inventory. Open work is tracked as
> [GitHub issues](https://github.com/Tobias-Run/P3DH/issues); closed findings
> live in `BACKLOG.md` as a decision history.
> `docs/projektbriefing_2026-06.txt` is the original project brief — a
> historical document, not a reliable description of the current state.

### A note on language

Project documentation is **English**. The viewer offers a **German/English
switch**; English is the default. Working notes and analysis write-ups under
`docs/` are partly German — they are marked as such, and translating them is
tracked separately.

## 📄 Read out of the data

**[The Correction Game](docs/korrekturspiel.md)** *(German)* — should an
institution proactively correct an error it found in a published Pillar 3
report, or stay silent and hope nobody notices? A game-theoretic analysis,
checked against the corrections in our own catalogue. Result: correct — but not
because the market rewards honesty (for four out of five institutions that is
not even measurable), but because the Data Hub itself changed the probability
of detection.

## 🔗 Live viewer (in the browser, no installation)

**Public:** **https://tobias-run.github.io/P3DH/** — no clone, no server.

The **branch-A viewer** reconstructs the bank templates (KM1, OV1, CCR1 …) with
full row and column labels and offers **peer benchmarks, time series and
comparison** across institutions.

This is **not a sample**. Of the 489 institutions in the catalogue, 476 file
XBRL-CSV, and all of them are processed; the remaining 13 publish only
qualitative PDF packages (`*DISDOCS`, out of scope for branch B, analysed
separately in [#38](https://github.com/Tobias-Run/P3DH/issues/38)). The
catalogue counts far more submissions than we show reports, because most
entries are corrections of the same report and only the newest one counts. The
exact figures for the current holdings are in `STATUS.md` — they change with
every pipeline run, which is why they are not repeated here.

Three things the official portal does not do:

- **Distribution instead of ranking.** Peer groups by size class, scope of
  consolidation and reference date; percentile bands instead of a naked
  leaderboard. An outlier sits at the edge of a distribution, not at the top of
  a list.
- **Plausibility against the population** — flagged, never hidden, never
  altered.
- **Country exposure across institutions**: home share, country HHI and an
  honest quality flag for the residual bucket.

Details:

- **Landing page:** `index.html` · **viewer:** `processed/zweig_a/viewer_json.html`
- **How it loads:** the viewer fetches a slim `index.json` upfront and each
  report **only when opened**, as a per-report JSON shard (native `JSON.parse`,
  no CSV parser in the browser). The shards are **derived from the branch-B
  parquet** (a single transformation point) and served from the orphan `data`
  branch via **jsDelivr** (fallback: `raw.githubusercontent.com`).
- **Locally:** `python3 -m http.server 8766` in the repository root →
  `http://localhost:8766/`
- **Design:** an editorial system (#61) — quiet header, serif headings, a single
  accent, and **red means focus, never judgement**. Two tests hold that: the
  accent colour may appear only on focus selectors, and every text-on-surface
  pairing must meet WCAG AA in both themes.

## What this is not

Not supervision and not a league table. Comparability across institutions is
genuinely limited: accounting frameworks, scopes of consolidation and national
options differ, and the reporting taxonomy changed in the middle of the
holdings. Every ranking carries that caveat visibly. We prefer a "we cannot say
that" to a precision the data does not support.

And: **missing is not zero.** Institutions may lawfully omit under CRR Art. 432,
and a template *we* cannot place is our gap, not theirs. The viewer distinguishes
the two everywhere — conflating them would quietly turn silence into a finding.

## ⚠ Disclaimer / data sources

An independent, **non-commercial research and education project**, **not**
affiliated with the EBA or GLEIF. All external data are **public** and used
exclusively for **scientific and educational purposes**. Sources: EBA Pillar 3
Data Hub (© EBA), EBA DPM 2.0, GLEIF (LEI names). Provided "as is", without
warranty — always check figures against the official EBA source; no investment
or legal advice. Full text: **`DISCLAIMER.md`**.

## Licence & citation

The **code** is under the **MIT licence** (`LICENSE`) — `scripts/`, `tests/`,
`.github/`, the viewer, the landing pages and the project texts.

The MIT licence does **not** cover material that originates elsewhere and is
only passed through here: `codebook/dpm_codebook.csv` and
`codebook/template_titles.csv` (EBA DPM 2.0), `interim/edap_recon/manifest_*.csv`
(EDAP catalogue), `processed/lei_names.csv` and `processed/entity_meta.csv`
(GLEIF), and the published dataset itself. We hold no rights to those and grant
none. The full delineation is in `DISCLAIMER.md`.

To cite the software: `CITATION.cff` (GitHub renders "Cite this repository"
from it). **The disclosure data analysed here must be cited separately** — it
comes from the EBA, not from us.

The software is archived on Zenodo. The **concept DOI**
[10.5281/zenodo.22666716](https://doi.org/10.5281/zenodo.22666716) always points
at the latest version; to cite a specific state, take the version DOI from the
corresponding Zenodo record. The DOI covers the **software**, not the dataset.

The dataset itself is described in `docs/datensatz.md` *(German)*: every column
with provenance and semantics, plus the documented traps in one place. How a
release is produced is in `docs/release.md` *(German)*.

## Two output branches, one shared core

The expensive, error-prone part (DPM join, unit semantics, `filing-indicators`,
"missing ≠ zero") exists **only once**. It produces a long-form truth that is
condensed into **branch B (parquet)** — and **both** outputs derive from that
parquet. Viewer and analytics therefore share **one transformation point** and
cannot drift apart:

```
/raw  ─►  parser + DPM join (codebook)  ─►  long_form_raw.csv  ─►  BRANCH B: /processed/long/p3dh_long.parquet
                                                                    (self-contained, DuckDB; EUR-normalised +
                                                                     original, LEI/entity keys, flags, FX)
                                                                          │  build_zweig_a_shards.py
                                                                          ▼
                                                          BRANCH A: JSON shards (data branch → jsDelivr)
                                                          - index.json (report metadata) + codebook.json
                                                          - benchmark.json (cross-report head templates, lazy)
                                                          - reports/<key>.json (per report, lazy)
                                                          → viewer_json.html reconstructs the templates;
                                                            benchmark / time series / comparison in the browser
```

Branch A is **always derived from** branch B, never parsed in parallel. That
nothing drifts is no longer a claim: `scripts/check_branch_parity.py` compares,
per (report, template), the **multiset** of all `(row, column, value)` triples
between the shards and `long_form_raw.csv` — as strings, not via `float()`, so
that even a formatting change is caught. Plus, per (report, template), the
**currency**: the same number in a different unit is the same error, and the
value check alone was blind to it (#55 — 9,086 facts with the wrong rate, parity
green). It runs in the pipeline **before** publishing and aborts before
diverging figures go out.

One deliberate exception, added after pipeline run #14 failed on it: a report
whose filing indicators are **all false** is a complete and lawful statement —
"I disclose nothing". The shard builder creates an **empty** shard for it (#28)
so the institution does not vanish from the viewer, and the parity check allows
a shard without a long-form counterpart **exactly when it carries no cells**.
A shard with cells and no counterpart remains an error.

> **Withdrawn:** the legacy CSV viewer (`viewer.html`) read the long form
> directly in the browser and was meant as an independent cross-check. At
> 413 MB and 2.3 million facts the tab dies of memory — locally too — and it was
> 13 commits behind (no open row axis, no cell discriminator, no coverage
> states). A cross-check that diverges by design is not one. The check above
> does the same thing without a browser, and more sharply.

## Working locally

The pipeline state (long form, coverage matrix, branch-B parquet) does **not**
live in the repository but on the `data` branch under `state/`. A fresh clone
fetches it:

```bash
bash scripts/fetch_state.sh     # ~300 MB, after that everything is analysable locally
```

Then `python3 scripts/build_zweig_b.py`, or DuckDB directly on the parquet. The
DPM Access database (720 MB) is needed only to *rebuild* the codebook — the
finished `codebook/dpm_codebook.csv` is in the repository.

## Repository layout

| Directory | Contents |
|---|---|
| `raw/` | raw XBRL-CSV packages, **immutable**, never overwritten (gitignored) |
| `interim/edap_recon/` | catalogues and manifests (full harvest, waves, latest-wins) |
| `processed/long/` | **branch B**: `p3dh_long.parquet` — the joined truth that feeds the shards (gitignored, regenerable) |
| `processed/zweig_a/` | **branch A**: `viewer_json.html` + redirect `index.html`; the JSON shards live on the `data` branch |
| `codebook/` | DPM mapping: code → label / unit / title |
| `scripts/` | harvester, downloader, parser, branch-B/A builders, publish script |
| `tests/` | the test suite; runs on every push (count: see the Tests badge above) |
| `docs/` | decision memos, format notes, query examples, project brief, analyses |

## Phases

- **Phase 0** — scoping and access clarification ✅ → `docs/phase0_decision_memo.md`
- **Phase 1** — ingestion: full catalogue harvester (`harvest_catalog_query.py`) + wave-wise download ✅
- **Phase 2** — parsing and DPM join → codebook + long form ✅
- **Phase 3** — branch B (parquet/DuckDB) + branch A (JSON viewer, fed from branch B) ✅ ·
  RF 4.1↔4.2 bridge built (5,277 observed cells: 5,091 stable, 63 rebound,
  123 ambiguous) and flagged in the viewer (#26) ✅ — the 123 all sit in LIQ2
  (`74.00.a`–`f`), tracked as #70
- **Phase 4** — explorations: eight benchmark profiles (KM1, headroom, risk,
  liquidity, NPL/CQ3, **credit-deterioration chain**, ESG/41.00,
  remuneration/REM1) ✅ · percentile bands per peer group ✅ · plausibility
  profile (#17) ✅ · footprint metrics (#12) ✅ · peer clustering (#11/#13) ✅ ·
  cross-corpus analyses: correction direction, country exposure, report volume
  against disclosure breadth ✅

## Automated pipeline (GitHub Actions)

`.github/workflows/pipeline.yml` runs the whole chain without the laptop. It
fires **weekly by cron (Mondays 04:00 UTC)** and can be started manually via
`workflow_dispatch`:

```
fetch_state.sh → plan_delta.py → download (new only) → parse (incremental)
   → build_zweig_b.py → build_zweig_a_shards.py → publish_data_branch.sh
```

The run is **stateless**: `raw/` starts empty, the holdings come from `state/` on
the `data` branch, and the coverage matrix says what has already been processed —
only the difference is downloaded. Three switches: `harvest` (re-harvest the
catalogue, opt-in because the Playwright/Power-BI part is the most fragile),
`full_reparse` and `refresh_codebook`.

Whether the run works fully or incrementally is decided **once, before the
download** — and download, parse and gate all read that same answer. A codebook
changed by commit forces a full reparse on its own, because the holdings carry
the fingerprint of the codebook they were built with (#57). A **sanity gate**
compares the holdings before and after in either mode and aborts before
publishing if they shrink incrementally. The step order is verified as a graph
(`check_pipeline_order.py`, run in `tests.yml`).

Two further workflows run on their own schedules:

- `.github/workflows/disdocs.yml` — monthly, measures the qualitative PDF corpus
  (#38). It downloads roughly 2 GB and would otherwise dominate the main chain's
  runtime; it works **incrementally** and only measures what it does not
  already know.
- `.github/workflows/cron_watch.yml` — daily, asks **whether the weekly run
  happened at all**. The monitor inside `pipeline.yml` counts *failed* scheduled
  runs and therefore depends on a run having taken place; a schedule that dies
  silently is invisible to it. GitHub disables scheduled workflows in
  repositories that see no activity for 60 days, without notice — this watcher
  exists for exactly that class of failure.

> The `data` branch is **force-pushed and carries exactly one commit**. It has no
> history: every run replaces the previous state entirely. To cite a specific
> state, use the release asset, not the branch.

## Working principles

1. Reproducibility: the raw layer is immutable, every transformation is
   scripted — and **byte-exact**: same inputs, same outputs. The rule that
   carries it: *every field that flows into the output belongs in the
   `ORDER BY`.* Enforced by `scripts/determinism.py` in the execution path, not
   merely in a test. Why this earned its own principle, and how it was violated
   three times: `docs/reproduzierbarkeit.md` *(German)*.
2. Disclose assumptions (in code and README); do not ask about trivia.
3. Preserve "missing" ≠ "zero" throughout (`filing-indicators`) — **including in
   the interface**: the viewer shows, per report, which templates were
   deliberately not disclosed, where our holdings have gaps, and where the
   report contradicts itself. Without a declaration, **no** statement is made.
4. Name comparability traps (accounting, consolidation, national options) as a
   caveat in every analysis. **Since the open row axis (#56):** templates with an
   open axis fall into two classes. In CCyB1 (`67.01.A`) the row is an ISO country
   code and therefore comparable across institutions; in CC2 (`66.02`) and
   LI2/LI3 (`64.01`, `64.02`) it is the institution's **own balance-sheet line**,
   i.e. free text in the local language — 5,324 distinct rows in `64.02` alone.
   Those are analysable within one report, but **not** for peer comparison
   without prior mapping.
5. Resubmissions: per (institution, module, reference date) only the newest
   submission counts ("latest wins"). The **full catalogue**, including older
   versions, remains as an audit trail in
   `interim/edap_recon/manifest_full.csv` — and it is what makes the correction
   analysis possible in the first place, because superseded versions are still
   retrievable.

---

*Design inspired by The Economist — to whom we owe the insight that a chart may
hold an opinion as long as it names its source. In no way affiliated with the
publication; typefaces and colour values are our own, and we left them the red
rectangle.*
