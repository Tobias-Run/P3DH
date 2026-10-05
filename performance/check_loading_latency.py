"""Browser regression: slow optional downloads must not gate the report series.

Uses locally served, real dataset files. Delays are controlled, not live speed
measurements. Pass --baseline-ref to compare an earlier viewer on the same data.
"""
import argparse
import asyncio
import functools
import http.server
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import check_viewer_runtime as runtime


async def check(baseline_ref=None):
    baseline = subprocess.check_output(['git', 'show', baseline_ref+':processed/zweig_a/viewer_json.html'], cwd=ROOT) if baseline_ref else None

    class Handler(runtime._H):
        def do_GET(self):
            if self.path.split('?', 1)[0] == '/baseline.html' and baseline:
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(baseline)))
                self.end_headers()
                self.wfile.write(baseline)
            else:
                super().do_GET()

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(runtime.VIEWER_DIR)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    from playwright.async_api import async_playwright
    results=[];errors=[]
    try:
        async with async_playwright() as p:
            browser=await p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            for version in (['baseline', 'fixed'] if baseline else ['fixed']):
                for delayed in ['labels', 'non_km1']:
                    page=await browser.new_page(viewport={'width':1440,'height':900})
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    requested=[]
                    page.on('request',lambda r:requested.append(r.url))
                    async def slow(route):
                        await asyncio.sleep(4)
                        if not page.is_closed():
                            await route.continue_()
                    pattern='**/labels.json' if delayed=='labels' else '**/benchmark/82.00.A.*.json'
                    await page.route(pattern,slow)
                    file='baseline.html' if version=='baseline' else 'viewer_json.html'
                    t=time.perf_counter()
                    await page.goto(f'http://127.0.0.1:{server.server_port}/{file}#r/549300TRUWO2CD2G5692/2026-03-31/CON',wait_until='domcontentloaded')
                    await page.wait_for_selector('.ovcard')
                    overview=time.perf_counter()-t
                    await page.wait_for_selector('#tsSection .ts',timeout=15000)
                    series=time.perf_counter()-t
                    labels=any('/labels.json' in u for u in requested)
                    if version=='fixed':
                        assert not labels, 'report/time series unnecessarily fetched labels'
                        if delayed=='non_km1':
                            assert not await page.evaluate("haveBenchmark(['82.00.A'])"), 'time series waited for unrelated overview data'
                        # The dictionary still loads when explicitly needed.
                        await page.unroute(pattern,slow)
                        await page.evaluate('ensureLabels()')
                        assert await page.evaluate('LABELS_LOADED && CB.size>0')
                    results.append({'version':version,'delayed':delayed,'delay_seconds':4,
                                    'overview_seconds':round(overview,3),'series_seconds':round(series,3),
                                    'labels_requested_before_series':labels})
                    await page.close()
            await browser.close()
    finally:
        server.shutdown();server.server_close()
    assert not errors, errors
    return {'method':'local real data, controlled 4-second delay; not a live timing benchmark',
            'cases':results,'javascript_errors':errors}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--baseline-ref')
    args=parser.parse_args()
    print(json.dumps(asyncio.run(check(args.baseline_ref)),indent=2))
