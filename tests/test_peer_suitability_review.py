import importlib.util
from pathlib import Path
import unittest
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('suitability',ROOT/'scripts/review_peer_suitability.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class SuitabilityReviewTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'),'Node needed for business-model display guards')
    def test_frontend_never_inherits_models_to_other_scopes_or_unknown_banks(self):
        viewer=(ROOT/'processed/zweig_a/viewer_json.html').read_text()
        functions=viewer[viewer.index('const MODEL_LABEL='):viewer.index('function bindAnalysisControls(')]
        script="const assert=require('node:assert/strict');\n"+(ROOT/'processed/zweig_a/business_model_pilot.js').read_text()+"\n"+"""
const repKey=r=>r.key;
const AP_DATA={reports:{ref:{features:{trea_eur:1,risk:{credit:.5,counterparty:.1,cva:.1,market:.1,operational:.2}}},peer:{features:{trea_eur:12,risk:{credit:.5,counterparty:.1,cva:.1,market:.1,operational:.2}}}},max_size_ratio:10};
"""+functions+"""
assert.equal(businessModel({lei:'unknown',scope:'CON'}),null);
assert.equal(businessModel({lei:'529900SSGT49ZZSWYE62',scope:'IND'}),null);
assert.equal(businessModel({lei:'529900SSGT49ZZSWYE62',scope:'CON'}).model,'vehicle_finance');
assert.equal(businessModel({lei:'MMYX0N4ZEZ13Z4XCG897',scope:'IND'}).status,'group_description');
const d=peerSuitability({key:'ref'},{key:'peer'});assert.equal(d.ratio,12);assert.equal(d.risk,0);assert(d.outside);
assert.equal(peerSuitability({key:'missing'},{key:'peer'}).ratio,null);
"""
        result=subprocess.run(['node','-e',script],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_pilot_sources_have_evidence_without_unknown_inheritance(self):
        p=module.pilot()
        for lei,m in p['models'].items():
            self.assertEqual(len(lei),20)
            self.assertTrue(m['source_url'].startswith('https://'))
            self.assertRegex(m['source_sha256'],r'^[a-f0-9]{64}$')
            self.assertTrue(m['evidence_terms'])
            self.assertTrue(m['scopes'])
        self.assertEqual(p['models']['MMYX0N4ZEZ13Z4XCG897']['status'],'group_description')

    def test_real_frozen_pair_requires_business_review_despite_low_distance(self):
        result=module.review()
        self.assertGreater(result['evaluated_roster_pairs'],0)
        self.assertTrue(result['mixed_reviewed_models'])
        case=next(f for f in result['mixed_reviewed_models'] if 'vehicle_finance' in f['models'])
        self.assertLessEqual(case['legacy_distance'],.25+1e-6)
        self.assertGreater(case['legacy_parts']['risk'],0)
        self.assertGreaterEqual(case['risk_rescaled_distance'],case['legacy_distance'])


if __name__=='__main__':unittest.main()
