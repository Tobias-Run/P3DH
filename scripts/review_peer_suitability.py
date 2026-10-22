"""Audit frozen proposals against the small, explicitly sourced model pilot.

Diagnostic only: never rewrites ownership, frozen membership or fit weights.
"""
import itertools
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def pilot(root=ROOT):
    text=(root/'processed/zweig_a/business_model_pilot.js').read_text()
    return json.loads(text.split('globalThis.BUSINESS_MODEL_PILOT=',1)[1].strip().removesuffix(';'))


def review(root=ROOT):
    frozen=json.loads((root/'codebook/stable_peer_groups.json').read_text())
    models=pilot(root);profiles=frozen['anchor_profiles'];findings=[];pairs=0
    weights=frozen['weights']
    for cluster in frozen['clusters']:
        lo,hi=cluster['size_log10_bounds']
        def norm(p):return .5 if hi==lo else min(1.,max(0.,(math.log10(p['trea_eur'])-lo)/(hi-lo)))
        for ka,kb in itertools.combinations(cluster['members'],2):
            pairs+=1;a,b=profiles[ka],profiles[kb]
            ma=models['models'].get(a['lei']);mb=models['models'].get(b['lei'])
            if not all(m and m['status']=='reviewed' and cluster['scope'] in m['scopes'] for m in [ma,mb]):continue
            if ma['model']==mb['model']:continue
            category=lambda x,y:.5 if 'unknown' in (x,y) else float(x!=y)
            risk=sum(abs(a['risk'][r]-b['risk'][r]) for r in a['risk'])/len(a['risk'])
            parts={'size':weights['size']*abs(norm(a)-norm(b)),
                   'risk':weights['risk']*risk,
                   'ownership':weights['ownership']*category(a['ownership'],b['ownership']),
                   'role':weights['role']*category(a['role'],b['role'])}
            # A scale sensitivity test, not a proposed production distance:
            # average five-dimensional L1 versus capped half-L1.
            alternate=parts.copy();alternate['risk']=weights['risk']*min(1.,risk*len(a['risk'])/2)
            findings.append({'cluster':cluster['id'],'date':cluster['date'],'reports':[ka,kb],
                'models':[ma['model'],mb['model']],'legacy_parts':parts,'legacy_distance':sum(parts.values()),
                'risk_rescaled_distance':sum(alternate.values()),
                'still_below_cutoff_after_risk_rescale':sum(alternate.values())<=frozen['threshold'],
                'source_urls':[ma['source_url'],mb['source_url']]})
    return {'pilot_version':models['version'],'frozen_policy':frozen['policy'],
        'evaluated_roster_pairs':pairs,'reviewed_model_entities':sum(m['status']=='reviewed' for m in models['models'].values()),
        'group_descriptions_without_entity_validation':sum(m['status']!='reviewed' for m in models['models'].values()),
        'mixed_reviewed_models':findings,
        'decision':'Keep frozen rosters versioned. Treat them as proposals, show model provenance and size/risk differences, and allow explicit custom membership. A blind risk-weight change does not establish economic comparability.'}


if __name__=='__main__':print(json.dumps(review(),ensure_ascii=False,indent=2))
