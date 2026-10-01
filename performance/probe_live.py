"""Bounded HTTP and Chromium observations of the production delivery path."""
import json
import os
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'performance/results'
URL = 'https://tobias-run.github.io/P3DH/processed/zweig_a/viewer_json.html'
HOSTS = {
    'landing': 'https://tobias-run.github.io/P3DH/',
    'pages': URL,
    'cdn_index': 'https://cdn.jsdelivr.net/gh/Tobias-Run/P3DH@data/index.json',
    'raw_index': 'https://raw.githubusercontent.com/Tobias-Run/P3DH/data/index.json',
}

def main():
    records = []
    for name, url in HOSTS.items():
        for n in range(3):
            headers = OUT / f'headers_{name}_{n}.txt'
            cmd = ['curl', '-sS', '-L', '--compressed', '--connect-timeout', '8',
                   '--max-time', '15', '-D', str(headers), '-o', '/dev/null',
                   '-w', '%{json}', url]
            r = subprocess.run(cmd, capture_output=True, text=True)
            try:
                obj = json.loads(r.stdout)
            except ValueError:
                obj = {'output': r.stdout}
            obj.update(name=name, sample=n, exit_code=r.returncode, error=r.stderr)
            records.append(obj)
            print(name, n, obj.get('http_code'), obj.get('time_total'), flush=True)
    (OUT / 'live_http.json').write_text(json.dumps(records, indent=2))
    with sync_playwright() as p:
        proxy = {'server': os.environ['HTTPS_PROXY']} if os.environ.get('HTTPS_PROXY') else None
        browser = p.chromium.launch(executable_path='/usr/bin/chromium',
                    headless=True, args=['--no-sandbox'], proxy=proxy)
        observations=[]
        from measure import OBSERVE
        for sample in range(3):
            ctx=browser.new_context(viewport={'width':1440,'height':900})
            page=ctx.new_page();page.add_init_script(OBSERVE)
            errors,requests=[],[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('requestfailed',lambda r:errors.append(r.url+': '+str(r.failure)))
            page.on('response',lambda r:requests.append({'url':r.url,'status':r.status}))
            for visit in ['cold','warm']:
                if visit=='warm':page.goto('about:blank')
                errors.clear();requests.clear()
                result={'url':URL,'browser':browser.version,'sample':sample,'visit':visit}
                t=time.perf_counter()
                try:
                    page.goto(URL+'#benchmark',wait_until='domcontentloaded',timeout=20000)
                    page.wait_for_function('window.__perf?.ready.benchmark',timeout=20000)
                    result['ready_ms']=page.evaluate('__perf.ready.benchmark')
                    page.wait_for_load_state('networkidle',timeout=20000)
                    result['rows']=page.locator('.bmtable tbody tr').count()
                    result['resources']=page.evaluate('performance.getEntriesByType("resource").map(x=>x.toJSON())')
                    result['navigation']=page.evaluate('performance.getEntriesByType("navigation")[0].toJSON()')
                    result['observed']=page.evaluate('__perf')
                    if sample==2 and visit=='cold':page.screenshot(path=str(OUT/'live_benchmark.png'))
                except Exception as e:
                    result['failure']=str(e)
                result.update(errors=list(errors),responses=list(requests),elapsed_ms=(time.perf_counter()-t)*1000)
                observations.append(result)
                (OUT/'live_browser.json').write_text(json.dumps(observations,indent=2))
                print({k:v for k,v in result.items() if k not in ('resources','responses','navigation','observed')},flush=True)
            ctx.close()
        browser.close()

if __name__ == '__main__':
    main()
