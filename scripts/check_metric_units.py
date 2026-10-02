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
    return {'cases': len(cases), 'results': cases}


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
