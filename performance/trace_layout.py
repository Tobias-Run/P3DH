"""Record actual layout-shift sources, including late optional report content."""
import json
import argparse
from playwright.sync_api import sync_playwright
from measure import OUT,serve,PROFILES
from test_ux import report_url

parser=argparse.ArgumentParser();parser.add_argument('--output',default='layout_sources.json');args=parser.parse_args()
server=serve();base=f'http://127.0.0.1:{server.server_port}';results=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    for profile,cfg in PROFILES.items():
        for scenario in ['benchmark','report']:
            ctx=b.new_context(viewport={'width':cfg['width'],'height':cfg['height']})
            page=ctx.new_page();cdp=ctx.new_cdp_session(page)
            cdp.send('Emulation.setCPUThrottlingRate',{'rate':cfg['cpu']})
            cdp.send('Network.enable');cdp.send('Network.emulateNetworkConditions',{'offline':False,'latency':cfg['latency'],
                'downloadThroughput':cfg['bps'],'uploadThroughput':cfg['bps']})
            page.add_init_script("""window.shifts=[];new PerformanceObserver(l=>{
              for(const e of l.getEntries()) if(!e.hadRecentInput) shifts.push({time:e.startTime,value:e.value,
                sources:e.sources.map(s=>({node:s.node?.nodeName,id:s.node?.id,cls:s.node?.getAttribute?.('class'),
                  previous:s.previousRect.toJSON(),current:s.currentRect.toJSON()}))});
            }).observe({type:'layout-shift',buffered:true});""")
            page.goto(report_url(base) if scenario=='report' else base+'/candidate/viewer.html#benchmark',wait_until='networkidle')
            page.wait_for_function('BM_LOADED');page.wait_for_timeout(2000)
            results.append({'profile':profile,'scenario':scenario,'shifts':page.evaluate('shifts')})
            page.screenshot(path=str(OUT/f'layout_{profile}_{scenario}.png'))
            ctx.close()
    b.close()
server.shutdown();(OUT/args.output).write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
