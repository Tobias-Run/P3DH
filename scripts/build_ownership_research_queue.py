"""Prioritise unreviewed institutions by TREA; no ownership inference or web calls.

Run with the current joined facts and reviewed ownership ledger:
  python scripts/build_ownership_research_queue.py
The CSV is the durable queue; the JSON supplies candidate URLs to the collector.
"""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def priority(con, known, blocked):
    rows = con.execute("""
        SELECT entityID, lei, scope, refPeriod, max(bank_name),
               min(fact_value_eur), count(DISTINCT fact_value_raw),
               count(DISTINCT coalesce(open_axis_dims,'')),
               bool_or(coalesce(unit_ambiguous,false))
        FROM p WHERE template_id='61.00' AND cell_row='0040' AND cell_col='0010'
        GROUP BY 1,2,3,4
        HAVING min(fact_value_eur)>0 AND isfinite(min(fact_value_eur))
           AND count(DISTINCT fact_value_raw)=1
           AND count(DISTINCT coalesce(open_axis_dims,''))=1
           AND NOT bool_or(coalesce(unit_ambiguous,false))
        ORDER BY refPeriod DESC, (scope='CON') DESC, entityID
    """).fetchall()
    chosen = {}
    for eid, lei, scope, date, name, value, *_ in rows:
        if lei in known or lei in chosen or (eid, date) in blocked:
            continue
        chosen[lei] = dict(lei=lei, name=name or lei, entityID=eid, scope=scope,
                           date=date, trea_eur=value)
    ordered = sorted(chosen.values(), key=lambda r: (-r['trea_eur'], r['lei']))
    return [dict(row, rank=i) for i, row in enumerate(ordered, 1)]


def build(root=ROOT):
    import duckdb
    register = list(csv.DictReader((root/'codebook/bank_classification.csv').open()))
    known = {r['lei'] for r in register}
    reviewed = {r['lei']: r for r in register}
    relations = {r['lei']: r for r in csv.DictReader(
        (root/'processed/lei_relations.csv').open())}
    ledger = {r['lei']: r for r in csv.DictReader(
        (root/'docs/advanced_peers/ownership_research.csv').open())}
    flags = list(csv.DictReader((root/'processed/scale_flags.csv').open()))
    blocked = {(r['entityID'], r['refPeriod']) for r in flags
               if r['urteil'] != 'unauffaellig' and r['template_id'] in ('', '61.00')}
    exclusions = list(csv.DictReader(
        (root/'codebook/ownership_research_size_exclusions.csv').open()))
    blocked.update((r['entityID'], r['date']) for r in exclusions if r['metric'] == 'trea')
    con = duckdb.connect()
    parquet = root/'processed/long/p3dh_long.parquet'
    con.read_parquet(str(parquet)).create_view('p')
    rows = [r for r in priority(con, known, blocked) if r['lei'] in ledger]
    con.close()
    for row in rows:
        # Discovery is a URL hint, never a reviewed company/owner identity.
        row['websites'] = [u for u in ledger[row['lei']]['candidate_websites'].split('|') if u]
        relation = relations.get(row['lei'], {})
        candidate = relation.get('ultimate_parent_lei') or relation.get('direct_parent_lei')
        if candidate and candidate != row['lei'] and re.fullmatch(r'[A-Z0-9]{20}', candidate):
            # This older relationship is a hint, not reviewed bank control.
            # Reuse the reviewed controller source only after bank-specific proof.
            row['controller_candidate_lei'] = candidate
            if candidate in reviewed:
                row['reviewed_controller_source_url'] = reviewed[candidate]['source_url']
    for i, row in enumerate(rows, 1):
        row['rank'] = i
    source_files = ['codebook/bank_classification.csv',
                    'codebook/ownership_research_size_exclusions.csv',
                    'processed/scale_flags.csv', 'processed/lei_relations.csv',
                    'docs/advanced_peers/ownership_research.csv']
    manifest = {'metric': 'TREA (KM1 61.00 r0040 c0010)',
                'method': 'Latest technically valid date per institution; CON preferred on ties; '
                          'positive, unambiguous amount/dimensions/unit; relevant scale and '
                          'explicit currency-review exclusions. Ownership is never inferred.',
                'rankable': len(rows),
                'pending_total': sum(lei not in known for lei in ledger),
                'source_hashes': {p: hashlib.sha256((root/p).read_bytes()).hexdigest()
                                  for p in source_files}}
    with parquet.open('rb') as f:
        manifest['joined_parquet_sha256'] = hashlib.file_digest(f, 'sha256').hexdigest()
    return rows, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'docs/advanced_peers')
    args = parser.parse_args()
    rows, manifest = build()
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output/'ownership_priority.csv').open('w', newline='', encoding='utf-8') as f:
        fields = ['rank', 'lei', 'name', 'entityID', 'scope', 'date', 'trea_eur']
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows({k: row[k] for k in fields} for row in rows)
    (args.output/'ownership_priority.json').write_text(
        json.dumps(rows, ensure_ascii=False, indent=2)+'\n')
    (args.output/'ownership_priority_manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(f"TREA queue: {len(rows)}/{manifest['pending_total']} pending institutions rankable.")


if __name__ == '__main__':
    main()
