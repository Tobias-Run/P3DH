"""Verify exact source-cell selection, conversion, redraws and safe fallbacks."""
from check_kpi_navigation import prepare, activate, SOURCE_VISIBLE, DELAY

EXPECTED = {'cet1': [('0050', '0010')], 'trea': [('0040', '0010')],
            'hr': [('0070', '0010'), ('0190', '0010')]}


def coordinates(page):
    return sorted(tuple(x) for x in page.locator('#tcontainer td.kpi-source').evaluate_all(
        'cells=>cells.map(c=>[c.dataset.row,c.dataset.col])'))


def pruefe(browser, url):
    errors, cases, activations = [], 0, 0
    for width, lang, dark in ((1280, 'en', False), (390, 'de', False),
                              (1280, 'de', True), (390, 'en', True)):
        context = browser.new_context(viewport={'width': width, 'height': 844},
                                      is_mobile=width == 390, has_touch=width == 390,
                                      reduced_motion='reduce' if dark else 'no-preference')
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        try:
            for metric in EXPECTED:
                link = prepare(page, url, lang, metric, keyboard=dark)
                page.evaluate('dark=>{DARK=dark;applyTheme();}', dark)
                before = page.evaluate('OV_METRICS().map(m=>[m.id,metricValue(byKey(activeKey),m)])')
                page.evaluate(DELAY)
                activate(link, 'Enter' if dark else ('tap' if width == 390 else 'click'))
                if dark:
                    page.wait_for_selector('.kpi-source')
                    assert page.evaluate(SOURCE_VISIBLE, '61.00'), 'Reduced motion still animates the jump'
                page.wait_for_function(SOURCE_VISIBLE, arg='61.00')
                page.wait_for_function('SHAPE!==null')
                page.wait_for_function(SOURCE_VISIBLE, arg='61.00')
                assert coordinates(page) == sorted(EXPECTED[metric])
                assert page.locator('.kpi-source').first.evaluate('c=>getComputedStyle(c).outlineStyle') == 'solid'
                assert page.locator('.kpi-source').first.get_attribute('aria-label')
                assert before == page.evaluate('OV_METRICS().map(m=>[m.id,metricValue(byKey(activeKey),m)])')
                # Monetary display may change scale; selection must still identify the raw cell.
                if metric == 'trea':
                    for scale in ('1', '1000000000'):
                        page.locator('#scaleSel').select_option(scale)
                        page.wait_for_selector('.kpi-source[data-row="0040"]')
                        assert coordinates(page) == EXPECTED['trea']
                    page.locator('#eurChk').check()
                    page.wait_for_selector('.kpi-source[data-row="0040"]')
                    assert coordinates(page) == EXPECTED['trea']
                # Unrelated manual filtering discards the selection.
                page.locator('#tfilter').fill('68.00')
                assert page.locator('.kpi-source').count() == 0
                assert page.evaluate('SOURCE_SELECTION') is None
                activations += 1
            cases += 1
            print(f'  Exakte KPI-Quelle: {width}px · {lang} · dark={dark} · CET1/TREA/Headroom: OK', flush=True)
        finally:
            context.close()
    context = browser.new_context()
    page = context.new_page()
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        page.goto(url+'#r/21380057HUGFEAF25W84/2025-12-31/CON', wait_until='networkidle')
        page.wait_for_selector('.ovcard[data-m="trea"]')
        before = page.evaluate('''() => ({raw:tplValue(byKey(activeKey),'61.00','0040','0010'),
            overview:metricValue(byKey(activeKey),METRICDOC.get('trea')),
            currency:curOf(byKey(activeKey),'61.00')})''')
        assert before['currency'] == 'SEK'
        assert before['raw']/1e9 != before['overview']
        page.locator('.ovcard[data-m="trea"]').click()
        page.locator('.mdet a[data-goto]').first.click()
        page.wait_for_function(SOURCE_VISIBLE, arg='61.00')
        assert coordinates(page) == EXPECTED['trea']
        original_display = page.locator('.kpi-source').inner_text()
        page.locator('#eurChk').check()
        page.wait_for_selector('.kpi-source')
        assert coordinates(page) == EXPECTED['trea']
        assert original_display != page.locator('.kpi-source').inner_text()
        assert before['raw'] == page.evaluate("tplValue(byKey(activeKey),'61.00','0040','0010')")
        assert before['overview'] == page.evaluate("metricValue(byKey(activeKey),METRICDOC.get('trea'))")
        cases += 1
        activations += 1
        print('  KPI-Quelle: SEK/EUR · umgerechneter Wert, unveränderte exakte Quellzelle: OK', flush=True)
    finally:
        context.close()
    for width in (1280, 390):
        for scenario in ('missing', 'conflicting', 'dimension'):
            context = browser.new_context(viewport={'width': width, 'height': 844})
            page = context.new_page()
            page.on('pageerror', lambda e: errors.append(str(e)))
            try:
                link = prepare(page, url)
                page.evaluate('''scenario=>{
                    const rep=byKey(activeKey), cells=rep.templates.get('61.00');
                    const source=cells.find(c=>c.row==='0050' && c.col==='0010');
                    if(scenario==='missing') rep.templates.set('61.00',cells.filter(c=>c!==source));
                    if(scenario==='conflicting') cells.push({...source,val:'0.999'});
                    if(scenario==='dimension'){
                        source.dim='source-slice';
                        cells.push({...source,dim:'other-slice',val:'0.2'});
                        DIMSEL.set('61.00','other-slice');
                    }
                }''', scenario)
                link.click()
                page.wait_for_function(SOURCE_VISIBLE, arg='61.00')
                if scenario == 'dimension':
                    assert page.locator('.dimsel[data-tid="61.00"]').input_value() == 'source-slice'
                    assert coordinates(page) == EXPECTED['cet1']
                    # Another slice's same coordinate must never get this highlight.
                    page.locator('.dimsel[data-tid="61.00"]').select_option('other-slice')
                    page.wait_for_selector('.source-note')
                    assert page.locator('.kpi-source').count() == 0
                else:
                    assert page.locator('.kpi-source').count() == 0
                    assert page.locator('.source-note').inner_text().startswith('No matching source cell')
                    assert page.evaluate('document.activeElement.tagName') == 'H3'
                cases += 1
                activations += 1
                print(f'  KPI-Quelle: {width}px · {scenario} · keine falsche Zelle markiert: OK', flush=True)
            finally:
                context.close()
    assert not errors, errors
    return {'cases': cases, 'source_activations': activations, 'javascript_errors': errors}


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
        server.server_close()
