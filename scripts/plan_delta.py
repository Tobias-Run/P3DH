"""Plan the download delta: which submissions of the parse manifest are not yet
in the processed state.

Why this exists: `download_raw_reports.py` skips files already present in `raw/`,
which is the right check on a workstation that keeps the whole corpus. A stateless
run (CI) starts with an empty `raw/`, so that check would re-download all ~2k ZIPs
from EDAP on every run. The processed state answers the question properly: a
submission is "done" once its source file appears in the coverage matrix (or, as a
fallback, in the long form).

Note the coverage matrix is the authoritative ledger: a submission can parse fine and
still contribute no placeable facts, so it exists in `filing_indicators.csv` but not
in `long_form_raw.csv`.

Output: interim/edap_recon/manifest_todo.csv (same columns as the input manifest) —
feed it to `download_raw_reports.py`.

Usage:  python scripts/plan_delta.py [manifest_in] [manifest_out]
"""

from pathlib import Path
import csv
import sys

ROOT = Path(__file__).resolve().parent.parent
RECON = ROOT / "interim" / "edap_recon"
PROCESSED = ROOT / "processed"

DEFAULT_IN = RECON / "manifest_parse.csv"
DEFAULT_OUT = RECON / "manifest_todo.csv"


def seen_sources():
    """Source files already represented in the processed state."""
    seen = set()
    for name in ("filing_indicators.csv", "long_form_raw.csv"):
        path = PROCESSED / name
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                src = row.get("source_file")
                if src:
                    seen.add(src)
    return seen


def main():
    man_in = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_IN
    man_out = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT

    if not man_in.exists():
        print(f"ERROR: manifest not found: {man_in}")
        return 1

    with open(man_in, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print(f"ERROR: empty manifest: {man_in}")
        return 1

    done = seen_sources()
    on_disk = {p.name for p in (ROOT / "raw").glob("*.zip")}
    todo = [r for r in rows if r["url"].split("/")[-1] not in done]

    man_out.parent.mkdir(parents=True, exist_ok=True)
    with open(man_out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(todo)

    missing_locally = sum(1 for r in todo if r["url"].split("/")[-1] not in on_disk)
    print(f"✓ {man_out}")
    print(f"  {len(rows)} im Manifest · {len(rows) - len(todo)} bereits verarbeitet · "
          f"{len(todo)} offen ({missing_locally} davon nicht in raw/)")
    if todo:
        print("  Hinweis: dauerhaft offene Einträge sind i. d. R. tote EDAP-Links "
              "(Katalogzeile ohne publizierte Datei).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
