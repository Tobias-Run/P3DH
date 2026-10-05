# Report and time-series loading, 5 October 2026

The production report view makes its time series wait for an unrelated 9.4 MB
decoded label dictionary and for every overview benchmark partition. The HTTP
loader tries its second origin only after the first fails, without a deadline.
A stalled CDN request can therefore leave initial loading or the time-series
placeholder indefinitely visible. The ordinary report/start view does not fetch
advanced peer groups: the newly published peer data is not its direct dependency.

The label wait was already present before PR #135; the merge did not introduce
that dependency. A new immutable data revision can require fresh CDN downloads,
but a particular slowdown on the user's desktop has not been independently
measured. Current probes returned HTTP 200 for both data origins. One cold CDN
index probe took 1.611 seconds versus 0.327 seconds at the raw origin; later
requests were faster. This supports adding a bounded fallback, not a claim of
a permanent CDN outage.

## Change

- Load time-series KM1 data independently of labels and unrelated overview
  partitions. Label loading remains on explicit table/KPI-source intent.
- If response headers from the preferred immutable data origin do not arrive
  within 1.2 seconds, start the alternative origin at the same pinned revision.
  The first valid JSON wins; outstanding requests are cancelled.
- After headers arrive, avoid starting a second large download merely because
  its body is still transferring. Each request has a 15-second deadline,
  including body reads; a stalled body can then fall back. Two stalled body
  transfers can therefore take approximately 30 seconds before a retry error.
- Keep SHA-256 integrity on both origins, missing-file semantics and legacy
  compatibility. The mutable revision pointer remains raw-origin-first and
  is not raced against a possibly stale CDN pointer.

## Controlled comparison

Same real local data and Chromium, with an artificial four-second delay:

| Delayed resource | Before: series ready | After: series ready |
| --- | ---: | ---: |
| Label dictionary | 5.523 s | 1.353 s |
| Non-KM1 overview partition | 5.231 s | 1.094 s |

The fixed report does not request the label dictionary before the series is
visible. A subsequent explicit label request succeeds. No JavaScript errors.
These timings describe the controlled test, not a promised desktop speedup.

The live-data functional check also rendered the report and series without
JavaScript errors and without requesting labels using the proposed viewer.
Chromium's execution-proxy certificate problem was handled by fetching every
intercepted HTTPS request with Python's configured, verified CA trust. No TLS
checks were disabled. These bridged timings are recorded separately and are
not treated as native-browser performance measurements.

## Validation

- 1,539 unit/data tests pass, including eight loader regressions for stalled
  headers, stalled bodies, cancelled losing requests, integrity errors,
  authoritative pointer absence, malformed pointers and both-origin failures.
- Advanced-peer browser tests pass in English/1280 px and German/390 px,
  including the 19 usable stable groups; zero JavaScript errors.
- General viewer runtime checks pass: report rendering, delayed and warm KPI
  source navigation, exact source-cell highlighting, desktop/mobile keyboard
  and touch navigation, filters, series, benchmark views and CSV export.

Reproduce with `python performance/check_loading_latency.py --baseline-ref
b7d59a2b13b685b386a0e7cb0d6286408b9bd344` and
`python -m unittest discover -s tests -p test_viewer_data_fetch.py`.
The browser check needs the existing local dataset and Chromium.

Detailed methods, requests, timings, data revision and local-codebook hash:
[`results/viewer_loading_2026-10-05.json`](results/viewer_loading_2026-10-05.json).
