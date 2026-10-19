"""Tests use synthetic content only; no vendor archive or user data."""
import importlib.util
import json
from pathlib import Path
import struct
import plistlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('installer', Path(__file__).resolve().parents[1] / 'installer.py')
i = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(i)


class Transactions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.archive = self.root / 'app.asar'
        value = b'let title="Example";'
        untouched = b'unchanged-code'
        tree = {'files': {'ui.js': {'size': len(value), 'offset': '0'},
                          'logic.js': {'size': len(untouched), 'offset': str(len(value))},
                          'link': {'link': 'logic.js'},
                          'external': {'size': 1, 'unpacked': True}}}
        raw = json.dumps(tree, separators=(',', ':')).encode()
        padded = raw + b'\0' * (-len(raw) % 4)
        self.archive.write_bytes(struct.pack('<4I', 4, len(padded)+8, len(padded)+4, len(raw)) + padded + value + untouched)
        start = value.index(b'"')
        end = value.index(b'"', start+1)+1
        translated = 'let title="ตัวอย่าง";'.encode()
        self.manifest = {'schema': 1, 'version': 'test', 'supported_app_version': 'test',
                         'source_sha256': i.file_hash(self.archive), 'files': {
            'ui.js': {'source_sha256': i.digest(value), 'patched_sha256': i.digest(translated),
                      'patches': [{'start': start, 'end': end, 'source_sha256': i.digest(value[start:end]), 'replacement': '"ตัวอย่าง"'}]}}}
        output = self.root / 'build.asar'
        self.manifest['patched_sha256'] = i.build(self.archive, output, self.manifest)
        self.original = self.archive.read_bytes()
        self.args = ['--archive', str(self.archive), '--backup-root', str(self.root/'backups')]
        self.mock = patch.object(i, 'load_manifest', return_value=self.manifest)
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def test_install_repeat_revert(self):
        i.main(['check', *self.args])
        self.assertFalse((self.root/'backups').exists())
        i.main(['install', *self.args])
        backup = next((self.root/'backups').iterdir())
        before = {p: p.stat().st_mtime_ns for p in self.root.rglob('*') if p.is_file()}
        i.main(['install', *self.args])
        self.assertEqual(before, {p: p.stat().st_mtime_ns for p in self.root.rglob('*') if p.is_file()})
        i.main(['revert', *self.args, '--backup', str(backup)])
        self.assertEqual(self.archive.read_bytes(), self.original)

    def test_unknown_base_refused_without_backup(self):
        self.archive.write_bytes(self.original+b'updated')
        with self.assertRaises(i.PatchError):
            i.main(['install', *self.args])
        self.assertFalse((self.root/'backups').exists())

    def test_corrupt_backup_cannot_overwrite_current(self):
        i.main(['install', *self.args])
        backup = next((self.root/'backups').iterdir())
        (backup/'app.asar').write_bytes(b'broken')
        before = self.archive.read_bytes()
        with self.assertRaises(i.PatchError):
            i.main(['revert', *self.args, '--backup', str(backup)])
        self.assertEqual(self.archive.read_bytes(), before)

    def test_concurrent_update_is_not_overwritten(self):
        proposed = self.root/'replacement'
        proposed.write_bytes(b'new')
        self.archive.write_bytes(b'concurrent-update')
        with self.assertRaises(i.PatchError):
            i.atomic_copy(proposed, self.archive, self.manifest['source_sha256'])
        self.assertEqual(self.archive.read_bytes(), b'concurrent-update')
        self.assertFalse(list(self.root.glob('.vivo-thai-*')))

    def test_symlink_refused(self):
        link = self.root/'shortcut'
        link.symlink_to(self.archive)
        with self.assertRaises(i.PatchError):
            i.safe_path(link)

    def test_background_toast_does_not_block_but_main_app_does(self):
        app = self.root / 'pcsuite.app'
        (app / 'Contents').mkdir(parents=True)
        (app / 'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleExecutable': 'pcsuite'}))
        toast = str(app / 'Contents/MacOS/mac_toast')
        main = str(app / 'Contents/MacOS/pcsuite')
        with patch.object(i.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, toast+'\n', '')):
            i.ensure_stopped(app)
        with patch.object(i.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, main+'\n'+toast+'\n', '')):
            with self.assertRaises(i.PatchError):
                i.ensure_stopped(app)


if __name__ == '__main__':
    unittest.main()
