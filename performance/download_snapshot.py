"""Pin and download the exact data used by the performance scenarios."""
import concurrent.futures
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'processed/zweig_a/data'
RESULTS = ROOT / 'performance/results'

def fetch(path):
    target = DATA / path
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['curl', '-fsSL', '--compressed', '--connect-timeout', '10',
                    '--max-time', '45', BASE + path, '-o', str(target)], check=True)
    raw = target.read_bytes()
    print(f'{path}: {len(raw):,} bytes', flush=True)
    return {'path': path, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-ref', help='Immutable data commit; default: current data branch')
    parser.add_argument('--all-reports', action='store_true', help='Download the complete corpus for regression tests')
    args=parser.parse_args()
    ref = args.data_ref or subprocess.check_output(['git', 'ls-remote', 'origin', 'refs/heads/data'],
                                                 cwd=ROOT, timeout=20, text=True).split()[0]
    BASE = f'https://raw.githubusercontent.com/Tobias-Run/P3DH/{ref}/'
    index_record = fetch('index.json')
    idx = json.loads((DATA / 'index.json').read_text())
    reports = idx['reports']
    chosen = sorted(reports, key=lambda r: r['nt'], reverse=True)[:3]
    chosen += [r for r in reports if r['entityID'].endswith('CON') and r['nt'] == 0][:1]
    chosen += reports[:1]
    ids = {r['entityID'] for r in chosen}
    selected = [r for r in reports if r['entityID'] in ids]
    if args.all_reports:
        selected = reports
    paths = ['codebook.json', 'benchmark.json', 'labels.json', 'peer_shape.json']
    paths += ['reports/' + r['f'] for r in selected]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        files = [index_record, *pool.map(fetch, paths)]
    manifest = {'main_sha': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                'data_sha': ref, 'reports': chosen, 'files': files}
    RESULTS.mkdir(parents=True, exist_ok=True)
    output = 'full_snapshot.json' if args.all_reports else 'snapshot.json'
    (RESULTS / output).write_text(json.dumps(manifest, indent=2))
