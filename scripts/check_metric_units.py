"""Check displayed monetary KPI units through real language switches."""
from check_kpi_navigation import REPORT


def pruefe(browser, url):
    cases, errors = [], []
    for width in (1280, 390):
        context = browser.new_context(viewport={'width': width, 'height': 844})
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        try:
            original = None
            for lang in ('en', 'de', 'en'):
                unit = 'bn EUR' if lang == 'en' else 'Mrd. EUR'
                page.goto(url + REPORT, wait_until='networkidle')
                if page.evaluate('LANG') != lang:
                    page.locator('#langBtn').click()
                page.wait_for_function("""unit =>
                    document.querySelector('.ovcard[data-m="trea"] .ovu')?.textContent === unit
                """, arg=unit)
                values = page.evaluate("""() => {
                    const rep = REPORTS.find(r=>repKey(r)===activeKey);
                    return OV_METRICS().map(m=>[m.id,metricValue(rep,m)]);
                }""")
                if original is None:
                    original = values
                assert values == original, 'Language switch changed KPI values'
                page.locator('.ovcard[data-m="trea"]').click()
                page.wait_for_selector('#ovSection .mdet a[data-goto]')
                assert page.locator('#ovSection .mdet a[data-goto]').first.get_attribute('data-goto') == '61.00'
                page.wait_for_selector('#tsSection .ts table')
                series = page.locator('#tsSection td.rl').all_text_contents()
                scale = 'bn' if lang == 'en' else 'Mrd.'
                for metric in ('TREA', 'CET1'):
                    assert any(f'{metric} ({scale}) EUR' in s for s in series), series
                if lang == 'en':
                    assert all('Mrd' not in text for text in page.locator('#ovSection, #tsSection').all_inner_texts())
                page.goto(url + '#benchmark?prof=km1', wait_until='networkidle')
                for metric in ('trea', 'cet1_amt'):
                    heading = page.locator(f'.bmtable th[data-k="{metric}"]')
                    heading.wait_for()
                    assert f'({unit})' in heading.inner_text(), heading.inner_text()
                page.reload(wait_until='networkidle')
                assert page.evaluate('LANG') == lang, 'Language was not persisted'
                assert f'({unit})' in page.locator('.bmtable th[data-k="trea"]').inner_text()
                cases.append({'width': width, 'lang': lang, 'unit': unit})
                print(f'  KPI-Einheiten: {width}px · {lang} · {unit} · Overview/Zeitreihe/Benchmark: OK', flush=True)
        finally:
            context.close()
    assert not errors, errors
    audit = pruefe_audit(browser, url)
    return {'cases': len(cases), 'results': cases, 'audit': audit}


def pruefe_audit(browser, url):
    """Every benchmark profile, plus report/compare scale controls and CSV."""
    context = browser.new_context(viewport={'width': 1280, 'height': 844})
    page = context.new_page()
    errors, seen, profiles = [], set(), 0
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        for lang in ('en', 'de'):
            page.goto(url + REPORT, wait_until='networkidle')
            if page.evaluate('LANG') != lang:
                page.locator('#langBtn').click()
            page.wait_for_function('LANG === document.documentElement.lang')
            registry = page.evaluate('PROFILES.map(p=>({id:p.id,metrics:p.metrics}))')
            for profile in registry:
                page.evaluate('id=>location.hash="#benchmark?prof="+id', profile['id'])
                page.wait_for_function('id=>document.querySelector("#bmProfile")?.value===id && !document.querySelector("#main").hasAttribute("aria-busy")', arg=profile['id'])
                metadata = page.evaluate('ids=>ids.map(id=>({id,unit:METRICDOC.get(id).unit}))', profile['metrics'])
                for metric in metadata:
                    if metric['unit'] not in ('Mrd EUR', 'Personen'):
                        continue
                    expected = ('bn EUR' if lang == 'en' else 'Mrd. EUR') if metric['unit'] == 'Mrd EUR' else ('people' if lang == 'en' else 'Personen')
                    assert f'({expected})' in page.locator(f'.bmtable th[data-k="{metric["id"]}"]').inner_text()
                    seen.add(metric['id'])
                notes = page.locator('.dcard .dnote').all_text_contents()
                if profile['id'] == 'headroom':
                    assert ('Difference in percentage points' if lang == 'en' else 'Differenz in Prozentpunkten') in notes
                if profile['id'] == 'verg':
                    assert ('Amount per head in EUR (ECB rate)' if lang == 'en' else 'Betrag je Kopf, in EUR (EZB-Kurs)') in notes
                    assert ('Absolute count' if lang == 'en' else 'Absolutzahl') in notes
                csv = page.evaluate('benchmarkCSV(benchmarkRows().slice(0,2),bmProf())')
                if lang == 'en':
                    assert all(word not in csv for word in ('Mrd', 'Tsd.', 'Mio.', 'Personen'))
                profiles += 1
            page.evaluate('''() => {
                const rep=REPORTS.find(r=>r.entityID.includes('549300TRUWO2CD2G5692') && r.refPeriod==='2026-03-31');
                PINS=new Set([repKey(rep)]); persist();
            }''')
            for route, target in ((REPORT, '#tcontainer .scalenote'), ('#compare', '#cmpBody .scalenote')):
                page.evaluate('hash=>location.hash=hash', route)
                page.wait_for_selector('#ovSection' if route == REPORT else '#cmpBody table')
                page.wait_for_selector('#scaleSel')
                if route == REPORT:
                    page.locator('.ovcard[data-m="trea"]').click()
                    page.locator('.mdet a[data-goto]').first.click()
                    page.wait_for_selector('#tcontainer section[data-template="61.00"] td.num')
                for scale, expected in (('1000', 'k' if lang == 'en' else 'Tsd.'), ('1000000', 'm' if lang == 'en' else 'Mio.'), ('1000000000', 'bn' if lang == 'en' else 'Mrd.')):
                    page.locator('#scaleSel').select_option(scale)
                    page.wait_for_function('([target,unit])=>document.querySelector(target)?.textContent.includes(unit+" EUR")', arg=[target, expected])
            print(f'  Einheiten-Audit: {lang} · {len(registry)} Profile · Report/Compare k/m/bn · CSV: OK', flush=True)
        assert len(seen) == 8, seen  # Seven billion-EUR metrics and one headcount.
        assert not errors, errors
        return {'profiles': profiles, 'metrics': sorted(seen), 'javascript_errors': errors}
    finally:
        context.close()


if __name__ == '__main__':
    from pathlib import Path
    from playwright.sync_api import sync_playwright
    import check_viewer_runtime as runtime

    server = runtime._serve()
    try:
        with sync_playwright() as pw:
            executable = '/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else runtime.CHROMIUM
            browser = pw.chromium.launch(executable_path=executable, args=['--no-sandbox'])
            print(pruefe(browser, f'http://localhost:{runtime.PORT}/viewer_json.html'))
            browser.close()
    finally:
        server.shutdown()
