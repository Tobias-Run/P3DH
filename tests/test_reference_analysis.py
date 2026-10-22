"""Run the actual reference-cohort and metric-statistics JavaScript."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'),'Node needed for reference analysis')
class ReferenceAnalysisTest(unittest.TestCase):
    def check(self,body):
        s=(ROOT/'processed/zweig_a/viewer_json.html').read_text()
        helpers=s[s.index('function peerMeta('):s.index('function analysisControls(')]
        helpers+=s[s.index('const PCT_MIN_GROUP='):s.index('function pctBadge(')]
        helpers+=s[s.index('function quart('):s.index('/* Tukey-Zaeune.')]
        helpers+=s[s.index('function metricPeerGroups('):s.index('function peerCoverage(')]
        helpers+=s[s.index('const FENCE='):s.index('const DBINS=')]
        helpers+=s[s.index('function fenceOutliers('):s.index('function fenceBadge(')]
        harness="""
const assert=require('node:assert/strict');
let BM_PEER='cluster',BM_OWN='',BM_ROLE='',BM_CLUSTER='a',BM_REF='',BM_EXCLUDED=new Set(),BM_ADDED=new Set();
let chosenDate='2025-12-31';const activeFilters=()=>({d:chosenDate});
const AP_DATA={metadata:{},stable_memberships:{},fitting_metrics:['trea']},AP_CLUSTERS=new Map([['a',{}],['b',{}]]);
const REPORTS=[],rows=[];
const leiParts=e=>({lei:e.split(':')[1].split('.')[0],scope:e.split('.')[1]});
const byKey=k=>REPORTS.find(r=>r.entityID+'|'+r.refPeriod===k),repKey=r=>r.entityID+'|'+r.refPeriod;
const META=new Map(),shortItype=()=> 'Large';
const BAR_KINDS=new Set(['eur']),barErlaubt=(p,r,m)=>!r.q?.bad;
const metricValue=(rep,m)=>rep.values[m.id]??null;
const outsideCorridor=(m,v)=>v!=null&&v!==0&&m.plausible&&(v<m.plausible[0]||v>m.plausible[1]);
const metric={id:'cet1',kind:'pct'},prof={cols:[metric],tpl:'61.00'};
for(let i=0;i<7;i++){
 const lei=String(i).repeat(20),entityID='rs:'+lei+'.CON',refPeriod=chosenDate;
 const rep={entityID,refPeriod,framework:'4.1',quality:{bad:i===0},values:{cet1:0,npl:i<4?i:null,trea:10}};REPORTS.push(rep);
 META.set(lei,{institution_type:'Large'});AP_DATA.metadata[lei]={ownership:'shareholder',role:'group_head',group_head:lei};
 AP_DATA.stable_memberships[lei+'|CON']=i<5?'a':'b';
 rows.push({key:repKey(rep),lei,date:refPeriod,scope:'CON',itype:'Large',q:{bad:i===0}});
}
BM_REF=REPORTS[0].entityID;
"""
        r=subprocess.run(['node','-e',harness+helpers+body],capture_output=True,text=True,timeout=5)
        self.assertEqual(r.returncode,0,r.stderr)

    def test_reference_group_never_pools_other_dates_scopes_frameworks(self):
        self.check("const valid=referencePopulation(rows).rows;assert.equal(valid.length,5);REPORTS[4].framework='4.2';assert.equal(referencePopulation(rows).rows.length,4);chosenDate='2026-03-31';assert.equal(referencePopulation(rows).rows.length,0);")

    def test_manual_membership_preserves_the_frozen_assignment(self):
        self.check("""
const before=JSON.stringify(AP_DATA.stable_memberships);
BM_EXCLUDED.add(REPORTS[4].entityID);assert.equal(referencePopulation(rows).rows.length,4);
BM_ADDED.add(REPORTS[5].entityID);assert.equal(referencePopulation(rows).rows.length,5);
assert.equal(JSON.stringify(AP_DATA.stable_memberships),before);
""")

    def test_known_group_is_not_counted_twice_in_a_custom_cohort(self):
        self.check("AP_DATA.metadata[rows[5].lei].group_head=rows[0].lei;BM_ADDED.add(REPORTS[5].entityID);const cohort=referencePopulation(rows).rows;assert.equal(cohort.length,5);assert(cohort.some(r=>r.key===rows[0].key));assert(!cohort.some(r=>r.key===rows[5].key));")

    def test_zero_and_ties_receive_midrank(self):
        self.check("const stats=analysisStats(referencePopulation(rows).rows,metric,prof);assert.equal(stats.n,5);assert.equal(stats.med,0);assert.equal(analysisRank(0,stats),50);")

    def test_missing_values_have_metric_specific_denominators(self):
        self.check("const cohort=referencePopulation(rows).rows;const stats=analysisStats(cohort,{id:'npl',kind:'ratio'},prof);assert.equal(stats.n,4);assert.equal(analysisRank(1,stats),null);")

    def test_unit_exclusions_precede_minimum_and_fitting_inputs_stay_unranked(self):
        self.check("const stats=analysisStats(referencePopulation(rows).rows,{id:'trea',kind:'eur'},prof);assert.equal(stats.n,4);assert(stats.suppressed);assert.equal(analysisRank(10,stats),null);")

    def test_reference_is_retained_as_known_family_representative(self):
        self.check("AP_DATA.metadata[rows[0].lei].role='subsidiary';AP_DATA.metadata[rows[1].lei].group_head=rows[0].lei;const cohort=referencePopulation(rows).rows;assert(cohort.some(r=>r.key===rows[0].key));assert(!cohort.some(r=>r.key===rows[1].key));")

    def test_reference_cannot_receive_a_rank_from_unusable_framework(self):
        self.check("REPORTS[0].framework='unknown';assert.equal(referencePopulation(rows).rows.length,0);")

    def test_reference_failing_the_profile_gate_is_not_ranked(self):
        self.check("prof.gate=[{id:'rem',plausible:[1,20]}];REPORTS[0].values.rem=1000;assert.equal(metricComparable(REPORTS[0],metric,prof),false);assert.equal(analysisStats(referencePopulation(rows).rows,metric,prof).n,4);")

    def test_coverage_and_statistics_use_identical_eligibility(self):
        self.check("""
metric.plausible=[0,30];REPORTS[0].values.cet1=100;
const cohort=referencePopulation(rows).rows.map(r=>({...r,cet1:metricValue(byKey(r.key),metric)}));
const count=[...metricPeerGroups(cohort,metric,prof).values()].flat().length;
assert.equal(count,4);assert.equal(count,analysisStats(cohort,metric,prof).n);
""")

    def test_custom_cohort_outlier_fences_include_added_banks(self):
        self.check("""
BM_EXCLUDED.add(REPORTS[4].entityID);BM_ADDED.add(REPORTS[5].entityID);
REPORTS.forEach((r,i)=>r.values.cet1=i===5?100:i);
const cohort=referencePopulation(rows).rows.map(r=>({...r,cet1:metricValue(byKey(r.key),metric)}));
assert.equal(cohort.length,5);
const marks=fenceOutliers(cohort,'cet1','cluster',()=> 'reference');
assert.equal(marks.size,1);assert.equal(marks.get(rows[5].key),'hoch');
""")


if __name__=='__main__':unittest.main()
