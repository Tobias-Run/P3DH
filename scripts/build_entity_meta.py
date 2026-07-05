"""Decode the EDAP catalog DSR response into per-institution metadata for clustering.

The Power BI `query` response (dumped by _dump_query_response.py) carries, per
submission row: EntityType, InstitutionType (EBA size class: Large/Other highest EEA,
Large subsidiaries), official entity name, module name and country. G-SII status is
derived authoritatively: institutions filing the "G-SIIs disclosures" module are G-SIIs.

DSR row format: row0.S = schema [{N,T,DN?}...]; each row's C holds values for columns
that are neither repeated (R bitmask -> copy previous row) nor null (Ø bitmask). Ints in
dict-encoded columns (DN) index ValueDicts[DN] — unless the string is inline (literal).

Output: processed/entity_meta.csv  (lei, name, country, entity_type, institution_type,
is_gsii, modules) — consumed by the viewer for filters.
"""

from pathlib import Path
import json
import csv
import re
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "interim" / "edap_recon" / "query_response.json"
OUT = ROOT / "processed" / "entity_meta.csv"

LEI_RE = re.compile(r"^([A-Z0-9]{20})\.(\w+)_")


def decode_rows(data):
    ds = data["results"][0]["result"]["data"]["dsr"]["DS"][0]
    dicts = ds.get("ValueDicts", {})
    rows_raw = ds["PH"][0]["DM0"]
    schema = rows_raw[0]["S"]
    ncols = len(schema)

    prev = [None] * ncols
    out = []
    for raw in rows_raw:
        c = list(raw.get("C", []))
        rbits = raw.get("R", 0)
        nbits = raw.get("Ø", 0)
        vals = []
        ci = 0
        for i, col in enumerate(schema):
            if nbits & (1 << i):
                vals.append(None)
                continue
            if rbits & (1 << i):
                vals.append(prev[i])
                continue
            v = c[ci]; ci += 1
            dn = col.get("DN")
            if dn is not None and isinstance(v, int):
                v = dicts[dn][v]
            vals.append(v)
        prev = vals
        out.append(vals)
    return schema, out


def main():
    data = json.loads(SRC.read_text())
    schema, rows = decode_rows(data)
    names = [s["N"] for s in schema]
    print(f"Decoded {len(rows)} rows, columns: {names}")
    # G0 url, G1 refdate, G2 EntityType, G3 InstitutionType, G4 ENT_NAM,
    # G5 ModuleName, G6 ReceptionDate, G7 FileName, G8 Country, G9 InstanceID

    ent = {}
    modules = defaultdict(set)
    for v in rows:
        fname = v[7] or (v[0] or "").split("/")[-1]
        m = LEI_RE.match(str(fname))
        if not m:
            continue
        lei = m.group(1)
        modules[lei].add(str(v[5] or ""))
        # keep the most complete record per LEI
        rec = ent.get(lei, {})
        ent[lei] = {
            "lei": lei,
            "name": str(v[4] or rec.get("name", "")),
            "country": str(v[8] or rec.get("country", "")),
            "entity_type": str(v[2] or rec.get("entity_type", "")),
            "institution_type": str(v[3] or rec.get("institution_type", "")),
        }

    out_rows = []
    for lei, rec in sorted(ent.items()):
        mods = modules[lei]
        rec["is_gsii"] = "true" if "G-SIIs disclosures" in mods else "false"
        rec["modules"] = "|".join(sorted(m for m in mods if m))
        out_rows.append(rec)

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["lei", "name", "country", "entity_type",
                                          "institution_type", "is_gsii", "modules"])
        w.writeheader()
        w.writerows(out_rows)

    gsii = sum(1 for r in out_rows if r["is_gsii"] == "true")
    itypes = defaultdict(int)
    for r in out_rows:
        itypes[r["institution_type"]] += 1
    print(f"\n✓ {OUT}")
    print(f"  Institute: {len(out_rows)}  ·  G-SIIs: {gsii}")
    print(f"  InstitutionType: {dict(itypes)}")


if __name__ == "__main__":
    main()
