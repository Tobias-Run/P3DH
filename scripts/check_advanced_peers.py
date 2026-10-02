"""Actual-browser regression for advanced peer UI and data compatibility."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'scripts'))
import check_viewer_runtime as runtime


def check():
    from playwright.sync_api import sync_playwright
    runtime.PORT=8813
    server=runtime._serve();errors=[];results=[]
    base=f'http://localhost:{runtime.PORT}/viewer_json.html'
    try:
        with sync_playwright() as p:
            binary=next((s for s in [runtime.CHROMIUM,'/usr/bin/chromium'] if Path(s).exists()),None)
            browser=p.chromium.launch(args=['--no-sandbox'],**({'executable_path':binary} if binary else {}))
            for width,height,lang in [(1280,800,'en'),(390,844,'de')]:
                page=browser.new_page(viewport={'width':width,'height':height})
                requests=[];page.on('request',lambda r:requests.append(r.url));page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(base+'#benchmark',wait_until='networkidle')
                page.wait_for_selector('#bmPeer')
                if lang=='de':page.click('#langBtn')
                page.wait_for_function('(lang)=>LANG===lang',arg=lang)
                assert not any('advanced_peers.json' in u for u in requests),'advanced data fetched on standard start'
                baseline=page.evaluate("JSON.stringify([...percentileMap(benchmarkRows(),sichtbareSpalten(bmProf())[0].id)])")
                page.select_option('#bmPeer','bank_type')
                page.wait_for_function("AP_DATA && document.querySelector('.peer-note') && !document.querySelector('#main[aria-busy=true]')")
                assert page.evaluate("JSON.stringify([...percentileMap(benchmarkRows(),sichtbareSpalten(bmProf())[0].id)])")==baseline,'overview/default peer basis changed'
                assert page.evaluate("AP_DATA.metadata['9ZHRYM6F437SQJ6OUG95'].ownership")=='cooperative'
                assert page.evaluate("AP_DATA.metadata['0W5QHUNYV4W7GJO62R27'].ownership")=='public'
                assert page.evaluate("AP_DATA.metadata['5493009EIBTCB1X12G89'].ownership")=='shareholder'
                checked=page.evaluate("""()=>({
                  coverage:AP_DATA.coverage.classified,
                  aib:AP_DATA.metadata['635400AKJBGNS5WNQL34'].ownership,
                  belfius:AP_DATA.metadata['A5GWLFH3KM7YV2SFQL84'].ownership,
                  dnb:AP_DATA.metadata['549300GKFG0RYRRQ1414'].ownership,
                  iccrea:AP_DATA.metadata['NNVPP80YIZGEY2314M97'].ownership,
                  ing:AP_DATA.metadata['3TK20IVIUJ8J3ZU0QE75'],
                  label:document.querySelector('#bmOwnership option[value=shareholder]').textContent})""")
                assert checked['coverage']>=184
                assert (checked['aib'],checked['belfius'],checked['dnb'],checked['iccrea'])==('shareholder','public','mixed','cooperative')
                assert checked['ing']['ownership_basis']=='reviewed_document_chain'
                assert checked['ing']['group_head']=='549300NYKK9MWM7GGW15'
                assert checked['label']==('Shareholder-owned' if lang=='en' else 'Aktionärsgetragen')
                page.select_option('#bmOwnership','public')
                page.wait_for_function("BM_OWN==='public' && document.querySelector('.peer-note')")
                out=page.evaluate('''()=>{const selected=advancedSelection(benchmarkRows());return {
                  owners:[...new Set(selected.rows.map(r=>peerMeta(r).ownership))],
                  csv:benchmarkCSV(selected.rows,bmProf()),count:selected.rows.length,
                  small:[...percentileMap(selected.rows.slice(0,4),sichtbareSpalten(bmProf())[0].id,'bank_type')].length}}''')
                assert out['owners']==['public'] and out['count']>0
                assert 'ownership_control_source' in out['csv'] and '# Peer basis: bank_type' in out['csv']
                assert out['small']==0,'percentiles rendered for fewer than five values'
                assert 'ownership=public' in page.url and 'peer=bank_type' in page.url,'filter not shareable'
                public_url=page.url;page.reload(wait_until='networkidle');page.wait_for_function("AP_DATA && BM_OWN==='public' && document.querySelector('.peer-note')")
                assert page.url==public_url
                page.select_option('#bmPeer','cluster');page.wait_for_function("BM_PEER==='cluster' && document.querySelector('.peer-diagnostics')")
                clusters=page.evaluate("[...AP_CLUSTERS.values()].filter(c=>c.members.length>=5).map(c=>c.id)")
                assert clusters,'no cluster with enough members'
                page.select_option('#bmCluster',clusters[0]);page.wait_for_function('(id)=>BM_CLUSTER===id && document.querySelector(".peer-note")',arg=clusters[0])
                public_count=out['count']
                out=page.evaluate('''()=>{const rows=advancedSelection(benchmarkRows()).rows;return {
                  clusters:[...new Set(rows.map(r=>AP_DATA.reports[r.key]?.cluster))],
                  suppressed:clusterFittingMetric('trea'),notSuppressed:clusterFittingMetric('cet1'),
                  csv:benchmarkCSV(rows,bmProf()),defaultKey:peerKeyOf(rows[0]),advancedKey:peerKeyOf(rows[0],'cluster')}}''')
                assert out['clusters']==[clusters[0]] and out['suppressed'] and not out['notSuppressed']
                assert out['defaultKey']!=out['advancedKey'] and '# Fitting method:' in out['csv']
                page.check('#bmPct')
                assert page.locator('.bmtable .pctb').count()>0,'non-fitting capital metrics lost percentiles'
                page.select_option('#bmProfile','risk')
                page.wait_for_function("BMP==='risk' && BM_DOM.context && JSON.parse(BM_DOM.context)[1]==='risk' && !document.querySelector('#main[aria-busy=true]')")
                assert page.locator('.bmtable .pctb').count()==0,'fitting risk inputs receive circular percentile badges'
                page.screenshot(path=f'/tmp/p3dh-advanced-peers-{lang}-{width}.png',full_page=False)
                page.goto(base+'#benchmark?peer=cluster&cluster=ffffffffffff',wait_until='networkidle')
                page.wait_for_function("BM_CLUSTER==='ffffffffffff' && document.querySelector('.peer-note')")
                assert page.locator('#bmCluster option:checked').get_attribute('value')=='ffffffffffff'
                assert page.locator('.bmtable tbody tr[data-key]').count()==0,'unavailable cluster silently widened'
                results.append({'width':width,'language':lang,'public_reports':public_count, 'clusters':len(clusters)})
                page.close()
            # A failed/missing manifest cannot silently fall back to standard.
            page=browser.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.route('**/advanced_peers.json',lambda route:route.abort())
            page.goto(base+'#benchmark',wait_until='networkidle')
            page.wait_for_selector('#bmPeer');page.select_option('#bmPeer','cluster')
            page.wait_for_selector('#bmPeerRetry');assert page.locator('#bmPeerStandard').count()==1
            assert page.locator('.bmtable').is_hidden() and page.locator('#bmCsv').is_disabled()
            page.unroute('**/advanced_peers.json');page.click('#bmPeerRetry')
            page.wait_for_function("AP_DATA && document.querySelector('.peer-note')")
            page.close()
            # An older data publication has no advanced manifest.
            page=browser.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            def old_codebook(route):
                response=route.fetch();book=response.json();book.pop('advanced_peers',None)
                route.fulfill(response=response,json=book)
            page.route('**/codebook.json',old_codebook)
            page.goto(base+'#benchmark?peer=bank_type',wait_until='networkidle')
            page.wait_for_selector('#bmPeerRetry')
            assert page.evaluate("BM_PEER==='bank_type' && AP_DATA===null")
            page.click('#bmPeerStandard');page.wait_for_selector('.bmtable')
            assert page.evaluate("BM_PEER==='standard'")
            page.close();browser.close()
    finally:server.shutdown();server.server_close()
    if errors:raise AssertionError(errors)
    print(json.dumps({'cases':results,'javascript_errors':len(errors)},indent=2))


if __name__=='__main__':check()
