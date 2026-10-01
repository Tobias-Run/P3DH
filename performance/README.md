# Performance review and reproducible experiments

The German review is in [`../docs/performance_review.md`](../docs/performance_review.md).
Raw measurements, response headers, screenshots and Chrome CPU profiles are in
[`results/`](results/). This harness is development tooling, not a runtime dependency
of the GitHub Pages site.

## Source and data

- Baseline main: `902d0add0d117473791d129bc2d9180e9761e7f4`
- Measured data: `f8adc69c5e8b623b289211cf4bb2f463916d23bf`
- Exact downloaded file sizes and SHA-256: `results/snapshot.json`.
- Source variant SHA-256: `results/variant_hashes.json`.
- `baseline`, `formatters`, and `network` HTML copies are generated and ignored by Git.
- `candidate` is `processed/zweig_a/viewer_json.html` in the working tree.

The data is deliberately pinned to a commit, so a later scheduled publication cannot
change half of an A/B experiment. No production deployment is required to run the tests.

## Reproduce

Python 3.12, Playwright and Chromium are required. This environment used
`/usr/bin/chromium`; change the explicit executable path in the scripts for another
machine. The repository's usual Python test dependencies are in `requirements.txt`.

From the repository root:

```bash
python performance/download_snapshot.py --data-ref f8adc69c5e8b623b289211cf4bb2f463916d23bf
python performance/prepare_variants.py
python performance/measure.py --variants baseline candidate --profiles desktop mobile4g --runs 5 --output final_comparison.json
python performance/measure.py --variants baseline formatters network candidate --profiles desktop --runs 3 --output desktop_ablation.json
python performance/verify.py
python performance/capture_profiles.py
python performance/partition_payload.py
python performance/probe_live.py
python performance/summarize.py
python performance/plot_results.py
```

Run measurement commands **sequentially**, without concurrent builds or browser
tests. Browser timings on a shared cloud host are subject to scheduling noise.
Do not interpret five lab samples as a population p75 or field Core Web Vitals.

## Scenarios and metrics

Each sample gets a new browser context. The cold visit loads `#benchmark` or BNP
Paribas' 2025-12-31 consolidated report (149 templates). The second visit leaves
the document for `about:blank`, then returns in the same context, preserving HTTP
cache but forcing a new document and a new `performance.timeOrigin`.

- Desktop: 1440 × 900, no artificial CPU/network throttle.
- Mobile simulation: 390 × 844, CPU 4× slowdown, 60 ms additional latency,
  500,000 bytes/s download and upload (4 Mbit/s), device scale factor 1.
- The local server sends gzip level 6, ETag and `Cache-Control: public, max-age=600`.
  It precompresses before timing to exclude compression work from the serving path.
- Production data uses Brotli in the observed jsDelivr responses. The local
  experiment uses gzip consistently across both variants, so its byte values and
  timings must not be substituted for production Brotli values.
- Ready time: relevant DOM exists, followed by two animation frames. This is a
  reproducible usable-view marker, not a browser-standard Core Web Vital.
- LCP and CLS are collected with PerformanceObserver in each navigation. CLS is
  aggregated with session windows; neither metric has field coverage here.
- Blocking time is the sum of `max(longtask.duration - 50 ms, 0)` during the
  observation window. It is **not** Lighthouse TBT (different window).
- Sort/profile/filter timings run the action and wait for two animation frames.
  They are synthetic action latencies, **not INP**.
- Heap is Chromium's coarse `performance.memory.usedJSHeapSize` snapshot and may
  vary with garbage collection. No forced GC is used.
- First expansion is timed until the populated table is observed. The optional
  peer shape strip may arrive later; it is captured in the settled snapshot.

The browser warms a complete benchmark render before three timed render-only
iterations. The median of those iterations is the microbenchmark value per sample.

## Validity and rejected data

The initial pilot discovered that navigating to the same fragment URL can remain
inside the same document. Its warm-visit numbers were invalid. The interrupted
pilot is retained locally as `results/excluded_same_document_navigation.json`
and excluded from Git and the report. `desktop_ablation.json` was produced before
this correction: only its **cold** samples are used in the review and summary.
The final comparison was restarted with the corrected navigation.

Live Chromium initially rejected the measurement environment's TLS interception
CA. This was an environment failure, not a website failure. The environment CA
was installed into the browser's NSS trust database in the **same execution** as
the live probe. TLS verification was not disabled. On an ordinary machine this
environment-specific setup is unnecessary.

## Correctness checks

`verify.py` checks:

- Full benchmark row values, sorting and percentile maps for all eight profiles.
- CSV content, excluding the necessarily different local view URL and creation timestamp.
- Entity time-series membership for all 883 reports, retaining CON/IND separation.
- German/English number formatting against the native reference across precision
  settings, negative zero, rounding boundaries and non-finite inputs.
- Mid-rank percentiles for 1,001 synthetic rows including ties, missing values and
  a below-minimum peer group.
- Raw table HTML for three large reports, including labels, flags and peer context.
- Labels absent from initial benchmark/collapsed report loads, followed by a
  successful direct expansion without pointer-hover prefetch.
- Cache revalidation after changing the body and ETag at the same URL.

The cache contract test verifies fresh data (`1, 1, 2`), but this Chromium/server
combination returned HTTP 200 for all three requests, without `If-None-Match`.
It therefore provides no evidence of 304 bandwidth savings. The controlled warm
runs likewise transferred JSON again; do not attribute the byte reduction to caching.

The existing browser regression suite can also be run with
`python performance/run_runtime_check.py`. It downloads missing report shards
from the pinned commit for test setup. For the Python suite, install the repository
test dependencies, then run `python -m pytest tests/ -q`.
The full suite checks corpus-wide minimum counts: first fetch all report shards
with `python performance/download_snapshot.py --data-ref f8adc69c5e8b623b289211cf4bb2f463916d23bf --all-reports`.
This writes `results/full_snapshot.json` without replacing the original scenario
manifest. The final suite passed 1,452 tests and skipped one Parquet schema check
because the Parquet artifact was not built. Plot generation requires Matplotlib.

The measured candidate source hash is retained in `variant_hashes.json`.
`final_revision.json` records the final source hash and verifies that its only
post-measurement source change is a comment rewording for an existing static test.

`partition_payload.py` is a separate **transfer-only** design experiment. It
partitions the real benchmark by template, verifies exact reconstruction, then
measures payloads needed by each profile. It does not ship a new loader and does
not claim end-to-end speedups for this unimplemented strategy.

## Reading artifacts

- `final_comparison.json`: raw controlled A/B runs.
- `*_summary.json`: median, descriptive p90, min and max, plus failures.
- `desktop_ablation.json`: cold component experiments (three repetitions).
- `live_http.json`, `headers_*.txt`, `live_browser.json`: actual hosted responses.
- `verification.json`: equivalence checks and output hashes.
- `*.cpuprofile`: load in Chrome DevTools → Performance/JavaScript profiler.
- `partition_experiment.json`: measured payload partition feasibility.

No performance script uploads data, changes GitHub Issues, merges a PR or deploys
the site. The only remote requests are reads of the public repository and Pages/CDN.

## Sequential issue implementation (#115–#119)

The earlier review and its `final_comparison.json` / `variant_hashes.json` describe
an earlier candidate. Follow-up implementation and measurements are documented in
[`../docs/performance_implementation.md`](../docs/performance_implementation.md).
Reproduce the final implementation after downloading all report shards:

```bash
python scripts/build_benchmark_parts.py
python performance/test_ux.py --issue 119
python performance/verify.py
python performance/run_runtime_check.py
python -m pytest tests/ -q
python performance/trace_layout.py --output layout_after.json
python performance/measure.py --variants baseline candidate --profiles desktop mobile4g --runs 5 --output implementation_comparison.json
python performance/measure_actions.py
```

Generating parts adds manifest metadata to the pinned codebook and retains the
legacy benchmark. Both variants use this same derived dataset. The final viewer
pages 100 rows; calculations and export still use all results. Source hashes for
each measurement are stored beside its raw output. Follow-up warm-cache behavior
uses normal caching for content-addressed parts and commit-pinned production data;
the earlier review's cache observations do not describe this final loader.
