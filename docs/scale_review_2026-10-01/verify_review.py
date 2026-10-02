"""Independent replay checks against the pinned parquet and retained originals."""
import csv,json,math,unittest,zipfile,io,hashlib
from pathlib import Path
import duckdb
ROOT=Path(__file__).resolve().parent

class ReviewChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.con=duckdb.connect()
  cls.con.read_parquet(str(ROOT/'data/p3dh_long.parquet')).create_view('p')
  cls.findings=json.loads((ROOT/'findings.json').read_text())
  with (ROOT/'review_119_findings.csv').open(encoding='utf-8-sig') as fh:
   cls.ledger=list(csv.DictReader(fh))
 def value(self,lei,date,tid,row,col,dp=None):
  sql='select fact_value_eur from p where lei=? and refPeriod=? and template_id=? and cell_row=? and cell_col=?'
  args=[lei,date,tid,row,col]
  if dp:sql+=' and datapoint_code=?';args.append(dp)
  values=self.con.execute(sql,args).fetchall()
  self.assertEqual(len(values),1)
  return values[0][0]
 def test_pinned_dataset(self):
  self.assertEqual(hashlib.sha256((ROOT/'data/p3dh_long.parquet').read_bytes()).hexdigest(),'8cc95fa2dd4a7d08c7502fb9e433bbe4f311d51ee50a17533730ee9db9fc6cdf')
 def test_original_list_reproduced(self):
  self.assertEqual(hashlib.sha256((ROOT/'data/rebuilt_flags.csv').read_bytes()).hexdigest(),'14f96727f50f42e2b9a40e8d0f64e9e20abc48a486f643ed243b00badc5c4dbb')
 def test_complete_ledger(self):
  self.assertEqual(len(self.ledger),119)
  keys=[(r['ebene'],r['lei'],r['scope'],r['refPeriod'],r['template_id']) for r in self.ledger]
  self.assertEqual(len(set(keys)),119)
  self.assertTrue(all(r['review_status'] and r['reason'] and r['source_urls'] for r in self.ledger))
 def test_raw_sources(self):
  summary=json.loads((ROOT/'raw_validation.json').read_text())['summary']
  self.assertEqual(summary,{'findings':119,'checked_facts_with_overlap':158553,'errors':0,'source_zips':280})
 def test_alpha_same_cells(self):
  f=next(f for f in self.findings if f['lei']=='213800DBQIB6VBNU5C64' and f['template_id']=='23.00')
  compare=f['comparisons'][0]
  self.assertEqual(compare['matched_cells'],15)
  self.assertGreater(compare['log_ratio'],6)
  self.assertLess(compare['log_ratio'],6.1)
  self.assertEqual(compare['near_power_fraction'],1)
  june=self.value(f['lei'],'2025-06-30','23.00','0010','0020')
  dec=self.value(f['lei'],'2025-12-31','23.00','0010','0020')
  self.assertAlmostEqual(dec/(june*1e6),1.012524887,places=6)
 def test_alpha_original_and_parameters(self):
  f=next(f for f in self.findings if f['lei']=='213800DBQIB6VBNU5C64' and f['template_id']=='23.00')
  with zipfile.ZipFile(ROOT/'data/sources'/f['source_files'][0]) as z:
   params=list(csv.DictReader(io.StringIO(z.read(next(n for n in z.namelist() if n.endswith('/parameters.csv'))).decode('utf-8-sig'))))
   params={r['name']:r['value'] for r in params}
   self.assertEqual(params['baseCurrency'],'iso4217:EUR')
   self.assertEqual(params['decimalsMonetary'],'-6')
   rows=list(csv.DictReader(io.StringIO(z.read(next(n for n in z.namelist() if n.endswith('/k_23.00.csv'))).decode('utf-8-sig'))))
   self.assertEqual(len(rows),21)
   self.assertEqual(next(r['factValue'] for r in rows if r['datapoint']=='dp3525522'),'15930.969975')
 def test_kh_direction(self):
  lei='KFUXYFTU2LHQFQZDQG45'
  june=self.value(lei,'2025-06-30','41.00','0010','0010')
  dec=self.value(lei,'2025-12-31','41.00','0010','0010')
  trea=self.value(lei,'2025-06-30','61.00','0040','0010')
  self.assertGreater(june/trea,100000)
  self.assertGreater(dec,1e9);self.assertLess(dec,1e10)
  self.assertLess(abs(math.log10(june/dec)-6),.1)
 def test_citi_historical_anchor(self):
  lei='N1FBEDJ5J41VKZLO2475'
  june=self.value(lei,'2025-06-30','68.00','0010','0010')
  repeated=self.value(lei,'2025-12-31','68.00','0010','0020')
  self.assertAlmostEqual(june/(repeated*1000),1,places=7)
  self.assertLess(abs(repeated),1e9)
 def test_bbva_no_scale_in_matching_cells(self):
  f=next(f for f in self.findings if f['lei']=='K8MS7FD7N5Z2WQ51AZ71' and f['template_id']=='83.01.C')
  compare=f['comparisons'][0]
  self.assertEqual(compare['matched_cells'],15)
  self.assertLess(abs(compare['log_ratio']),.1)
  self.assertEqual(compare['near_power_fraction'],1)
 def test_rabobank_scope(self):
  lei='DG3RU1DBUFHT4ZF9WN62'
  for row in ('0010','0040','0210'):
   q1=self.value(lei,'2026-03-31','61.00',row,'0010')
   dec=self.value(lei,'2025-12-31','61.00',row,'0010')
   self.assertGreater(q1/dec,.9);self.assertLess(q1/dec,1.1)
   self.assertGreater(q1,1e10)
  self.assertEqual(self.value(lei,'2026-03-31','61.00','0280','0010'),103493)
 def test_austria_current_vs_historical_columns(self):
  lei='D1HEB8VEU6D9M8ZUXG17'
  june=self.value(lei,'2025-06-30','71.00','0560','0010')
  current=self.value(lei,'2025-12-31','71.00','0560','0010')
  past=self.value(lei,'2025-12-31','71.00','0560','0020')
  self.assertLess(abs(math.log10(current/june)),.1)
  self.assertLess(abs(math.log10(june/past)-6),.001)
 def test_cr10_semantic_type_conflict(self):
  row=self.con.execute("select fact_value,data_type,fact_value_eur,fx_rate,col_label from p where lei='KR6LSKV3BTSJRD41IF75' and refPeriod='2025-12-31' and template_id='29.02.A' and datapoint_code='dp3529486'").fetchone()
  self.assertEqual(row[0],.5);self.assertEqual(row[1],'monetary')
  self.assertIn('Risk weight',row[4]);self.assertNotEqual(row[0],row[2])

if __name__=='__main__':unittest.main(verbosity=2)
