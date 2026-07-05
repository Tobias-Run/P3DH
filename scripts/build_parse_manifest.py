"""Build the parse manifest: union of the original latest-wins set and the random
sample, filtered to CODIS submissions (the only module the parser/codebook support yet).

Output: interim/edap_recon/manifest_parse.csv — consumed by xbrl_csv_parser.py.
"""

from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parent.parent
RECON = ROOT / "interim" / "edap_recon"
SOURCES = [RECON / "manifest_latest.csv", RECON / "manifest_sample.csv"]
OUT = RECON / "manifest_parse.csv"


def main():
    rows, seen = [], set()
    for src in SOURCES:
        if not src.exists():
            continue
        with open(src, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if "CODIS" not in r["url"] or r["url"] in seen:
                    continue
                seen.add(r["url"])
                rows.append(r)

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    leis = {r["lei"] for r in rows}
    print(f"✓ {OUT}")
    print(f"  {len(rows)} CODIS-Submissions · {len(leis)} Institute")


if __name__ == "__main__":
    main()
