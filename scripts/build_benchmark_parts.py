"""Derive immutable template payloads and their dependency manifest.

Keeps benchmark.json for older viewers. File names contain content hashes; the
publisher additionally pins the entire dataset to one Git commit (#118).
"""
import hashlib
import json
from pathlib import Path

def encoded(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()

def dependencies(profile,metrics):
    needed={profile['tpl'],*profile.get('cross',[])}
    if profile.get('trend'):needed.add('61.00')
    for ident in [*profile['metrics'],*profile.get('gate',[])]:
        m=metrics[ident]
        needed.update(cell[0] for cell in m.get('cells',[]))
        if m.get('kind')=='shareOfTrea':needed.add('61.00')
    return sorted(needed)

def build(directory):
    directory=Path(directory)
    bm=json.loads((directory/'benchmark.json').read_text())
    codebook=json.loads((directory/'codebook.json').read_text())
    reg=codebook['metrics'];metrics={m['id']:m for m in reg['metrics']}
    parts={}
    for key,templates in bm.items():
        for tid,cells in templates.items():parts.setdefault(tid,{})[key]=cells
    manifest={'schema':1,'version':hashlib.sha256(encoded(bm)).hexdigest(),'templates':{},
              'profiles':{p['id']:dependencies(p,metrics) for p in reg['profiles']}}
    overview={c[0] for m in reg['metrics'] if m.get('ov') for c in m.get('cells',[])}
    overview.add('61.00') # report time series
    manifest['overview']=sorted(overview)
    # Empty dependencies must still be marked loaded, never silently omitted.
    needed=set().union(*map(set,manifest['profiles'].values()),overview)
    for tid in sorted(set(parts)|needed):
        data=encoded(parts.get(tid,{}));sha=hashlib.sha256(data).hexdigest()
        relative=f'benchmark/{tid}.{sha}.json'
        path=directory/relative;path.parent.mkdir(exist_ok=True)
        if not path.exists():path.write_bytes(data)
        manifest['templates'][tid]={'path':relative,'sha256':sha}
    # Publication copies only the current files. Old snapshots stay addressable
    # through the immutable Git revision selected by data_version.json.
    keep={x['path'] for x in manifest['templates'].values()}
    for path in (directory/'benchmark').glob('*.json'):
        if path.relative_to(directory).as_posix() not in keep:path.unlink()
    codebook['benchmark_parts']=manifest
    (directory/'codebook.json').write_bytes(encoded(codebook))
    return manifest

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parents[1]/'processed/zweig_a/data')
    args=parser.parse_args();m=build(args.data_dir)
    print(f"{len(m['templates'])} template payloads; dataset {m['version']}")
