"""Exercise the real publisher against a disposable local bare repository."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class VersionPublishTest(unittest.TestCase):
    def test_pointer_pins_the_snapshot_and_publish_keeps_two_commits(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);project=root/'project';scripts=project/'scripts';scripts.mkdir(parents=True)
            shutil.copy(ROOT/'scripts/publish_data_branch.sh',scripts)
            data=project/'processed/zweig_a/data';(data/'reports').mkdir(parents=True)
            (data/'index.json').write_text('{"generation":1}')
            (data/'reports/a.json').write_text('{"value":42}')
            # A stale pointer copied from a restored snapshot must not survive.
            (data/'data_version.json').write_text('{"revision":"stale"}')
            remote=root/'remote.git';subprocess.run(['git','init','--bare','-q',str(remote)],check=True)
            bin_dir=root/'bin';bin_dir.mkdir();curl=bin_dir/'curl';curl.write_text('#!/bin/sh\nexit 0\n');curl.chmod(0o755)
            env={**os.environ,'P3DH_PUSH_URL':str(remote),'PATH':str(bin_dir)+os.pathsep+os.environ['PATH']}
            subprocess.run(['bash',str(scripts/'publish_data_branch.sh')],env=env,check=True,capture_output=True,text=True)
            def git(*args):return subprocess.check_output(['git','--git-dir',str(remote),*args],text=True).strip()
            pointer=json.loads(git('show','data:data_version.json'));rev=pointer['revision']
            self.assertEqual(pointer['schema'],1)
            self.assertEqual(rev,git('rev-parse','data^'))
            self.assertEqual(git('rev-list','--count','data'),'2')
            self.assertEqual(json.loads(git('show',rev+':reports/a.json')),{'value':42})
            self.assertNotIn('data_version.json',git('ls-tree','--name-only',rev))

if __name__=='__main__':unittest.main()
