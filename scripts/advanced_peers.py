"""Explainable peer analysis, built from joined facts; no browser-side fitting.

Complete-linkage clustering of mixed size/risk/ownership/role distances. Clusters
are fitted separately per date, scope and framework, on one representative per
known group. Isolates stay isolates. Unknown ownership is never inferred from an unreviewed
name, legal form or parent; missing risk cells never become zero.
"""
from pathlib import Path
import collections
import csv
import hashlib
import heapq
import json
import math
import re
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
OWNERSHIP = {"cooperative", "public", "shareholder", "mixed", "mutual", "foundation", "savings", "unknown"}
RISK_ROWS = {"credit": "0010", "counterparty": "0070", "cva": "0120",
             "market": "0260", "operational": "0320"}
THRESHOLD = .25
MAX_SIZE_RATIO = 10.
WEIGHTS = {"size": .25, "risk": .50, "ownership": .15, "role": .10}
METHOD = "complete-linkage-gower-caliper-v1"


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode()


def register(root=ROOT):
    """Current reviewed ownership, not an assertion about historical ownership."""
    result = {}
    path = root / "codebook" / "bank_classification.csv"
    if not path.exists():
        return result
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        lei = row["lei"].strip()
        if not re.fullmatch(r"[A-Z0-9]{20}", lei) or lei in result:
            raise ValueError(f"Invalid or duplicate classification LEI: {lei}")
        category = row["ownership"]
        if category not in OWNERSHIP - {"unknown"}:
            raise ValueError(f"Invalid ownership for {lei}")
        if urlparse(row["source_url"]).scheme != "https" or not row["evidence_quote"].strip():
            raise ValueError(f"Missing classification evidence for {lei}")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["reviewed_at"]):
            raise ValueError(f"Missing review date for {lei}")
        if not re.fullmatch(r"[a-f0-9]{64}", row["source_sha256"]):
            raise ValueError(f"Missing evidence hash for {lei}")
        for field in ("supporting_source_url", "control_source_url"):
            if row.get(field) and (urlparse(row[field]).scheme != "https" or not urlparse(row[field]).netloc):
                raise ValueError(f"Invalid supporting evidence for {lei}")
        if row.get("ownership_basis") == "reviewed_control_chain":
            if not re.fullmatch(r"[A-Z0-9]{20}", row.get("controller_lei", "")) or not row.get("control_source_url") or not re.fullmatch(r"[a-f0-9]{64}", row.get("control_source_sha256", "")):
                raise ValueError(f"Missing reviewed control chain for {lei}")
        result[lei] = {k: row.get(k, "") for k in ["ownership", "source_url", "evidence_quote",
                                           "reviewed_at", "source_sha256", "source_hash_kind", "supporting_source_url",
                                           "ownership_basis", "controller_lei", "control_source_url", "control_source_sha256"]}
    return result


def traits(root, leis):
    from build_entity_groups import lade_gleif, lade_ezb, kopf_von
    gleif = lade_gleif(root / "processed" / "lei_relations.csv")
    ezb = lade_ezb(root / "processed" / "coverage_gap.csv")
    classifications = register(root)
    result = {}
    for lei in sorted(leis):
        head, source = kopf_von(lei, gleif, ezb)
        role = ("subsidiary" if head and head != lei else
                "group_head" if head == lei and source in {"ezb", "beide"} else
                "no_consolidating_parent" if source == "eigen" else "unknown")
        result[lei] = {"ownership": "unknown", "role": role,
                       "group_head": head, "group_source": source}
        result[lei].update(classifications.get(lei, {}))
        # Only explicit reviewed chains override the older group snapshot.
        # A parent name or an unreviewed classification never propagates.
        if result[lei].get("ownership_basis") == "reviewed_control_chain":
            result[lei].update(group_head=result[lei]["controller_lei"],
                               group_source="reviewed_gleif", role="subsidiary")
    return result


def quantile(values, p):
    s = sorted(values)
    i = (len(s)-1)*p
    lo, hi = math.floor(i), math.ceil(i)
    return s[lo]+(s[hi]-s[lo])*(i-lo)


def normalized_sizes(profiles):
    values = [math.log10(p["trea_eur"]) for p in profiles.values()]
    lo, hi = quantile(values, .05), quantile(values, .95)
    return {k: 0.5 if hi == lo else min(1., max(0.,
            (math.log10(p["trea_eur"])-lo)/(hi-lo))) for k, p in profiles.items()}, (lo, hi)


def distance(a, b, sizes, weights=WEIGHTS):
    """Gower-style block distance. Unknown categories cost .5, never a match.

    Risk is the average absolute difference of five proportions, unnormalized:
    OV1 categories need not sum to 100%. Values are not percentages here.
    """
    # A size difference must not be fully compensated by other similarities.
    # A finite dissimilarity of one enforces the caliper under complete linkage
    # while keeping silhouette diagnostics defined (no infinities/NaN).
    if max(a["trea_eur"], b["trea_eur"])/min(a["trea_eur"], b["trea_eur"]) > MAX_SIZE_RATIO:
        return 1.
    category = lambda x, y: .5 if "unknown" in (x, y) else float(x != y)
    parts = {"size": abs(sizes[a["key"]]-sizes[b["key"]]),
             "risk": sum(abs(a["risk"][r]-b["risk"][r]) for r in RISK_ROWS)/len(RISK_ROWS),
             "ownership": category(a["ownership"], b["ownership"]),
             "role": category(a["role"], b["role"])}
    return sum(weights[k]*v for k, v in parts.items())/sum(weights.values())


def complete_link(keys, distances, cutoff=THRESHOLD):
    """Deterministic agglomeration; maximum pair distance bounds every group.

    Lance-Williams max update avoids rechecking all member pairs on each merge.
    Unlike single linkage, A-B-C cannot be a cluster if A-C exceeds the cutoff.
    """
    active = {i: (key,) for i, key in enumerate(sorted(keys))}
    d, heap = {}, []
    for i in active:
        for j in active:
            if i >= j:
                continue
            value = distances[tuple(sorted((active[i][0], active[j][0])))]
            d[i, j] = value
            heapq.heappush(heap, (value, active[i], active[j], i, j))
    serial = len(active)
    while heap:
        value, _, _, i, j = heapq.heappop(heap)
        if i not in active or j not in active:
            continue
        if value > cutoff:
            break
        members = tuple(sorted(active[i]+active[j]))
        others = [k for k in active if k not in (i, j)]
        for k in others:
            value_new = max(d[tuple(sorted((i, k)))], d[tuple(sorted((j, k)))])
            d[k, serial] = value_new
            left, right = sorted((active[k], members))
            heapq.heappush(heap, (value_new, left, right, k, serial))
        del active[i], active[j]
        active[serial] = members
        serial += 1
    return sorted(active.values())


def representatives(profiles):
    """Prefer a reported group head, then an EEA head; deterministic LEI tie.

    Unknown group heads remain distinct and are explicitly counted as unknown.
    This is a lower-bound safeguard, not proof of independent observations.
    """
    groups = collections.defaultdict(list)
    for p in profiles.values():
        groups[p["group_head"] or "unknown:"+p["lei"]].append(p)
    selected, excluded = [], {}
    for values in groups.values():
        values.sort(key=lambda p: (p["role"] != "group_head",
                                  "highest EEA" not in p["institution_type"], p["key"]))
        selected.append(values[0]["key"])
        for p in values[1:]:
            excluded[p["key"]] = values[0]["key"]
    return sorted(selected), excluded


def assignments(groups):
    return {key: set(group)-{key} for group in groups for key in group}


def cluster_block(profiles):
    sizes, scale = normalized_sizes(profiles)
    keys = sorted(profiles)
    distances = {(a, b): distance(profiles[a], profiles[b], sizes)
                 for i, a in enumerate(keys) for b in keys[i+1:]}
    groups = complete_link(keys, distances)
    # Sensitivity is neighbourhood Jaccard under tighter/looser thresholds;
    # it is not a probability or a bootstrap confidence interval.
    alternatives = [assignments(complete_link(keys, distances, cutoff))
                    for cutoff in (.20, .30)]
    result = []
    for group in groups:
        if len(group) < 2:
            continue
        pairs = [distances[tuple(sorted((a, b)))]
                 for i, a in enumerate(group) for b in group[i+1:]]
        sensitivity = []
        for key in group:
            peers = set(group)-{key}
            sensitivity.extend(len(peers & alt[key])/len(peers | alt[key])
                               if peers | alt[key] else 1. for alt in alternatives)
        cohesion = max(pairs)
        # Standard silhouette on the same distance matrix; undefined for one
        # non-singleton cluster plus no other observations.
        silhouettes = []
        outside = [other for other in groups if other != group]
        for key in group:
            a = sum(distances[tuple(sorted((key, peer)))]
                    for peer in group if peer != key)/(len(group)-1)
            if outside:
                b = min(sum(distances[tuple(sorted((key, peer)))]
                            for peer in other)/len(other) for other in outside)
                silhouettes.append((b-a)/max(a, b) if max(a, b) else 0.)
        id_ = hashlib.sha256("|".join(group).encode()).hexdigest()[:12]
        result.append({"id": id_, "members": list(group), "max_distance": round(cohesion, 6),
                       "sensitivity": round(sum(sensitivity)/len(sensitivity), 6),
                       "silhouette": round(sum(silhouettes)/len(silhouettes), 6) if silhouettes else None,
                       "size_log10_bounds": [round(x, 6) for x in scale],
                       "unknown_ownership": sum(profiles[k]["ownership"] == "unknown" for k in group),
                       "unknown_groups": sum(not profiles[k]["group_head"] for k in group),
                       "median_risk": {r: round(quantile([profiles[k]["risk"][r] for k in group], .5), 6)
                                       for r in RISK_ROWS}})
    return result


def load_profiles(con, root=ROOT, extra_leis=()):
    """Use the shard-builder's p view; read original EUR amounts once.

    Distinct conflicting amounts or multiple dimensions invalidate a coordinate.
    Scale findings are conservatively excluded for the two contributing templates.
    """
    meta, coords = {}, collections.defaultdict(dict)
    records = con.execute("""SELECT entityID, lei, scope, refPeriod, framework_version,
        max(bank_name), max(institution_type) FROM p GROUP BY 1,2,3,4,5 ORDER BY 1,4""").fetchall()
    by_key = collections.defaultdict(list)
    for eid, lei, scope, date, fw, name, itype in records:
        key = eid+"|"+date
        by_key[key].append({"key": key, "lei": lei, "scope": scope, "date": date,
                            "framework": fw or "unknown", "name": name or lei,
                            "institution_type": itype or ""})
    metadata = traits(root, {r[1] for r in records} | set(extra_leis))
    invalid_framework = {}
    for key, values in by_key.items():
        if len(values) == 1 and values[0]["framework"] != "unknown":
            meta[key] = {**values[0], **metadata[values[0]["lei"]]}
        else:
            invalid_framework[key] = "missing_or_ambiguous_framework"
    rows = con.execute("""SELECT entityID, refPeriod, template_id, cell_row,
        min(fact_value_eur), count(DISTINCT fact_value_raw),
        count(DISTINCT coalesce(open_axis_dims,''))
        FROM p WHERE cell_col='0010' AND
        ((template_id='61.00' AND cell_row='0040') OR
         (template_id='60.00.A' AND cell_row IN ('0010','0070','0120','0260','0320')))
        GROUP BY 1,2,3,4 ORDER BY 1,2,3,4""").fetchall()
    for eid, date, tid, row, value, distinct, dims in rows:
        if distinct == 1 and dims == 1 and value is not None and math.isfinite(value):
            coords[eid+"|"+date][tid, row] = value
    blocked = set()
    flags = root / "processed" / "scale_flags.csv"
    if flags.exists():
        with flags.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        for r in rows:
            if r["urteil"] != "unauffaellig" and (not r["template_id"] or r["template_id"] in {"61.00", "60.00.A"}):
                blocked.add(r["entityID"]+"|"+r["refPeriod"])
    profiles, missing = {}, invalid_framework
    for key, m in meta.items():
        c = coords[key]
        trea = c.get(("61.00", "0040"))
        if key in blocked:
            missing[key] = "scale_finding"
            continue
        if trea is None or trea <= 0:
            missing[key] = "missing_or_ambiguous_size"
            continue
        risk = {name: c.get(("60.00.A", row)) for name, row in RISK_ROWS.items()}
        if any(v is None or v < 0 or v > trea for v in risk.values()):
            missing[key] = "missing_or_invalid_risk"
            continue
        profiles[key] = {**m, "trea_eur": trea,
                         "risk": {k: v/trea for k, v in risk.items()}}
    return profiles, metadata, missing


def build(con, root=ROOT, extra_leis=()):
    profiles, metadata, missing = load_profiles(con, root, extra_leis)
    blocks = collections.defaultdict(dict)
    for key, p in profiles.items():
        blocks[p["date"], p["scope"], p["framework"]][key] = p
    clusters, excluded = [], {}
    for block in sorted(blocks):
        selected, dropped = representatives(blocks[block])
        excluded.update(dropped)
        groups = cluster_block({k: profiles[k] for k in selected})
        for c in groups:
            c.update(dict(zip(["date", "scope", "framework"], block)))
            clusters.append(c)
    memberships = {key: c["id"] for c in clusters for key in c["members"]}
    reports = {key: {"cluster": memberships.get(key), "features":
                    {"trea_eur": p["trea_eur"], "risk": p["risk"]}}
               for key, p in sorted(profiles.items())}
    for key, rep in excluded.items():
        reports[key]["representative"] = rep
        reports[key]["cluster"] = None
    return {"schema": 1, "method": METHOD, "threshold": THRESHOLD, "weights": WEIGHTS,
            "max_size_ratio": MAX_SIZE_RATIO,
            "fitting_metrics": ["trea", "sh_credit", "sh_ccr", "sh_cva", "sh_market", "sh_op"],
            "source_files": {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in [root/"codebook/bank_classification.csv",
                                          root/"processed/lei_relations.csv",root/"processed/coverage_gap.csv",
                                          root/"processed/scale_flags.csv"] if path.exists()},
            "metadata": metadata, "reports": reports, "clusters": clusters,
            "excluded": missing,
            "coverage": {"entities": len(metadata),
                         "classified": sum(m["ownership"] != "unknown" for m in metadata.values()),
                         "eligible_reports": len(profiles), "excluded_reports": len(missing),
                         "group_duplicates": len(excluded)}}
