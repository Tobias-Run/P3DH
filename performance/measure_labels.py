"""First table immediately after overview, or after 1.5 s reading, five repeats."""
import json
import argparse
from playwright.sync_api import sync_playwright
from measure import OUT,PROFILES,OBSERVE,serve
from test_ux import report_url

parser=argparse.ArgumentParser()
parser.add_argument('--variant',default='candidate')
parser.add_argument('--runs',type=int,default=5)
parser.add_argument('--output',default='issue116_expansion.json')
args=parser.parse_args()
server=serve();base=f'http://127.0.0.1:{server.server_port}';results=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    for run in range(args.runs):
        for profile in ['desktop','mobile4g']:
            cfg=PROFILES[profile]
            for delay in [0,1500]:
                ctx=b.new_context(viewport={'width':cfg['width'],'height':cfg['height']})
                page=ctx.new_page();page.add_init_script(OBSERVE)
                cdp=ctx.new_cdp_session(page);cdp.send('Network.enable')
                cdp.send('Network.emulateNetworkConditions',{'offline':False,'latency':cfg['latency'],
                    'downloadThroughput':cfg['bps'],'uploadThroughput':cfg['bps']})
                cdp.send('Emulation.setCPUThrottlingRate',{'rate':cfg['cpu']})
                page.goto(report_url(base).replace('/candidate/','/'+args.variant+'/'),wait_until='domcontentloaded')
                page.wait_for_function('window.__perf?.ready.report')
                if delay:page.wait_for_timeout(delay)
                before=page.evaluate("()=>{const t=performance.now();document.querySelector('details.theme').open=true;return t;}")
                page.wait_for_function("document.querySelector('details.theme .tbody').dataset.done==='1'")
                ms=page.evaluate('performance.now()')-before
                results.append({'run':run,'profile':profile,'reading_ms':delay,'expand_ms':ms,
                    'report_ready_ms':page.evaluate('__perf.ready.report'),'cells':page.locator('details.theme td.num').count()})
                (OUT/args.output).write_text(json.dumps(results,indent=2))
                print(profile,delay,round(ms),flush=True);ctx.close()
    b.close()
server.shutdown()
