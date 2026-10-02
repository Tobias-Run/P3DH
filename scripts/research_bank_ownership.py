"""Collect official website evidence for ownership review; never auto-classify.

Discovery uses existing LEI-to-Wikidata IDs (P856) and explicit reviewed seeds.
Wikidata is discovery only, not proof. Fetch a bounded number of same-site governance
pages per institution; archive response hashes, extracted text and failures.
Run after the separately documented GLEIF/website discovery fetch, e.g.:
  python scripts/research_bank_ownership.py --discovery /path/to/discovery.json --output interim/ownership_research
"""
import argparse
import concurrent.futures
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
KEYWORDS=re.compile(r'co.operativ|genossenschaft|mutual|member.owned|customer.owned|sharehold|ownership|owned by|majority.owned|public.law|state.owned|government.owned|selveiende|aktionär|eigentüm|trägerschaft|träger der|actionnair|sociétaire|participaci[oó]n|accionist|azionist|propriet|soci[ée]t[ée] coop|cooperativa|skarb|udziałow|omistaj|aandeelhoud|eigena|ägar|eiere|self.owned',re.I)
GOVERNANCE=re.compile(r'about|profil|sharehold|ownership|owner|aktion|eigent|traeger|actionna|governance|corporate|annual.report|gesch[aä]ft|unternehmen|ueber|über|ejer|selveiende|azionist|omist|aandeel|investor|rapport|cooperat|groupe|group/',re.I)

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


def collect(bank,output,max_pages=12):
    pages=[];visited=set();queue=[(0,u) for u in bank.get('websites',[])[:2]]
    base_hosts=set()
    for url in bank.get('websites',[]):
        host=(urllib.parse.urlparse(url).hostname or '').removeprefix('www.')
        if host:base_hosts.add(host)
    while queue and len(pages)<max_pages:
        queue.sort(key=lambda x:(x[0],len(x[1]),x[1]));priority,url=queue.pop(0)
        if url in visited or urllib.parse.urlparse(url).scheme not in ('http','https'):continue
        visited.add(url);p=fetch(url,output/'pages');pages.append(p)
        if p.get('status')!=200 or p.get('error'):continue
        host=(urllib.parse.urlparse(p['url']).hostname or '').removeprefix('www.');base_hosts.add(host)
        for link in p['links']:
            link=link.split('#')[0]
            target=(urllib.parse.urlparse(link).hostname or '').removeprefix('www.')
            if not any(target==h or target.endswith('.'+h) for h in base_hosts):continue
            if not GOVERNANCE.search(link) or link in visited:continue
            # Ownership before investor navigation; recurse so a governance
            # landing page does not consume the entire ownership investigation.
            score=1 if re.search('sharehold|ownership|owner|aktion|eigent|actionna|azionist|omist|ejer',link,re.I) else 2 if re.search('annual|geschaeft|geschäft|report|rapport',link,re.I) else 4
            queue.append((score,link))
        time.sleep(.1)
    return {**bank,'pages':[{'url':p.get('url',p['requested_url']),'status':p.get('status'),
                             'sha256':p.get('sha256'),'error':p.get('error'),'hits':p.get('hits',[])} for p in pages],
            'status':'evidence_collected' if any(p.get('hits') for p in pages) else
                     'website_no_ownership_passage' if any(p.get('status')==200 for p in pages) else 'website_unavailable'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--discovery',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--workers',type=int,default=4);parser.add_argument('--max-pages',type=int,default=12)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    banks=json.loads(args.discovery.read_text());completed=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(collect,bank,args.output,args.max_pages):bank for bank in banks}
        for future in concurrent.futures.as_completed(futures):
            row=future.result();completed.append(row)
            (args.output/(row['lei']+'.json')).write_text(json.dumps(row,ensure_ascii=False,indent=2))
            print(len(completed),'/',len(banks),row['name'],row['status'],flush=True)
    (args.output/'research.json').write_text(json.dumps(sorted(completed,key=lambda r:r['lei']),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
