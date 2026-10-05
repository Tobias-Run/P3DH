"""Execute real comparison selection helpers; never substitute another date."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'Node needed for viewer selection helpers')
class CompareDatesTest(unittest.TestCase):
    def check(self,body):
        source=(ROOT/'processed/zweig_a/viewer_json.html').read_text()
        source='function compareSelection'+source.split('function compareSelection',1)[1].split('let CMP_RENDER',1)[0]
        harness="""
const assert=require('node:assert/strict');
const report=(entityID,refPeriod,tpls={})=>({entityID,refPeriod,loaded:true,
 templates:new Map(Object.entries(tpls).map(([t,values])=>[t,values.map(val=>({val}))]))});
const a=report('A.CON','2025-06-30'),a2=report('A.CON','2025-12-31'),a3=report('A.CON','2026-03-31');
const b=report('B.CON','2025-06-30'),b2=report('B.CON','2025-12-31');
const reports=[a,a2,a3,b,b2];
"""
        result=subprocess.run(['node','-e',harness+source+body],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_mixed_pins_choose_latest_common_date(self):
        self.check("const s=compareSelection([a3,b],reports);assert.equal(s.date,'2025-12-31');assert.deepEqual(s.slots.map(x=>x.rep),[a2,b2]);")

    def test_explicit_date_keeps_missing_bank_without_fallback(self):
        self.check("const s=compareSelection([a,b],reports,'2026-03-31');assert.equal(s.slots[0].rep,a3);assert.equal(s.slots[1].rep,null);assert.equal(s.slots.length,2);")

    def test_consolidation_scope_is_not_replaced(self):
        self.check("const ind=report('B.IND','2026-03-31');const s=compareSelection([a,b],[...reports,ind],'2026-03-31');assert.equal(s.slots[1].rep,null);")

    def test_disjoint_dates_never_mix_periods(self):
        self.check("const s=compareSelection([a3,b],[a3,b]);assert.equal(s.common.length,0);assert.equal(s.date,a3.refPeriod);assert.equal(s.slots[1].rep,null);")

    def test_duplicate_dates_of_same_bank_collapse(self):
        self.check("const s=compareSelection([a,a2,b],reports);assert.equal(s.slots.length,2);assert.deepEqual(s.slots.map(x=>x.entityID),['A.CON','B.CON']);")

    def test_unavailable_shared_date_is_preserved(self):
        self.check("const s=compareSelection([a,b],reports,'2024-12-31');assert.equal(s.date,'2024-12-31');assert(s.dates.includes(s.date));assert(s.slots.every(x=>x.rep===null));")

    def test_template_zero_counts_null_and_empty_do_not(self):
        self.check("""
const r1=report('A.CON','2025-12-31',{'61.00':[0],empty:[],nulls:[null],partial:[1]});
const r2=report('B.CON','2025-12-31',{'61.00':[2],nulls:[null]});
const g=compareTemplates([{rep:r1},{rep:r2}]);
assert.deepEqual(g.common,['61.00']);assert.deepEqual(g.partial,['partial']);assert.equal(g.counts.get('partial'),1);
""")

    def test_missing_or_failed_report_denies_all_bank_coverage(self):
        self.check("""
const r=report('A.CON','2025-12-31',{'61.00':[0]});
for(const other of [{rep:null},{rep:r,error:true}]){
 const g=compareTemplates([{rep:r},other]);assert.equal(g.common.length,0);assert.deepEqual(g.partial,['61.00']);
}
""")


if __name__=='__main__':unittest.main()
