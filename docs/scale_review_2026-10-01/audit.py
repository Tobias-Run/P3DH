import csv, json, math, collections, hashlib, sys
from pathlib import Path
import duckdb

ROOT=Path(__file__).resolve().parent
con=duckdb.connect()
con.read_parquet(str(ROOT/'data/p3dh_long.parquet')).create_view('p')
flags=list(csv.DictReader(open(ROOT/'data/rebuilt_flags.csv')))
flags=[r for r in flags if r['urteil']!='unauffaellig']
con.execute('CREATE TABLE flag_eids(entityID VARCHAR)')
con.executemany('INSERT INTO flag_eids VALUES (?)',[(eid,) for eid in sorted({r['entityID'] for r in flags})])
facts=con.execute("""SELECT entityID,refPeriod,template_id,cell_row,cell_col,
 coalesce(open_axis_dims,''),fact_value_eur,datapoint_code,source_file,
 row_label,col_label,currency,decimals_monetary,framework_version
 FROM p WHERE data_type='monetary' AND fact_value_eur IS NOT NULL AND entityID IN (SELECT entityID FROM flag_eids)
 ORDER BY entityID,refPeriod,template_id,cell_row,cell_col,open_axis_dims,datapoint_code""").fetchall()
groups=collections.defaultdict(lambda:collections.defaultdict(lambda:collections.defaultdict(list)))
sources=collections.defaultdict(set)
for eid,date,tid,row,col,dims,value,dp,source,rl,cl,cur,dec,fw in facts:
 groups[eid][date][tid].append({'row':row,'col':col,'dims':dims,'value':value,'dp':dp,'row_label':rl,'col_label':cl,'currency':cur,'decimals':dec,'framework':fw})
 sources[eid,date,tid].add(source)

def unique_cells(rows):
 cells=collections.defaultdict(list)
 for r in rows:
  if r['value']!=0:cells[r['row'],r['col'],r['dims'],r['dp']].append(r['value'])
 return {key:vals[0] for key,vals in cells.items() if len(vals)==1}

def quantile(xs,q):
 xs=sorted(xs);pos=q*(len(xs)-1);lo=int(pos);hi=math.ceil(pos)
 return xs[lo]+(xs[hi]-xs[lo])*(pos-lo) if xs else None

def compare(a,b):
 ca,cb=unique_cells(a),unique_cells(b)
 keys=ca.keys()&cb.keys()
 logs=[math.log10(abs(cb[k]/ca[k])) for k in keys if cb[k]/ca[k]>0]
 if not logs:return None
 median=quantile(logs,.5);exponent=round(median/3)*3
 return {'matched_cells':len(logs),'sign_changes_excluded':sum(cb[k]/ca[k]<0 for k in keys),'log_ratio':round(median,6),'factor':10**median,
 'q10':quantile(logs,.1),'q90':quantile(logs,.9),
 'near_power_fraction':sum(abs(x-exponent)<=math.log10(2) for x in logs)/len(logs),
 'power':exponent}

out=[]
for flag in flags:
 eid,date,tid=flag['entityID'],flag['refPeriod'],flag['template_id']
 templates=[tid] if tid else list(groups[eid][date])
 rows=[r for t in templates for r in groups[eid][date][t]]
 own={t:groups[eid][date][t] for t in templates}
 comparisons=[]
 for other_date,other_templates in groups[eid].items():
  if other_date==date:continue
  if tid:
   result=compare(rows,other_templates.get(tid,[]))
   if result:comparisons.append({'date':other_date,'source_urls':['https://errp.eba.europa.eu/public-documents/'+s.split('_')[3]+'/input/'+s for s in sorted(sources[eid,other_date,tid])],**result})
  else:
   logs=[];ts=[]
   for t,rs in own.items():
    result=compare(rs,other_templates.get(t,[]))
    if result:ts.append({'template':t,**result})
   if ts:comparisons.append({'date':other_date,'templates':ts})
 positive=[r['value'] for r in rows if r['value']>0]
 source_files=sorted({source for t in templates for source in sources[eid,date,t]})
 source_urls=['https://errp.eba.europa.eu/public-documents/'+source.split('_')[3]+'/input/'+source for source in source_files]
 out.append({**flag,'source_files':source_files,'source_urls':source_urls,
 'n_positive':len(positive),'min_positive':min(positive) if positive else None,
 'median_positive':quantile(positive,.5),'max_positive':max(positive) if positive else None,
 'comparisons':comparisons})
(ROOT/'findings.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
for f in out:
 if f['ebene']=='template':
  comparisons='; '.join(f"{r['date']}: n={r['matched_cells']} log={r['log_ratio']:.3f} q10/90={r['q10']:.2f}/{r['q90']:.2f} near={r['near_power_fraction']:.0%}" for r in f['comparisons'])
  print(f"{f['bank_name'][:27]:27} {f['refPeriod']} {f['template_id']:7} {comparisons}")
