"""Internal report links must remain in the viewer despite an external base URL."""
from playwright.sync_api import sync_playwright
from measure import serve, DATA

def main():
    server=serve();base=f'http://127.0.0.1:{server.server_port}'
    with sync_playwright() as p:
        b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        page=b.new_page();page.goto(base+'/candidate/viewer.html#benchmark',wait_until='networkidle')
        page.wait_for_selector('.bmtable tbody tr')
        target=page.locator('.bmtable td.bank a').first.get_attribute('href')
        page.evaluate("""()=>{const base=document.createElement('base');base.href='https://raw.githubusercontent.com/Tobias-Run/P3DH/test/viewer.html';document.head.prepend(base);}""")
        assert page.locator('.bmtable td.bank a').first.evaluate('(a)=>a.href').startswith('https://raw.githubusercontent.com/')
        # Reports still use local data in this harness; absolute request routes
        # avoid confusing an injected external base with unavailable report files.
        page.route('https://raw.githubusercontent.com/Tobias-Run/P3DH/test/data/**',lambda r:r.fulfill(body=(DATA/r.request.url.split('/test/data/',1)[1]).read_bytes(),content_type='application/json',headers={'Access-Control-Allow-Origin':'*'}))
        page.locator('.bmtable td.bank a').first.click()
        page.wait_for_selector('#ovSection .ovcard')
        assert page.url.startswith(base+'/candidate/viewer.html#r/')
        assert page.evaluate('location.hash')==target
        page.locator('#tabBenchmark').click();page.wait_for_selector('.bmtable tbody tr')
        page.evaluate("location.hash='#benchmark?country=Sweden'")
        page.wait_for_function("location.hash.includes('country=Sweden')")
        page.locator('.bmtable td.bank a').first.click();page.wait_for_selector('#ovSection .ovcard')
        assert 'country=Sweden' in page.url
        print('PASS: external base, report navigation, return and retained query');b.close()
    server.shutdown()

if __name__=='__main__':main()
