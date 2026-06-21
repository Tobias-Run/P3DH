"""Resolve the LEIs seen in the data to legal entity names via the public GLEIF API.

Reads the distinct LEIs from processed/long_form_raw.csv and writes
processed/lei_names.csv (lei, legal_name, jurisdiction) for the viewer to consume.
GLEIF is the authoritative LEI register; the API is public (no auth, no rate key needed
for this volume).
"""

from pathlib import Path
from urllib.request import urlopen, Request
import csv
import json
import re
import time

ROOT = Path(__file__).resolve().parent.parent
LONGFORM = ROOT / "processed" / "long_form_raw.csv"
OUT = ROOT / "processed" / "lei_names.csv"
API = "https://api.gleif.org/api/v1/lei-records/"
LEI_RE = re.compile(r"[A-Z0-9]{20}")


def distinct_leis(path: Path):
    leis = set()
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            m = LEI_RE.search(row.get("entityID", ""))
            if m:
                leis.add(m.group(0))
    return sorted(leis)


def fetch(lei: str):
    req = Request(API + lei, headers={"Accept": "application/json", "User-Agent": "P3DH/1.0"})
    with urlopen(req, timeout=15) as r:
        attr = json.load(r)["data"]["attributes"]
    entity = attr["entity"]
    return {
        "lei": lei,
        "legal_name": entity["legalName"]["name"],
        "jurisdiction": entity.get("jurisdiction", ""),
    }


def main():
    leis = distinct_leis(LONGFORM)
    print(f"Resolving {len(leis)} LEIs via GLEIF...")
    rows = []
    for lei in leis:
        try:
            rec = fetch(lei)
            print(f"  {lei}  {rec['legal_name']}")
        except Exception as e:
            rec = {"lei": lei, "legal_name": "", "jurisdiction": ""}
            print(f"  {lei}  FEHLER: {e}")
        rows.append(rec)
        time.sleep(0.3)  # be polite to the API

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["lei", "legal_name", "jurisdiction"])
        w.writeheader()
        w.writerows(rows)
    print(f"\n✓ {OUT}  ({sum(1 for r in rows if r['legal_name'])}/{len(rows)} resolved)")


if __name__ == "__main__":
    main()
