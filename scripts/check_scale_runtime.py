"""#122: check actual filing warnings on desktop/mobile, in both languages."""
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import check_viewer_runtime as runtime

CASES = [
    ('Alpha', '213800DBQIB6VBNU5C64', '2025-06-30', '23.00'),
    ('K&H June', 'KFUXYFTU2LHQFQZDQG45', '2025-06-30', '41.00'),
    ('K&H December', 'KFUXYFTU2LHQFQZDQG45', '2025-12-31', '41.00'),
    ('Citibank June', 'N1FBEDJ5J41VKZLO2475', '2025-06-30', '68.00'),
    ('Citibank December', 'N1FBEDJ5J41VKZLO2475', '2025-12-31', '68.00'),
    ('BBVA', 'K8MS7FD7N5Z2WQ51AZ71', '2025-06-30', '83.01.C'),
    ('Rabobank', 'DG3RU1DBUFHT4ZF9WN62', '2026-03-31', '61.00'),
    ('Bank Austria', 'D1HEB8VEU6D9M8ZUXG17', '2025-12-31', '71.00'),
    ('CR10 open', 'KR6LSKV3BTSJRD41IF75', '2025-12-31', '29.02.A'),
]


def check():
    from playwright.sync_api import sync_playwright
    with (ROOT / 'processed/scale_flags.csv').open() as fh:
        flags = {(r['lei'], r['refPeriod'], r['template_id']): r
                 for r in csv.DictReader(fh) if r['ebene'] == 'template'}
    server = runtime._serve()
    errors, results = [], []
    try:
        with sync_playwright() as p:
            binary = next((s for s in [runtime.CHROMIUM, '/usr/bin/chromium'] if Path(s).exists()), None)
            browser = p.chromium.launch(args=['--no-sandbox'], **({'executable_path': binary} if binary else {}))
            for width, height in [(1280, 800), (390, 844)]:
                page = browser.new_page(viewport={'width': width, 'height': height})
                page.on('pageerror', lambda e: errors.append(str(e)))
                for name, lei, date, template in CASES:
                    page.goto(f'http://localhost:{runtime.PORT}/viewer_json.html#r/{lei}/{date}/CON',
                              wait_until='networkidle')
                    page.wait_for_selector('#ovSection', state='attached')
                    result = page.evaluate('''([lei,date,tpl])=>{
                      const rep=REPORTS.find(r=>r.entityID==='rs:'+lei+'.CON' && r.refPeriod===date);
                      const sc=rep.quality?.sc;
                      const result={};
                      for(const lang of ['en','de']){
                        LANG=lang; renderOverview(rep);
                        result[lang]={note:document.querySelector('.ovsc')?.textContent||'',
                          badge:scaleBadge(rep.quality,tpl),
                          warning:!!document.querySelector('.ovsc')};
                      }
                      if(sc?.d){
                        result.detail=sc.d[tpl]||null;
                        result.bars={trea:barErlaubt({tpl:'61.00'},{q:rep.quality},
                          {cells:[['61.00','0040','0010']]}),
                          liquidity:barErlaubt({tpl:'61.00'},{q:rep.quality},
                          {cells:[['61.00','0280','0010']]})};
                        const prof=bmAll().km1;
                        bmSort={...prof.defaultSort}; BM_COLS=null;
                        result.csv=benchmarkCSV([{key:repKey(rep),q:rep.quality,
                          name:lei,lei,date,scope:'CON'}],prof);
                      }
                      return result;
                    }''', [lei, date, template])
                    expected = flags.get((lei, date, template))
                    for lang in ('en', 'de'):
                        assert bool(result[lang]['badge']) == bool(expected), (name, lang, result)
                        if expected:
                            assert result[lang]['warning'], (name, lang)
                            direction = {'zu_gross': ('too large', 'zu groß'),
                                         'zu_klein': ('too small', 'zu klein'),
                                         'unklar': ('direction uncertain', 'Richtung unklar')}[expected['richtung']]
                            assert direction[lang == 'de'] in result[lang]['note'], (name, lang, direction)
                            if expected['referenz_stichtag']:
                                assert expected['referenz_stichtag'] in result[lang]['note']
                    if expected:
                        assert result['detail']['r'] == expected['richtung']
                        rows = list(csv.DictReader(z for z in result['csv'].splitlines() if not z.startswith('#')))
                        exported = json.loads(rows[0]['scale_finding'])
                        assert exported[template]['r'] == expected['richtung']
                        assert exported[template]['a'] == expected['umfang']
                        if name == 'Rabobank' and expected['umfang'] == 'teilbereich':
                            assert result['bars'] == {'trea': True, 'liquidity': False}, result['bars']
                    results.append({'case': name, 'viewport': width, 'template_warning': bool(expected),
                                    'direction': expected['richtung'] if expected else '', 'languages': ['en', 'de']})
                    print('PASS', width, name, flush=True)
                page.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    assert not errors, errors
    print(json.dumps({'cases': len(results), 'language_checks': len(results)*2,
                      'javascript_errors': errors, 'results': results}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    check()
