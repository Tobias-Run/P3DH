"""Reproducible browser A/B: identical pinned data, gzip, HTTP cache and CDP throttling.

python performance/measure.py --variants baseline candidate --runs 5
Timing output is lab evidence, not field Core Web Vitals. Each sample gets a
fresh browser context; a repeat navigation in that context measures warm cache.
"""
import argparse
import functools
import gzip
import hashlib
import http.server
import json
import statistics
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'processed/zweig_a/data'
OUT = ROOT / 'performance/results'
PROFILES = {'desktop': {'cpu': 1, 'latency': 0, 'bps': -1, 'width': 1440, 'height': 900},
            'mobile4g': {'cpu': 4, 'latency': 60, 'bps': 500000, 'width': 390, 'height': 844}}
OBSERVE = """(() => {
  window.__perf = {longtasks:[],lcp:[],cls:[],ready:{}};
  for (const type of ['longtask','largest-contentful-paint','layout-shift']) {
    new PerformanceObserver(list=>{ for(const e of list.getEntries()) {
      if(type==='longtask') __perf.longtasks.push({start:e.startTime,duration:e.duration});
      if(type==='largest-contentful-paint') __perf.lcp.push({start:e.startTime,size:e.size});
      if(type==='layout-shift'&&!e.hadRecentInput) __perf.cls.push({start:e.startTime,value:e.value});
    }}).observe({type,buffered:true});
  }
  new MutationObserver(()=>{
    for(const [key,selector] of Object.entries({sidebar:'#reportList .report',
        benchmark:'.bmtable tbody tr', report:'#ovSection .ovcard'})) {
      if(!__perf.ready[key] && document.querySelector(selector))
        requestAnimationFrame(()=>requestAnimationFrame(()=>{
          if(!__perf.ready[key]) __perf.ready[key]=performance.now();
        }));
    }
  }).observe(document,{childList:true,subtree:true});
})();"""

class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def send_response(self,code,message=None):
        self.server.requests.append({'path':self.path,'status':code,
            'if_none_match':self.headers.get('If-None-Match'),
            'cache_control':self.headers.get('Cache-Control')})
        super().send_response(code,message)
    def do_GET(self):
        parts = urlsplit(self.path).path.strip('/').split('/')
        if len(parts)<2:
            self.send_error(404); return
        variant, rest = parts[0], '/'.join(parts[1:])
        if rest == 'viewer.html':
            path = ROOT/'processed/zweig_a/viewer_json.html' if variant=='candidate' else ROOT/f'performance/{variant}/viewer_json.html'
        elif rest.startswith('data/'):
            path = DATA / rest[5:]
        else:
            self.send_error(404); return
        item = self.server.payloads.get(str(path))
        if item is None:
            self.send_error(404); return
        raw, packed, etag = item
        if self.headers.get('If-None-Match')==etag:
            self.send_response(304)
            self.send_header('ETag',etag)
            self.send_header('Cache-Control','public, max-age=600')
            self.end_headers(); return
        use_gzip='gzip' in self.headers.get('Accept-Encoding','')
        body=packed if use_gzip else raw
        self.send_response(200)
        self.send_header('Content-Type','text/html; charset=utf-8' if path.suffix=='.html' else 'application/json')
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','public, max-age=600')
        self.send_header('ETag',etag)
        self.send_header('Vary','Accept-Encoding')
        if use_gzip: self.send_header('Content-Encoding','gzip')
        self.end_headers()
        try: self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError): pass

def serve():
    server=Server(('127.0.0.1',0),Handler)
    server.payloads={}
    server.requests=[]
    paths=[*DATA.rglob('*.json'),*ROOT.glob('performance/*/viewer_json.html'),ROOT/'processed/zweig_a/viewer_json.html']
    for path in paths:
        raw=path.read_bytes()
        server.payloads[str(path)]=(raw,gzip.compress(raw,6), '"'+hashlib.sha256(raw).hexdigest()+'"')
    threading.Thread(target=server.serve_forever,daemon=True).start()
    return server

def snapshot(page,cdp):
    return page.evaluate("""() => ({...__perf,
      now:performance.now(), navigation:performance.getEntriesByType('navigation').map(x=>x.toJSON()),
      paint:performance.getEntriesByType('paint').map(x=>x.toJSON()),
      resources:performance.getEntriesByType('resource').map(x=>x.toJSON()),
      nodes:document.querySelectorAll('*').length,
      rows:document.querySelectorAll('.bmtable tbody tr').length,
      heap:performance.memory?.usedJSHeapSize,
    })""")

def interaction(page, expression):
    return page.evaluate("""async expression=>{
      const before=performance.now(); await eval(expression);
      const script=performance.now()-before;
      await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
      return {script_ms:script,paint_ms:performance.now()-before,nodes:document.querySelectorAll('*').length};
    }""",expression)

def sample(browser,base,variant,profile,scenario,warm=False):
    cfg=PROFILES[profile]
    ctx=browser.new_context(viewport={'width':cfg['width'],'height':cfg['height']}, device_scale_factor=1)
    page=ctx.new_page(); page.set_default_timeout(30000); page.add_init_script(OBSERVE)
    cdp=ctx.new_cdp_session(page)
    cdp.send('Network.enable')
    cdp.send('Network.emulateNetworkConditions',{'offline':False,'latency':cfg['latency'],
             'downloadThroughput':cfg['bps'],'uploadThroughput':cfg['bps']})
    cdp.send('Emulation.setCPUThrottlingRate',{'rate':cfg['cpu']})
    errors=[]; statuses=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('response',lambda r:statuses.append({'url':r.url,'status':r.status}))
    report=json.loads((OUT/'snapshot.json').read_text())['reports'][0]
    lei=report['entityID'][3:23]; scope=report['entityID'].split('.')[-1]
    fragment='#benchmark' if scenario=='benchmark' else f'#r/{lei}/{report["refPeriod"]}/{scope}'
    url=base+'/'+variant+'/viewer.html'+fragment
    records=[]
    for visit in ('cold','warm') if warm else ('cold',):
        # goto() to an identical URL/hash can be a same-document navigation.
        # Leave the document first, retaining the context's HTTP cache.
        if visit=='warm':
            page.goto('about:blank')
        errors.clear(); statuses.clear()
        page.goto(url,wait_until='domcontentloaded')
        field='benchmark' if scenario=='benchmark' else 'report'
        page.wait_for_function(f'window.__perf?.ready.{field}')
        # Finish optional initial downloads before measuring the settled session.
        page.wait_for_function('BM_LOADED')
        page.wait_for_timeout(1800 if profile=='mobile4g' else 600)
        page.wait_for_load_state('networkidle')
        rec={'variant':variant,'profile':profile,'scenario':scenario,'visit':visit,
             'initial':snapshot(page,cdp),'errors':list(errors),'statuses':list(statuses),'interactions':{}}
        if visit=='cold' and scenario=='benchmark':
            for name,expr in [('sort',"bmSort.dir*=-1; renderBenchmark()"),
                              ('profile',"BMP='npl'; renderBenchmark()"),
                              ('filter',"document.getElementById('reportFilter').value='bank'; document.getElementById('reportFilter').dispatchEvent(new Event('input',{bubbles:true}))")]:
                rec['interactions'][name]=interaction(page,expr)
            # Deterministic full-data render microbench, after one warm-up.
            rec['micro']=page.evaluate("""async()=>{
              document.getElementById('reportFilter').value=''; BMP='km1';
              await renderBenchmark();
              let runs=[]; for(let i=0;i<3;i++){
                const t=performance.now(); await renderBenchmark();
                runs.push(performance.now()-t);
              }
              return {render_ms:runs, rows:document.querySelectorAll('.bmtable tbody tr').length};
            }""")
        if visit=='cold' and scenario=='report':
            expand_start=page.evaluate('performance.now()')
            rec['interactions']['expand']=interaction(page,"document.querySelector('details.theme').open=true")
            page.wait_for_function("document.querySelector('details.theme[open] .tbody')?.dataset.done==='1'")
            rec['expand_ready_ms']=page.evaluate('performance.now()')-expand_start
            page.wait_for_load_state('networkidle')
            rec['expanded']=snapshot(page,cdp)
            rec['expanded']['cells']=page.locator('#tcontainer td.num').count()
            # Return to an empty persisted UI state before repeat navigation.
            page.evaluate('localStorage.clear()')
        records.append(rec)
    ctx.close()
    return records

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--variants',nargs='+',default=['baseline','candidate'])
    ap.add_argument('--profiles',nargs='+',default=list(PROFILES)); ap.add_argument('--runs',type=int,default=3)
    ap.add_argument('--scenarios',nargs='+',default=['benchmark','report']); ap.add_argument('--output',default='measurements.json')
    args=ap.parse_args(); server=serve(); results=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        for n in range(args.runs):
            # Alternate the order to avoid always favouring one version.
            for variant in args.variants if n%2==0 else list(reversed(args.variants)):
                for profile in args.profiles:
                    for scenario in args.scenarios:
                        try:
                            samples=sample(browser,f'http://127.0.0.1:{server.server_port}',variant,profile,scenario,warm=True)
                            for s in samples: s.update(run=n,browser=browser.version)
                            results.extend(samples)
                            first=samples[0]; print(variant,profile,scenario,n,
                                round(first['initial']['ready'][scenario]),'ms',flush=True)
                        except Exception as e:
                            results.append({'variant':variant,'profile':profile,'scenario':scenario,'run':n,'failure':str(e)})
                            print('FAILED',variant,profile,scenario,str(e)[:200],flush=True)
                        (OUT/args.output).write_text(json.dumps(results,indent=2))
        browser.close()
    server.shutdown()

if __name__=='__main__': main()
