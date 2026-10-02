"""Direct scale evidence and source-bound human reviews (#122).

Population jumps only nominate candidates. A review is valid for the exact
facts it checked, including source, unit, FX conversion and taxonomy labels.
No function changes a filed value or interprets decimals as a multiplier.
"""
from collections import defaultdict
import hashlib
import json
import math
import re
from pathlib import Path
from statistics import median

REVIEW_FILE = Path(__file__).resolve().parent.parent / "codebook/scale_reviews.json"
FIELDS = ("entityID", "refPeriod", "template_id", "cell_row", "cell_col",
          "open_axis_dims", "datapoint_code", "fact_value_eur", "source_file",
          "fact_value_raw", "currency", "fx_rate", "data_type", "row_label",
          "col_label", "framework_version")


def load_reviews(path=REVIEW_FILE):
    with Path(path).open(encoding="utf-8") as fh:
        data = json.load(fh)
    if data["version"] != 1:
        raise ValueError("Unsupported scale review version")
    return data["reviews"]


def collect(con, keys):
    """Read only nominated templates and review guards, at all own dates."""
    con.execute("CREATE OR REPLACE TEMP TABLE scale_keys(e VARCHAR, t VARCHAR)")
    if not keys:
        return {}
    keys = set(keys)
    whole_reports = {e for e, t in keys if t == '*'}
    keys = {(e, t) for e, t in keys if t == '*' or e not in whole_reports}
    con.executemany("INSERT INTO scale_keys VALUES (?, ?)", sorted(keys))
    fields = ", ".join("p." + name for name in FIELDS)
    rows = con.execute(f"""SELECT {fields} FROM p JOIN scale_keys k
        ON p.entityID=k.e AND (p.template_id=k.t OR k.t='*')
        WHERE p.data_type='monetary' AND p.fact_value_eur IS NOT NULL
        ORDER BY {fields}""").fetchall()
    out = defaultdict(list)
    for values in rows:
        row = dict(zip(FIELDS, values))
        out[tuple(values[:3])].append(row)
        out[(values[0], values[1], '*')].append(row)
    return dict(out)


def fingerprint(rows):
    # Sort canonical lines, including duplicates. SQL input order is immaterial.
    lines = sorted(json.dumps([r.get(f) for f in FIELDS], ensure_ascii=False,
                              separators=(",", ":"), allow_nan=False) for r in rows)
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def identity(row):
    return (row["cell_row"], row["cell_col"], row["open_axis_dims"] or "",
            row["datapoint_code"])


def is_amount(row):
    # A known semantic conflict must not make fixed 0.5 risk weights EUR values.
    # Preserve the raw/codebook data; exclude it only from scale evidence.
    return (row.get("data_type") == "monetary"
            and not re.search(r"\brisk weights?\s*$", (row.get("col_label") or "").lower()))


def unique_amounts(rows):
    grouped = defaultdict(list)
    for row in rows:
        value = row["fact_value_eur"]
        if is_amount(row) and value and math.isfinite(value):
            grouped[identity(row)].append(row)
    return {key: values[0] for key, values in grouped.items() if len(values) == 1}


def direct_compare(current, reference):
    """Signed same-datapoint comparison; duplicates/zeros/sign flips abstain."""
    own, other = unique_amounts(current), unique_amounts(reference)
    pairs = []
    for key in sorted(own.keys() & other.keys()):
        ratio = other[key]["fact_value_eur"] / own[key]["fact_value_eur"]
        if ratio > 0:
            pairs.append((key, math.log10(ratio)))
    return pairs


def cell_record(key, factor=""):
    row, col, dims, dp = key
    return {"r": row, "c": col, "d": dims, "dp": dp, "f": factor}


def finding_affects(record, template, row=None, col=None):
    """Conservative applicability for CSV consumers, including legacy files."""
    if record.get("ebene") == "report":
        return True
    if record.get("template_id") != template:
        return False
    if record.get("umfang") != "teilbereich" or (row is None and col is None):
        return True
    cells = json.loads(record.get("betroffene_zellen") or "[]")
    # Unknown extent is uncertainty, not proof of unaffected values.
    return not cells or any((row is None or x["r"] == row)
                           and (col is None or x["c"] == col) for x in cells)


def evaluate(key, facts, offsets):
    """A missing/changed reference is uncertainty, never a clean bill.

    Direct coherent shifts plus population position can support a small-scale
    hypothesis. A population shift alone never confirms a defect. Mixed shifts
    retain affected cells and are explicitly tentative unless a review resolves
    direction/scope with additional evidence.
    """
    entity, date, template = key
    choices = []
    for other_key in sorted(facts):
        if other_key[0] != entity or other_key[2] != template or other_key[1] == date:
            continue
        pairs = direct_compare(facts.get(key, []), facts[other_key])
        shifted = [(k, log) for k, log in pairs if abs(log) >= 2.5]
        choices.append((len(shifted), len(pairs), other_key[1], pairs))
    default = {"urteil": "verdacht", "richtung": "unklar", "umfang": "unklar",
               "referenz_stichtag": "", "beleg_status": "referenz_fehlt",
               "faktor_geschaetzt": "", "faktoren": [], "betroffene_zellen": [],
               "begruendung": "Ein Populationssprung allein bestätigt keinen Skalenfehler.",
               "vergleich_n": 0, "zeitreihe_faktor": ""}
    if not choices:
        return default
    _, n, ref, pairs = max(choices, key=lambda x: (x[0], x[1], x[2]))
    shifted = [(k, log) for k, log in pairs if abs(log) >= 2.5]
    default.update(referenz_stichtag=ref, vergleich_n=n, beleg_status="direkter_vergleich")
    if n >= 5 and not shifted:
        return None  # No observed scale jump; no claim about unpaired cells.
    if len(shifted) < 5:
        return default
    logs = [log for _, log in shifted]
    exponent = round(median(logs) / 3) * 3
    same_direction = all(log * exponent > 0 for log in logs)
    coherent = (len(shifted) / n >= .7 and same_direction and abs(exponent) >= 3
                and sum(abs(log - exponent) <= .5 for log in logs) / len(logs) >= .7)
    own_offset = offsets.get(key)
    ref_offset = offsets.get((entity, ref, template))
    # Both directions stay unknown unless an independent magnitude/review
    # anchor identifies the faulty side. In particular, do not trust a maximum.
    supported_small = (coherent and exponent > 0 and n >= 10
                       and own_offset is not None and own_offset <= -1.5
                       and ref_offset is not None and ref_offset > -1)
    default.update(urteil="skaliert" if supported_small else "verdacht",
                   richtung="zu_klein" if supported_small else "unklar",
                   umfang="template" if coherent else "teilbereich",
                   zeitreihe_faktor=round(10 ** abs(median(logs))),
                   betroffene_zellen=[cell_record(k, f"10^{round(abs(log)/3)*3}")
                                      for k, log in shifted],
                   begruendung="Direkter Zellvergleich; Richtung und Faktor sind Hypothesen.")
    if coherent and supported_small:
        default["faktor_geschaetzt"] = f"10^{abs(exponent)}"
        default["faktoren"] = [default["faktor_geschaetzt"]]
    return default


def apply_reviews(findings, facts, reviews):
    """Reject/replace only after EVERY source fingerprint matches.

    A stale review demotes its existing candidate and clears the old factor;
    it never silently reuses an exclusion or 'confirmed' source-level judgment.
    """
    outcomes = []
    hashes = {}
    def matches(guard):
        key = tuple(guard['key'])
        if key not in hashes:
            hashes[key] = fingerprint(facts[key]) if facts.get(key) else None
        return hashes[key] == guard['sha256']

    for review in reviews:
        guards = review["guards"]
        if not all(matches(g) for g in guards):
            for key in map(tuple, review["replaces"]):
                if key in findings:
                    findings[key].update(urteil="verdacht", beleg_status="review_veraltet",
                                         richtung="unklar", umfang="unklar",
                                         faktor_geschaetzt="", faktoren=[], betroffene_zellen=[],
                                         begruendung="Quelldaten geändert; frühere Sichtprüfung gilt nicht mehr.")
            outcomes.append({"id": review["id"], "status": "veraltet"})
            continue
        for key in map(tuple, review["replaces"]):
            findings.pop(key, None)
        for decision in review["decisions"]:
            findings[tuple(decision["key"])] = {**decision["finding"],
                                               "review_id": review["id"]}
        outcomes.append({"id": review["id"], "status": "angewendet"})
    return outcomes
