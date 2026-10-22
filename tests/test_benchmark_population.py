"""Execute benchmark population helpers with explicit missing-data fixtures."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'),'Node required for viewer JavaScript')
class BenchmarkPopulationTest(unittest.TestCase):
    def check(self,body):
        source=(ROOT/'processed/zweig_a/viewer_json.html').read_text()
        helpers=source[source.index('function metricPeerGroups('):source.index('function peerControls(')]
        harness="""
const assert=require('node:assert/strict');
const PCT_MIN_GROUP=5,BAR_KINDS=new Set(['eur']),BM_PEER='cluster';
const AP_DATA={fitting_metrics:['trea']};
const peerKeyOf=(r,basis)=>r.assigned===false?null:[r.cluster,r.date,r.scope,r.framework].join('|');
const barErlaubt=(p,r,m)=>!r.badUnit;
const sichtbareSpalten=p=>p.cols;
const metric={id:'cet1',kind:'pct'},prof={cols:[metric]};
const row=(i,extra={})=>({key:String(i),cet1:.1,trea:1,cluster:'a',date:'2025-12-31',scope:'CON',framework:'4.1',...extra});
"""
        result=subprocess.run(['node','-e',harness+helpers+body],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_zero_is_valid_missing_and_nonfinite_are_not(self):
        self.check("const d=peerCoverage([0,1,2,3,4].map(i=>row(i,{cet1:0})).concat([row(5,{cet1:null}),row(6,{cet1:NaN})]),prof)[0];assert.equal(d.comparable,5);assert.equal(d.usableGroups,1);assert.equal(d.ranked,5);")

    def test_no_pooling_dates_scopes_or_frameworks(self):
        self.check("""
for(const field of ['date','scope','framework']){
 const rows=[0,1,2,3,4,5].map(i=>row(i,{[field]:i<3?'one':'two'}));
 const d=peerCoverage(rows,prof)[0];assert.equal(d.comparable,6);assert.equal(d.usableGroups,0);assert.equal(d.ranked,0);
}
""")

    def test_each_metric_has_its_own_denominator(self):
        self.check("const rows=[0,1,2,3,4].map(i=>row(i,{npl:i===4?null:1}));const d=peerCoverage(rows,{cols:[metric,{id:'npl',kind:'ratio'}]});assert.equal(d[0].ranked,5);assert.equal(d[1].ranked,0);")

    def test_unassigned_values_do_not_produce_percentiles(self):
        self.check("const d=peerCoverage([0,1,2,3,4,5].map(i=>row(i,{assigned:i<4})),prof)[0];assert.equal(d.comparable,6);assert.equal(d.ranked,0);")

    def test_unit_exclusions_apply_before_group_minimum(self):
        self.check("const d=peerCoverage([0,1,2,3,4].map(i=>row(i,{badUnit:i===0})),{cols:[{id:'trea',kind:'eur'}]},'standard')[0];assert.equal(d.comparable,4);assert.equal(d.usableGroups,0);")

    def test_fitting_variables_are_not_advertised_as_rankable(self):
        self.check("const d=peerCoverage([0,1,2,3,4].map(i=>row(i)),{cols:[{id:'trea',kind:'eur'}]})[0];assert(d.suppressed);assert.equal(d.ranked,0);")


if __name__=='__main__':unittest.main()
