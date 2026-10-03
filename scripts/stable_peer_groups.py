"""Frozen peer rosters, explicitly refreshed from latest usable bank profiles."""
import argparse
import collections
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def ownership_overlay(root, metadata):
    """User-authorized assignments affect exploratory fitting, never the register."""
    result = {lei: {**m, 'classification_status': 'reviewed' if m['ownership'] != 'unknown' else 'unknown'}
              for lei, m in metadata.items()}
    path = root/'codebook/bank_classification_assumptions.csv'
    if not path.exists():
        return result
    from advanced_peers import OWNERSHIP
    seen = set()
    with path.open(encoding='utf-8') as f:
        for row in csv.DictReader(f):
            lei = row['lei']
            if not re.fullmatch(r'[A-Z0-9]{20}', lei) or lei in seen or row['ownership'] not in OWNERSHIP-{'unknown'} or not re.fullmatch(r'[a-f0-9]{64}', row['input_sha256']):
                raise ValueError('Invalid or duplicate exploratory assignment: '+lei)
            seen.add(lei)
            if lei not in result or result[lei]['ownership'] != 'unknown':
                continue
            if row['classification_status'] not in {'assumption', 'externally_reported_unverified'} or not row['basis'].strip():
                raise ValueError('Missing exploratory provenance: '+lei)
            result[lei].update(ownership=row['ownership'], classification_status=row['classification_status'],
                               assumption_confidence=row['confidence'], assumption_basis=row['basis'],
                               assignment_input_sha256=row['input_sha256'])
    return result


def snapshot(profiles, metadata, root=ROOT):
    from advanced_peers import cluster_block, representatives, encoded, METHOD, WEIGHTS, THRESHOLD, MAX_SIZE_RATIO
    exploratory = ownership_overlay(root, metadata)
    blocks = collections.defaultdict(dict)
    for key, p in profiles.items():
        blocks[p['date'], p['scope'], p['framework']][key] = {**p, **exploratory[p['lei']]}
    considered, memberships, cohorts = set(), {}, []
    # A bank/scope is fitted once at its latest usable date. Older observations
    # subsequently use that fixed roster, including across framework revisions.
    for block in sorted(blocks, key=lambda b: (-int(b[0].replace('-', '')), b[1], b[2])):
        candidates = {k:p for k,p in blocks[block].items() if p['lei']+'|'+p['scope'] not in considered}
        selected, _ = representatives(candidates)
        considered.update(p['lei']+'|'+p['scope'] for p in candidates.values())
        if len(selected) < 2:
            continue
        for c in cluster_block({k:candidates[k] for k in selected}):
            roster = sorted(candidates[k]['lei'] for k in c['members'])
            stable_id = hashlib.sha256(encoded(['stable-v1', block[1], roster])).hexdigest()[:12]
            c.update(id=stable_id, date=block[0], scope=block[1], framework=block[2], roster=roster)
            for lei in roster:
                identity = lei+'|'+block[1]
                assert identity not in memberships
                memberships[identity] = stable_id
            cohorts.append(c)
    sources = [root/'codebook/bank_classification.csv', root/'codebook/bank_classification_assumptions.csv',
               root/'processed/lei_relations.csv', root/'processed/coverage_gap.csv', root/'processed/scale_flags.csv']
    return {'schema':1, 'policy':'frozen-latest-usable-bank-scope-v1', 'method':METHOD,
            'weights':WEIGHTS, 'threshold':THRESHOLD, 'max_size_ratio':MAX_SIZE_RATIO,
            'source_files':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources if p.exists()},
            'clusters':cohorts, 'memberships':memberships, 'metadata':exploratory,
            'anchor_profiles':{k:profiles[k] for c in cohorts for k in c['members']}}


def load(root, metadata):
    path = root/'codebook/stable_peer_groups.json'
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if data.get('schema') != 1 or data.get('policy') != 'frozen-latest-usable-bank-scope-v1':
        raise ValueError('Unsupported stable peer roster')
    ids, expected = set(), {}
    for c in data['clusters']:
        if c['id'] in ids or len(c['roster']) != len(set(c['roster'])):
            raise ValueError('Duplicate stable peer roster')
        ids.add(c['id'])
        for lei in c['roster']:
            key = lei+'|'+c['scope']
            if key in expected:
                raise ValueError('Bank belongs to multiple stable peer groups: '+key)
            expected[key] = c['id']
    if data['memberships'] != expected:
        raise ValueError('Stable membership map disagrees with roster')
    # Keep the frozen roster even if a later publication lacks a member. Never
    # replace it with another bank or re-fit without an explicit refresh.
    return {'stable_policy':data['policy'], 'stable_clusters':data['clusters'],
            'stable_memberships':data['memberships'], 'stable_metadata':data['metadata'],
            'stable_source_files':data['source_files']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', help='Explicitly replace the frozen roster')
    args = parser.parse_args()
    path = ROOT/'codebook/stable_peer_groups.json'
    if path.exists() and not args.refresh:
        raise SystemExit('Roster already exists. Use --refresh to deliberately replace it.')
    import duckdb
    from advanced_peers import load_profiles, encoded
    con = duckdb.connect()
    con.from_parquet(str(ROOT/'processed/long/p3dh_long.parquet')).create_view('p')
    # Existing manifest includes the complete viewer population, including
    # institutions without usable fitting observations.
    current = json.loads((ROOT/'processed/zweig_a/data/advanced_peers.json').read_text())
    profiles, metadata, _ = load_profiles(con, ROOT, current['metadata'])
    data = snapshot(profiles, metadata, ROOT)
    path.write_bytes(encoded(data));con.close()
    print(f"Frozen groups: {len(data['clusters'])}; >=5 members: {sum(len(c['roster'])>=5 for c in data['clusters'])}; bank/scope memberships: {len(data['memberships'])}")


if __name__ == '__main__':
    main()
