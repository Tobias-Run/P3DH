"""Reconstruct the measured source variants without committing HTML copies."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE_REF='902d0add0d117473791d129bc2d9180e9761e7f4'
FILE='processed/zweig_a/viewer_json.html'
baseline=subprocess.check_output(['git','show',f'{BASE_REF}:{FILE}'],cwd=ROOT).decode()
candidate=(ROOT/FILE).read_text()

def replace_span(text,start,end,replacement):
    a=text.index(start); b=text.index(end,a)
    return text[:a]+replacement+text[b:]

# Each experiment adds one independently reviewable family of changes.
number_code=candidate[candidate.index('// Reuse locale formatters:'):candidate.index('function fmt(v)')]
formatters=replace_span(baseline,'function nf(v, min, max){','function fmt(v)',number_code)
network=formatters.replace("{cache:'no-store'}","{cache:'no-cache'}")
network=network.replace('async function getJSON(path){',
    '// Revalidate mutable branch URLs on every visit. Unlike no-store this permits\n'
    '// ETag/304 reuse without trusting the CDN browser max-age (currently seven days).\n'
    'async function getJSON(path){')
new_prefetch=candidate[candidate.index('    // Fetch labels on intent,'):candidate.index('\n  }catch(err){',candidate.index('async function init()'))]
network=replace_span(network,'    // Labels NACH dem ersten Rendern nachziehen.','\n  }catch(err){',new_prefetch)
hashes={}
for name,source in [('baseline',baseline),('formatters',formatters),('network',network),('candidate',candidate)]:
    hashes[name]=hashlib.sha256(source.encode()).hexdigest()
    if name!='candidate':
        dest=ROOT/f'performance/{name}/viewer_json.html'
        dest.parent.mkdir(exist_ok=True)
        dest.write_text(source)
(ROOT/'performance/results/variant_hashes.json').write_text(json.dumps({'baseline_ref':BASE_REF,'sha256':hashes},indent=2))
print(json.dumps(hashes,indent=2))
