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
