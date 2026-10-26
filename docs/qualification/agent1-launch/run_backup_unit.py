"""Real backup method/filesystem unit; custody actor/event doubles are explicit.

NOT installed custody or authenticated backup/restore acceptance.
Overlap cases use a tripwire copy function to avoid legacy recursive copying.
"""
import ast
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(sys.argv.pop(1)) if len(sys.argv) > 1 else ROOT / 'aethel/enterprise/custody.py'

class AuthorityBoundaryError(RuntimeError): pass


def method():
    tree = ast.parse(SOURCE.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'EnterpriseCustody')
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'backup')
    namespace = {'Path': Path, 'shutil': shutil, 'time': types.SimpleNamespace(time=lambda: 0),
        'CustodyEvent': lambda **kw: kw, 'AuthorityBoundaryError': AuthorityBoundaryError}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SOURCE), 'exec'), namespace)
    return namespace['backup']


class BackupUnit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'live' / 'tenant'
        self.source.mkdir(parents=True)
        (self.source / 'record').write_bytes(b'live-fixture')
        self.events = []
        self.actor = types.SimpleNamespace(tenant_root=self.source, tenant='tenant',
            _lock=threading.RLock(), telemetry=types.SimpleNamespace(incr=lambda _: None),
            _ignore_lock_files=lambda directory, names: [], _append_event=self.events.append)
        self.backup = method()
    def test_existing_destination_preserved(self):
        dest = self.root / 'existing'; dest.mkdir(); (dest/'precious').write_bytes(b'preserve-fixture')
        with self.assertRaises(FileExistsError): self.backup(self.actor, dest)
        self.assertEqual((dest/'precious').read_bytes(), b'preserve-fixture')
        self.assertEqual(self.events, [])
    def test_same_root_refused_before_io(self):
        with patch.object(shutil, 'copytree', side_effect=AssertionError('copy tripwire')):
            with self.assertRaises(AuthorityBoundaryError): self.backup(self.actor, self.source)
        self.assertEqual((self.source/'record').read_bytes(), b'live-fixture')
    def test_ancestor_refused_before_io(self):
        with patch.object(shutil, 'copytree', side_effect=AssertionError('copy tripwire')):
            with self.assertRaises(AuthorityBoundaryError): self.backup(self.actor, self.source.parent)
        self.assertEqual((self.source/'record').read_bytes(), b'live-fixture')
    def test_descendant_refused_before_copy(self):
        with patch.object(shutil, 'copytree', side_effect=AssertionError('copy tripwire')):
            with self.assertRaises(AuthorityBoundaryError): self.backup(self.actor, self.source/'nested')
        self.assertFalse((self.source/'nested').exists())
    def test_new_disjoint_destination_copied(self):
        dest = self.root/'snapshot'
        self.assertEqual(self.backup(self.actor, dest), dest)
        self.assertEqual((dest/'record').read_bytes(), b'live-fixture')
        self.assertEqual((self.source/'record').read_bytes(), b'live-fixture')
        self.assertEqual(len(self.events), 1)
    def test_symlink_destination_preserved(self):
        target=self.root/'target'; target.mkdir(); (target/'precious').write_bytes(b'preserve-fixture')
        link=self.root/'link'; link.symlink_to(target, target_is_directory=True)
        with self.assertRaises(FileExistsError): self.backup(self.actor, link)
        self.assertTrue(link.is_symlink())
        self.assertEqual((target/'precious').read_bytes(), b'preserve-fixture')

if __name__ == '__main__': unittest.main(verbosity=2)
