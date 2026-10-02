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
