"""Native, TLS-verified production Pages measurements with CDP cache/byte evidence.

No interception/fulfilment of requests. Requires Chromium to trust the managed
proxy CA in its NSS database; TLS verification is never disabled. Traffic uses
the inherited HTTPS proxy. Lab throttling is distinct from physical phone testing.
"""
import argparse,hashlib,json,os,time
from pathlib import Path
from playwright.sync_api import sync_playwright
from measure import OBSERVE, PROFILES, snapshot, interaction

URL='https://tobias-run.github.io/P3DH/processed/zweig_a/viewer_json.html'
ROOT=Path(__file__).resolve().parents[1]

def action(page, expression):
    start=page.evaluate('performance.now()')
    result=interaction(page,expression)
    tasks=page.evaluate('start=>__perf.longtasks.filter(x=>x.start>=start)',start)
    result['blocking_ms']=sum(max(0,t['duration']-50) for t in tasks)
    result['longtask_count']=len(tasks)
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--revision',required=True)
    parser.add_argument('--runs',type=int,default=5)
    parser.add_argument('--output',default='production_2026-10-02')
    args=parser.parse_args();out=ROOT/'performance/results'/args.output;out.mkdir(parents=True,exist_ok=True)
    reports=json.loads((ROOT/'performance/results/snapshot.json').read_text())['reports']
    rep=reports[0];lei=rep['entityID'][3:23];scope=rep['entityID'].split('.')[-1]
    fragments={'benchmark':'#benchmark','report':f'#r/{lei}/{rep["refPeriod"]}/{scope}'}
    records=[]
    with sync_playwright() as p:
        launch={'executable_path':'/usr/bin/chromium','args':['--no-sandbox']}
        if os.environ.get('HTTPS_PROXY'):launch['proxy']={'server':os.environ['HTTPS_PROXY']}
        browser=p.chromium.launch(**launch)
        for run in range(args.runs):
            for profile,cfg in PROFILES.items():
                for scenario,fragment in fragments.items():
                    ctx=browser.new_context(viewport={'width':cfg['width'],'height':cfg['height']},device_scale_factor=1)
                    page=ctx.new_page();page.set_default_timeout(60000);page.add_init_script(OBSERVE)
                    cdp=ctx.new_cdp_session(page);cdp.send('Network.enable')
                    cdp.send('Emulation.setCPUThrottlingRate',{'rate':cfg['cpu']})
                    cdp.send('Network.emulateNetworkConditions',{'offline':False,'latency':cfg['latency'],
                        'downloadThroughput':cfg['bps'],'uploadThroughput':cfg['bps']})
                    errors=[];failed=[];network={}
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    page.on('requestfailed',lambda r:failed.append({'url':r.url,'error':r.failure}))
                    def response(e):
                        r=e['response'];h={k.lower():v for k,v in r['headers'].items()}
                        network.setdefault(e['requestId'],{}).update({'url':r['url'],'status':r['status'],
                            'protocol':r['protocol'],'fromDiskCache':r.get('fromDiskCache',False),
                            'fromServiceWorker':r.get('fromServiceWorker',False),
                            'headers':{k:h[k] for k in ['cache-control','content-encoding','etag','timing-allow-origin'] if k in h}})
                    cdp.on('Network.responseReceived',response)
                    cdp.on('Network.requestServedFromCache',lambda e:network.setdefault(e['requestId'],{}).update({'servedFromCache':True}))
                    cdp.on('Network.loadingFinished',lambda e:network.setdefault(e['requestId'],{}).update({'encodedDataLength':e['encodedDataLength']}))
                    for visit in ['cold','warm']:
                        if visit=='warm':page.goto('about:blank')
                        errors.clear();failed.clear();network.clear()
                        rec={'variant':'pages','profile':profile,'scenario':scenario,'visit':visit,'run':run,
                             'browser':browser.version,'url':URL+fragment,'timestamp_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
                        try:
                            page.goto(URL+fragment,wait_until='domcontentloaded')
                            page.wait_for_function(f'window.__perf?.ready.{scenario}')
                            page.wait_for_function('BM_LOADED')
                            page.wait_for_load_state('networkidle');page.wait_for_timeout(2000)
                            revision=page.evaluate('DATA_REV');assert revision==args.revision,('Dataset changed',revision,args.revision)
                            assert page.evaluate('!!BM_MANIFEST'),'Missing production manifest'
                            if scenario=='benchmark':
                                assert page.locator('.bmtable tbody tr').count()<=100
                                assert not any('/benchmark.json' in x.get('url','') for x in network.values())
                            rec.update(initial=snapshot(page,cdp),errors=list(errors),request_failures=list(failed),
                                data_revision=revision,network=list(network.values()),interactions={})
                            if scenario=='benchmark' and visit=='cold':
                                rec['interactions']['sort']=action(page,'bmSort.dir*=-1;renderBenchmark()')
                                rec['interactions']['filter']=action(page,"document.getElementById('reportFilter').value='bank';renderReportList();renderBenchmark()")
                            if scenario=='report' and visit=='cold':
                                rec['interactions']['expand']=page.evaluate("""async()=>{
                                  const d=document.querySelector('details.theme');const start=performance.now();d.open=true;
                                  await new Promise((resolve,reject)=>{const until=performance.now()+30000;const poll=()=>{
                                    if(d.querySelector('.tbody').dataset.done==='1')return requestAnimationFrame(()=>requestAnimationFrame(resolve));
                                    if(performance.now()>until)return reject(new Error('Expansion timed out'));setTimeout(poll,10);};poll();});
                                  return {paint_ms:performance.now()-start};
                                }""")
                            if run==args.runs-1 and visit=='cold':page.screenshot(path=str(out/f'{profile}_{scenario}.png'))
                        except Exception as e:rec.update(failure=str(e),errors=list(errors),request_failures=list(failed),network=list(network.values()))
                        rec['errors']=list(errors)
                        if visit=='cold':page.evaluate('localStorage.clear()') # retain HTTP cache, reset expanded/saved UI
                        records.append(rec);(out/'measurements.json').write_text(json.dumps(records,indent=2))
                        print(run,profile,scenario,visit,'FAIL '+rec['failure'][:100] if 'failure'in rec else round(rec['initial']['ready'][scenario]),flush=True)
                    ctx.close()
        browser.close()
    assert not any('failure' in r or r.get('errors') for r in records),'Production failures recorded'

if __name__=='__main__':main()
