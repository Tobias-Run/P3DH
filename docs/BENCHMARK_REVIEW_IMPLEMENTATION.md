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
