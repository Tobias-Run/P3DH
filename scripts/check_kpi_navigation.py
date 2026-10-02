"""Real KPI source-link activation after lazy rendering (#124).

Used by check_viewer_runtime.py; also runnable as a focused local regression.
No fixed render timeout in the viewer: tests delay labels and peer redraws.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
REPORT = '#r/549300TRUWO2CD2G5692/2026-03-31/CON'
DELAY = """() => {
  const original=window.fetch;
  window.fetch=(...args)=>original(...args).then(response=>
    /labels.json|peer_shape.json/.test(String(args[0]))
      ? new Promise(resolve=>setTimeout(()=>resolve(response),450)) : response);
  LABELS_LOADED=false; LABELS_PROMISE=null;
  SHAPE=null; SHAPE_PROMISE=null;
}"""
SOURCE_VISIBLE = """tid => {
  const sec=[...document.querySelectorAll('#tcontainer section[data-template]')]
    .find(s=>s.dataset.template===tid);
  if(!sec || !sec.querySelector('td.num')) return false;
  const target=document.activeElement;
  if(!sec.contains(target)) return false;
  if(sec.querySelector('.kpi-source') ? !target.matches('.kpi-source') : target!==sec.querySelector('h3')) return false;
  const box=target.getBoundingClientRect();
  const header=document.querySelector('header').getBoundingClientRect();
  return box.top>=header.bottom-2 && box.bottom<=innerHeight
    && box.left>=0 && box.right<=innerWidth && sec.closest('details').open;
}"""


def prepare(page, url, lang='en', metric='cet1', keyboard=False):
    page.goto(url+REPORT, wait_until='networkidle')
    page.wait_for_selector('#ovSection .ovcard')
    if page.evaluate('LANG') != lang:
        page.locator('#langBtn').click()
    card=page.locator(f'#ovSection .ovcard[data-m="{metric}"]')
    if keyboard:
        card.focus(); card.press('Enter')
    else:
        card.click()
    link=page.locator('#ovSection .mdet a[data-goto]').first
    link.wait_for(state='visible')
    return link


def activate(link, mode):
    if mode=='Enter':
        link.focus(); link.press('Enter')
    elif mode=='tap':
        link.tap()
    else:
        link.click()


def pruefe(browser, url):
    results, errors = [], []
    for width in (1280,390):
        modes=['click','Enter']+(['tap'] if width==390 else [])
        for lang in ('en','de'):
            for mode in modes:
                ctx=browser.new_context(viewport={'width':width,'height':844},
                                        is_mobile=width==390,has_touch=width==390)
                page=ctx.new_page()
                page.on('pageerror',lambda e:errors.append(str(e)))
                try:
                    link=prepare(page,url,lang,keyboard=mode=='Enter')
                    target=link.get_attribute('data-goto')
                    before=page.evaluate('location.hash')
                    page.evaluate(DELAY)
                    activate(link,mode)
                    page.wait_for_function(SOURCE_VISIBLE,arg=target,timeout=10000)
                    # A later peer-shape redraw must preserve keyboard focus.
                    page.wait_for_function('SHAPE!==null',timeout=10000)
                    page.wait_for_function(SOURCE_VISIBLE,arg=target,timeout=10000)
                    assert page.locator('#tfilter').input_value()==target
                    assert page.evaluate('location.hash')==before
                    # Repeat with a derived KPI and warm labels/peer cache.
                    card=page.locator('#ovSection .ovcard[data-m="hr"]')
                    card.click()
                    warm=page.locator('#ovSection .mdet a[data-goto]').first
                    warm.wait_for(state='visible')
                    activate(warm,mode)
                    page.wait_for_function(SOURCE_VISIBLE,arg=warm.get_attribute('data-goto'),timeout=10000)
                    results.append({'width':width,'lang':lang,'activation':mode,
                                    'cold_source':target,'warm_derived_source':warm.get_attribute('data-goto')})
                    print(f'  KPI-Quelle: {width}px · {lang} · {mode} · verzögert + warm: OK',flush=True)
                finally:
                    ctx.close()
    # Changing the filter/report while labels arrive cancels the obsolete jump.
    # Search-derived KPIs may have multiple sources in different theme blocks.
    for width,lang,mode in [(1280,'en','click'),(390,'de','tap')]:
        ctx=browser.new_context(viewport={'width':width,'height':844},
                                is_mobile=width==390,has_touch=width==390)
        page=ctx.new_page()
        page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(url+'#r/BFXS5XCH7N0Y05NIXW11/2025-12-31/CON',wait_until='networkidle')
            page.wait_for_selector('#ovSection .ovcard')
            if page.evaluate('LANG')!=lang:page.locator('#langBtn').click()
            query=page.evaluate("METRICDOC.get('forb_pe').en")
            for target in ('80.00.A','82.00.A'):
                page.locator('#tfilter').fill(query)
                if not page.locator('#tcontainer .mdet').count():
                    page.locator('.mchip[data-ms="forb_pe"]').click()
                link=page.locator(f'#tcontainer .mdet a[data-goto="{target}"]')
                link.wait_for(state='visible')
                before=page.evaluate('location.hash')
                page.evaluate(DELAY)
                activate(link,mode)
                page.wait_for_function(SOURCE_VISIBLE,arg=target,timeout=10000)
                assert page.evaluate('location.hash')==before
            results.append({'width':width,'lang':lang,'search_sources':['80.00.A','82.00.A']})
            print(f'  KPI-Suche: {width}px · {lang} · beide fachlichen Quellen erreichbar: OK',flush=True)
        finally:
            ctx.close()
    for action in ('filter','report'):
        ctx=browser.new_context(viewport={'width':1280,'height':844})
        page=ctx.new_page()
        page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            link=prepare(page,url)
            page.evaluate(DELAY)
            link.click()
            if action=='filter':
                page.locator('#tfilter').fill('68.00')
            else:
                page.evaluate("location.hash='#r/BFXS5XCH7N0Y05NIXW11/2025-12-31/CON'")
                page.wait_for_function("activeKey==='rs:BFXS5XCH7N0Y05NIXW11.CON|2025-12-31' && !!document.getElementById('tfilter')")
            before=page.evaluate("()=>({scroll:document.getElementById('main').scrollTop,windowY:scrollY})")
            after=page.evaluate("""async()=>{
              await ensureLabels();
              await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
              return {scroll:document.getElementById('main').scrollTop,windowY:scrollY};
            }""")
            assert before==after,(action,before,after)
            assert not page.locator('#tcontainer [data-jump-template]').count()
            results.append({'obsolete_jump_cancelled':action})
            print(f'  KPI-Quelle: ausstehender Sprung nach {action}-Wechsel verworfen: OK',flush=True)
        finally:
            ctx.close()
    assert not errors,errors
    return {'cases':len(results),'source_activations':24,'javascript_errors':errors,'results':results}


if __name__=='__main__':
    sys.path.insert(0,str(ROOT/'scripts'))
    import check_viewer_runtime as runtime
    from playwright.sync_api import sync_playwright
    server=runtime._serve()
    try:
        with sync_playwright() as p:
            binary=next((x for x in [runtime.CHROMIUM,'/usr/bin/chromium'] if Path(x).exists()),None)
            browser=p.chromium.launch(args=['--no-sandbox'],**({'executable_path':binary} if binary else {}))
            result=pruefe(browser,f'http://localhost:{runtime.PORT}/viewer_json.html')
            browser.close()
        print(json.dumps(result,ensure_ascii=False,indent=2))
    finally:
        server.shutdown();server.server_close()
