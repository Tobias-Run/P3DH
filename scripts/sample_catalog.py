"""Draw a reproducible random sample from the full EDAP catalog.

Full catalog (manifest_full.csv, 4278 rows) still contains resubmissions, so first reduce
to latest-wins per (lei, consolidation, country, module, refdate), then take a random
fraction. Deterministic via a fixed seed so the sample is stable across runs.

Usage: python scripts/sample_catalog.py [fraction] [seed]   (defaults 0.20, 42)
Output: interim/edap_recon/manifest_sample.csv
"""

from pathlib import Path
import csv
import sys
import random
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
FULL = ROOT / "interim" / "edap_recon" / "manifest_full.csv"
OUT = ROOT / "interim" / "edap_recon" / "manifest_sample.csv"
GROUP_KEYS = ["lei", "consolidation", "country", "module", "refdate"]


def main():
    fraction = float(sys.argv[1]) if len(sys.argv) > 1 else 0.20
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42

    with open(FULL, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # latest-wins: keep the highest submission_ts per group
    latest = {}
    for r in rows:
        key = tuple(r[k] for k in GROUP_KEYS)
        if key not in latest or r["submission_ts"] > latest[key]["submission_ts"]:
            latest[key] = r
    latest_rows = list(latest.values())

    rnd = random.Random(seed)
    k = round(len(latest_rows) * fraction)
    sample = rnd.sample(latest_rows, k)
    sample.sort(key=lambda r: (r["country"], r["lei"], r["refdate"]))

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(sample)

    inst = len({r["lei"] for r in sample})
    countries = len({r["country"] for r in sample})
    print(f"Full catalog:        {len(rows)} rows")
    print(f"Latest-wins:         {len(latest_rows)} submissions")
    print(f"Sample ({fraction:.0%}, seed {seed}): {len(sample)} submissions "
          f"· {inst} institutions · {countries} countries")
    print(f"✓ {OUT}")


if __name__ == "__main__":
    main()
