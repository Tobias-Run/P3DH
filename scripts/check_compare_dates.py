"""Real-browser regression for common-date comparison and template groups."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import check_viewer_runtime as runtime


def check():
    from playwright.sync_api import sync_playwright
    runtime.PORT=8821;server=runtime._serve();errors=[];results=[]
    a='rs:549300TRUWO2CD2G5692.CON';b='rs:21380057HUGFEAF25W84.CON'
    base=f'http://localhost:{runtime.PORT}/viewer_json.html'
    url=base+'#compare?pin='+a+'|2026-03-31,'+b+'|2025-06-30'
    try:
        with sync_playwright() as p:
            binary=next((s for s in [runtime.CHROMIUM,'/usr/bin/chromium'] if Path(s).exists()),None)
            browser=p.chromium.launch(args=['--no-sandbox'],**({'executable_path':binary} if binary else {}))
            for width,language in [(1280,'en'),(390,'de')]:
                page=browser.new_page(viewport={'width':width,'height':844})
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(url,wait_until='networkidle');page.wait_for_selector('#cmpDate')
                if language=='de':page.click('#langBtn');page.wait_for_selector('#cmpDate')
                assert page.locator('#cmpDate').input_value()=='2025-12-31'
                heads=page.locator('#cmpBody thead th .cl').all_text_contents()
                assert len(heads)==2 and all('2025-12-31' in h for h in heads),heads
                assert 'cmpdate=2025-12-31' in page.url
                check_groups=page.evaluate("""()=>{
                  const s=compareSelection([...PINS].map(byKey),REPORTS,CMPDATE);
                  const g=compareTemplates(s.slots);
                  const groups=[...document.querySelectorAll('#cmpTpl optgroup')];
                  return {common:g.common,partial:g.partial,
                    actual:groups.map(x=>[...x.querySelectorAll('option:not([disabled])')].map(o=>o.value))};
                }""")
                assert check_groups['actual'][0]==check_groups['common']
                if check_groups['partial']:assert check_groups['actual'][1]==check_groups['partial']
                page.select_option('#cmpDate','2026-03-31');page.wait_for_selector('#cmpDate')
                page.wait_for_function("CMPDATE==='2026-03-31' && document.querySelector('#cmpBody table')")
                heads=page.locator('#cmpBody thead th .cl').all_text_contents()
                assert len(heads)==2 and all('2026-03-31' in h for h in heads),heads
                missing='Kein Report für diesen Stichtag' if language=='de' else 'No report for this reference date'
                missing_index=next((i for i,h in enumerate(heads) if missing in h),None)
                assert missing_index is not None,heads
                assert page.locator('#cmpBody tbody tr').first.locator('td').nth(missing_index+1).inner_text()=='—'
                assert page.locator('#cmpTpl optgroup').count()==2
                assert page.locator('#cmpTpl optgroup').first.locator('option:disabled').count()==1
                assert page.locator('#cmpTpl optgroup').last.locator('option').first.inner_text().endswith('(1/2)')
                shared=page.url;page.reload(wait_until='networkidle');page.wait_for_selector('#cmpDate')
                assert page.locator('#cmpDate').input_value()=='2026-03-31' and page.url==shared
                page.goto(base+'#compare?pin='+a+'|2025-06-30,'+b+'|2025-12-31&cmpdate=2024-12-31',wait_until='networkidle')
                page.wait_for_selector('#cmpDate');assert page.locator('#cmpDate').input_value()=='2024-12-31'
                assert page.locator('#cmpBody table').count()==0
                assert page.evaluate('PINS.size')==2
                results.append({'width':width,'language':language,'common_templates':len(check_groups['common']),
                                'partial_templates':len(check_groups['partial']),'same_date_and_missing_reports':'pass'})
                page.close()
            # A failed shard must stay visible as a failed column and recover.
            page=browser.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            failed='**/reports/rs_21380057HUGFEAF25W84.CON__2025-12-31.json'
            page.route(failed,lambda route:route.abort())
            page.goto(url,wait_until='networkidle');page.wait_for_selector('#cmpRetry')
            assert 'Report could not be loaded' in page.locator('#cmpBody thead').inner_text()
            assert page.locator('#cmpBody thead th .cl').count()==2
            page.unroute(failed);page.click('#cmpRetry');page.wait_for_selector('#cmpDate')
            page.wait_for_function("!document.querySelector('#cmpRetry') && !!document.querySelector('#cmpBody table')")
            assert page.locator('#cmpTpl optgroup').first.locator('option:not([disabled])').count()>0
            page.close()
            # A delayed comparison must not replace a view selected meanwhile.
            page=browser.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.add_init_script("""const originalFetch=window.fetch;
              window.fetch=async(...args)=>{
                if(String(args[0]).includes('labels.json'))await new Promise(r=>setTimeout(r,1500));
                return originalFetch(...args);
              };""")
            page.goto(url,wait_until='domcontentloaded');page.wait_for_function("VIEW==='compare'")
            page.click('#tabBenchmark');page.wait_for_selector('.bmtable')
            page.wait_for_timeout(1800);assert page.evaluate("VIEW==='benchmark'")
            assert page.locator('#cmpBody').count()==0
            page.close();browser.close()
    finally:server.shutdown();server.server_close()
    assert not errors,errors
    print(json.dumps({'cases':results,'failed_report_retry':'pass','stale_navigation':'pass','javascript_errors':errors},indent=2))


if __name__=='__main__':check()
