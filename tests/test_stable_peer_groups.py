"""Stable membership follows bank identity, never the historical fitting result."""
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'scripts'))
import stable_peer_groups as stable
import advanced_peers as ap


def observation(lei,date='2026-03-31',scope='CON',fw='4.2',scale=1):
    return dict(key=f'rs:{lei}.{scope}|{date}',lei=lei,date=date,scope=scope,framework=fw,
                institution_type='highest EEA',ownership='shareholder',role='group_head',
                group_head=lei,group_source='test',trea_eur=1e9*scale,
                risk={r:.1 for r in ap.RISK_ROWS})


class StablePeersTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);(self.root/'codebook').mkdir()
    def tearDown(self):self.tmp.cleanup()
    def snapshot(self,observations):
        metadata={p['lei']:{k:p[k] for k in ['ownership','role','group_head','group_source']} for p in observations}
        return stable.snapshot({p['key']:p for p in observations},metadata,self.root)

    def test_history_and_framework_change_do_not_change_membership(self):
        latest=[observation('A'*20),observation('B'*20)]
        older=[observation('A'*20,'2025-12-31',fw='4.1',scale=100),observation('B'*20,'2025-12-31',fw='4.1')]
        a=self.snapshot(latest);b=self.snapshot(latest+older)
        self.assertEqual(a['clusters'],b['clusters'])
        self.assertEqual(a['memberships'],b['memberships'])
        self.assertEqual(b['clusters'][0]['date'],'2026-03-31')
        self.assertEqual(b['clusters'][0]['roster'],['A'*20,'B'*20])

    def test_no_older_backfill_for_latest_isolated_bank(self):
        latest=[observation('A'*20,scale=100),observation('B'*20)]
        older=[observation('A'*20,'2025-12-31'),observation('B'*20,'2025-12-31')]
        self.assertFalse(self.snapshot(latest+older)['memberships'])

    def test_scope_and_anchor_framework_are_separate(self):
        obs=[observation('A'*20),observation('B'*20),observation('C'*20,scope='IND'),
             observation('D'*20,scope='IND'),observation('E'*20,fw='4.1'),observation('F'*20,fw='4.1')]
        data=self.snapshot(obs)
        self.assertEqual(len(data['clusters']),3)
        for c in data['clusters']:
            self.assertEqual(len(c['members']),2)
            self.assertEqual(len(c['roster']),2)
        self.assertEqual(ap.encoded(data),ap.encoded(self.snapshot(list(reversed(obs)))))

    def test_explicit_assumptions_never_replace_reviewed_type_or_group_identity(self):
        path=self.root/'codebook/bank_classification_assumptions.csv'
        with path.open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['lei','ownership','classification_status','confidence','basis','input_sha256']);w.writeheader()
            for lei in ['A'*20,'B'*20]:w.writerow(dict(lei=lei,ownership='public',classification_status='assumption',confidence='mittel',basis='user provided assignment',input_sha256='0'*64))
        m={lei:dict(ownership=owner,role='subsidiary',group_head='P'*20,group_source='test') for lei,owner in [('A'*20,'cooperative'),('B'*20,'unknown')]}
        result=stable.ownership_overlay(self.root,m)
        self.assertEqual(result['A'*20]['ownership'],'cooperative')
        self.assertEqual(result['B'*20]['ownership'],'public')
        self.assertEqual(result['B'*20]['classification_status'],'assumption')
        self.assertEqual(result['B'*20]['group_head'],'P'*20)
        self.assertEqual(m['B'*20]['ownership'],'unknown')

    def test_loader_keeps_roster_when_current_data_loses_a_member(self):
        data=self.snapshot([observation('A'*20),observation('B'*20)])
        path=self.root/'codebook/stable_peer_groups.json';path.write_bytes(ap.encoded(data))
        loaded=stable.load(self.root,{'A'*20:{'ownership':'shareholder'}})
        self.assertEqual(loaded['stable_memberships'],data['memberships'])
        self.assertEqual(loaded['stable_clusters'][0]['roster'],['A'*20,'B'*20])
        self.assertEqual(path.read_bytes(),ap.encoded(data))

    def test_loader_rejects_membership_roster_disagreement(self):
        data=self.snapshot([observation('A'*20),observation('B'*20)])
        data['memberships']['A'*20+'|CON']='wrong'
        (self.root/'codebook/stable_peer_groups.json').write_bytes(ap.encoded(data))
        with self.assertRaisesRegex(ValueError,'disagrees'):stable.load(self.root,{})

if __name__=='__main__':unittest.main()
