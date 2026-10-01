"""Browser regression for bilingual derivation roles, formulas and series headers."""
from playwright.sync_api import sync_playwright
from measure import serve
from test_ux import report_url

def main():
    server=serve();base=f'http://127.0.0.1:{server.server_port}'
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        page=browser.new_page();page.goto(report_url(base),wait_until='networkidle')
        page.wait_for_function('LABELS_LOADED && haveBenchmark(overviewTemplates())')
        result=page.evaluate("""()=>{
          const rep=byKey(activeKey);const saved=LANG;let count=0;
          for(const metric of METRICDOC.values()){
            const value=metricValue(rep,metric);
            LANG='en';const english=document.createElement('div');english.innerHTML=metricDetail(rep,metric.id);
            const roles=[...english.querySelectorAll('td.role')].slice(0,(metric.cells||[]).length).map(x=>x.textContent);
            (metric.cells||[]).forEach((cell,i)=>{if(roles[i]===cell[3])throw new Error('Untranslated '+cell[3]);});
            if(metric.id==='hr' && english.querySelector('.res td:nth-child(3)').textContent!=='total capital ratio − overall capital requirement')throw new Error('Incorrect English formula');
            LANG='de';const german=document.createElement('div');german.innerHTML=metricDetail(rep,metric.id);
            const deRoles=[...german.querySelectorAll('td.role')].slice(0,(metric.cells||[]).length).map(x=>x.textContent);
            (metric.cells||[]).forEach((cell,i)=>{if(deRoles[i]!==cell[3])throw new Error('Changed German role');});
            if(metric.formula && german.querySelector('.res td:nth-child(3)').textContent!==metric.formula)throw new Error('Changed German formula');
            if(metricValue(rep,metric)!==value)throw new Error('Changed numeric result');
            count++;
          }
          LANG='en';renderTimeseries(rep);const en=document.querySelector('#tsSection h3').textContent;
          if(!en.includes('Time series')||!en.includes('reference dates'))throw new Error(en);
          LANG='de';renderTimeseries(rep);const de=document.querySelector('#tsSection h3').textContent;
          if(!de.includes('Zeitreihe')||!de.includes('Stichtage'))throw new Error(de);
          LANG=saved;return {metrics:count,roles:true,formulas:true,unchanged_values:true,series_headers:true};
        }""")
        print(result);browser.close()
    server.shutdown()

if __name__=='__main__':main()
