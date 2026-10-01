"""Plot final implementation A/B medians; lab timings, not field vitals."""
import json
from pathlib import Path
import os
os.environ.setdefault("MPLCONFIGDIR","/tmp/p3dh-matplotlib")
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from summarize import summarize

out=Path(__file__).resolve().parent/'results'
result=summarize(out/'implementation_comparison.json')
assert not result['failures'],result['failures']
assert all(x['ready_ms']['n']==5 for x in result['groups'].values())
(out/'implementation_comparison_summary.json').write_text(json.dumps(result,indent=2))
fig,axes=plt.subplots(1,3,figsize=(14,4.5))
labels=['Desktop kalt','Desktop warm','Mobil kalt','Mobil warm']
cases=[('desktop','cold'),('desktop','warm'),('mobile4g','cold'),('mobile4g','warm')]
for ax,scenario,metric,title in zip(axes,['benchmark','report','benchmark'],['ready_ms','ready_ms','cls'],
    ['Benchmark bereit (s)','Berichtsübersicht bereit (s)','Benchmark CLS im Labor']):
    for i,(variant,label,color) in enumerate([('baseline','Ausgangscode','#888888'),('candidate','Umsetzung','#12556e')]):
        values=[result['groups'][f'{variant} / {profile} / {scenario} / {visit}'][metric]['median']/(1000 if metric=='ready_ms' else 1)
            for profile,visit in cases]
        bars=ax.bar([x+(i-.5)*.36 for x in range(4)],values,width=.36,label=label,color=color)
        ax.bar_label(bars,fmt='%.3f' if metric=='cls' else '%.2f',fontsize=8,padding=3)
    ax.set_xticks(range(4),labels,rotation=25,ha='right');ax.set_title(title);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    ax.spines[['top','right']].set_visible(False)
axes[0].legend(fontsize=9)
fig.suptitle('P3DH: 5 Wiederholungen je Fall · Chromium · Mobil: CPU 4× / 4 Mbit/s / 60 ms')
fig.text(.5,.005,'Benchmark: 100 sichtbare Zeilen je Seite; vollständige Berechnung und CSV. Labormediane, keine Feld-Core-Web-Vitals.',ha='center',fontsize=8)
fig.tight_layout(rect=(0,.025,1,.95));fig.savefig(out/'implementation_comparison.png',dpi=160)
print('Wrote final summary and plot')
