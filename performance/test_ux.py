"""Browser contracts for the sequential UX changes; no production writes."""
import argparse
import json
from playwright.sync_api import sync_playwright
from measure import OUT, serve

def report_url(base):
    r=json.loads((OUT/'snapshot.json').read_text())['reports'][0]
    return base+'/candidate/viewer.html#r/'+r['entityID'][3:23]+'/'+r['refPeriod']+'/'+r['entityID'].split('.')[-1]

def labels(browser,base):
    context=browser.new_context(viewport={'width':390,'height':844},has_touch=True,is_mobile=True)
    page=context.new_page(); errors=[]; requests=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:requests.append(r.url))
    page.goto(base+'/candidate/viewer.html#benchmark',wait_until='networkidle')
    page.wait_for_selector('.bmtable tbody tr')
    assert not any(x.endswith('labels.json') for x in requests)
    page.goto(report_url(base),wait_until='networkidle')
    page.wait_for_selector('#ovSection .ovcard')
    page.wait_for_function('LABELS_LOADED')
    assert page.evaluate('LABELS_LOADED')
    assert sum(x.endswith('labels.json') for x in requests)==1
    page.locator('details.theme summary').first.tap()
    page.wait_for_function("document.querySelector('details.theme .tbody').dataset.done==='1'")
    assert page.locator('details.theme td.num').count()>0
    # Focus-only activation is usable, and repeated readers do not refetch.
    page.evaluate('Promise.all([ensureLabels(),ensureLabels(),ensureLabels()])')
    assert sum(x.endswith('labels.json') for x in requests)==1
    assert not errors,errors
    context.close()

    context=browser.new_context();page=context.new_page();errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.route('**/labels.json',lambda r:r.abort())
    page.goto(report_url(base),wait_until='networkidle')
    page.locator('details.theme summary').first.click()
    retry=page.locator('details.theme .tbody button')
    retry.wait_for()
    assert page.locator('details.theme td.num').count()==0
    page.unroute('**/labels.json')
    retry.click()
    page.wait_for_function("document.querySelector('details.theme .tbody').dataset.done==='1'")
    assert page.locator('details.theme td.num').count()>0
    assert not errors,errors
    context.close()

    context=browser.new_context();page=context.new_page();errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.add_init_script("""const originalFetch=window.fetch;
      window.fetch=async(...args)=>{const r=await originalFetch(...args);
        if(String(args[0]).includes('/reports/')) await new Promise(r=>setTimeout(r,600));
        return r;};""")
    page.goto(report_url(base),wait_until='domcontentloaded')
    page.wait_for_function("VIEW==='reports' && activeKey")
    page.evaluate("location.hash='#benchmark'")
    page.wait_for_selector('.bmtable tbody tr')
    page.wait_for_load_state('networkidle')
    assert page.evaluate("VIEW==='benchmark' && activeKey===null")
    assert not page.locator('#tcontainer').count()
    assert not errors,errors
    context.close()
    return {'benchmark_without_labels':True,'report_prefetch':True,'touch_expansion':True,
            'deduplicated_labels':True,'failure_retry':True,'stale_report_navigation':True}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--issue',default='116')
    args=parser.parse_args();server=serve();base=f'http://127.0.0.1:{server.server_port}'
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        result=labels(browser,base)
        if int(args.issue)>=117: result['benchmark']=benchmark(browser,base)
        if int(args.issue)>=118: result['partition']=partition(browser,base)
        browser.close()
    server.shutdown()
    (OUT/f'issue{args.issue}_ux.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

def benchmark(browser,base):
    ctx=browser.new_context();page=ctx.new_page();errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(base+'/candidate/viewer.html#benchmark',wait_until='networkidle')
    page.wait_for_selector('.bmtable tbody tr')
    result=page.evaluate("""async()=>{
      const first=document.querySelector('.bmtable tbody tr');
      const key=first.dataset.key, control=document.getElementById('bmProfile');
      await renderBenchmark();
      if(document.querySelector('.bmtable tbody tr')!==first) throw new Error('Redraw discarded stable row');
      const th=document.querySelector('th[data-k="name"]');th.focus();th.click();
      await renderBenchmark();
      const retained=[...document.querySelectorAll('.bmtable tbody tr')].find(r=>r.dataset.key===key);
      if(retained && retained!==first)
        throw new Error('Sort discarded existing row');
      if(document.getElementById('bmProfile')!==control || document.activeElement!==th)
        throw new Error('Sort discarded controls/focus');
      const snapshot=()=>[...document.querySelectorAll('.bmtable tbody tr')].map(r=>[r.dataset.key,r.innerHTML]);
      const checks=[];
      for(const p of PROFILES){
        BMP=p.id;bmSort={...p.defaultSort};
        // Registry profiles carry sort as a tuple; use the resolved profile.
        bmSort={...bmProf().defaultSort};
        BM_PCT=true;await renderBenchmark();
        for(const col of ['name',bmProf().cols[0].id]){
          bmSort={col,dir:-1};await renderBenchmark();const cached=snapshot();
          BM_DOM={context:null,rows:new Map()};await renderBenchmark();
          if(JSON.stringify(cached)!==JSON.stringify(snapshot())) throw new Error('Stale cells '+p.id+' '+col);
          checks.push(p.id+'/'+col);
        }
      }
      BMP='km1';BM_PCT=false;BM_HIDEFLAG=false;BM_COLS=null;
      document.getElementById('reportFilter').value='bank';
      bmSort={...bmProf().defaultSort};await renderBenchmark();
      const expected=benchmarkRows().map(r=>r.key);
      const actual=[...document.querySelectorAll('.bmtable tbody tr')].map(r=>r.dataset.key);
      if(JSON.stringify(expected.slice(0,BM_PAGE_SIZE))!==JSON.stringify(actual))throw new Error('Filter order/rows changed');
      const paged=[];
      for(let i=0;i<Math.ceil(expected.length/BM_PAGE_SIZE);i++){
        BM_PAGE=i;await renderBenchmark();
        paged.push(...[...document.querySelectorAll('.bmtable tbody tr')].map(r=>r.dataset.key));
        if(BM_DOM.rows.size>BM_PAGE_SIZE)throw new Error('Unbounded row cache');
      }
      if(JSON.stringify(paged)!==JSON.stringify(expected))throw new Error('Pagination lost/duplicated rows');
      let exported='';ladeHerunter=(name,csv)=>{exported=csv;};document.getElementById('bmCsv').click();
      if(!exported.includes('# '+tr('rows:')+' '+expected.length))throw new Error('Export lost rows');
      const d=bmSort.dir;const header=document.querySelector('th[data-k="'+bmSort.col+'"]');
      header.click();header.click();header.click();
      if(bmSort.dir!==-d)throw new Error('Duplicate event handlers');
      return {reused_rows:true,preserved_controls_and_focus:true,cached_vs_fresh:checks,filtered_rows:expected.length,pagination_complete:true,export:true};
    }""")
    assert not errors,errors
    ctx.close();return result

def partition(browser,base):
    from measure import DATA,ROOT
    from urllib.parse import urlsplit
    ctx=browser.new_context();page=ctx.new_page();requests=[];errors=[]
    page.on('request',lambda r:requests.append(r.url))
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(base+'/candidate/viewer.html#benchmark',wait_until='networkidle')
    page.wait_for_selector('.bmtable tbody tr')
    parts=lambda:[x for x in requests if '/benchmark/' in x]
    assert len(parts())==1 and '/61.00.' in parts()[0],parts()
    assert not any(x.endswith('/benchmark.json') for x in requests)
    page.select_option('#bmProfile','npl')
    page.wait_for_function("haveBenchmark(BM_MANIFEST.profiles.npl) && document.querySelector('th[data-k=npl]')")
    before=len(parts());page.select_option('#bmProfile','km1')
    page.wait_for_function("document.querySelector('th[data-k=cet1]')")
    assert len(parts())==before,'Cached profile fetched again'
    # A delayed response for a former profile must not replace the latest one.
    page.evaluate("""()=>{const original=window.fetch;window.fetch=async(...args)=>{
      const r=await original(...args);if(String(args[0]).includes('/41.00.'))await new Promise(r=>setTimeout(r,500));return r;};
      BMP='esg';bmSort={...bmProf().defaultSort};renderBenchmark();
      BMP='km1';bmSort={...bmProf().defaultSort};renderBenchmark();}""")
    page.wait_for_function("BM_TEMPLATES.has('41.00')")
    assert page.evaluate("BMP==='km1' && !!document.querySelector('th[data-k=cet1]')")
    # Failed partial requests remain retryable; no permanent rejected promise.
    page.route('**/benchmark/30.01.*',lambda r:r.abort())
    page.select_option('#bmProfile','verg');page.locator('#bmLoadStatus button').wait_for()
    page.unroute('**/benchmark/30.01.*');page.locator('#bmLoadStatus button').click()
    page.wait_for_function("haveBenchmark(BM_MANIFEST.profiles.verg) && !document.getElementById('bmLoadStatus')")
    assert not errors,errors;ctx.close()

    # Fulfil all requests locally but use a non-local page origin so the real
    # CDN/raw URL construction, CORS, integrity and version pinning execute.
    ctx=browser.new_context();page=ctx.new_page();seen=[];revision='a'*40
    def fulfil(route):
        url=route.request.url;seen.append(url)
        if url.endswith('/favicon.ico'):route.fulfill(status=204);return
        if url=='https://viewer.test/viewer.html':
            route.fulfill(status=200,content_type='text/html',body=(ROOT/'processed/zweig_a/viewer_json.html').read_bytes());return
        if url.endswith('/data_version.json'):
            body=json.dumps({'schema':1,'revision':revision}).encode()
        else:
            marker='@'+revision+'/' if 'cdn.jsdelivr.net' in url else '/'+revision+'/'
            assert marker in url, 'Unpinned data URL '+url
            relative=url.split(marker,1)[1];body=(DATA/relative).read_bytes()
            if 'cdn.jsdelivr.net' in url and '/benchmark/' in url:body=b'{}' # force integrity fallback
        route.fulfill(status=200,body=body,headers={'Content-Type':'application/json','Access-Control-Allow-Origin':'*'})
    page.route('**/*',fulfil)
    page.goto('https://viewer.test/viewer.html#benchmark',wait_until='networkidle')
    page.wait_for_selector('.bmtable tbody tr')
    assert page.evaluate('DATA_REV')==revision
    assert any('raw.githubusercontent.com' in u and '/benchmark/' in u for u in seen)
    ctx.close()
    return {'km1_only':True,'cached_profile_switch':True,'latest_profile_wins':True,
            'partial_failure_retry':True,'all_data_pinned':True,'integrity_failure_same_revision_fallback':True}

if __name__=='__main__':main()
