"""Derive compact descriptive statistics from raw browser observations."""
import json
import statistics
from collections import defaultdict
from pathlib import Path

OUT=Path(__file__).resolve().parent/'results'

def quantile(xs,p):
    xs=sorted(xs);i=(len(xs)-1)*p;lo=int(i);hi=min(lo+1,len(xs)-1)
    return xs[lo]+(xs[hi]-xs[lo])*(i-lo)

def stats(xs):
    return {'n':len(xs),'median':statistics.median(xs),'p90':quantile(xs,.9),'min':min(xs),'max':max(xs)}

def summarize(path):
    groups=defaultdict(lambda:defaultdict(list)); failures=[]
    for row in json.loads(path.read_text()):
        # Pilot ablation's repeat goto was same-document navigation. Its cold
        # samples are valid; those warm samples are explicitly excluded.
        if path.name=='desktop_ablation.json' and row.get('visit')=='warm':continue
        if 'failure' in row: failures.append(row);continue
        key=' / '.join(row[k] for k in ('variant','profile','scenario','visit'))
        g=groups[key];s=row['initial'];nav=s['navigation'][0]
        g['ready_ms'].append(s['ready'][row['scenario']])
        g['ttfb_ms'].append(nav['responseStart']-nav['requestStart'])
        g['wire_bytes'].append(nav['transferSize']+sum(x['transferSize'] for x in s['resources']))
        g['decoded_bytes'].append(nav['decodedBodySize']+sum(x['decodedBodySize'] for x in s['resources']))
        g['requests'].append(1+len(s['resources']))
        g['nodes'].append(s['nodes']);g['heap_bytes'].append(s['heap'])
        g['longtask_count'].append(len(s['longtasks']))
        g['blocking_ms'].append(sum(max(0,x['duration']-50) for x in s['longtasks']))
        if s['lcp']:g['lcp_ms'].append(s['lcp'][-1]['start'])
        # CLS uses the maximum session window, with <=1 s gaps and <=5 s length.
        best=0;window=0;start=last=None
        for shift in s['cls']:
            t=shift['start']
            if last is None or t-last>1000 or t-start>5000:
                start=t;window=0
            window+=shift['value'];best=max(best,window);last=t
        g['cls'].append(best)
        for name,vals in row.get('interactions',{}).items():
            if name=='expand':continue # async trigger time is not completion
            g[name+'_script_ms'].append(vals['script_ms'])
            g[name+'_paint_ms'].append(vals['paint_ms'])
        if row.get('micro'):g['render_micro_ms'].append(statistics.median(row['micro']['render_ms']))
        if 'expand_ready_ms' in row:g['expand_ready_ms'].append(row['expand_ready_ms'])
        if row['errors']:failures.append({'key':key,'errors':row['errors']})
    return {'source':path.name,'failures':failures,'groups':{k:{m:stats(v) for m,v in metrics.items()} for k,metrics in groups.items()}}

if __name__=='__main__':
    for filename in ['desktop_ablation.json','final_comparison.json','report_expansion.json']:
        path=OUT/filename
        if path.exists():
            result=summarize(path)
            (OUT/(path.stem+'_summary.json')).write_text(json.dumps(result,indent=2))
            print(filename, 'failures:',len(result['failures']))
            for group,metrics in result['groups'].items():
                print(group, 'ready', round(metrics['ready_ms']['median']), 'ms',
                      'wire',round(metrics['wire_bytes']['median']/1024),'KiB',
                      'blocking',round(metrics['blocking_ms']['median']), 'ms',
                      'sort',round(metrics.get('sort_paint_ms',{'median':0})['median']), 'ms')
