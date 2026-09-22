"""Resolve the LEIs seen in the data to legal entity names via the public GLEIF API.

Reads the distinct LEIs from processed/long_form_raw.csv and writes
processed/lei_names.csv (lei, legal_name, jurisdiction). GLEIF is the authoritative
LEI register; the API is public (no auth, no rate key needed for this volume).

NOT in the pipeline, and no longer the viewer's source of names. That was the
original purpose, and this docstring claimed it long after it stopped being true:
since processed/entity_meta.csv the names come from the EDAP catalogue, which
covers all 508 institutions instead of the 174 resolved here.

What the file is still for is the thing entity_meta cannot be — an INDEPENDENT
register. Where EDAP and GLEIF disagree about an institution's name, that is an
observation, and it needs two sources to exist. README.md and DISCLAIMER.md carry
it as a provenance record for exactly that reason. Run it to refresh that
cross-check, not to feed the viewer.
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
