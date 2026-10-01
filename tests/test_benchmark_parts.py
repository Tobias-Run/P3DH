import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('parts',ROOT/'scripts/build_benchmark_parts.py')
parts=importlib.util.module_from_spec(spec);spec.loader.exec_module(parts)

class PartitionTest(unittest.TestCase):
    def fixture(self,path):
        bm={'a':{'61.00':[['r','c',0]],'82.00.A':[['r','c',None]]},
            'b':{'61.00':[['r','c',-2]]}}
        cb={'metrics':{'metrics':[{'id':'ratio','cells':[['82.00.A','r','c']], 'ov':True},
                                  {'id':'gate','cells':[['60.00.A','r','c']]}],
                       'profiles':[{'id':'mixed','tpl':'82.00.A','metrics':['ratio'],'gate':['gate'],'trend':'r','cross':['21.01.D']}]}}
        (path/'benchmark.json').write_text(json.dumps(bm));(path/'codebook.json').write_text(json.dumps(cb))
        return bm
    def test_lossless_dependencies_and_immutable_names(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d);bm=self.fixture(path);m=parts.build(path);rebuilt={}
            self.assertEqual(m['profiles']['mixed'],['21.01.D','60.00.A','61.00','82.00.A'])
            for tid,item in m['templates'].items():
                raw=(path/item['path']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),item['sha256'])
                for key,cells in json.loads(raw).items():rebuilt.setdefault(key,{})[tid]=cells
            self.assertEqual(rebuilt,bm)
            self.assertEqual(parts.build(path),m)
            old=m['templates']['61.00']['path'];bm['b']['61.00'][0][2]=42
            (path/'benchmark.json').write_text(json.dumps(bm));n=parts.build(path)
            self.assertNotEqual(n['version'],m['version']);self.assertNotEqual(n['templates']['61.00']['path'],old)
            self.assertFalse((path/old).exists())
            self.assertEqual(n['templates']['82.00.A'],m['templates']['82.00.A'])

if __name__=='__main__':unittest.main()
