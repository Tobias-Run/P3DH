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

    def test_additions_are_selected_thirty_or_explicitly_reviewed_followup_cases(self):
        baseline=set(self.selection['baseline_unknown_leis'])
        selected={r['lei'] for r in self.selection['selected']}
        self.assertEqual(len(selected),30)
        followup={case['lei'] for path in (ROOT/'docs/advanced_peers/ownership_batches').glob('batch_*.json')
                  for case in json.loads(path.read_text())['accepted']}
        controllers={lei for path in (ROOT/'docs/advanced_peers/ownership_batches').glob('reviewed_controllers_*.json')
                     for lei in json.loads(path.read_text())}
        self.assertEqual(baseline.intersection(self.registry),(selected|followup|controllers)&baseline)
        self.assertEqual(len(baseline-set(self.registry)),len(baseline-selected-followup-controllers))
        self.assertEqual(baseline,set(self.selection['unrankable_leis']) |
                         {r['lei'] for r in self.selection['ranking_candidates']})

    def test_followup_evidence_matches_explicit_registry_basis(self):
        for path in (ROOT/'docs/advanced_peers/ownership_batches').glob('batch_*.json'):
            for case in json.loads(path.read_text())['accepted']:
                record=self.registry[case['lei']]
                self.assertEqual(record['ownership_basis'],case['ownership_basis'])
                self.assertEqual(record['ownership'],case['ownership'])
                self.assertEqual(record['source_sha256'],case['ownership_evidence']['sha256'])
                if case['ownership_basis']=='direct_ownership':
                    self.assertEqual(record['evidence_quote'],case['ownership_evidence']['quote'])
                    self.assertEqual(record['source_url'],case['ownership_evidence']['url'])
                    self.assertFalse(record['controller_lei'])
                elif case['ownership_basis']=='registered_bank_form':
                    self.assertEqual(record['source_hash_kind'],'canonical_gleif_record')
                    self.assertEqual(case['legal_form_evidence']['elf_code'],'R71C')
                    self.assertEqual(case['legal_form_evidence']['jurisdiction'],'NO')
                    self.assertEqual(record['ownership'],'savings')
                    self.assertEqual(record['source_sha256'],case['bank_identity']['gleif_record_sha256'])
                else:
                    self.assertEqual(record['controller_lei'],case['controller_lei'])
                    self.assertEqual(record['control_source_sha256'],case['control_evidence']['sha256'])
                    if case['ownership_basis']=='reviewed_control_chain':
                        proof=case['control_evidence']
                        self.assertEqual(proof['relationship']['startNode']['id'],case['lei'])
                        self.assertEqual(proof['relationship']['endNode']['id'],case['controller_lei'])
                        self.assertEqual(proof['relationship']['status'],'ACTIVE')
                        self.assertEqual(proof['registration']['status'],'PUBLISHED')
                        self.assertEqual(proof['registration']['corroborationLevel'],'FULLY_CORROBORATED')
                    else:
                        self.assertEqual(record['ownership_basis'],'reviewed_document_chain')
                        name=case.get('matched_legal_name',case['name'])
                        self.assertIn(name.casefold(),' '.join(case['control_evidence']['quote'].split()).casefold())
                    self.assertEqual(record['ownership'],self.registry[case['controller_lei']]['ownership'])

    def test_seventy_case_campaign_covers_fixed_selection_without_duplicate_acceptance(self):
        directory=ROOT/'docs/advanced_peers/ownership_batches'
        for filename in ['campaign_next70.json','campaign_next70b.json','campaign_next70c.json','campaign_next70d.json']:
            with self.subTest(campaign=filename):
                self.check_seventy_case_campaign(directory,filename)

    def check_seventy_case_campaign(self,directory,filename):
        campaign=json.loads((directory/filename).read_text())
        selected=[];accepted=[];deferred=[];attempts=[]
        for item in campaign['batches']:
            batch=json.loads((directory/('batch_'+item['batch']+'.json')).read_text())
            self.assertEqual(batch['batch_size'],5)
            selected.extend(item['banks'])
            accepted.extend(case['lei'] for case in batch['accepted'])
            deferred.extend(case['lei'] for case in batch['deferred'])
            self.assertTrue(all(case['next_action'] for case in batch['deferred']))
            self.assertEqual(set(item['banks']),{case['lei'] for case in batch['accepted']+batch['deferred']})
            for lei in item['banks']:
                self.assertLessEqual(sum(row['lei']==lei for row in batch['page_attempts']),4)
            attempts.extend(batch['page_attempts'])
        self.assertEqual(len(selected),70)
        self.assertEqual(len(set(selected)),70)
        self.assertEqual(len(accepted),campaign['accepted'])
        self.assertEqual(len(deferred),campaign['deferred'])
        self.assertFalse(set(accepted)&set(deferred))
        self.assertEqual(len(attempts),campaign['page_attempts'])
        self.assertEqual(sum(row['new_network_fetch'] for row in attempts),campaign['new_network_fetches'])
        self.assertTrue(set(accepted)<=set(self.registry))
        # A historical deferred case can receive a sourced decision in a later
        # explicitly revisited campaign; the earlier snapshot stays unchanged.
        later_acceptance={case['lei'] for path in directory.glob('batch_*.json')
                          for case in json.loads(path.read_text())['accepted']
                          if path.stem>'batch_'+campaign['batches'][-1]['batch']}
        self.assertTrue((set(deferred)&set(self.registry))<=later_acceptance)

    def test_fourth_campaign_distinguishes_first_reviews_and_targeted_followups(self):
        directory=ROOT/'docs/advanced_peers/ownership_batches'
        campaign=json.loads((directory/'campaign_next70d.json').read_text())
        with (directory.parent/'next70d_selection.csv').open() as source:
            selected=list(csv.DictReader(source))
        fresh=[row for row in selected if row['review_mode']=='first_review']
        repeat=[row for row in selected if row['review_mode']=='targeted_follow_up']
        self.assertEqual((len(fresh),len(repeat)),(19,51))
        self.assertEqual((campaign['first_reviews'],campaign['targeted_follow_ups']),(19,51))
        self.assertTrue(all(not row['previous_batch'] for row in fresh))
        for rows in [fresh,repeat]:
            self.assertEqual([int(row['rank']) for row in rows],sorted(int(row['rank']) for row in rows))
            self.assertEqual([float(row['trea_eur']) for row in rows],sorted((float(row['trea_eur']) for row in rows),reverse=True))
        for row in repeat:
            previous=json.loads((directory/('batch_'+row['previous_batch']+'.json')).read_text())
            self.assertIn(row['lei'],{case['lei'] for case in previous['deferred']})
            self.assertNotIn(row['lei'],{case['lei'] for case in previous['accepted']})

    def test_current_owner_sources_do_not_turn_minority_anchors_into_majority_control(self):
        directory=ROOT/'docs/advanced_peers/ownership_batches'
        controllers=json.loads((directory/'reviewed_controllers_next70d.json').read_text())
        erste=controllers['PQOH26KWDF7CG10L6792']
        self.assertEqual(erste['ownership'],'shareholder')
        self.assertIn('30.06.2026',erste['ownership_evidence']['quote'])
        self.assertIn('Foundation direct 6.08%',erste['ownership_evidence']['quote'])
        pzu=controllers['QLPCKOOKVX32FUELX240']
        self.assertEqual(pzu['ownership'],'mixed')
        self.assertIn('9.07.2026',pzu['ownership_evidence']['quote'])
        self.assertIn('State Treasury 34.2%',pzu['ownership_evidence']['quote'])
        self.assertIn('65.8%',pzu['ownership_evidence']['quote'])
        cases=[case for item in json.loads((directory/'campaign_next70d.json').read_text())['batches']
               for case in json.loads((directory/('batch_'+item['batch']+'.json')).read_text())['accepted']]
        bcc=next(case for case in cases if case['lei']=='95980020140005881190')
        self.assertEqual(bcc['ownership'],'cooperative')
        self.assertEqual(bcc['ownership_evidence']['quote_kind'],'visual_diagram_transcription')
        self.assertEqual(bcc['ownership_evidence']['pdf_page'],28)
        self.assertAlmostEqual(bcc['ownership_evidence']['cooperative_share_percent'],97.41)
        ibercaja=next(case for case in cases if case['lei']=='549300OLBL49CW8CT155')
        self.assertEqual(ibercaja['ownership'],'foundation')
        self.assertIn('únicos propietarios del banco son cuatro fundaciones',ibercaja['ownership_evidence']['quote'])

    def test_ppf_source_is_not_reused_for_a_different_registered_parent(self):
        directory=ROOT/'docs/advanced_peers/ownership_batches'
        batch=json.loads((directory/'batch_057.json').read_text())
        case=next(case for case in batch['deferred'] if case['lei']=='31570014BNQ1Q99CNQ35')
        proof=case['unresolved_control_evidence']
        self.assertEqual(proof['registered_ultimate_parent_lei'],'984500CE58365CB10V25')
        self.assertEqual(proof['registered_ultimate_parent_name'],'AMALAR HOLDING s.r.o.')
        self.assertIn('PPF Group N.V.',proof['different_entity_source']['quote'])
        self.assertTrue(proof['different_entity_source']['does_not_identify_amalar_owners'])
        self.assertNotIn(case['lei'],self.registry)

    def test_targeted_batch_respects_budget_and_records_unresolved_proof(self):
        batch=json.loads((ROOT/'docs/advanced_peers/ownership_batches/batch_002.json').read_text())
        attempts=batch['page_attempts']
        counts={lei:sum(row['lei']==lei for row in attempts)
                for lei in {row['lei'] for row in attempts}}
        self.assertEqual(len(counts),batch['batch_size'])
        self.assertLessEqual(max(counts.values()),batch['limits']['page_attempts_per_bank'])
        self.assertEqual(batch['new_network_fetches'],sum(row['new_network_fetch'] for row in attempts))
        self.assertEqual(len(batch['accepted'])+len(batch['deferred']),batch['batch_size'])
        self.assertTrue(all(case['next_action'] for case in batch['deferred']))
        cgd=next(case for case in batch['accepted'] if case['lei']=='TO822O0VT80V06K0FH57')
        self.assertIn('fully owned by the State',cgd['ownership_evidence']['quote'])
        eurobank=next(case for case in batch['accepted'] if case['lei']=='213800KGF4EFNUQKAT69')
        self.assertIn('04.09.2026',eurobank['ownership_evidence']['quote'])

    def test_wrong_bank_website_and_retired_holding_remain_unclassified(self):
        directory=ROOT/'docs/advanced_peers/ownership_batches'
        bulgarian='549300UY81ESCZJ0GR95'
        case=next(c for c in json.loads((directory/'batch_023.json').read_text())['deferred']
                  if c['lei']==bulgarian)
        self.assertEqual(case['identity_evidence']['record']['attributes']['entity']['jurisdiction'],'BG')
        ledger=next(r for r in csv.DictReader((ROOT/'docs/advanced_peers/ownership_research.csv').open())
                    if r['lei']==bulgarian)
        self.assertFalse(ledger['candidate_websites'])
        self.assertNotIn(bulgarian,self.registry)
        holding='9598002AYDQER7DXLR16'
        case=next(c for c in json.loads((directory/'batch_028.json').read_text())['deferred']
                  if c['lei']==holding)
        self.assertEqual(case['identity_evidence']['record']['attributes']['entity']['status'],'INACTIVE')
        self.assertIn('24 September 2025',case['merger_evidence']['quote'])
        self.assertNotIn(holding,self.registry)

    def test_cooperative_majority_uses_current_shareholder_column_after_merger(self):
        batch=json.loads((ROOT/'docs/advanced_peers/ownership_batches/batch_027.json').read_text())
        case=next(c for c in batch['accepted'] if c['lei']=='549300LYFYVPUCG6SY25')
        proof=case['ownership_evidence']
        self.assertIn('Entity 2025 2024',proof['quote'])
        self.assertIn('Grucajrural Inversiones, S.L. - 87,948',proof['quote'])
        self.assertEqual(proof['majority_calculation']['as_of'],'2025-12-31')
        self.assertAlmostEqual(proof['majority_calculation']['share_percent'],51.825)
        self.assertEqual(case['ownership'],'cooperative')

    def test_control_review_distinguishes_foundation_votes_from_names_and_coop_minority(self):
        directory=ROOT/'docs/advanced_peers/ownership_batches'
        frick=next(c for c in json.loads((directory/'batch_038.json').read_text())['accepted']
                   if c['lei']=='529900RQOBT3ZJMDRK43')
        self.assertEqual(frick['ownership'],'foundation')
        self.assertIn('With voting rights: Kuno Frick Family Foundation',frick['ownership_evidence']['quote'])
        self.assertIn('Without voting rights: PC capital',frick['ownership_evidence']['quote'])
        coop=next(c for c in json.loads((directory/'batch_034.json').read_text())['deferred']
                  if c['lei']=='549300EHNXQVOI120S55')
        self.assertEqual(coop['unresolved_control_evidence']['cooperative_stakes_percent'],41)
        self.assertNotIn(coop['lei'],self.registry)
        signet=next(c for c in json.loads((directory/'batch_044.json').read_text())['accepted']
                    if c['lei']=='2534005A84927EKSR789')
        self.assertEqual(signet['ownership'],'shareholder')
        self.assertIn('Investment company owned by the family',signet['ownership_evidence']['quote'])

    def test_french_bank_ownership_requires_both_current_bank_and_owner_reports(self):
        batch=json.loads((ROOT/'docs/advanced_peers/ownership_batches/batch_031.json').read_text())
        case=next(c for c in batch['accepted'] if c['lei']=='9695002JOWSRCLLLNY11')
        record=self.registry[case['lei']]
        self.assertEqual(record['supporting_source_url'],case['supporting_ownership_evidence']['url'])
        self.assertIn('France) est détenu à 100%',case['supporting_ownership_evidence']['quote'])
        self.assertIn('2025 Edmond de Rothschild Holding S.A.',case['ownership_evidence']['quote'])
        self.assertIn('famille Rothschild',case['ownership_evidence']['quote'])

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
