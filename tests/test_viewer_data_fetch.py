"""Run the viewer's real loader against controlled slow/failing HTTP origins."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'Node is needed to exercise browser JavaScript')
class ViewerDataFetchTest(unittest.TestCase):
    def check(self, body):
        html = (ROOT/'processed/zweig_a/viewer_json.html').read_text()
        source = html.split('const DATA_BASES =', 1)[1].split('/* ================= formatting', 1)[0]
        source = 'const DATA_BASES =' + source
        source = source.replace('DATA_HEDGE_MS=1200, DATA_TIMEOUT_MS=15000',
                                'DATA_HEDGE_MS=10, DATA_TIMEOUT_MS=60')
        harness = """
const assert=require('node:assert/strict');
const LOCAL=false;
const revision='a'.repeat(40);
const calls=[];
const response=(status,data)=>({ok:status===200,status,json:async()=>data});
const stalled=signal=>new Promise((resolve,reject)=>signal.addEventListener('abort',()=>{
  const e=new Error('aborted');e.name='AbortError';reject(e);
},{once:true}));
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
"""
        script = harness + source + '\n(async()=>{\n' + body + '\n})().catch(e=>{console.error(e);process.exit(1)});'
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_hanging_headers_use_same_revision_fallback_and_cancel_loser(self):
        self.check("""
DATA_REV=revision;
global.fetch=(url,options)=>{calls.push({url,options});
  return url.includes('jsdelivr')?stalled(options.signal):Promise.resolve(response(200,{value:42}));};
assert.deepEqual(await getJSON('benchmark/km1.json','sha256-example'),{value:42});
assert.equal(calls.length,2);
assert(calls.every(c=>c.url.includes(revision)));
assert(calls.every(c=>c.options.integrity==='sha256-example'));
assert(calls[0].options.signal.aborted);
""")

    def test_healthy_body_is_not_downloaded_twice(self):
        self.check("""
global.fetch=async(url,options)=>{calls.push(url);
  return {ok:true,status:200,json:async()=>{await wait(25);return {ok:true};}};};
assert.deepEqual(await getJSON('labels.json'),{ok:true});
assert.equal(calls.length,1);
""")

    def test_stalled_body_has_deadline_and_then_falls_back(self):
        self.check("""
global.fetch=async(url,options)=>{calls.push(url);
  return url.includes('jsdelivr')?{ok:true,status:200,json:()=>stalled(options.signal)}:response(200,{ok:true});};
assert.deepEqual(await getJSON('index.json'),{ok:true});
assert.equal(calls.length,2);
""")

    def test_both_stalled_origins_reject_instead_of_hanging(self):
        self.check("""
global.fetch=(url,options)=>{calls.push(url);return stalled(options.signal);};
await assert.rejects(getJSON('index.json'),e=>e.name==='AbortError'&&e.missing===false);
assert.equal(calls.length,2);
""")

    def test_integrity_failure_falls_back_without_dropping_integrity(self):
        self.check("""
global.fetch=async(url,options)=>{calls.push(options);
  if(url.includes('jsdelivr'))throw new TypeError('integrity mismatch');
  return response(200,{verified:true});};
assert.deepEqual(await getJSON('advanced_peers.json','sha256-required'),{verified:true});
assert(calls.every(c=>c.integrity==='sha256-required'));
""")

    def test_pointer_does_not_race_authoritative_legacy_absence(self):
        self.check("""
global.fetch=async(url)=>{calls.push(url);await wait(25);return response(404,null);};
assert.equal(await getJSON('data_version.json'),null);
assert.equal(calls.length,1);
assert(calls[0].includes('raw.githubusercontent.com'));
""")

    def test_only_confirmed_missing_origins_allow_legacy_fallback(self):
        self.check("""
global.fetch=async()=>response(404,null);
await assert.rejects(getJSON('index.json'),e=>e.missing===true);
global.fetch=async(url)=>response(url.includes('jsdelivr')?503:404,null);
await assert.rejects(getJSON('index.json'),e=>e.missing===false);
""")

    def test_pointer_fallback_preserves_validation(self):
        self.check("""
global.fetch=async(url)=>response(url.includes('raw.githubusercontent.com')?503:200,{schema:1,revision});
await selectDataVersion();assert.equal(DATA_REV,revision);
global.fetch=async()=>response(200,{schema:1,revision:'not-a-sha'});
await assert.rejects(selectDataVersion(),/Invalid dataset version/);
assert.equal(DATA_REV,revision);
""")


if __name__ == '__main__':
    unittest.main()
