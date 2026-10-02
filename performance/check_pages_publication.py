"""Verify merged Pages HTML, the published snapshot pointer and every part hash."""
import base64,hashlib,json,subprocess,urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'performance/results/production_2026-10-02'

def api(path):return json.loads(subprocess.check_output(['gh','api','repos/Tobias-Run/P3DH/'+path]))
def read(url):
    request=urllib.request.Request(url,headers={'Cache-Control':'no-cache','Pragma':'no-cache'})
    with urllib.request.urlopen(request,timeout=30) as response:
        return response.read(),{k:v for k,v in response.headers.items() if k.lower() in ['cache-control','content-encoding','etag','timing-allow-origin']}
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    pointer=json.loads(base64.b64decode(api('contents/data_version.json?ref=data')['content']))
    head=api('git/ref/heads/data')['object']['sha'];commit=api('commits/'+head)
    assert pointer['schema']==1 and pointer['revision']==commit['parents'][0]['sha']
    revision=pointer['revision'];rawbase=f'https://raw.githubusercontent.com/Tobias-Run/P3DH/{revision}/'
    page,headers=read('https://tobias-run.github.io/P3DH/processed/zweig_a/viewer_json.html')
    assert page==(ROOT/'processed/zweig_a/viewer_json.html').read_bytes(),'Pages still serves different viewer code'
    cb=json.loads(read(rawbase+'codebook.json')[0]);manifest=cb['benchmark_parts']
    assert manifest['schema']==1
    parts={};reconstructed={}
    for tid,part in manifest['templates'].items():
        body,_=read(rawbase+part['path']);actual=hashlib.sha256(body).hexdigest()
        assert actual==part['sha256']
        for key,cells in json.loads(body).items():reconstructed.setdefault(key,{})[tid]=cells
        parts[tid]={'path':part['path'],'sha256':actual,'raw_bytes':len(body)}
    legacy=json.loads(read(rawbase+'benchmark.json')[0]);assert legacy==reconstructed,'Partition differs from retained legacy benchmark'
    # CDN copy must have identical bytes to the immutable raw snapshot.
    cdnbody,cdnheaders=read('https://cdn.jsdelivr.net/gh/Tobias-Run/P3DH@'+revision+'/'+parts['61.00']['path'])
    assert hashlib.sha256(cdnbody).hexdigest()==parts['61.00']['sha256']
    index=json.loads(read(rawbase+'index.json')[0]);result={'pipeline_run':36933243825,'merge_sha':'b22b1b79c1dbe2397c47c5555cc5238a0af071f8',
        'data_head':head,'data_revision':revision,'pages_sha256':hashlib.sha256(page).hexdigest(),'pages_headers':headers,
        'parts':parts,'cdn_km1_headers':cdnheaders,'stats':index['stats'],'pointer_parent_matches':True,'pages_matches_merged_viewer':True,
        'all_part_hashes_verified':True,'lossless_reconstruction':True,'cdn_part_matches':True}
    (OUT/'publication.json').write_text(json.dumps(result,indent=2));print('Publication verified',revision,'templates',len(parts),'reports',len(index['reports']))

if __name__=='__main__':main()
