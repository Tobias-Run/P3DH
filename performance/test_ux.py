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
        browser.close()
    server.shutdown()
    (OUT/f'issue{args.issue}_ux.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
