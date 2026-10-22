"""Actual-browser checks for usable benchmark coverage and peer populations."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import check_viewer_runtime as runtime


def check():
    from playwright.sync_api import sync_playwright
    runtime.PORT=8823;server=runtime._serve();errors=[];results=[]
    base=f'http://localhost:{runtime.PORT}/viewer_json.html'
    try:
        with sync_playwright() as p:
            binary=next((s for s in [runtime.CHROMIUM,'/usr/bin/chromium'] if Path(s).exists()),None)
            browser=p.chromium.launch(args=['--no-sandbox'],**({'executable_path':binary} if binary else {}))
            for width,lang in [(1280,'en'),(390,'de')]:
                page=browser.new_page(viewport={'width':width,'height':844})
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(base+'#benchmark?peer=cluster&d=2026-03-31',wait_until='networkidle')
                page.wait_for_selector('#bmCoverage')
                if lang=='de':page.click('#langBtn');page.wait_for_selector('#bmCoverage')
                summary=page.evaluate("""()=>({
                  groups:document.querySelectorAll('#bmCluster optgroup').length,
                  usable:document.querySelector('#bmCluster optgroup').querySelectorAll('option').length,
                  coverage:peerCoverage(advancedSelection(benchmarkRows()).rows,bmProf()).map(d=>({id:d.metric.id,valid:d.comparable,groups:d.usableGroups,ranked:d.ranked}))})""")
                assert summary['groups']==2
                assert 0<summary['usable']<42
                assert page.locator('#bmCoverage tr[data-coverage=cet1]').count()==1
                page.select_option('#bmProfile','npl')
                page.wait_for_function("BMP==='npl' && document.querySelector('#bmCoverage [data-coverage=npl]')")
                assert page.evaluate("peerCoverage(advancedSelection(benchmarkRows()).rows,bmProf())[0].ranked")==0
                assert page.locator('#bmCluster optgroup').first.locator('option').count()==0
                results.append({'width':width,'lang':lang,'coverage':summary,'missing_march_npl':'pass'})
                page.close()
            page=browser.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base+'#benchmark?peer=cluster&prof=npl&d=2025-12-31&pct=1',wait_until='networkidle')
            page.wait_for_selector('#bmCoverage')
            group='60359f158ce7'
            before=page.evaluate("""id=>{
              const rows=advancedSelection(benchmarkRows()).rows;
              const ranks=percentileMap(rows,'npl','cluster');
              return Object.fromEntries(rows.filter(r=>clusterOf(r)===id).map(r=>[r.key,ranks.get(r.key)]));
            }""",group)
            page.select_option('#bmCluster',group)
            page.wait_for_function('(id)=>BM_CLUSTER===id',arg=group)
            after=page.evaluate("""()=>{
              const rows=advancedSelection(benchmarkRows()).rows,ranks=percentileMap(rows,'npl','cluster');
              return Object.fromEntries(rows.map(r=>[r.key,ranks.get(r.key)]));
            }""")
            assert len(before)==5 and before==after,(before,after)
            page.close()
            page=browser.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base+'#benchmark?prof=npl&d=2025-12-31&pct=1',wait_until='networkidle')
            page.wait_for_selector('.bmtable')
            key='rs:549300TRUWO2CD2G5692.CON|2025-12-31'
            rank="key=>percentileMap(advancedSelection(benchmarkRows()).rows,'npl',BM_PEER).get(key)"
            initial=page.evaluate(rank,key)
            page.fill('#reportFilter',"UNICREDIT, SOCIETA' PER AZIONI")
            page.wait_for_function("benchmarkDisplayRows(advancedSelection(benchmarkRows()).rows).length===1")
            assert page.evaluate(rank,key)==initial
            assert page.locator('.bmtable tbody tr[data-key]').count()==1
            assert initial['n']>=5
            page.close()
            for width,lang in [(1280,'en'),(390,'de')]:
                page=browser.new_page(viewport={'width':width,'height':900})
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(base+'#r/549300TRUWO2CD2G5692/2025-12-31/CON',wait_until='networkidle')
                page.wait_for_selector('#ovBenchmark')
                if lang=='de':page.click('#langBtn');page.wait_for_selector('#ovBenchmark')
                page.click('#tabBenchmark');page.wait_for_selector('#bmReferenceSummary')
                assert page.evaluate("BM_REF==='rs:549300TRUWO2CD2G5692.CON'")
                assert page.locator('.analysis-card').count()==5
                assert page.locator('#bmModelWarning').count()==1
                assert page.locator('#bmDate').input_value()=='2025-12-31'
                population=page.evaluate('comparisonPopulation().rows.length')
                page.locator('#bmMembers summary').click()
                member=page.locator('[data-peer-member]:not([disabled])').first
                entity=member.get_attribute('data-peer-member');member.uncheck()
                page.wait_for_function('(n)=>comparisonPopulation().rows.length===n',arg=population-1)
                page.locator('#bmMembers summary').click();page.check('#bmConfirmMembers')
                page.wait_for_function('BM_CONFIRMED')
                shared=page.url;page.reload(wait_until='networkidle');page.wait_for_selector('#bmReferenceSummary')
                assert page.evaluate('(entity)=>BM_EXCLUDED.has(entity)',entity)
                assert page.evaluate('BM_CONFIRMED') and page.url==shared
                stats=page.evaluate("""()=>{
                  const m=METRICDOC.get('npl'),s=analysisStats(comparisonPopulation().rows,m,bmProf());
                  return {n:s.n,p:analysisRank(metricValue(analysisReference(),m),s)};
                }""")
                assert stats['n']>=5
                exported=page.evaluate('referenceAnalysisCSV()')
                import csv,io
                records=list(csv.DictReader(io.StringIO('\n'.join(l for l in exported.splitlines() if not l.startswith('#')))))
                npl=next(r for r in records if r['metric']=='npl')
                assert int(npl['peer_n'])==stats['n'] and abs(float(npl['percentile'])-stats['p'])<1e-8
                assert '# Dataset revision:' in exported and entity not in exported.split('# Exact comparison report keys: ')[1].split('\n')[0]
                page.locator('[data-benchmark-source=npl]').click()
                page.wait_for_function("VIEW==='reports' && OPENMETRIC==='npl'")
                report_rank=page.evaluate("overviewPercentiles().get('npl').get('rs:549300TRUWO2CD2G5692.CON|2025-12-31')")
                assert report_rank['n']==stats['n'] and abs(report_rank['p']-stats['p'])<1e-8
                assert page.locator('#ctxChk').is_disabled()
                country=page.evaluate("META.get('549300TRUWO2CD2G5692').country")
                page.select_option('#fCountry',country)
                page.wait_for_function("comparisonPopulation().rows.length<5 && !document.querySelector('.ovcard[data-m=npl] .pctb')")
                page.select_option('#fCountry','')
                page.wait_for_selector('.ovcard[data-m=npl] .pctb')
                page.click('#tabBenchmark');page.wait_for_selector('#bmReferenceSummary')
                assert page.evaluate('comparisonPopulation().rows.length')==population-1
                page.select_option('#bmDate','2026-03-31');page.wait_for_selector('#bmReferenceSummary')
                page.wait_for_function("activeFilters().d==='2026-03-31'")
                assert page.evaluate("analysisStats(comparisonPopulation().rows,METRICDOC.get('npl'),bmProf()).n")==0
                assert not page.evaluate('BM_CONFIRMED')
                assert page.locator('.analysis-card[data-analysis-metric=npl] strong').inner_text()=='—'
                page.screenshot(path=f'/tmp/p3dh-reference-analysis-{width}-{lang}.png',full_page=False)
                results.append({'width':width,'lang':lang,'reference_analysis':'pass','custom_membership':'pass','report_and_csv_match':'pass','missing_date_values':'pass'})
                page.close()
            browser.close()
    finally:server.shutdown();server.server_close()
    assert not errors,errors
    print(json.dumps({'cases':results,'javascript_errors':errors},indent=2))


if __name__=='__main__':check()
