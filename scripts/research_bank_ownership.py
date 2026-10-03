"""Collect official website evidence for ownership review; never auto-classify.

Discovery uses existing LEI-to-Wikidata IDs (P856) and explicit reviewed seeds.
Wikidata is discovery only, not proof. Fetch a bounded number of same-site governance
pages per institution; archive response hashes, extracted text and failures.
Run after the separately documented GLEIF/website discovery fetch, e.g.:
  python scripts/research_bank_ownership.py --discovery /path/to/discovery.json --output interim/ownership_research
"""
import argparse
import concurrent.futures
import csv
import datetime
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

AGENT='P3DH-research/1.0 (https://github.com/Tobias-Run/P3DH)'
KEYWORDS=re.compile(r'co.operativ|genossenschaft|mutual|member.owned|customer.owned|sharehold|ownership|owned by|majority.owned|public.law|state.owned|government.owned|selveiende|selvejende|aktionär|eigentüm|trägerschaft|träger der|actionnair|sociétaire|participaci[oó]n|accionist|azionist|propriet|soci[ée]t[ée] coop|cooperativa|skarb|udziałow|omistaj|aandeelhoud|eigena|ägar|eiere|self.owned',re.I)
GOVERNANCE=re.compile(r'about|profil|sharehold|ownership|owner|aktion|aktsion|eigent|traeger|actionna|governance|corporate|annual.report|gesch[aä]ft|unternehmen|ueber|über|ejer|selve[i]?ende|selvejende|azionist|omist|aandeel|investor|rapport|cooperat|groupe|group/|vedt(?:ae|a|æ)gt|statut|satzung|om-oss|om-sparekassen|om-middelfart|om-merkur|gremien|o-nas|par-mums',re.I)


def governance_priority(url):
    """Rank discovered source paths; home ownership and privacy are not bank owners."""
    path=urllib.parse.unquote(urllib.parse.urlparse(url).path)
    if re.search(r'ejerbolig|eierbolig|privatliv|privacy|cookie|lost-device|'
                 r'shareholders?-meeting|karriere|careers|jobs|contact|'
                 r'financing|trade-finance|ressourcen-des-eigentuemers|'
                 r'ejerskifte|virksomhedsejer|immobilieneigent|asset-owners|'
                 r'digitale-vaerktoejer|rapporti-dormienti',path,re.I):
        return None
    if not GOVERNANCE.search(path):return None
    if re.search(r'sharehold|ownership|owner|aktion|aktsion|eigent|actionna|azionist|'
                 r'omist|ejer|selvejende|selveiende|vedt(?:ae|a|æ)gt|statut|satzung',path,re.I):return 1
    if re.search(r'annual|geschaeft|geschäft|report|rapport',path,re.I):return 2
    return 4

class PageText(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.links=[];self.ignore=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.ignore+=1
        if tag=='a':
            h=dict(attrs).get('href','')
            if h:self.links.append(h)
        if tag in ('p','li','div','h1','h2','h3','br','tr','td','th'):self.parts.append('\n')
        if tag=='sup':self.parts.append(' [footnote ')
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.ignore=max(0,self.ignore-1)
        if tag=='sup':self.parts.append('] ')
    def handle_data(self,data):
        if not self.ignore:self.parts.append(data)


def fetch(url,directory,refresh=False):
    """Return archived evidence, never suppress TLS verification or retry 403."""
    directory.mkdir(parents=True,exist_ok=True)
    cache=directory/(hashlib.sha256(url.encode()).hexdigest()+'.json')
    previous = json.loads(cache.read_text()) if cache.exists() else None
    if previous and (previous.get('status') == 403 or '403' in previous.get('error', '')):
        return previous
    if previous and not refresh:
        # A temporary outage is not evidence that ownership is unavailable.
        transient = previous.get('status') in (429, 500, 502, 503, 504) or (
            previous.get('status') is None and '403' not in previous.get('error', ''))
        retrieved = datetime.datetime.strptime(previous['retrieved_at'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc).timestamp()
        cooldown = max(300, previous.get('retry_after_seconds', 0))
        if not transient or time.time()-retrieved < cooldown:
            return previous
    result={'requested_url':url,'retrieved_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    try:
        request=urllib.request.Request(url,headers={'User-Agent':AGENT})
        with urllib.request.urlopen(request,timeout=22) as response:
            body=response.read(16*1024*1024+1);actual=response.url;mime=response.headers.get('Content-Type','')
            if len(body)>16*1024*1024:raise ValueError('Response exceeds 16 MiB evidence limit')
        result.update({'http_status':200,'url':actual,'sha256':hashlib.sha256(body).hexdigest()})
        if 'json' in mime:
            # Public CMS responses contain HTML inside JSON strings. Running
            # them through HTMLParser would remove tags and insert invalid
            # literal newlines, destroying both the data and its evidence.
            text=body.decode('utf-8-sig');json.loads(text);links=[]
        elif 'pdf' in mime or urllib.parse.urlparse(actual).path.lower().endswith('.pdf'):
            import io
            from pypdf import PdfReader
            text='\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(body)).pages);links=[]
        else:
            page=PageText();page.feed(body.decode('utf-8','replace'))
            text='\n'.join(' '.join(p.split()) for p in ''.join(page.parts).splitlines() if p.strip());links=page.links
        hits=[]
        for m in KEYWORDS.finditer(text):
            start=max(0,m.start()-140);end=min(len(text),m.end()+400)
            if hits and start<=hits[-1]['end']:hits[-1]['end']=end;hits[-1]['quote']=text[hits[-1]['start']:end]
            else:hits.append({'start':start,'end':end,'quote':text[start:end]})
        result.update({'url':actual,'status':200,'sha256':hashlib.sha256(body).hexdigest(),'text':text,
                       'links':[urllib.parse.urljoin(actual,h) for h in links],'hits':hits[:60]})
    except Exception as e:
        result.update({'status':getattr(e,'code',None),'error':str(e)})
        if isinstance(e, urllib.error.HTTPError):
            retry = e.headers.get('Retry-After', '')
            if retry.isdigit():result['retry_after_seconds'] = int(retry)
    if previous:
        result['previous_attempts'] = previous.get('previous_attempts', []) + [
            {k:previous.get(k) for k in ('retrieved_at','status','error','sha256')}]
    cache.write_text(json.dumps(result,ensure_ascii=False,indent=2));return result


def collect(bank,output,max_pages=12,cache_dir=None,cache_only=False):
    pages=[];visited=set();queue=[(0,u) for u in bank.get('websites',[])[:2]]
    base_hosts=set()
    for url in bank.get('websites',[]):
        host=(urllib.parse.urlparse(url).hostname or '').removeprefix('www.')
        if host:base_hosts.add(host)
    while queue and len(pages)<max_pages:
        queue.sort(key=lambda x:(x[0],len(x[1]),x[1]));priority,url=queue.pop(0)
        if url in visited or urllib.parse.urlparse(url).scheme not in ('http','https'):continue
        visited.add(url)
        directory=cache_dir if cache_dir is not None else output/'pages'
        cache=directory/(hashlib.sha256(url.encode()).hexdigest()+'.json')
        if cache_only and not cache.exists():
            pages.append({'requested_url':url,'status':None,'error':'Not cached; network disabled for this pass'})
            continue
        p=json.loads(cache.read_text()) if cache_only else fetch(url,directory)
        pages.append(p)
        if p.get('status')!=200 or p.get('error'):continue
        host=(urllib.parse.urlparse(p['url']).hostname or '').removeprefix('www.');base_hosts.add(host)
        for link in p['links']:
            link=link.split('#')[0]
            target=(urllib.parse.urlparse(link).hostname or '').removeprefix('www.')
            if not any(target==h or target.endswith('.'+h) for h in base_hosts):continue
            score=governance_priority(link)
            if score is None or link in visited:continue
            # Ownership before investor navigation; recurse so a governance
            # landing page does not consume the entire ownership investigation.
            queue.append((score,link))
        time.sleep(.1)
    return {**bank,'collection_mode':'cache_only' if cache_only else 'network_allowed',
            'pages':[{'url':p.get('url',p['requested_url']),'status':p.get('status'),
                             'sha256':p.get('sha256'),'error':p.get('error'),'hits':p.get('hits',[])} for p in pages],
            'status':'evidence_collected' if any(p.get('hits') for p in pages) else
                     'website_no_ownership_passage' if any(p.get('status')==200 for p in pages) else 'website_unavailable'}


def select_batch(banks,output,max_banks=5,repeat=False,known=(),cache_only=False):
    """Keep input priority; saved cases prevent expensive repeated investigations."""
    selected=[];seen=set()
    for bank in banks:
        lei=bank['lei']
        if lei in seen or lei in known:continue
        seen.add(lei)
        saved=output/(lei+'.json')
        if not repeat and saved.exists():
            previous=json.loads(saved.read_text())
            # A cache-only probe must not prevent the first bounded live pass.
            if cache_only or previous.get('collection_mode')!='cache_only':continue
        selected.append(bank)
        if len(selected)==max_banks:break
    return selected


def compact_bundle(completed,max_chars=12000,max_hits=2,max_quote_chars=650):
    """Hard character cap on review context, not an estimate of billed tokens.

    Full evidence stays in the cache and per-case checkpoint. Excerpts are
    discovery material: a human still verifies identity, owners and control.
    """
    bundle={'purpose':'Manual ownership review; excerpts are not accepted classifications.',
            'cases':[],'deferred_leis':[]}
    size=lambda value:len(json.dumps(value,ensure_ascii=False,separators=(',',':')))
    for bank in sorted(completed,key=lambda b:(b.get('rank',10**9),b['lei'])):
        case={k:bank[k] for k in ('lei','name','rank','date','trea_eur',
                                 'controller_candidate_lei','reviewed_controller_source_url') if k in bank}
        case.update(status=bank['status'],excerpts=[])
        hits=[]
        for page in bank.get('pages',[]):
            if page.get('status')!=200 or page.get('error'):continue
            for hit in page.get('hits',[]):
                quote=' '.join(hit['quote'].split())
                score=bool(re.search(r'\d[.,\d]*\s*%|wholly|majority|100 percent|entirely',quote,re.I))
                hits.append((score,page,quote))
        unique=set()
        for _,page,quote in sorted(hits,key=lambda h:not h[0]):
            quote=quote[:max_quote_chars]
            if quote in unique:continue
            unique.add(quote)
            case['excerpts'].append(dict(url=page['url'],sha256=page.get('sha256'),quote=quote))
            if len(case['excerpts'])==max_hits:break
        # Reserve space for deferred IDs, so the published bundle never exceeds
        # the cap even when a case has an unusually long URL/name.
        reserve=sum(len(b['lei'])+4 for b in completed)
        candidate={**bundle,'cases':bundle['cases']+[case]}
        while case['excerpts'] and size(candidate)+reserve>max_chars:
            case['excerpts'].pop()
        if size(candidate)+reserve<=max_chars:bundle['cases'].append(case)
        else:bundle['deferred_leis'].append(bank['lei'])
    if size(bundle)>max_chars:raise ValueError('Context budget too small even for deferred case IDs')
    return bundle


def checkpoint(path,value):
    """An interrupted write must not look like a completed institution."""
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2))
    temporary.replace(path)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--discovery',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--workers',type=int,default=2);parser.add_argument('--max-pages',type=int,default=4)
    parser.add_argument('--max-banks',type=int,default=5)
    parser.add_argument('--max-context-chars',type=int,default=12000)
    parser.add_argument('--cache-dir',type=Path)
    parser.add_argument('--cache-only',action='store_true')
    parser.add_argument('--registry',type=Path,default=Path(__file__).resolve().parent.parent/'codebook/bank_classification.csv')
    parser.add_argument('--repeat',action='store_true',help='Explicitly revisit saved cases; cache/403 protections still apply')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    if args.workers<1 or args.max_pages<1 or args.max_banks<1 or args.max_context_chars<256:
        parser.error('Positive page/bank/worker limits and a context budget of at least 256 characters are required')
    known={r['lei'] for r in csv.DictReader(args.registry.open())} if args.registry.exists() else set()
    banks=select_batch(json.loads(args.discovery.read_text()),args.output,args.max_banks,args.repeat,known,args.cache_only);completed=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(collect,bank,args.output,args.max_pages,args.cache_dir,args.cache_only):bank for bank in banks}
        for future in concurrent.futures.as_completed(futures):
            row=future.result();completed.append(row)
            checkpoint(args.output/(row['lei']+'.json'),row)
            print(len(completed),'/',len(banks),row['name'],row['status'],flush=True)
    (args.output/'research.json').write_text(json.dumps(sorted(completed,key=lambda r:r['lei']),ensure_ascii=False,indent=2))
    bundle=compact_bundle(completed,args.max_context_chars)
    encoded=json.dumps(bundle,ensure_ascii=False,separators=(',',':'))
    (args.output/'review_bundle.json').write_text(encoded)
    print(f'Review bundle: {len(encoded)} characters; {len(bundle["deferred_leis"])} cases deferred. Full evidence remains archived.')

if __name__=='__main__':main()
