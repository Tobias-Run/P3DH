"""Robust ECB reference FX rate fetcher for every (currency, refPeriod) pair in the
long form.

Design goals (this data feed will be re-run repeatedly as the pipeline scales):
  - Incremental: only fetches pairs missing from processed/fx_rates.csv, never
    re-fetches (or silently overwrites) rates it already has. Safe to run in CI
    on every build without hammering the API or racing rate-limits.
  - Two independent sources: frankfurter.app (primary, ECB-sourced proxy) falls
    back to the official ECB Data Portal SDW API if the primary is unreachable
    or returns nothing for a date — a single provider outage can't stall the
    pipeline.
  - Retried with backoff on transient network errors; a persistently failing
    pair is left out of the CSV (not written as blank) and reported, so the next
    run retries it automatically instead of the gap silently becoming permanent.
  - Sanity-bounded: a rate outside a plausible EUR cross-rate range is rejected
    rather than trusted, since a malformed API response is worse than a gap.

Output: processed/fx_rates.csv (currency, refdate, rate_to_eur) — 1 unit of
currency = rate_to_eur EUR. Consumed by the viewer's EUR normalization toggle.

Usage: python3 scripts/fetch_fx_rates.py [--force]
  --force   re-fetch every pair even if already present (e.g. to pick up an
            ECB revision), instead of only the missing ones.
"""

from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import argparse
import csv
import json
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
LONGFORM = ROOT / "processed" / "long_form_raw.csv"
OUT = ROOT / "processed" / "fx_rates.csv"

MAX_RETRIES = 3
BACKOFF_BASE = 1.5          # seconds; doubles each retry
REQUEST_TIMEOUT = 15
# Plausible bounds for "1 unit of currency = X EUR" across our currency set
# (smallest ~ISK at ~0.006, largest currencies we handle are all < 2 EUR/unit).
RATE_MIN, RATE_MAX = 1e-5, 10.0


def pairs_needed():
    pairs = set()
    with open(LONGFORM, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            cur = r["baseCurrency"].replace("iso4217:", "")
            if cur:
                pairs.add((cur, r["refPeriod"]))
    return sorted(pairs)


def load_existing():
    rates = {}
    if OUT.exists():
        with open(OUT, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("rate_to_eur"):
                    rates[(r["currency"], r["refdate"])] = float(r["rate_to_eur"])
    return rates


def _get_json(url: str):
    req = Request(url, headers={"User-Agent": "P3DH/1.0 (research pipeline)"})
    with urlopen(req, timeout=REQUEST_TIMEOUT) as r:
        return json.load(r)


def _with_retries(fn, *args):
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args)
        except (URLError, HTTPError, TimeoutError, ValueError, KeyError) as e:
            last_err = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF_BASE * (2 ** attempt))
    raise last_err


def fetch_frankfurter(cur: str, date: str) -> float:
    data = _get_json(f"https://api.frankfurter.app/{date}?from={cur}&to=EUR")
    return float(data["rates"]["EUR"])


def fetch_ecb_sdw(cur: str, date: str) -> float:
    """Fallback: official ECB Data Portal SDW series (units of `cur` per 1 EUR;
    invert for EUR-per-unit to match our schema)."""
    url = (f"https://data-api.ecb.europa.eu/service/data/EXR/D.{cur}.EUR.SP00.A"
           f"?startPeriod={date}&endPeriod={date}&format=jsondata&lastNObservations=1")
    data = _get_json(url)
    series = data["dataSets"][0]["series"]
    first = next(iter(series.values()))
    obs = next(iter(first["observations"].values()))
    cur_per_eur = float(obs[0])
    return 1.0 / cur_per_eur


def fetch_rate(cur: str, date: str) -> float:
    if cur == "EUR":
        return 1.0
    try:
        rate = _with_retries(fetch_frankfurter, cur, date)
    except Exception:
        rate = _with_retries(fetch_ecb_sdw, cur, date)  # let this raise if it also fails
    if not (RATE_MIN <= rate <= RATE_MAX):
        raise ValueError(f"rate {rate} outside plausible bounds [{RATE_MIN},{RATE_MAX}]")
    return rate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-fetch pairs already in fx_rates.csv")
    args = ap.parse_args()

    needed = pairs_needed()
    existing = {} if args.force else load_existing()
    missing = [p for p in needed if p not in existing]

    if not missing:
        print(f"✓ {OUT} already covers all {len(needed)} (currency, refdate) pairs — nothing to fetch")
        return

    print(f"{len(needed)} pairs needed, {len(existing)} already cached, fetching {len(missing)}...")
    failures = []
    for cur, date in missing:
        try:
            rate = fetch_rate(cur, date)
            existing[(cur, date)] = rate
            print(f"  ✓ {cur} {date}: {rate}")
        except Exception as e:
            failures.append((cur, date, str(e)[:80]))
            print(f"  ✗ {cur} {date}: {e}")
        time.sleep(0.2)  # be polite to the free APIs

    rows = [{"currency": c, "refdate": d, "rate_to_eur": r}
            for (c, d), r in sorted(existing.items())]
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["currency", "refdate", "rate_to_eur"])
        w.writeheader()
        w.writerows(rows)

    print(f"\n✓ {OUT}  ({len(existing)}/{len(needed)} pairs covered)")
    if failures:
        print(f"  {len(failures)} pair(s) still missing (will retry next run):")
        for c, d, err in failures:
            print(f"    {c} {d}: {err}")
        sys.exit(1)  # non-zero so CI surfaces a persistently-failing rate feed


if __name__ == "__main__":
    main()
