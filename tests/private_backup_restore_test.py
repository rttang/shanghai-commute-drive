import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/restore_private_assets.py'


class PrivateRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='private-backup-test-')
        self.root = Path(self.temp.name)
        self.parts = self.root/'parts'; self.parts.mkdir()
        self.target = self.root/'target'; self.target.mkdir()
        self.content = b'known private asset fixture\n'
        self.sha = hashlib.sha256(self.content).hexdigest()
        part = self.parts/'part.zip'
        with zipfile.ZipFile(part, 'w') as z: z.writestr('objects/'+self.sha, self.content)
        self.manifest = {'schemaVersion': 1, 'visibility': 'private', 'files': [
            {'file': name, 'bytes': len(self.content), 'sha256': self.sha, 'part': 'part.zip', 'group': 'runtime'}
            for name in ['public/one.bin', 'public/copy.bin']],
            'parts': [{'file': 'part.zip', 'bytes': part.stat().st_size, 'sha256': hashlib.sha256(part.read_bytes()).hexdigest()}]}

    def tearDown(self): self.temp.cleanup()

    def run_restore(self, *extra):
        manifest = self.root/'manifest.json'; manifest.write_text(json.dumps(self.manifest))
        return subprocess.run([sys.executable, str(SCRIPT), '--parts', str(self.parts), '--manifest', str(manifest), '--target', str(self.target), *extra], capture_output=True, text=True)

    def test_deduplicated_object_restores_both_paths_and_is_idempotent(self):
        self.assertEqual(self.run_restore().returncode, 0)
        self.assertEqual((self.target/'public/one.bin').read_bytes(), self.content)
        self.assertEqual((self.target/'public/copy.bin').read_bytes(), self.content)
        self.assertEqual(self.run_restore().returncode, 0)

    def test_different_local_file_is_retained_without_overwrite(self):
        (self.target/'public').mkdir(); p=self.target/'public/one.bin'; p.write_bytes(b'new local work')
        self.assertNotEqual(self.run_restore().returncode, 0)
        self.assertEqual(p.read_bytes(), b'new local work')
        self.assertFalse((self.target/'public/copy.bin').exists())

    def test_path_traversal_is_rejected_before_any_write(self):
        self.manifest['files'][0]['file']='public/../../escape.bin'
        self.assertNotEqual(self.run_restore().returncode, 0)
        self.assertFalse((self.root/'escape.bin').exists())
        self.assertEqual(list(self.target.iterdir()), [])

    def test_corrupt_part_and_corrupt_object_are_rejected(self):
        p=self.parts/'part.zip'; p.write_bytes(p.read_bytes()+b'corrupt')
        self.assertNotEqual(self.run_restore().returncode, 0)
        self.assertEqual(list(self.target.iterdir()), [])
        with zipfile.ZipFile(p,'w') as z:z.writestr('objects/'+self.sha,b'x'*len(self.content))
        self.manifest['parts'][0].update(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        self.assertNotEqual(self.run_restore().returncode, 0)
        self.assertFalse((self.target/'public/one.bin').exists())


if __name__ == '__main__': unittest.main()
