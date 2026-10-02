"""Read-only check that the flagged monetary facts were copied faithfully."""
import collections,csv,hashlib,io,json,math,zipfile
from decimal import Decimal,InvalidOperation
from pathlib import Path
import duckdb
ROOT=Path(__file__).resolve().parent
findings=json.loads((ROOT/'findings.json').read_text())
con=duckdb.connect()
con.read_parquet(str(ROOT/'data/p3dh_long.parquet')).create_view('p')
raw={};sources=[]
for source in json.loads((ROOT/'source_downloads.json').read_text()):
 if 'error' in source:continue
 path=ROOT/'data/sources'/source['filename']
 body=path.read_bytes()
 assert hashlib.sha256(body).hexdigest()==source['sha256']
 tables={};parameters={}
 with zipfile.ZipFile(path) as z:
  for name in z.namelist():
   basename=Path(name).name
   if not basename.endswith('.csv'):continue
   rows=list(csv.DictReader(io.StringIO(z.read(name).decode('utf-8-sig'))))
   if basename=='parameters.csv':parameters={r['name']:r['value'] for r in rows}
   if basename.startswith('k_'):
    tid=basename[2:-4].upper();tables[tid]=collections.Counter((r.get('datapoint'),r.get('factValue')) for r in rows)
 raw[source['filename']]=tables
 sources.append({**source,'parameters':parameters})
results=[]
for finding in findings:
 query="SELECT template_id,datapoint_code,fact_value_raw,fact_value,fact_value_eur,fx_rate,source_file FROM p WHERE entityID=? AND refPeriod=? AND data_type='monetary' AND fact_value_eur IS NOT NULL"
 args=[finding['entityID'],finding['refPeriod']]
 if finding['template_id']:query+=' AND template_id=?';args.append(finding['template_id'])
 rows=con.execute(query,args).fetchall()
 errors=[]
 for tid,dp,vr,v,eur,fx,source in rows:
  if source not in raw or (dp,vr) not in raw[source].get(tid,{}):errors.append({'reason':'raw_value_not_found','source':source,'template':tid,'datapoint':dp,'raw':vr})
  if not math.isclose(v*fx,eur,rel_tol=1e-12,abs_tol=1e-9):errors.append({'reason':'EUR_conversion','source':source,'template':tid,'datapoint':dp})
  if not math.isclose(float(vr),v,rel_tol=1e-12,abs_tol=1e-9):errors.append({'reason':'raw_to_float','source':source,'template':tid,'datapoint':dp})
 results.append({'entityID':finding['entityID'],'date':finding['refPeriod'],'template':finding['template_id'],'checked_facts':len(rows),'errors':errors})
summary={'findings':len(results),'checked_facts_with_overlap':sum(r['checked_facts'] for r in results),'errors':sum(len(r['errors']) for r in results),'source_zips':len(sources)}
(ROOT/'raw_validation.json').write_text(json.dumps({'summary':summary,'sources':sources,'findings':results},indent=2,ensure_ascii=False)+'\n')
print(summary)
for r in results:
 if r['errors']:print(r)
assert summary['errors']==0
