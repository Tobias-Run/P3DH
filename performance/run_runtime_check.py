"""Run the existing browser regression suite against the pinned data snapshot.

Missing report shards requested by the suite are read from the same immutable data
commit. These network reads are exclusively test setup, never timed benchmarks.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import check_viewer_runtime as runtime

OUT=ROOT/'performance/results'
DATA=ROOT/'processed/zweig_a/data'
ref=json.loads((OUT/'snapshot.json').read_text())['data_sha']
runtime.CHROMIUM='/usr/bin/chromium'
original=runtime._H.do_GET
downloads=[]

def serve(self):
    path=Path(self.translate_path(self.path)).resolve()
    if path.is_relative_to(DATA/'reports') and path.suffix=='.json' and not path.exists():
        rel=path.relative_to(DATA).as_posix()
        path.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(['curl','-fsSL','--compressed','--connect-timeout','10',
                        '--max-time','30',f'https://raw.githubusercontent.com/Tobias-Run/P3DH/{ref}/{rel}',
                        '-o',str(path)],check=True)
        downloads.append(rel)
    return original(self)

runtime._H.do_GET=serve
if __name__=='__main__':
    problems=runtime.pruefe()
    (OUT/'runtime_verification.json').write_text(json.dumps({'data_sha':ref,'extra_downloads':downloads,'failures':problems},indent=2))
    for item in problems:print('FAIL:',item)
    print('Runtime checks:', 'PASS' if not problems else 'FAIL')
    sys.exit(bool(problems))
