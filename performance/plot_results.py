"""Export the controlled benchmark medians and observed min/max ranges."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=Path(__file__).resolve().parent/'results'
groups=json.loads((OUT/'final_comparison_summary.json').read_text())['groups']
fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
for ax,profile,title in zip(axes,['desktop','mobile4g'],['Desktop','Mobil simuliert · 4 Mbit/s · CPU 4×']):
    for offset,variant,label,color in [(-.18,'baseline','Ausgangsstand','#61758b'),(.18,'candidate','Optimiert','#087e8b')]:
        vals=[groups[f'{variant} / {profile} / benchmark / {visit}']['ready_ms'] for visit in ['cold','warm']]
        med=[v['median']/1000 for v in vals]
        err=[[ (v['median']-v['min'])/1000 for v in vals],[(v['max']-v['median'])/1000 for v in vals]]
        bars=ax.bar([offset,1+offset],med,width=.34,color=color,label=label,yerr=err,capsize=4)
        ax.bar_label(bars,labels=[f'{v:.2f} s' for v in med],padding=8)
    ax.set_xticks([0,1],['Kaltstart','Wiederbesuch'])
    ax.set_title(title);ax.set_ylabel('Benchmark bereit (Sekunden)');ax.set_ylim(0,ax.get_ylim()[1]*1.18)
    ax.spines[['top','right']].set_visible(False)
axes[0].legend(loc='upper right',fontsize=8)
fig.suptitle('P3DH · Median aus fünf Läufen je Bedingung\nFehlerbalken: beobachtetes Minimum–Maximum, keine Konfidenzintervalle',fontsize=11)
fig.savefig(OUT/'benchmark_comparison.svg')
fig.savefig(OUT/'benchmark_comparison.png',dpi=160)
