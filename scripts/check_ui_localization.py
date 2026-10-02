"""Exercise issue #127 in the browser, including cold loading and warm caches."""
from check_kpi_navigation import REPORT

HOLD_REPORTS = """() => {
  const fetchReport=window.fetch;
  const gate=new Promise(resolve=>window.releaseReports=resolve);
  window.fetch=(...args)=>fetchReport(...args).then(async response=>{
    if(String(args[0]).includes('/reports/')) await gate;
    return response;
  });
}"""


def pruefe(browser, url):
    errors, cases = [], 0
    for width in (1280, 390):
        context = browser.new_context(viewport={'width': width, 'height': 844})
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        try:
            page.goto(url + REPORT, wait_until='networkidle')
            initial = None
            for lang in ('en', 'de', 'en'):
                page.evaluate('hash=>location.hash=hash', REPORT)
                page.wait_for_selector('#tfilter')
                if page.evaluate('LANG') != lang:
                    page.locator('#langBtn').click()
                expected = 'Search: metric, template, title…' if lang == 'en' else 'Suchen: Kennzahl, Template, Titel…'
                page.wait_for_function('value=>document.querySelector("#tfilter")?.placeholder===value', arg=expected)
                values = page.evaluate('OV_METRICS().map(m=>[m.id,metricValue(byKey(activeKey),m)])')
                if initial is None:
                    initial = values
                assert values == initial, 'Translation changed KPI values'
                mixed = page.evaluate('''() => {
                    const r=REPORTS.find(isMixedCur), p=leiParts(r.entityID);
                    return '#r/'+p.lei+'/'+r.refPeriod+'/'+p.scope;
                }''')
                page.evaluate('hash=>location.hash=hash', mixed)
                phrase = 'varies by template' if lang == 'en' else 'je Template verschieden'
                page.wait_for_function('phrase=>document.querySelector("#main .rhead")?.textContent.includes(phrase)', arg=phrase)
                page.evaluate('PINS=new Set(REPORTS.slice(0,2).map(repKey));persist();location.hash="#compare"')
                page.wait_for_selector('#cmpBody table')
                assert page.locator('#main h2').inner_text() == ('Compare' if lang == 'en' else 'Vergleich')
                assert page.locator('#cmpBody th').first.inner_text() == ('Cell' if lang == 'en' else 'Zelle')
                assert page.locator('.chip button').first.get_attribute('title') == ('remove' if lang == 'en' else 'entfernen')
                # Exercise the real pin limit and confirm its translated dialog.
                messages = []
                page.once('dialog', lambda dialog: (messages.append(dialog.message), dialog.accept()))
                page.evaluate('''() => {
                    PINS=new Set(REPORTS.slice(0,4).map(repKey));
                    togglePin(repKey(REPORTS[4]));
                }''')
                assert messages == [('Compare at most 4 reports.' if lang == 'en' else 'Maximal 4 Reports vergleichen.')]
                for profile in ('esg', 'verg', 'headroom'):
                    page.evaluate('id=>location.hash="#benchmark?prof="+id', profile)
                    page.wait_for_function('id=>document.querySelector("#bmProfile")?.value===id && !document.querySelector("#main").hasAttribute("aria-busy")', arg=profile)
                    expected_options = page.evaluate('(PROFILES.map(p=>LANG==="en"?p.en:p.label))')
                    assert page.locator('#bmProfile option').all_text_contents() == expected_options
                    assert page.locator('label').filter(has=page.locator('#bmPct')).inner_text() == ('Percentile within peer group' if lang == 'en' else 'Perzentil je Peer-Gruppe')
                    if profile in ('esg', 'verg'):
                        note = page.evaluate('id=>{const p=PROFILES.find(p=>p.id===id);return LANG==="en"?p.note_en:p.note}', profile)
                        assert note in page.locator('#main .caveat').first.inner_text()
                    sources = page.locator('.dsrc').all_text_contents()
                    assert any(('reference dates' if lang == 'en' else 'Stichtage') in s for s in sources), sources
                    tails = page.locator('.dsum b').all_text_contents()
                    assert tails, 'No outlier margin counts exercised'
                    assert all(not any(word in s.split() for word in (('links', 'rechts') if lang == 'en' else ('left', 'right'))) for s in tails)
                    headers = page.evaluate('benchmarkCSV([],bmProf()).split("\\n").find(s=>s.startsWith("institution,"))')
                    assert headers.startswith('institution,lei,country,size_class,consolidation,reference_date,framework,')
                cases += 1
                print(f'  UI-Lokalisierung: {width}px · {lang} · Report/Compare/Profilcache/Diagramme: OK', flush=True)
        finally:
            context.close()
    for lang in ('en', 'de'):
        for view in ('report', 'compare'):
            context = browser.new_context()
            context.add_init_script('(' + HOLD_REPORTS + ')()')
            context.add_init_script('localStorage.setItem("p3dh",'+repr('{"lang":"'+lang+'","pins":["rs:549300TRUWO2CD2G5692.CON|2026-03-31"]}')+')')
            page = context.new_page()
            page.on('pageerror', lambda e: errors.append(str(e)))
            try:
                page.goto(url + (REPORT if view == 'report' else '#compare'), wait_until='domcontentloaded')
                expected = ('Loading report…' if view == 'report' else 'Loading 1 report(s)…') if lang == 'en' else ('Lade Report…' if view == 'report' else 'Lade 1 Report(s)…')
                page.wait_for_function('expected=>document.querySelector("#main .status")?.textContent.includes(expected)', arg=expected)
                page.evaluate('releaseReports()')
                page.wait_for_selector('#ovSection .ovcard' if view == 'report' else '#cmpBody table')
                cases += 1
                print(f'  UI-Ladezustand: {lang} · {view} · verzögertes Shard: OK', flush=True)
            finally:
                context.close()
    assert not errors, errors
    return {'cases': cases, 'javascript_errors': errors}


if __name__ == '__main__':
    from playwright.sync_api import sync_playwright
    import check_viewer_runtime as runtime

    server = runtime._serve()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
            print(pruefe(browser, f'http://localhost:{runtime.PORT}/viewer_json.html'))
            browser.close()
    finally:
        server.shutdown()
