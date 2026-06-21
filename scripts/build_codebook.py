"""Phase 2: Build the real DPM codebook by resolving dp<n> datapoint codes
against the DPM 2.0 Access dictionary (pure-python, no pyodbc/mdbtools needed).

Resolution chain:
    dp<n>  ==  Variable.VariableID
           ->  VariableVersion (VariableID -> VariableVID)
           ->  TableVersionCell.CellCode  == "{Template, rNNNN, cNNNN}"

A single datapoint can appear in several template cells (shared variable), so the
codebook keeps every (template, row, col) occurrence. The long-form join later
disambiguates by the template_id already known from the k-file.
"""

from pathlib import Path
from collections import defaultdict
import csv
import re

from access_parser import AccessParser

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "codebook" / "DPM2_v4.2.accdb"  # covers RF 4.0/4.1/4.2 (cumulative IDs)
REPORT_CODES = ROOT / "codebook" / "mini_codebook_from_reports.csv"
OUT = ROOT / "codebook" / "dpm_codebook.csv"

CELLCODE_RE = re.compile(r"\{([^,]+),\s*r(\w+),\s*c(\w+)")


def decode_cellcode_field(raw: str) -> str:
    """The 4.2 DB stores CellCode as a unicode memo that access-parser mis-reads:
    a junk header + BOM followed by byte-pair-swapped UTF-16. Recover the text.
    The 4.0 DB stored it as plain text, so pass those through unchanged."""
    if not raw:
        return ""
    if raw.startswith("{"):  # already clean (4.0-style)
        return raw
    bs = bytearray()
    for ch in raw:
        bs += ord(ch).to_bytes(2, "big")
    idx = bs.find(b"\xfe\xff")
    payload = bs[idx + 2:] if idx >= 0 else bs
    swapped = bytearray()
    for i in range(0, len(payload) - 1, 2):
        swapped += bytes([payload[i + 1], payload[i]])
    if len(payload) % 2:
        swapped.append(payload[-1])
    return swapped.decode("latin-1", "replace").strip()


def build_resolution_maps(db: AccessParser):
    """Return VariableID -> set(VariableVID) and VariableVID -> set(CellCode)."""
    vv = db.parse_table("VariableVersion")
    id2vid = defaultdict(set)
    for vid, varid in zip(vv["VariableVID"], vv["VariableID"]):
        id2vid[varid].add(vid)

    tvc = db.parse_table("TableVersionCell")
    vid2cell = defaultdict(set)
    for vvid, code in zip(tvc["VariableVID"], tvc["CellCode"]):
        if code:
            vid2cell[vvid].add(decode_cellcode_field(code))
    return id2vid, vid2cell


def parse_cellcode(code: str):
    """'{C_24.00, r0010, c0050}' -> ('C_24.00', '0010', '0050')."""
    m = CELLCODE_RE.match(code.strip())
    if not m:
        return None
    return m.group(1).strip(), m.group(2), m.group(3)


def load_report_codes(path: Path):
    codes = []
    with open(path) as f:
        for r in csv.DictReader(f):
            codes.append((r["datapoint_code"], int(r["datapoint_code"].replace("dp", "")), r.get("frequency", "")))
    return codes


def main():
    print(f"Reading DPM dictionary: {DB_PATH.name}")
    db = AccessParser(str(DB_PATH))
    id2vid, vid2cell = build_resolution_maps(db)

    report_codes = load_report_codes(REPORT_CODES)
    print(f"Resolving {len(report_codes)} datapoint codes...")

    rows = []
    resolved = 0
    for dp_str, dp_int, freq in report_codes:
        cells = set()
        for vvid in id2vid.get(dp_int, ()):
            cells |= vid2cell.get(vvid, set())
        if cells:
            resolved += 1
            for code in sorted(cells):
                parsed = parse_cellcode(code)
                if not parsed:
                    continue
                tmpl, row, col = parsed
                rows.append({
                    "datapoint_code": dp_str,
                    "variable_id": dp_int,
                    "template": tmpl,
                    "row": row,
                    "col": col,
                    "cell_code": code,
                    "frequency": freq,
                })
        else:
            rows.append({
                "datapoint_code": dp_str, "variable_id": dp_int,
                "template": "", "row": "", "col": "",
                "cell_code": "[unresolved: needs DPM >=4.1]", "frequency": freq,
            })

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["datapoint_code", "variable_id", "template", "row", "col", "cell_code", "frequency"])
        w.writeheader()
        w.writerows(rows)

    print(f"\n✓ Codebook: {OUT}")
    print(f"  Datapoints resolved: {resolved}/{len(report_codes)} ({100*resolved//len(report_codes)}%)")
    print(f"  Codebook rows (incl. multi-cell): {len(rows)}")
    print(f"  Unresolved (need DPM release 4.1/4.2): {len(report_codes)-resolved}")


if __name__ == "__main__":
    main()
