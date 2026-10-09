# Comparison at a common reference date

Compare selects institutions and consolidation scopes, then resolves every
column at one reference date. The default is the latest date available for all
selected institutions. If no common date exists, it uses the latest date in the
combined history and explicitly marks missing reports. A date selected by the
user or supplied in a shared link is retained even if some or all reports are
unavailable. No column falls back to an older report or another consolidation
scope.

The comparison has its own reference-date selector. Changing it keeps the
institutions selected and reloads matching reports. Pinning another quarter of
the same institution/scope replaces the old pin rather than consuming another
comparison column. Legacy links or saved selections with multiple quarters of
one institution/scope are deduplicated. The four-column limit remains.

The selected date is persisted and shared as `cmpdate=YYYY-MM-DD` alongside the
existing report-pin keys. Pinned keys identify the selected institution/scope;
the displayed report date is governed by the comparison selector. Old shared
links without this parameter select the latest common date automatically.

## Template dropdown

At the selected date, options are grouped into:

1. **Filled by all selected institutions**.
2. **Filled by some selected institutions**, with counts such as **2/4**.

Filled means at least one non-null reported value in the loaded template.
A reported zero counts; an empty array or only null values does not. Merely
declaring a template in filing indicators does not make it filled. Counts use
all selected institutions, including a missing or failed report; a subset is
never labelled as coverage of all banks. Groups are recomputed on date changes.
Existing template selection is preserved where available.

A missing report remains a visible column with an explanation and dashes.
Failed report downloads are labelled separately and can be retried. Labels must
load before a labelled matrix is rendered; a failed label download provides a
retry instead of a silently unlabelled table. An obsolete asynchronous render
cannot overwrite a later date selection or a view selected meanwhile.

## Validation

- Eight JavaScript helper regressions exercise latest-common-date selection,
  explicit missing dates, consolidation scope, disjoint dates, duplicate pins,
  unavailable shared dates, zero/null/empty values and missing/failed coverage.
- Full suite: 1,549 tests pass.
- Actual Chromium on English/1280px and German/390px checks common-date column
  headings, template groups/counts, missing columns, shared-link reloads and an
  unavailable date. The fixture pair has 78 common and 54 partial templates at
  2025-12-31. These are fixture counts, not application-wide totals.
- Browser checks cover failed report retry and navigation during a delayed
  label load, with no JavaScript errors. The comparison check is included in CI.
- Advanced-peer browser regressions continue to pass on desktop/mobile.

Run `python -m unittest discover -s tests -p test_compare_dates.py` and
`python scripts/check_compare_dates.py`. The browser check needs Chromium and
the existing local dataset; it uses real locally served reports without
changing the data publication.
