"""Fetch ECB reference FX rates for every (currency, refPeriod) pair in the long form.

Source: frankfurter.app (free proxy of the official ECB reference rates; returns the
nearest previous business day for weekend/holiday dates, which matches how period-end
reference rates are commonly applied).

Output: processed/fx_rates.csv (currency, refdate, rate_to_eur) — 1 unit of currency
= rate_to_eur EUR. Consumed by the viewer's EUR normalization toggle.
"""

from pathlib import Path
from urllib.request import urlopen, Request
import csv
import json
import time

ROOT = Path(__file__).resolve().parent.parent
LONGFORM = ROOT / "processed" / "long_form_raw.csv"
OUT = ROOT / "processed" / "fx_rates.csv"


def pairs_needed():
    pairs = set()
    with open(LONGFORM, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            cur = r["baseCurrency"].replace("iso4217:", "")
            if cur:
                pairs.add((cur, r["refPeriod"]))
    return sorted(pairs)


def fetch_rate(cur: str, date: str) -> float:
    if cur == "EUR":
        return 1.0
    url = f"https://api.frankfurter.app/{date}?from={cur}&to=EUR"
    req = Request(url, headers={"User-Agent": "P3DH/1.0"})
    with urlopen(req, timeout=15) as r:
        data = json.load(r)
    return float(data["rates"]["EUR"])


def main():
    pairs = pairs_needed()
    print(f"Fetching {len(pairs)} ECB rates...")
    rows = []
    for cur, date in pairs:
        try:
            rate = fetch_rate(cur, date)
            print(f"  {cur} {date}: {rate}")
        except Exception as e:
            rate = ""
            print(f"  {cur} {date}: FEHLER {e}")
        rows.append({"currency": cur, "refdate": date, "rate_to_eur": rate})
        time.sleep(0.2)

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["currency", "refdate", "rate_to_eur"])
        w.writeheader()
        w.writerows(rows)
    ok = sum(1 for r in rows if r["rate_to_eur"] != "")
    print(f"\n✓ {OUT}  ({ok}/{len(rows)} Kurse)")


if __name__ == "__main__":
    main()
