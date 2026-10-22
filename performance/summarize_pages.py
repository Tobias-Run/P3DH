"""Summarize native Pages timings and CDP network bytes, avoiding TAO ambiguity."""
import json,statistics
from pathlib import Path
from collections import defaultdict
from summarize import summarize,stats

OUT=Path(__file__).resolve().parent/'results/production_2026-10-02'

def main():
    raw=json.loads((OUT/'measurements.json').read_text())
    assert len(raw)==40 and not any('failure' in x or x.get('errors') for x in raw)
    result=summarize(OUT/'measurements.json');metrics=defaultdict(lambda:defaultdict(list))
    for row in raw:
        key=' / '.join(row[k] for k in ('variant','profile','scenario','visit'))
        m=metrics[key]
        m['cdp_wire_bytes'].append(sum(n.get('encodedDataLength',0) for n in row['network']))
        m['http_response_count'].append(sum('status'in n for n in row['network']))
        m['cached_response_count'].append(sum(n.get('fromDiskCache',False) or n.get('servedFromCache',False) for n in row['network']))
        for kind,action in row['interactions'].items():
            for name in ['blocking_ms','longtask_count','nodes','paint_ms']:
                if name in action:m[kind+'_'+name].append(action[name])
    for key,values in metrics.items():result['groups'][key].update({name:stats(v) for name,v in values.items()})
    result['expected_samples']=40;result['data_revision']=raw[0]['data_revision']
    result['request_failures']=[{'profile':x['profile'],'scenario':x['scenario'],'visit':x['visit'],'run':x['run'],'failures':x['request_failures']} for x in raw if x.get('request_failures')]
    result['http_errors']=[{'profile':x['profile'],'scenario':x['scenario'],'visit':x['visit'],'run':x['run'],'responses':[n for n in x['network'] if n.get('status',0)>=400]} for x in raw if any(n.get('status',0)>=400 for n in x['network'])]
    (OUT/'summary.json').write_text(json.dumps(result,indent=2))
    for key,values in result['groups'].items():
        print(key,'ready',round(values['ready_ms']['median']),'ms','CLS',round(values['cls']['median'],4),
              'wire',round(values['cdp_wire_bytes']['median']/1024),'KiB','cache',round(values['cached_response_count']['median']))
    plot(result)
    print('Request failures',len(result['request_failures']),'HTTP error samples',len(result['http_errors']))

def plot(result):
    import os
    os.environ.setdefault('MPLCONFIGDIR','/tmp/p3dh-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(10,4.6))
    cases=[('desktop','benchmark'),('desktop','report'),('mobile4g','benchmark'),('mobile4g','report')]
    for i,(visit,label,color) in enumerate([('cold','Erster Besuch','#12556e'),('warm','Wiederbesuch','#c8102e')]):
        values=[result['groups'][f'pages / {profile} / {scenario} / {visit}']['ready_ms'] for profile,scenario in cases]
        bars=ax.bar([j+(i-.5)*.35 for j in range(4)],[v['median']/1000 for v in values],width=.35,color=color,label=label)
        ax.bar_label(bars,fmt='%.2f s',padding=3)
    ax.set_xticks(range(4),['Desktop Benchmark','Desktop Bericht','Mobil Benchmark','Mobil Bericht'])
    ax.set_ylabel('Sekunden bis zur ersten nutzbaren Ansicht');ax.set_title('P3DH auf GitHub Pages · 5 Wiederholungen je Fall')
    ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);ax.spines[['top','right']].set_visible(False);ax.legend()
    fig.text(.5,.015,'Native HTTPS-Auslieferung mit Brotli und Browsercache · Mobil: Chromium CPU 4× / 4 Mbit/s / 60 ms; keine Feldwerte.',ha='center',fontsize=8)
    fig.tight_layout(rect=(0,.05,1,1));fig.savefig(OUT/'pages_timings.png',dpi=160)

if __name__=='__main__':main()
