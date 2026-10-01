"""Regression: authoritative missing pointer vs invalid/offline publication."""
import json
from measure import serve,ROOT,DATA
from playwright.sync_api import sync_playwright

def main():
    server=serve()
    with sync_playwright() as p:
     b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
     for case in ['legacy','invalid','offline']:
      ctx=b.new_context();page=ctx.new_page();seen=[]
      def fulfil(route):
       url=route.request.url;seen.append(url)
       if url=='https://viewer.test/viewer.html':route.fulfill(body=(ROOT/'processed/zweig_a/viewer_json.html').read_bytes(),content_type='text/html');return
       if url.endswith('favicon.ico'):route.fulfill(status=204);return
       if url.endswith('data_version.json'):
        if case=='offline':route.abort();return
        if case=='invalid':route.fulfill(body='{"schema":1,"revision":"broken"}',content_type='application/json');return
        route.fulfill(status=404 if 'raw.githubusercontent.com' in url else 503,headers={'Access-Control-Allow-Origin':'*'});return
       path=url.split('@data/',1)[-1] if '@data/' in url else url.split('/data/',1)[-1]
       route.fulfill(body=(DATA/path).read_bytes(),content_type='application/json',headers={'Access-Control-Allow-Origin':'*'})
      page.route('**/*',fulfil);page.goto('https://viewer.test/viewer.html#benchmark',wait_until='networkidle')
      if case=='legacy':
       page.wait_for_selector('.bmtable tbody tr');assert page.evaluate('DATA_REV') is None
       assert not any('cdn.jsdelivr.net' in x and x.endswith('data_version.json') for x in seen)
      else:
       assert not page.locator('.bmtable').count();assert not any(x.endswith('index.json') for x in seen)
      print(case,'PASS');ctx.close()
     b.close()
    server.shutdown()

if __name__=='__main__':main()
