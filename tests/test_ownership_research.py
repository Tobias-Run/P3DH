"""Evidence collection must preserve source boundaries and access failures."""
import datetime
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import hashlib

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'scripts'))
import research_bank_ownership as research


class EvidenceCollectionTest(unittest.TestCase):
    def test_batch_priority_and_resume_do_not_repeat_attempted_cases(self):
        banks=[{'lei':'a'},{'lei':'a'},{'lei':'b'},{'lei':'c'}]
        with tempfile.TemporaryDirectory() as d:
            directory=Path(d);(directory/'a.json').write_text('{}')
            self.assertEqual(research.select_batch(banks,directory,1),[{'lei':'b'}])
            self.assertEqual(research.select_batch(banks,directory,2,repeat=True),
                             [{'lei':'a'},{'lei':'b'}])
            self.assertEqual(research.select_batch(banks,directory,2,repeat=True,known={'a','b'}),
                             [{'lei':'c'}])

    def test_review_bundle_has_hard_character_cap_without_losing_checkpoints(self):
        banks=[{'lei':str(i).zfill(20),'name':'Bank '+str(i),'rank':i,
                'status':'evidence_collected','pages':[{'url':'https://example.com/owners',
                'status':200,'sha256':'0'*64,'hits':[{'quote':'State owns 34.4%. '+'x'*2000}]*50}]}
               for i in range(5)]
        bundle=research.compact_bundle(banks,max_chars=1600)
        encoded=json.dumps(bundle,ensure_ascii=False,separators=(',',':'))
        self.assertLessEqual(len(encoded),1600)
        self.assertEqual({b['lei'] for b in banks},
                         {b['lei'] for b in bundle['cases']}|set(bundle['deferred_leis']))
        self.assertEqual(len(banks[0]['pages'][0]['hits']),50)
        for case in bundle['cases']:
            self.assertLessEqual(len(case['excerpts']),2)
            for proof in case['excerpts']:self.assertLessEqual(len(proof['quote']),650)

    def test_cache_probe_does_not_block_first_live_pass(self):
        banks=[{'lei':'a'}]
        with tempfile.TemporaryDirectory() as d:
            directory=Path(d)
            (directory/'a.json').write_text('{"collection_mode":"cache_only"}')
            self.assertEqual(research.select_batch(banks,directory),banks)
            self.assertEqual(research.select_batch(banks,directory,cache_only=True),[])

    def test_failed_checkpoint_replace_preserves_previous_complete_case(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'a.json';path.write_text('{"status":"old"}')
            with patch.object(Path,'replace',side_effect=OSError('interrupted')):
                with self.assertRaises(OSError):research.checkpoint(path,{'status':'new'})
            self.assertEqual(json.loads(path.read_text()),{'status':'old'})

    def test_cache_only_pass_cannot_make_network_requests_even_for_transient_errors(self):
        with tempfile.TemporaryDirectory() as d:
            directory=Path(d);url,_=self.cached(directory,503)
            with patch.object(research.urllib.request,'urlopen') as request:
                result=research.collect({'lei':'a','websites':[url]},directory,
                                        cache_dir=directory,cache_only=True)
                request.assert_not_called()
            self.assertEqual(result['status'],'website_unavailable')

    def test_collect_never_exceeds_page_attempt_budget(self):
        root='https://example.com'
        links=[root+'/ownership/'+str(i) for i in range(20)]
        def source(url,directory):
            return {'requested_url':url,'url':url,'status':200,'sha256':'0'*64,
                    'hits':[],'links':links}
        with tempfile.TemporaryDirectory() as d:
            with patch.object(research,'fetch',side_effect=source) as fetcher:
                with patch.object(research.time,'sleep'):
                    result=research.collect({'lei':'a','websites':[root]},Path(d),max_pages=4)
            self.assertEqual(fetcher.call_count,4)
            self.assertEqual(len(result['pages']),4)

    def test_public_cms_json_preserves_embedded_markup_and_share_percentages(self):
        from unittest.mock import MagicMock
        body=json.dumps({'content':{'rendered':'<p>State share: 34.4%</p>'}}).encode()
        response=MagicMock();response.read.return_value=body
        response.url='https://example.com/wp-json/pages'
        response.headers.get.return_value='application/json; charset=UTF-8'
        response.__enter__.return_value=response
        with tempfile.TemporaryDirectory() as d:
            with patch.object(research.urllib.request,'urlopen',return_value=response):
                result=research.fetch(response.url,Path(d))
        self.assertEqual(result['status'],200)
        self.assertEqual(json.loads(result['text'])['content']['rendered'],'<p>State share: 34.4%</p>')
        self.assertEqual(result['sha256'],hashlib.sha256(body).hexdigest())

    def test_table_cells_and_footnotes_cannot_change_a_share_percentage(self):
        p=research.PageText();p.feed('<table><tr><td>BlackRock<sup>1</sup></td><td>7.1%</td><td>SFPI<sup>2</sup></td><td>5.7%</td></tr></table>')
        text=' '.join(''.join(p.parts).split())
        self.assertEqual(text,'BlackRock [footnote 1] 7.1% SFPI [footnote 2] 5.7%')
        self.assertNotIn('17.1%',text)

    def test_scripts_and_styles_are_not_ownership_evidence(self):
        p=research.PageText();p.feed('<script>owned by fabricated owner</script><style>state-owned</style><p>Actual disclosure</p>')
        self.assertEqual(' '.join(''.join(p.parts).split()),'Actual disclosure')

    def cached(self,directory,status,error='',age=600,retry=0):
        url='https://example.com/owners';record={'requested_url':url,'status':status,'error':error,
          'retrieved_at':(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(seconds=age)).strftime('%Y-%m-%dT%H:%M:%SZ'),
          'retry_after_seconds':retry}
        (directory/(hashlib.sha256(url.encode()).hexdigest()+'.json')).write_text(json.dumps(record));return url,record

    def test_access_denial_is_not_retried_even_on_parser_refresh(self):
        with tempfile.TemporaryDirectory() as d:
            directory=Path(d);url,record=self.cached(directory,403)
            with patch.object(research.urllib.request,'urlopen') as request:
                self.assertEqual(research.fetch(url,directory,refresh=True),record);request.assert_not_called()

    def test_server_retry_after_is_respected(self):
        with tempfile.TemporaryDirectory() as d:
            directory=Path(d);url,record=self.cached(directory,429,age=600,retry=1200)
            with patch.object(research.urllib.request,'urlopen') as request:
                self.assertEqual(research.fetch(url,directory),record);request.assert_not_called()

    def test_transient_outage_does_not_permanently_mark_a_source_unavailable(self):
        with tempfile.TemporaryDirectory() as d:
            directory=Path(d);url,record=self.cached(directory,503)
            with patch.object(research.urllib.request,'urlopen',side_effect=TimeoutError('temporary outage')) as request:
                result=research.fetch(url,directory);request.assert_called_once()
                self.assertEqual(result['previous_attempts'][0]['status'],503)
                self.assertEqual(result['error'],'temporary outage')


if __name__=='__main__':unittest.main()
