# Benchmark review implementation

Implementation order requested on 22 October 2026: start with review point 6
(usable coverage), then fix the reference population and build the bank-centred
workflow, results, economic peer review and reproducible exports.

## 1. Usable coverage

The benchmark now reports comparable values, usable peer populations (minimum
five values per metric) and values receiving percentile context. It applies
the existing metric-specific unit/scale exclusions and separates reference
date, scope and framework where the chosen basis defines them. Missing values
are not zero. Fitting inputs remain unranked in cluster mode.

The cluster selector separates usable from insufficient-data groups for the
current eligible metric. Each option gives current comparable values versus
frozen roster size; roster size alone never establishes availability. If all
dates are selected, an explicit note asks for a date-specific coverage check.
Ownership assumptions/unverified classifications are counted separately.

Checks: six controlled JavaScript regressions plus actual Chromium in English
at 1280px and German at 390px. On the pinned production snapshot
`06988f21634d853db3b7a09dbc81d23f6a0acaf3`, March 2026 has six usable CET1
populations with 43 rankable observations, while NSFR has five populations
with 38 observations. March NPL has no usable values. No JavaScript errors.

This first change exposes the current population without silently changing the
frozen roster or refreshing classifications. Subsequent changes address the
separately identified filter/deduplication inconsistencies.

## 2. Canonical populations and display search

Known-family representatives are selected within each peer partition before
cluster/ownership/role filters. The stable group identifier belongs to that
partition, so a mother in another group cannot suppress its subsidiary here.
Unknown families remain separate. The same cluster has identical members and
metric ranks whether selected explicitly or viewed among all clusters.

Search now filters display rows after statistics are computed. Country, size,
scope and date remain deliberate comparison-population filters. Their role is
stated in the UI. Standard peer keys now include the reporting framework;
unknown frameworks have no percentile. The legacy standard explorer keeps its
published report population independently of whether optional peer metadata
was previously opened; it does not claim proven group independence.

Checks: ten JavaScript population/coverage regressions and actual browser
checks. Cluster `60359f158ce7` at 2025-12-31 retains all five NPL observations
and identical per-metric ranks in both filter states. Searching the exact
UniCredit name reduces visible rows to one without changing its statistical
denominator or percentile. Legacy distribution contract tests pass.

## 3. Reference institution, date and scope

The Benchmark tab from an explicitly opened report uses that institution,
report date and scope as its reference. The overview also offers an explicit
entry button. Alternatively, select a reference in the data explorer. An
available stable assignment is suggested first; the user can choose another
basis, cluster and population filters. This is a proposal, not a certified
economic peer group.

Reference analysis accepts only the exact date, scope and reporting framework
of the reference report. Missing reports are not substituted with another
date. An explicit unavailable date produces a missing-reference state. The
explorer starts at the latest available date; choosing all dates remains
possible and is represented by `d=all` in the shared link. Search and folding
conspicuous rows affect display only.

## 4. Decision-useful statistics and distributions

The default KM1 analysis starts with CET1, capital headroom, LCR, NSFR and NPL.
Each card shows the institution's value, its metric-specific valid n, median,
Q1–Q3, numerical percentile and difference from the median. Ratios use
percentage-point differences. Medians/quartiles/percentiles require at least
five valid values; zero remains valid and missing values stay missing.
Profile eligibility, plausible corridors and the existing monetary unit/scale
guards apply before statistics. Clustering inputs are not ranked in cluster
mode. A high numerical percentile is not a judgement of bank quality; NPL
explicitly explains its adverse direction.

Distributions follow the visible columns and add a reference-value marker;
out-of-range markers are labelled. Custom-cohort outlier fences use the same
cohort, including added institutions. For UniCredit CON at 2025-12-31, the
unmodified nine-member proposal has CET1 n=9/P83, LCR n=8/P69, NSFR n=8/P56
and NPL n=9/P39 (rounded display percentiles). At March 2026 NPL is missing;
the analysis does not carry December's values forward.

## 5. Economic review and user-controlled membership

The member panel shows ownership provenance, explicitly assumed/unverified
classifications, current TREA size ratios, risk-share differences and available
business-model descriptions. Missing fitting features are stated explicitly.
The user can omit or add banks at the same date/scope/framework. Known families
still have one representative, with the reference institution preferred.
Changes and the user's membership confirmation are shareable. Confirmation
does not claim independent economic validation and resets when the population
or date changes. Frozen assignments are never rewritten by this interaction.

`business_model_pilot.js` contains a deliberately limited official-source pilot
dated 2026-10-22, with exact LEI/scope applicability, evidence terms and source
SHA-256 values:

- [Volkswagen Financial Services](https://www.vwfs.com/en.html), CON:
  financing, leasing, insurance and mobility.
- [BNP Paribas](https://group.bnpparibas/en/group), CON: diversified banking
  across its three stated business divisions.
- [BNY](https://www.bny.com/corporate/global/en/about-us.html), IND: a group
  description of custody/securities services, explicitly **not validated for
  the individual reporting entity**. It is not counted as a reviewed model.

There is no automatic inheritance to other entities or scopes. All other
business models remain unreviewed. This is not a completed taxonomy for the
476 reporting institutions. UniCredit/Deutsche Bank source pages returned
HTTP 403 in this review and were not used as evidence.

Run `python scripts/review_peer_suitability.py` to reproduce
[the diagnostic result](benchmark_peer_suitability_2026-10-22.json). The script
enumerates 897 within-roster pairs; business-model comparison is possible only
for the sourced pilot, not for all those pairs. The reviewed VWFS–BNP pair is
in stable group `0a36f009f9f1` despite different business models. Its legacy
distance is 0.1733, including only 0.0246 from the risk term. Replacing the
mean absolute risk-share distance with capped half-L1 raises total distance to
0.2102, still below the 0.25 threshold. This sensitivity experiment does not
justify a blind coefficient change or a new frozen roster. The UI warns about
mixed reviewed models and leaves membership decisions explicit.

## 6. Consistent report context and reproducible exports

Opening a KPI's definition/source from the analysis retains the cohort.
The report overview uses its same n and percentile; reports outside the active
cohort/date get no fallback percentile. Published arbitrary-cell peer context
cannot be recomputed from the profile extracts, so its control is disabled
while reference analysis is active, with an explanatory tooltip. The ordinary
report view retains its existing published cell context.

The reference-analysis CSV includes the exact data revision, advanced-peer
SHA-256, pilot version, reference report, basis/cluster, full statistical
membership and confirmation state. Per metric it records the own value,
valid n, median, quartiles, percentile, delta/unit, ownership provenance counts,
unknown heads and source cells. The table CSV retains the displayed rows and
adds cohort statistics per visible metric; display search does not change
their denominator. Shared links reproduce the configuration against the
then-current dataset; the CSV additionally records the immutable revision and
exact members for auditability.

## Validation and release boundaries

The implementation is split into dependent PRs: coverage first, canonical
populations second, reference analysis/review/exports third. No production
data, ownership table, fit weights or frozen memberships are modified.

Validation uses the pinned snapshot above and all 883 locally rebuilt report
shards. The complete Python/Node suite, actual-browser guided-analysis checks
(English 1280px, German 390px), existing compare/advanced-peer checks and the
general viewer runtime cover the implementation. The guided cases verify
membership edits and confirmation across reload, matching report/CSV ranks,
missing March NPL, and no JavaScript errors. Localization explicitly exercises
the all-date explorer as well as cold/warm report and comparison loads.

Final local result on 2026-10-22: **1,573 tests passed, zero skipped**. The
general viewer runtime, reference-analysis browser regression and JavaScript
syntax checks passed. Desktop/mobile guided cases reported zero JavaScript
errors, including the report overview updating after population-filter changes.
