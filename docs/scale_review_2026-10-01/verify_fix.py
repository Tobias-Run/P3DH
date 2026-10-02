"""Verify the complete #122 delta against the pinned reviewed data."""
import collections
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import scale_evidence as evidence
import duckdb


def read(path):
    with Path(path).open(encoding='utf-8-sig') as fh:
        return list(csv.DictReader(fh))


def key(row):
    return tuple(row[f] for f in ['ebene', 'entityID', 'refPeriod', 'template_id'])


parquet = ROOT / 'processed/long/p3dh_long.parquet'
assert hashlib.sha256(parquet.read_bytes()).hexdigest() == '8cc95fa2dd4a7d08c7502fb9e433bbe4f311d51ee50a17533730ee9db9fc6cdf', 'Use the pinned review snapshot'
old = read(AUDIT / 'data/rebuilt_flags.csv')
new = read(ROOT / 'processed/scale_flags.csv')
o, n = {key(r): r for r in old}, {key(r): r for r in new}
assert len(old) == 930 and len(new) == 929
assert all(n[k]['urteil'] == r['urteil'] for k, r in o.items() if r['ebene'] == 'report')
assert {k for k in n if k not in o} == {
    ('template', 'rs:KFUXYFTU2LHQFQZDQG45.CON', '2025-06-30', '41.00'),
    ('template', 'rs:N1FBEDJ5J41VKZLO2475.CON', '2025-06-30', '68.00')}
assert {k for k in o if k not in n} == {
    ('template', 'rs:KFUXYFTU2LHQFQZDQG45.CON', '2025-12-31', '41.00'),
    ('template', 'rs:N1FBEDJ5J41VKZLO2475.CON', '2025-12-31', '68.00'),
    ('template', 'rs:K8MS7FD7N5Z2WQ51AZ71.CON', '2025-06-30', '83.01.C')}
reviews = evidence.load_reviews()
con = duckdb.connect()
con.read_parquet(str(parquet)).create_view('p')
facts = evidence.collect(con, {tuple(g['key'][::2]) for r in reviews for g in r['guards']})
# Collect uses (entity, template); review guards carry (entity, date, template).
for r in reviews:
    assert all(evidence.fingerprint(facts[tuple(g['key'])]) == g['sha256'] for g in r['guards']), r['id']
    for d in r['decisions']:
        row = n[('template', *d['key'])]
        for field in ['urteil', 'richtung', 'umfang', 'referenz_stichtag', 'beleg_status', 'faktor_geschaetzt']:
            assert row[field] == d['finding'][field], (r['id'], field)
        assert json.loads(row['betroffene_zellen']) == d['finding']['betroffene_zellen']
        assert json.loads(row['faktoren']) == d['finding']['faktoren']
assert sum(r['umfang'] == 'teilbereich' for r in new) == 9
assert sum(len(json.loads(r['betroffene_zellen'])) for r in new) == 261
assert all(not r['faktor_geschaetzt'] for r in new if r['urteil'] == 'verdacht')
status = json.loads((ROOT / 'processed/scale_review_status.json').read_text())
assert len(status) == 48 and all(r['status'] == 'angewendet' for r in status)

# IRRBB: all monetary values and calculated ratios remain byte-for-byte equal;
# only caution/SOT classification fields may change.
base = 'b22b1b79c1dbe2397c47c5555cc5238a0af071f8'
old_irr = list(csv.DictReader(subprocess.check_output(['git', 'show', base+':processed/irrbb_sensitivity.csv'], cwd=ROOT).decode().splitlines()))
new_irr = read(ROOT / 'processed/irrbb_sensitivity.csv')
assert len(old_irr) == len(new_irr) == 1980
allowed = {'vorbehalt', 'sot_eve', 'sot_nii'}
irr_delta = []
for a, b in zip(old_irr, new_irr):
    changed = {k for k in a if a[k] != b[k]}
    assert not changed - allowed, (a['lei'], changed)
    if changed:
        irr_delta.append({'bank': a['bank_name'], 'lei': a['lei'], 'date': a['refPeriod'],
                          'scenario': a['szenario'], 'before': a['vorbehalt'], 'after': b['vorbehalt']})
assert len(irr_delta) == 30
con.close()
result = {
    'snapshot': 'f47ef2d32968e59188b4139ede3ccac1d9737f21',
    'all_checks_passed': True, 'old_rows': len(old), 'new_rows': len(new),
    'old_active_findings': 119, 'new_active_findings': 118, 'report_status_changes': 0,
    'counts': {f'{a}/{b}': v for (a,b),v in collections.Counter((r['ebene'],r['urteil']) for r in new).items()},
    'added_keys': sorted(set(n)-set(o)), 'removed_keys': sorted(set(o)-set(n)),
    'applied_source_bound_reviews': 48, 'partial_findings': 9, 'affected_cell_masks': 261,
    'irrbb_changed_rows': irr_delta,
    'full_delta': [{'key': k, 'before': o.get(k), 'after': n.get(k)} for k in sorted(set(o)|set(n)) if o.get(k) != n.get(k)]}
print(json.dumps({k:v for k,v in result.items() if k!='full_delta'}, ensure_ascii=False, indent=2))
(AUDIT / 'scale_diff_122.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
