"""Phase 2: Build the fully-labelled DPM codebook from the DPM 2.0 Access dictionary
(pure-python access-parser — no pyodbc/mdbtools needed).

Resolution chain (pure ID joins, no fragile text matching):
    dp<n>  ==  Variable.VariableID
           ->  VariableVersion        (VariableID -> VariableVID)
           ->  TableVersionCell       (VariableVID -> TableVID + CellCode)
    CellCode "{K_61.00, r0010, c0010}"  ->  template, row, col
    TableVID -> TableVersion.Name      (template title)
    TableVID + ordinate -> HeaderVersion.Label  (row / column label)

The 4.2 DB stores several text fields with inconsistent, per-record Unicode packing
that access-parser mis-reads. `dpm_decode` brute-forces the candidate decodings and
keeps the one with the highest printable-ASCII ratio.
"""

from pathlib import Path
from collections import defaultdict
import csv
import re

from access_parser import AccessParser

ROOT = Path(__file__).resolve().parent.parent
# Cumulative DPM 2.0 dictionary (RF 4.0/4.1/4.2). Download (755 MB unzipped, gitignored):
#   https://www.eba.europa.eu/sites/default/files/2025-11/d67068fe-6327-4890-9163-3a9fcdabb58f/DPM2%20Database_v%204_2_20251125.zip
DB_PATH = ROOT / "codebook" / "DPM2_v4.2.accdb"
REPORT_CODES = ROOT / "codebook" / "mini_codebook_from_reports.csv"
OUT = ROOT / "codebook" / "dpm_codebook.csv"

CELLCODE_RE = re.compile(r"\{([^,]+),\s*r(\w+),\s*c(\w+)")


def _printable_ratio(s: str) -> float:
    if not s:
        return -1.0
    return sum(1 for c in s if 32 <= ord(c) < 127) / len(s)


def dpm_decode(v) -> str:
    """Robustly decode an access-parser field against the 4.2 DB's mixed encodings."""
    if v is None:
        return ""
    if not isinstance(v, str):
        return str(v)
    cands = [v]
    if all(ord(c) < 256 for c in v):
        try:
            cands.append(v.encode("latin-1").decode("utf-16-le"))
        except Exception:
            pass
    bs = bytearray()
    for ch in v:
        bs += ord(ch).to_bytes(2, "big")
    cands.append(bs.decode("latin-1", "replace"))            # big-endian direct
    sw = bytearray()
    for k in range(0, len(bs) - 1, 2):
        sw += bytes([bs[k + 1], bs[k]])
    cands.append(sw.decode("latin-1", "replace"))            # byte-pair swapped
    i = bs.find(b"\xfe\xff")
    if i >= 0:                                                # BOM + swap (CellCode)
        p = bs[i + 2:]
        s2 = bytearray()
        for k in range(0, len(p) - 1, 2):
            s2 += bytes([p[k + 1], p[k]])
        cands.append(s2.decode("latin-1", "replace"))
    return max(cands, key=_printable_ratio).replace("\x00", "").strip()


def clean_text(s: str) -> str:
    """Drop values access-parser failed to decode (memo-overflow rows come back as
    binary junk). Keep only clean printable text."""
    if not s:
        return ""
    if any(ord(c) < 32 or ord(c) == 127 for c in s):
        return ""
    if _printable_ratio(s) < 0.85:
        return ""
    return s


def _direction(v) -> str:
    for c in dpm_decode(v):
        if c in "XYZ":
            return c
    return ""


def build_label_index(db):
    """Return title_by_tvid and label[(tvid, axis, ordinate)] = text."""
    tv = db.parse_table("TableVersion")
    title_by_tvid = {int(vid): clean_text(dpm_decode(name)) for vid, name in zip(tv["TableVID"], tv["Name"])}

    hdr = db.parse_table("Header")
    dir_by_hid = {int(h): _direction(d) for h, d in zip(hdr["HeaderID"], hdr["Direction"])}

    hv = db.parse_table("HeaderVersion")
    cl_by_hvid = {int(vid): (dpm_decode(c), dpm_decode(l))
                  for vid, c, l in zip(hv["HeaderVID"], hv["Code"], hv["Label"])}

    labels = {}
    tvh = db.parse_table("TableVersionHeader")
    for tvid, hid, hvid in zip(tvh["TableVID"], tvh["HeaderID"], tvh["HeaderVID"]):
        d = dir_by_hid.get(int(hid))
        if d not in ("X", "Y"):
            continue
        code, label = cl_by_hvid.get(int(hvid), ("", ""))
        if not code or not label:
            continue
        axis = "row" if d == "Y" else "col"
        labels[(int(tvid), axis, code.zfill(4))] = label
    return title_by_tvid, labels


def build_resolution_maps(db):
    """VariableID -> set(VariableVID); VariableVID -> set((TableVID, decoded CellCode))."""
    vv = db.parse_table("VariableVersion")
    id2vid = defaultdict(set)
    for vid, varid in zip(vv["VariableVID"], vv["VariableID"]):
        id2vid[varid].add(vid)

    tvc = db.parse_table("TableVersionCell")
    vid2cell = defaultdict(set)
    for vvid, tvid, code in zip(tvc["VariableVID"], tvc["TableVID"], tvc["CellCode"]):
        if code:
            vid2cell[vvid].add((int(tvid), dpm_decode(code)))
    return id2vid, vid2cell


def parse_cellcode(code: str):
    m = CELLCODE_RE.match(code.strip())
    if not m:
        return None
    return m.group(1).strip(), m.group(2), m.group(3)


def load_template_titles():
    """Authoritative template titles from the EBA Annotated Table Layout TOC
    (extract_template_titles.py). Keyed by DPM code 'K_61.00'. Empty if absent."""
    path = ROOT / "codebook" / "template_titles.csv"
    titles = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                titles[r["template"]] = r["title"]
        # base fallback: a sheet variant like K_19.02.d reuses K_19.02.<any> title
        for code, title in list(titles.items()):
            parts = code.split(".")
            if len(parts) == 3 and len(parts[-1]) == 1:  # K_NN.NN.x
                titles.setdefault(".".join(parts[:2]), title)
    return titles


def title_for(tmpl: str, titles: dict) -> str:
    """Exact match, else fall back to the base template (drop sheet sub-letter)."""
    if tmpl in titles:
        return titles[tmpl]
    parts = tmpl.split(".")
    if len(parts) == 3 and len(parts[-1]) == 1:
        return titles.get(".".join(parts[:2]), "")
    return ""


def load_report_codes(path: Path):
    out = []
    with open(path) as f:
        for r in csv.DictReader(f):
            out.append((r["datapoint_code"], int(r["datapoint_code"].replace("dp", "")), r.get("frequency", "")))
    return out


def main():
    print(f"Reading DPM dictionary: {DB_PATH.name}")
    db = AccessParser(str(DB_PATH))
    print("  building label index...")
    title_by_tvid, labels = build_label_index(db)
    print("  building resolution maps...")
    id2vid, vid2cell = build_resolution_maps(db)
    title_csv = load_template_titles()
    print(f"  template titles (EBA layout): {len(title_csv)}")

    report_codes = load_report_codes(REPORT_CODES)
    print(f"Resolving {len(report_codes)} datapoint codes...")

    rows = []
    resolved = 0
    for dp_str, dp_int, freq in report_codes:
        cells = set()
        for vvid in id2vid.get(dp_int, ()):
            cells |= vid2cell.get(vvid, set())
        if not cells:
            rows.append({"datapoint_code": dp_str, "variable_id": dp_int, "template": "",
                         "row": "", "col": "", "template_title": "", "row_label": "",
                         "col_label": "", "frequency": freq})
            continue
        resolved += 1
        for tvid, code in sorted(cells):
            parsed = parse_cellcode(code)
            if not parsed:
                continue
            tmpl, row, col = parsed
            rows.append({
                "datapoint_code": dp_str, "variable_id": dp_int,
                "template": tmpl, "row": row, "col": col,
                "template_title": title_for(tmpl, title_csv) or title_by_tvid.get(tvid, ""),
                "row_label": labels.get((tvid, "row", row.zfill(4)), ""),
                "col_label": labels.get((tvid, "col", col.zfill(4)), ""),
                "frequency": freq,
            })

    # A datapoint resolves through several table-version releases that collapse to the
    # same (template, row, col); keep the most complete-labelled variant per cell.
    best = {}
    for r in rows:
        key = (r["datapoint_code"], r["template"], r["row"], r["col"])
        completeness = len(r["template_title"]) + len(r["row_label"]) + len(r["col_label"])
        if key not in best or completeness > best[key][0]:
            best[key] = (completeness, r)
    rows = [r for _, r in best.values()]
    rows.sort(key=lambda r: (r["template"], r["row"], r["col"], r["datapoint_code"]))

    fields = ["datapoint_code", "variable_id", "template", "row", "col",
              "template_title", "row_label", "col_label", "frequency"]
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    labelled = sum(1 for r in rows if r["row_label"] or r["col_label"])
    print(f"\n✓ Codebook: {OUT}")
    print(f"  Datapoints resolved: {resolved}/{len(report_codes)} ({100*resolved//len(report_codes)}%)")
    print(f"  Codebook rows (incl. multi-cell): {len(rows)}")
    print(f"  Rows with axis label: {labelled}")


if __name__ == "__main__":
    main()
