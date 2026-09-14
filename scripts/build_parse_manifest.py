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
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from submissions import latest_wins  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RECON = ROOT / "interim" / "edap_recon"
SOURCES = [RECON / "manifest_full.csv",     # Voll-Katalog (alle Stichtage)
           RECON / "manifest_latest.csv", RECON / "manifest_sample.csv",
           RECON / "manifest_wave.csv"]   # full reference-date waves (e.g. 2025-12-31)
OUT = RECON / "manifest_parse.csv"

# "latest wins" (README, Arbeitsprinzip 5) muss HIER greifen, nicht erst beim
# Parsen: die Wellen- und Voll-Kataloge listen jede je gesehene Einreichung,
# inklusive überholter Fassungen. Ohne diese Reduktion lädt ein full_reparse
# 1.963 ZIPs, von denen 1.097 ältere Resubmissions sind, die anschliessend
# verworfen werden — mehr Downloads als der vollständige Bestand überhaupt
# braucht.
#
# Die Regel selbst steht seit #88 in `submissions.py`, weil sie vorher zweimal
# im Repo stand und eine der beiden Fassungen falsch war.


def main():
    rows, seen = [], set()
    for src in SOURCES:
        if not src.exists():
            continue
        with open(src, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                # DISDOCS sind die qualitativen PDF-Berichte, kein XBRL-CSV.
                if "DISDOCS" in r["url"] or r["url"] in seen:
                    continue
                seen.add(r["url"])
                rows.append(r)

    kept = latest_wins(rows)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=kept[0].keys())
        w.writeheader()
        w.writerows(kept)

    leis = {r["lei"] for r in kept}
    reports = {(r["lei"], r["consolidation"], r["refdate"]) for r in kept}
    print(f"✓ {OUT}")
    print(f"  {len(kept)} XBRL-Submissions · {len(leis)} Institute · {len(reports)} Reports")
    print(f"  ({len(rows) - len(kept)} überholte Resubmissions ausgeschlossen)")


if __name__ == "__main__":
    main()
