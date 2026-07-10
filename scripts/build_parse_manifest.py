"""Build the parse manifest: union of the original latest-wins set and the random
sample, filtered to XBRL-CSV report packages.

All Pillar 3 XBRL modules share the same package structure (reports/k_*.csv,
FilingIndicators.csv, parameters.csv) and are covered by the DPM codebook —
CODIS, MRELTLACDIS (K_90/91), REMDIS (K_30), FINDIS, IRRBBDIS, ESGDIS, GSIIDIS.
Excluded are only the *DISDOCS packages: those contain the banks' qualitative
Pillar 3 PDF reports, not XBRL-CSV (candidate for a separate PDF index later).

Output: interim/edap_recon/manifest_parse.csv — consumed by xbrl_csv_parser.py.
"""

from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parent.parent
RECON = ROOT / "interim" / "edap_recon"
SOURCES = [RECON / "manifest_latest.csv", RECON / "manifest_sample.csv",
           RECON / "manifest_wave.csv"]   # full reference-date waves (e.g. 2025-12-31)
OUT = RECON / "manifest_parse.csv"


def main():
    rows, seen = [], set()
    for src in SOURCES:
        if not src.exists():
            continue
        with open(src, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if "DISDOCS" in r["url"] or r["url"] in seen:
                    continue
                seen.add(r["url"])
                rows.append(r)

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    leis = {r["lei"] for r in rows}
    print(f"✓ {OUT}")
    print(f"  {len(rows)} XBRL-Submissions · {len(leis)} Institute")


if __name__ == "__main__":
    main()
