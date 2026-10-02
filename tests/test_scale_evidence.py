"""#122: disprove population-only judgments, retain mixed defects safely."""
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import scale_evidence as s


def fact(index, value=100, date='2025-06-30', dp=None, col='0010', label='Amount'):
    return dict(zip(s.FIELDS, ['rs:E.CON', date, '23.00', str(index).zfill(4), col,
                              '', dp or f'dp{index}', float(value), 'original.zip', str(value),
                              'EUR', 1., 'monetary', 'Exposure', label, '4.1']))


class DirectEvidenceTest(unittest.TestCase):
    def test_cell_composition_changes_do_not_create_a_scale_defect(self):
        a = [fact(i, 100) for i in range(12)]
        b = [fact(i, 110, '2025-12-31') for i in range(12)]
        b += [fact(i, 1e9, '2025-12-31') for i in range(12, 50)]
        key = ('rs:E.CON', '2025-06-30', '23.00')
        other = ('rs:E.CON', '2025-12-31', '23.00')
        self.assertIsNone(s.evaluate(key, {key: a, other: b}, {key: -5, other: 0}))

    def test_dp_and_dimensions_are_part_of_identity(self):
        a = [fact(1)]
        self.assertEqual(s.direct_compare(a, [fact(1, 1e8, dp='different')]), [])
        b = fact(1, 1e8); b['open_axis_dims'] = 'country=FR'
        self.assertEqual(s.direct_compare(a, [b]), [])

    def test_duplicates_and_sign_changes_abstain(self):
        self.assertEqual(s.direct_compare([fact(1), fact(1)], [fact(1, 1e8)]), [])
        self.assertEqual(s.direct_compare([fact(1, -10)], [fact(1, 1e7)]), [])
        self.assertAlmostEqual(s.direct_compare([fact(1, -10)], [fact(1, -1e7)])[0][1], 6)

    def test_risk_weights_are_not_currency_amounts_but_rwa_is(self):
        self.assertFalse(s.is_amount(fact(1, .5, label='c Risk weight')))
        self.assertTrue(s.is_amount(fact(1, 1e9, label='Risk weighted exposure amount')))

    def test_mixed_defect_survives_a_normal_median(self):
        a = [fact(i) for i in range(25)]
        b = [fact(i, 1e8 if i < 5 else 100, '2025-12-31') for i in range(25)]
        k = ('rs:E.CON', '2025-06-30', '23.00'); ref = ('rs:E.CON', '2025-12-31', '23.00')
        result = s.evaluate(k, {k:a, ref:b}, {k:-1, ref:0})
        self.assertEqual(result['umfang'], 'teilbereich')
        self.assertEqual(len(result['betroffene_zellen']), 5)
        self.assertEqual(result['urteil'], 'verdacht')
        self.assertEqual(result['faktor_geschaetzt'], '')

    def test_an_oversized_reference_cannot_confirm_the_small_side(self):
        k = ('rs:E.CON', '2025-06-30', '23.00'); ref = ('rs:E.CON', '2025-12-31', '23.00')
        result = s.evaluate(k, {k:[fact(i) for i in range(12)],
            ref:[fact(i, 1e8, '2025-12-31') for i in range(12)]}, {k:0, ref:6})
        self.assertEqual(result['urteil'], 'verdacht')
        self.assertEqual(result['richtung'], 'unklar')

    def test_missing_reference_is_not_clean(self):
        key = ('rs:E.CON','2025-06-30','23.00')
        self.assertEqual(s.evaluate(key, {key:[fact(1)]}, {})['beleg_status'], 'referenz_fehlt')

    def test_strong_direct_and_population_evidence_can_support_small_scale(self):
        k = ('rs:E.CON', '2025-06-30', '23.00'); ref = ('rs:E.CON', '2025-12-31', '23.00')
        result=s.evaluate(k,{k:[fact(i) for i in range(12)],
                            ref:[fact(i,1e8,'2025-12-31') for i in range(12)]},{k:-6,ref:0})
        self.assertEqual(result['urteil'],'skaliert')
        self.assertEqual(result['faktor_geschaetzt'],'10^6')


class ReviewGuardTest(unittest.TestCase):
    def setUp(self):
        self.key = ('rs:E.CON','2025-06-30','23.00')
        self.rows = [fact(1)]
        self.review = {'id':'review', 'guards':[{'key':self.key,'sha256':s.fingerprint(self.rows)}],
                       'replaces':[self.key], 'decisions':[]}

    def test_changed_value_source_unit_fx_or_label_invalidates_review(self):
        for field, value in [('fact_value_eur', 101), ('source_file','new.zip'),
                             ('currency','USD'), ('fx_rate', .9), ('col_label','Other')]:
            with self.subTest(field=field):
                rows=[{**self.rows[0],field:value}]
                findings={self.key:{'urteil':'skaliert','faktor_geschaetzt':'10^6'}}
                result=s.apply_reviews(findings,{self.key:rows},[self.review])
                self.assertEqual(result[0]['status'],'veraltet')
                self.assertEqual(findings[self.key]['urteil'],'verdacht')
                self.assertEqual(findings[self.key]['faktor_geschaetzt'],'')

    def test_fingerprint_order_independence_and_duplicate_sensitivity(self):
        rows=[fact(1),fact(2)]
        self.assertEqual(s.fingerprint(rows),s.fingerprint(rows[::-1]))
        self.assertNotEqual(s.fingerprint(rows),s.fingerprint(rows+[rows[0]]))

    def test_confirmed_rejection_and_direction_replacement(self):
        findings={self.key:{'urteil':'skaliert'}}
        s.apply_reviews(findings,{self.key:self.rows},[self.review])
        self.assertNotIn(self.key,findings)
        other=('rs:E.CON','2025-12-31','23.00')
        self.review['decisions']=[{'key':other,'finding':{'richtung':'zu_gross'}}]
        s.apply_reviews(findings,{self.key:self.rows},[self.review])
        self.assertEqual(findings[other]['richtung'],'zu_gross')

    def test_collect_whole_report_and_template_does_not_duplicate_facts(self):
        con=duckdb.connect()
        types={name:('DOUBLE' if name in ('fact_value_eur','fx_rate') else 'VARCHAR') for name in s.FIELDS}
        con.execute('CREATE TABLE p('+','.join(f'{k} {v}' for k,v in types.items())+')')
        con.execute('INSERT INTO p VALUES ('+','.join('?' for _ in s.FIELDS)+')',list(self.rows[0].values()))
        collected=s.collect(con,{('rs:E.CON','*'),('rs:E.CON','23.00')})
        self.assertEqual(len(collected[self.key]),1)
        self.assertEqual(s.fingerprint(collected[self.key]),s.fingerprint(self.rows))
        con.close()

    def test_curated_reviews_preserve_uncertainty_and_mixed_factors(self):
        reviews=s.load_reviews()
        self.assertEqual(len(reviews),48)
        for review in reviews:
            self.assertTrue(review['guards'])
            for guard in review['guards']:
                self.assertEqual(len(guard['sha256']),64)
            for d in review['decisions']:
                f=d['finding']
                if f['umfang']=='teilbereich':self.assertTrue(f['betroffene_zellen'])
                if len(f['faktoren'])!=1:self.assertEqual(f['faktor_geschaetzt'],'')


class ConsumerTest(unittest.TestCase):
    def test_liquidity_does_not_mark_capital_or_irrbb_denominator(self):
        r={'ebene':'template','template_id':'61.00','umfang':'teilbereich',
           'betroffene_zellen':json.dumps([{'r':'0280','c':'0010'}])}
        self.assertFalse(s.finding_affects(r,'61.00','0020','0010'))
        self.assertTrue(s.finding_affects(r,'61.00','0280','0010'))
        self.assertFalse(s.finding_affects(r,'68.00'))

    def test_irrbb_includes_template_defect_and_preserves_clean_capital(self):
        import build_irrbb_sensitivity as irr
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'flags.csv'
            fields=['lei','scope','refPeriod','ebene','template_id','urteil','umfang','betroffene_zellen']
            with p.open('w',newline='') as fh:
                w=csv.DictWriter(fh,fields);w.writeheader()
                w.writerows([dict(lei='CITI',scope='CON',refPeriod='2025-06-30',ebene='template',template_id='68.00',urteil='skaliert'),
                    dict(lei='RABO',scope='CON',refPeriod='2026-03-31',ebene='template',template_id='61.00',urteil='skaliert',umfang='teilbereich',betroffene_zellen='[{"r":"0280","c":"0010"}]')])
            self.assertEqual(irr.lade_skalenmarken(p),{('CITI','CON','2025-06-30')})

    def test_index_does_not_reuse_first_template_factor_for_another(self):
        import build_zweig_a_shards as shards
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'processed').mkdir()
            with (root/'processed/scale_flags.csv').open('w',newline='') as fh:
                fields=['entityID','refPeriod','ebene','template_id','urteil','faktor_geschaetzt','richtung','umfang','betroffene_zellen']
                w=csv.DictWriter(fh,fields);w.writeheader()
                w.writerows([dict(entityID='E',refPeriod='D',ebene='template',template_id='61.00',urteil='skaliert',faktor_geschaetzt='10^6',richtung='zu_klein',umfang='teilbereich',betroffene_zellen='[{"r":"0280","c":"0010"}]'),
                             dict(entityID='E',refPeriod='D',ebene='template',template_id='29.02.A',urteil='verdacht',richtung='unklar',umfang='unklar')])
            sc=shards.load_scale_flags(root)['E|D']
            self.assertEqual(sc['f'],'')
            self.assertEqual(sc['d']['29.02.A']['u'],'verdacht')
            self.assertEqual(sc['d']['61.00']['f'],'10^6')


if __name__=='__main__': unittest.main()
