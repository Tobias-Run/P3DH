"""Transfer-only experiment: partition benchmark cells without changing values.

This does not change the shipping loader. It measures the actual compressed
payload per metric profile and verifies lossless reconstruction by template.
"""
import gzip
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'processed/zweig_a/data'
OUT=ROOT/'performance/results'

def sizes(value):
    raw=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()
    return {'raw_bytes':len(raw),'gzip_bytes':len(gzip.compress(raw,6))}

def main():
    bm=json.loads((DATA/'benchmark.json').read_text())
    reg=json.loads((DATA/'codebook.json').read_text())['metrics']
    metrics={m['id']:m for m in reg['metrics']}
    tids=sorted({t for report in bm.values() for t in report})
    parts={t:{k:r[t] for k,r in bm.items() if t in r} for t in tids}
    rebuilt={k:{} for k in bm}
    for t,part in parts.items():
        for key,cells in part.items():rebuilt[key][t]=cells
    assert rebuilt==bm, 'Partition lost or changed cells'
    result={'full':sizes(bm),'lossless_reconstruction':True,'profiles':{},
            'per_template':{t:sizes(v) for t,v in parts.items()}}
    for p in reg['profiles']:
        needed={p['tpl'],*p.get('cross',[])}
        if p.get('trend'):needed.add('61.00')
        for mid in [*p['metrics'],*p.get('gate',[])]:
            needed.update(c[0] for c in metrics[mid].get('cells',[]))
        sliced={k:{t:cells for t,cells in r.items() if t in needed} for k,r in bm.items()}
        sliced={k:r for k,r in sliced.items() if r}
        for k,r in sliced.items():
            for t,cells in r.items():assert cells==bm[k][t]
        result['profiles'][p['id']]={**sizes(sliced),'templates':sorted(needed),'reports':len(sliced)}
    (OUT/'partition_experiment.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
