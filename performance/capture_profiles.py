"""Capture Chrome DevTools CPU profiles of three complete benchmark renders."""
import json
from playwright.sync_api import sync_playwright
from measure import OUT, serve

def main():
    server=serve();summaries={}
    with sync_playwright() as p:
        b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        for variant in ['baseline','candidate']:
            ctx=b.new_context();pg=ctx.new_page();cdp=ctx.new_cdp_session(pg)
            pg.goto(f'http://127.0.0.1:{server.server_port}/{variant}/viewer.html#benchmark',wait_until='networkidle')
            pg.wait_for_selector('.bmtable tbody tr');pg.evaluate('renderBenchmark()')
            cdp.send('Profiler.enable');cdp.send('Profiler.start')
            pg.evaluate('async()=>{for(let i=0;i<3;i++)await renderBenchmark();}')
            profile=cdp.send('Profiler.stop')['profile']
            (OUT/f'{variant}.cpuprofile').write_text(json.dumps(profile))
            nodes={n['id']:n['callFrame']['functionName'] or '(anonymous)' for n in profile['nodes']}
            times={}
            for ident,delta in zip(profile.get('samples',[]),profile.get('timeDeltas',[])):
                name=nodes[ident];times[name]=times.get(name,0)+delta/1000
            summaries[variant]={'duration_ms':(profile['endTime']-profile['startTime'])/1000,
                                 'self_ms':dict(sorted(times.items(),key=lambda x:x[1],reverse=True)[:20])}
            ctx.close()
        b.close()
    server.shutdown();(OUT/'cpu_summary.json').write_text(json.dumps(summaries,indent=2))
    print(json.dumps(summaries,indent=2))

if __name__=='__main__':main()
