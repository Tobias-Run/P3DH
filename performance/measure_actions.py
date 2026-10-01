"""Five sort/filter actions per profile after one settled load; synthetic latency."""
import argparse,json
from playwright.sync_api import sync_playwright
from measure import OUT,PROFILES,serve,interaction

parser=argparse.ArgumentParser();parser.add_argument('--output',default='issue117_actions.json');args=parser.parse_args()
server=serve();base=f'http://127.0.0.1:{server.server_port}';results=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    for profile,cfg in PROFILES.items():
        ctx=browser.new_context(viewport={'width':cfg['width'],'height':cfg['height']})
        page=ctx.new_page();cdp=ctx.new_cdp_session(page)
        cdp.send('Emulation.setCPUThrottlingRate',{'rate':cfg['cpu']})
        page.goto(base+'/candidate/viewer.html#benchmark',wait_until='networkidle')
        page.wait_for_selector('.bmtable tbody tr')
        for run in range(5):
            sort=interaction(page,"bmSort.dir*=-1; renderBenchmark()")
            filtering=interaction(page,"document.getElementById('reportFilter').value='bank';renderReportList();renderBenchmark()")
            page.evaluate("async()=>{document.getElementById('reportFilter').value='';renderReportList();await renderBenchmark();}")
            results.append({'profile':profile,'run':run,'sort':sort,'filter':filtering})
            (OUT/args.output).write_text(json.dumps(results,indent=2))
            print(profile,run,'sort',round(sort['paint_ms']),'filter',round(filtering['paint_ms']),flush=True)
        ctx.close()
    browser.close()
server.shutdown()
