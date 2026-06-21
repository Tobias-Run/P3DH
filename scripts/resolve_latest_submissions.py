"""Phase 1.5: Resubmission-Policy "latest wins".

Liest den vollständigen Roh-Katalog (manifest_urls.csv, eine Zeile je gesehene
Submission) und reduziert ihn auf genau eine Zeile je (lei, consolidation,
country, module, refdate) — die mit dem höchsten submission_ts.

Der Roh-Katalog selbst bleibt unverändert (Audit-Trail); dieser Schritt
erzeugt eine abgeleitete, gefilterte Sicht, die Download/Parsing tatsächlich
konsumieren.
"""

from pathlib import Path
import csv
from collections import defaultdict

RECON_DIR = Path(__file__).resolve().parent.parent / "interim" / "edap_recon"
MANIFEST_IN = RECON_DIR / "manifest_urls.csv"
MANIFEST_OUT = RECON_DIR / "manifest_latest.csv"

GROUP_KEYS = ["lei", "consolidation", "country", "module", "refdate"]


def main():
    if not MANIFEST_IN.exists():
        print(f"ERROR: {MANIFEST_IN} fehlt — erst harvest_catalog.py ausführen")
        return

    with open(MANIFEST_IN, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    groups = defaultdict(list)
    for row in rows:
        key = tuple(row[k] for k in GROUP_KEYS)
        groups[key].append(row)

    latest_rows = []
    superseded = []
    for key, group_rows in groups.items():
        group_rows.sort(key=lambda r: r["submission_ts"])
        latest_rows.append(group_rows[-1])
        superseded.extend(group_rows[:-1])

    latest_rows.sort(key=lambda r: r["url"])

    fieldnames = list(rows[0].keys())
    with open(MANIFEST_OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(latest_rows)

    print(f"Roh-Katalog: {len(rows)} Submissions, {len(groups)} unique (Institut, Modul, Stichtag)")
    print(f"→ {len(latest_rows)} aktuelle Submissions nach {MANIFEST_OUT}")
    if superseded:
        print(f"\n{len(superseded)} ältere Resubmission(en) ausgeschlossen (nicht heruntergeladen/geparst):")
        for row in superseded:
            print(f"  - {row['lei']}.{row['consolidation']}_{row['country']}_{row['refdate']}"
                  f"  (verworfen: {row['submission_ts']})")


if __name__ == "__main__":
    main()
