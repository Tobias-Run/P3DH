"""Download the reviewed snapshot and originals, rejecting changed content."""
import concurrent.futures
import hashlib
import urllib.request
from pathlib import Path
import json
ROOT = Path(__file__).resolve().parent

def fetch(item):
    path, url, expected = item
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=120) as response:
            content = response.read()
    else:
        content = path.read_bytes()
    actual = hashlib.sha256(content).hexdigest()
    if actual != expected:
        raise RuntimeError(f"Source changed: {url}: {actual} != {expected}")
    if not path.exists():
        path.write_bytes(content)
    return path.name

sources = json.loads((ROOT / 'source_downloads.json').read_text())
items = [(ROOT / 'data/p3dh_long.parquet',
          'https://raw.githubusercontent.com/Tobias-Run/P3DH/f47ef2d32968e59188b4139ede3ccac1d9737f21/state/p3dh_long.parquet',
          '8cc95fa2dd4a7d08c7502fb9e433bbe4f311d51ee50a17533730ee9db9fc6cdf')]
items.extend((ROOT / 'data/sources' / s['filename'], s['url'], s['sha256']) for s in sources)
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    for result in pool.map(fetch, items):
        print('Verified', result, flush=True)
