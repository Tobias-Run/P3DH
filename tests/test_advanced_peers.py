"""Safety and statistical properties of advanced peer formation."""
import csv
import itertools
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import advanced_peers as ap


def profile(key, risk=.2, size=1e9, ownership='cooperative', role='group_head', head=''):
    return {'key':key,'lei':key,'risk':{r:risk for r in ap.RISK_ROWS},
            'trea_eur':size,'ownership':ownership,'role':role,'group_head':head,
            'institution_type':'Large highest EEA'}


class StatisticalTest(unittest.TestCase):
    def test_complete_link_prevents_chaining(self):
        d={('a','b'):.1,('b','c'):.1,('a','c'):.4}
        groups=ap.complete_link(['a','b','c'],d,.2)
        self.assertEqual(groups,[('a','b'),('c',)])

    def test_complete_link_diameter_and_partition(self):
        rng=random.Random(12);keys=[str(i) for i in range(24)]
        values={k:rng.random() for k in keys}
        d={tuple(sorted((a,b))):abs(values[a]-values[b]) for a,b in itertools.combinations(keys,2)}
        groups=ap.complete_link(keys,d,.25)
        self.assertEqual(sorted(k for g in groups for k in g),sorted(keys))
        for group in groups:
            for pair in itertools.combinations(group,2):self.assertLessEqual(d[tuple(sorted(pair))],.25)

    def test_order_is_reproducible_with_ties(self):
        keys=['a','b','c','d'];d={pair:.1 for pair in itertools.combinations(keys,2)}
        self.assertEqual(ap.complete_link(keys,d),ap.complete_link(list(reversed(keys)),dict(reversed(list(d.items())))))

    def test_cutoff_boundary_and_isolates(self):
        self.assertEqual(ap.complete_link(['a','b'],{('a','b'):.25}),[('a','b')])
        self.assertEqual(ap.complete_link(['a','b'],{('a','b'):.25001}),[('a',),('b',)])
        self.assertEqual(ap.cluster_block({'a':profile('a')}),[])

    def test_size_normalization_is_currency_scale_invariant(self):
        profiles={str(i):profile(str(i),size=10**(i+3)) for i in range(10)}
        a,_=ap.normalized_sizes(profiles)
        b,_=ap.normalized_sizes({k:{**p,'trea_eur':p['trea_eur']*1e6} for k,p in profiles.items()})
        for key in a:self.assertAlmostEqual(a[key],b[key])

    def test_distance_respects_ownership_and_role(self):
        a=profile('a');b=profile('b');sizes={'a':.5,'b':.5}
        self.assertEqual(ap.distance(a,b,sizes),0)
        self.assertAlmostEqual(ap.distance(a,{**b,'ownership':'public'},sizes),.15)
        self.assertAlmostEqual(ap.distance(a,{**b,'role':'subsidiary'},sizes),.10)
        self.assertAlmostEqual(ap.distance(a,{**b,'ownership':'unknown'},sizes),.075)

    def test_size_caliper_cannot_be_compensated_by_identical_risk_and_ownership(self):
        a=profile('a',size=1e9);b=profile('b',size=1e9*ap.MAX_SIZE_RATIO+1)
        self.assertEqual(ap.distance(a,b,{'a':0,'b':1}),1.)
        groups=ap.cluster_block({'a':a,'b':b,'c':profile('c',size=1.01e9)})
        for group in groups:
            self.assertFalse({'a','b'} <= set(group['members']))

    def test_unknown_is_not_treated_as_shared_known_ownership(self):
        a=profile('a',ownership='unknown');b=profile('b',ownership='unknown')
        self.assertGreater(ap.distance(a,b,{'a':.5,'b':.5}),0)

    def test_known_family_dedup_prefers_group_head(self):
        p={'a':profile('a',role='subsidiary',head='z'),'z':profile('z',head='z'),
           'u':profile('u',head=''),'v':profile('v',head='')}
        selected,excluded=ap.representatives(p)
        self.assertEqual(selected,['u','v','z']);self.assertEqual(excluded,{'a':'z'})

    def test_diagnostics_have_defined_bounds(self):
        p={'a':profile('a',risk=0),'b':profile('b',risk=.01),
           'c':profile('c',risk=.99),'d':profile('d',risk=1)}
        groups=ap.cluster_block(p)
        self.assertEqual(len(groups),2)
        for c in groups:
            self.assertLessEqual(c['max_distance'],ap.THRESHOLD)
            self.assertTrue(0<=c['sensitivity']<=1)
            self.assertTrue(-1<=c['silhouette']<=1)
            self.assertEqual(len(c['members']),2)


class InputsTest(unittest.TestCase):
    def setUp(self):
        import duckdb
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'processed').mkdir();(self.root/'codebook').mkdir()
        self.con=duckdb.connect()
        self.con.execute('''CREATE TABLE p(entityID VARCHAR,lei VARCHAR,scope VARCHAR,
          refPeriod VARCHAR,framework_version VARCHAR,bank_name VARCHAR,institution_type VARCHAR,
          template_id VARCHAR,cell_row VARCHAR,cell_col VARCHAR,fact_value_raw VARCHAR,
          fact_value_eur DOUBLE,open_axis_dims VARCHAR)''')

    def tearDown(self):self.con.close();self.tmp.cleanup()

    def add(self,lei,date='2025-12-31',scope='CON',fw='4.1',skip=None,scale=1):
        cells=[('61.00','0040',1e9)]+[('60.00.A',row,0 if name=='cva' else 1e8) for name,row in ap.RISK_ROWS.items()]
        for tid,row,value in cells:
            if row==skip and tid=='60.00.A':continue
            self.con.execute('INSERT INTO p VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
              ['rs:'+lei+'.'+scope,lei,scope,date,fw,lei,'Large highest EEA',tid,row,'0010',str(value*scale),value*scale,None])

    def test_missing_risk_is_not_imputed_as_zero(self):
        self.add('missing',skip='0120');self.add('zero')
        p,_,missing=ap.load_profiles(self.con,self.root)
        self.assertNotIn('rs:missing.CON|2025-12-31',p)
        self.assertEqual(missing['rs:missing.CON|2025-12-31'],'missing_or_invalid_risk')
        self.assertEqual(p['rs:zero.CON|2025-12-31']['risk']['cva'],0)

    def test_conflicting_coordinates_do_not_fit(self):
        self.add('a')
        self.con.execute("INSERT INTO p SELECT entityID,lei,scope,refPeriod,framework_version,bank_name,institution_type,template_id,cell_row,cell_col,'123',123,open_axis_dims FROM p WHERE template_id='61.00'")
        p,_,missing=ap.load_profiles(self.con,self.root)
        self.assertFalse(p);self.assertIn('missing_or_ambiguous_size',missing.values())

    def test_multiple_dimensions_do_not_fit(self):
        self.add('a')
        self.con.execute("INSERT INTO p SELECT entityID,lei,scope,refPeriod,framework_version,bank_name,institution_type,template_id,cell_row,cell_col,fact_value_raw,fact_value_eur,'dimension' FROM p WHERE cell_row='0320'")
        p,_,_=ap.load_profiles(self.con,self.root);self.assertFalse(p)

    def test_hard_date_scope_framework_boundaries(self):
        for lei in ['a','b']:self.add(lei)
        for lei in ['c','d']:self.add(lei,date='2026-03-31')
        for lei in ['e','f']:self.add(lei,scope='IND')
        for lei in ['g','h']:self.add(lei,fw='4.2')
        data=ap.build(self.con,self.root)
        self.assertEqual(len(data['clusters']),4)
        for cluster in data['clusters']:self.assertEqual(len(cluster['members']),2)
        self.assertEqual(ap.encoded(data),ap.encoded(ap.build(self.con,self.root)))

    def test_scale_findings_block_only_fitting_templates(self):
        self.add('a');self.add('b')
        path=self.root/'processed/scale_flags.csv'
        path.write_text('entityID,refPeriod,template_id,urteil\nrs:a.CON,2025-12-31,60.00.A,verdacht\nrs:b.CON,2025-12-31,23.00,skaliert\n')
        p,_,missing=ap.load_profiles(self.con,self.root)
        self.assertIn('rs:b.CON|2025-12-31',p)
        self.assertEqual(missing['rs:a.CON|2025-12-31'],'scale_finding')

    def test_no_name_based_ownership_guessing(self):
        self.add('Genossenschaft Bank eG')
        _,m,_=ap.load_profiles(self.con,self.root)
        self.assertEqual(m['Genossenschaft Bank eG']['ownership'],'unknown')

    def test_classification_evidence_is_mandatory(self):
        (self.root/'codebook/bank_classification.csv').write_text('lei,ownership,source_url,evidence_quote,reviewed_at,source_sha256\n549300TRUWO2CD2G5692,shareholder,http://example.com,claim,2026-10-02,'+'0'*64+'\n')
        with self.assertRaises(ValueError):ap.register(self.root)

    def test_missing_or_conflicting_framework_cannot_form_a_cohort(self):
        self.add('missing',fw=None)
        self.add('conflict',fw='4.1');self.add('conflict',fw='4.2')
        p,_,missing=ap.load_profiles(self.con,self.root)
        self.assertFalse(p)
        self.assertEqual(set(missing.values()),{'missing_or_ambiguous_framework'})
        self.assertEqual(len(missing),2)

    def test_ownership_does_not_propagate_from_an_unreviewed_parent_chain(self):
        parent='549300TRUWO2CD2G5692';child='529900SS7ZWCX82U3W60'
        (self.root/'processed/lei_relations.csv').write_text(
            'lei,ultimate_parent_lei,ultimate_parent_reason\n'+child+','+parent+',\n')
        (self.root/'codebook/bank_classification.csv').write_text(
            'lei,ownership,source_url,evidence_quote,reviewed_at,source_sha256\n'+parent+
            ',shareholder,https://example.com,reviewed owners,2026-10-02,'+'0'*64+'\n')
        self.assertEqual(ap.traits(self.root,[child])[child]['ownership'],'unknown')

    def test_reviewed_control_chain_requires_controller_and_second_source(self):
        (self.root/'codebook/bank_classification.csv').write_text(
            'lei,ownership,source_url,evidence_quote,reviewed_at,source_sha256,ownership_basis\n'
            '549300TRUWO2CD2G5692,shareholder,https://example.com,reviewed owners,2026-10-02,'+
            '0'*64+',reviewed_control_chain\n')
        with self.assertRaisesRegex(ValueError,'control chain'):ap.register(self.root)

    def test_private_equity_cooperative_holdings_are_not_cooperative_banks(self):
        registry=ap.register(ROOT)
        for lei in ['549300UARE5MHTBUPJ19','724500AG21Z9GIJE4735']:
            self.assertNotEqual(registry.get(lei,{}).get('ownership'),'cooperative')

    def test_document_control_chain_requires_separate_control_evidence(self):
        (self.root/'codebook/bank_classification.csv').write_text(
            'lei,ownership,source_url,evidence_quote,reviewed_at,source_sha256,ownership_basis\n'
            '549300TRUWO2CD2G5692,shareholder,https://example.com,reviewed owners,2026-10-02,'+
            '0'*64+',reviewed_document_chain\n')
        with self.assertRaisesRegex(ValueError,'control chain'):ap.register(self.root)

    def test_reviewed_document_parent_overrides_stale_group_snapshot(self):
        child='3TK20IVIUJ8J3ZU0QE75';parent='549300NYKK9MWM7GGW15'
        (self.root/'codebook/bank_classification.csv').write_text(
            'lei,ownership,source_url,evidence_quote,reviewed_at,source_sha256,ownership_basis,controller_lei,control_source_url,control_source_sha256\n'+
            child+',shareholder,https://example.com/owners,reviewed owners,2026-10-02,'+
            '0'*64+',reviewed_document_chain,'+parent+',https://example.com/annual,'+'1'*64+'\n')
        m=ap.traits(self.root,[child])[child]
        self.assertEqual((m['group_head'],m['role'],m['group_source']),
                         (parent,'subsidiary','reviewed_document'))


class OwnershipResearchSnapshotTest(unittest.TestCase):
    def setUp(self):
        doc=ROOT/'docs/advanced_peers'
        self.selection=json.loads((doc/'top30_selection.json').read_text())
        self.evidence=json.loads((doc/'top30_ownership_evidence.json').read_text())
        self.registry=ap.register(ROOT)

    def test_only_selected_thirty_are_added_to_frozen_unknown_population(self):
        baseline=set(self.selection['baseline_unknown_leis'])
        selected={r['lei'] for r in self.selection['selected']}
        self.assertEqual(len(selected),30)
        self.assertEqual(baseline.intersection(self.registry),selected)
        self.assertEqual(len(baseline-set(self.registry)),291)
        self.assertEqual(baseline,set(self.selection['unrankable_leis']) |
                         {r['lei'] for r in self.selection['ranking_candidates']})

    def test_accounting_assets_order_and_currency_overlay(self):
        values=self.selection['selected']
        self.assertEqual([r['rank'] for r in values],list(range(1,31)))
        self.assertEqual([r['assets_eur'] for r in values],
                         sorted((r['assets_eur'] for r in values),reverse=True))
        self.assertEqual(values[0]['lei'],'3TK20IVIUJ8J3ZU0QE75')
        millennium=next(r for r in self.selection['source_overlays']
                        if r['lei']=='259400OFDZ9KPZEO8K78')
        self.assertEqual(millennium['currency'],'PLN')
        self.assertAlmostEqual(millennium['assets_eur'],
                               millennium['reported_assets']*millennium['eur_per_currency'])
        self.assertNotIn(millennium['lei'],{r['lei'] for r in values})

    def test_selected_evidence_agrees_with_live_registry_and_control_sources(self):
        for selected in self.selection['selected']:
            lei=selected['lei'];record=self.registry[lei];audit=self.evidence[lei]
            with self.subTest(lei=lei):
                proof=audit['ownership_evidence']
                self.assertEqual(record['ownership'],audit['ownership'])
                self.assertEqual(record['source_url'],proof['url'])
                self.assertEqual(record['source_sha256'],proof['sha256'])
                self.assertEqual(record['evidence_quote'],proof['quote'])
                self.assertTrue(audit['interpretation'])
                if 'control_evidence' in audit:
                    control=audit['control_evidence']
                    self.assertEqual(record['controller_lei'],audit['controller_lei'])
                    self.assertEqual(record['control_source_sha256'],control['sha256'])
                    self.assertNotEqual(proof['url'],control['url'])
                    self.assertEqual(record['ownership'],
                                     self.registry[record['controller_lei']]['ownership'])


if __name__=='__main__':unittest.main()
