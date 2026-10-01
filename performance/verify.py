"""Behavioural equivalence and cache/lazy-loading contracts in a real browser.

Uses the pinned data and server from measure.py. It compares all metric profiles,
all reports' time-series membership, both locales, per-cell table HTML and exports.
"""
import hashlib
import json
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
from measure import ROOT, DATA, OUT, serve

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def capture(browser,base,variant,check_lazy=True):
    ctx=browser.new_context(); pg=ctx.new_page(); pg.set_default_timeout(30000)
    errors=[]; pg.on('pageerror',lambda e:errors.append(str(e)))
    pg.goto(f'{base}/{variant}/viewer.html#benchmark',wait_until='networkidle')
    pg.wait_for_selector('.bmtable tbody tr')
    start_resources=pg.evaluate("performance.getEntriesByType('resource').map(x=>x.name)")
    result=pg.evaluate("""async()=>{
      const profiles={};
      for(const p of PROFILES){
        BMP=p.id; const prof=bmProf();
        if(!prof) throw new Error('Missing profile '+p.id);
        bmSort={...prof.defaultSort};
        const rows=benchmarkRows();
        const allowed=prof.gate.length?rows.filter(r=>!r._out):rows;
        const pcts={}; for(const c of prof.cols)
          pcts[c.id]=[...percentileMap(allowed,c.id)].sort((a,b)=>a[0].localeCompare(b[0]));
        // URL metadata necessarily differs between baseline and candidate.
        const csv=benchmarkCSV(allowed,prof).split('\\n').filter(x=>!x.includes('http://')&&!x.startsWith('# '+tr('created:'))).join('\\n');
        profiles[p.id]={rows,pcts,csv};
      }
      const membership=REPORTS.map(r=>[repKey(r),entityReports(r).map(repKey)]);
      const formats={};
      for(const lang of ['de','en']){
        LANG=lang; const vals=[0,-0,0.0001,-0.0001,1.005,1234567.89,-1e12,null,undefined,NaN,Infinity];
        formats[lang]=[];
        for(const v of vals) for(const [lo,hi] of [[0,0],[0,2],[2,2],[1,5]]){
          const expected=Number.isFinite(Number(v))?Number(v).toLocaleString(LOCALE(),
              {minimumFractionDigits:lo,maximumFractionDigits:hi}):'';
          const want=lang==='de'?expected.split('.').join(NBSP):expected;
          const got=nf(v,lo,hi);
          if(got!==want) throw new Error('Number format changed: '+v+' '+lang);
          formats[lang].push(got);
        }
      }
      LANG='en';
      const synthetic=[];
      for(let i=0;i<1000;i++) synthetic.push({key:String(i),itype:'A',scope:'CON',date:'2025',v:i%13===0?null:(i%17)-8});
      synthetic.push({key:'small',itype:'B',scope:'CON',date:'2025',v:1});
      const actual=percentileMap(synthetic,'v');
      for(const r of synthetic){
        const peers=synthetic.filter(x=>peerKeyOf(x)===peerKeyOf(r)&&x.v!=null&&isFinite(x.v));
        const got=actual.get(r.key);
        if(r.v==null||peers.length<PCT_MIN_GROUP){if(got) throw new Error('Unexpected percentile');continue;}
        const want=(peers.filter(x=>x.v<r.v).length+peers.filter(x=>x.v===r.v).length/2)/peers.length*100;
        if(!got||got.p!==want||got.n!==peers.length) throw new Error('Mid-rank changed');
      }
      await ensureLabels(); await ensureShapes();
      return {profiles,membership,formats,syntheticCases:synthetic.length};
    }""")
    chosen=json.loads((OUT/'snapshot.json').read_text())['reports'][:3]
    tables=[]
    for report in chosen:
        tables.append(pg.evaluate("""async key=>{
          const r=byKey(key); await ensureLoaded(r);
          return [...r.templates.keys()].sort().map(t=>[t,renderTemplate(t,r.templates.get(t),r)]);
        }""",report['k']))
    result['tables']=tables
    # Visible desktop screenshot of the same large report.
    pg.evaluate("async key=>{ await renderReport(byKey(key)); }",chosen[0]['k'])
    pg.screenshot(path=str(OUT/f'{variant}_report.png'))
    result['errors']=errors
    if variant=='candidate' and check_lazy:
        assert not any(x.endswith('labels.json') for x in start_resources), 'Labels eagerly loaded'
        # Fresh report navigation + direct expansion must work without hover prefetch.
        fresh=ctx.new_page()
        r=chosen[0]; lei=r['entityID'][3:23]; scope=r['entityID'].split('.')[-1]
        fresh.goto(f'{base}/{variant}/viewer.html#r/{lei}/{r["refPeriod"]}/{scope}',wait_until='networkidle')
        fresh.wait_for_selector('#ovSection .ovcard')
        assert fresh.evaluate('LABELS_LOADED'), 'Report did not prepare labels'
        fresh.evaluate("document.querySelector('details.theme').open=true")
        fresh.wait_for_function("document.querySelector('details.theme .tbody').dataset.done==='1'")
        assert fresh.locator('details.theme td.num').count()>0
        assert fresh.evaluate('LABELS_LOADED')
        fresh.close()
    ctx.close()
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cpu-only',action='store_true')
    args=parser.parse_args()
    server=serve(); base=f'http://127.0.0.1:{server.server_port}'
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        a=capture(browser,base,'baseline'); b=capture(browser,base,'candidate',not args.cpu_only)
        for variant,result in [('baseline',a),('candidate',b)]:
            (OUT/f'{variant}_equivalence.json').write_text(json.dumps(result,ensure_ascii=False))
        checks={}
        for key in a:
            checks[key]={'equal':a[key]==b[key],'baseline_sha256':digest(a[key]),'candidate_sha256':digest(b[key])}
            print(key,checks[key]['equal'],flush=True)
        assert not a['errors'] and not b['errors'], (a['errors'],b['errors'])
        assert all(v['equal'] for v in checks.values()), checks
        # Exercise changing a resource at the same URL: revalidation must fetch
        # the new body, rather than obeying a still-fresh cache entry.
        pg=browser.new_page();pg.goto(base+'/candidate/viewer.html#benchmark',wait_until='networkidle')
        path=str(DATA/'cache_probe.json')
        import gzip
        def value(n):
            raw=json.dumps({'version':n}).encode()
            server.payloads[path]=(raw,gzip.compress(raw),f'"revision-{n}"')
        value(1); assert pg.evaluate("getJSON('cache_probe.json')")=={'version':1}
        assert pg.evaluate("getJSON('cache_probe.json')")=={'version':1}
        value(2); assert pg.evaluate("getJSON('cache_probe.json')")=={'version':2}
        probes=[r for r in server.requests if 'cache_probe' in r['path']]
        checks['cache_revalidation']={'equal':True,'versions':[1,1,2],'http':probes}
        if not args.cpu_only:
            checks['lazy_labels']={'equal':True,'benchmark_initial':False,'report_prefetch':True,'direct_expansion':True}
        (OUT/'verification.json').write_text(json.dumps(checks,indent=2))
        browser.close()
    server.shutdown()

if __name__=='__main__':main()
