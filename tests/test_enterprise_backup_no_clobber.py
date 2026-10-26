"""Normal installed custody API tests; no initializer/authority doubles."""
from pathlib import Path
import secrets
import tempfile
import unittest

from aethel.enterprise.custody import compose
from aethel.enterprise.errors import AuthorityBoundaryError


class EnterpriseBackupNoClobber(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = compose(self.root / 'custody', tenant='tenant', hmac_key=secrets.token_bytes(32))
        self.addCleanup(self.store.close)
        self.store.put(b'backup-fixture', record_id='record')

    def test_existing_destination_preserved(self):
        destination = self.root / 'existing'
        destination.mkdir()
        (destination / 'precious').write_bytes(b'preserve-fixture')
        with self.assertRaises(FileExistsError):
            self.store.backup(destination)
        self.assertEqual((destination / 'precious').read_bytes(), b'preserve-fixture')
        self.assertEqual(self.store.get('record'), b'backup-fixture')

    def test_live_root_and_ancestor_refused(self):
        for destination in (self.store.tenant_root, self.store.tenant_root.parent):
            with self.subTest(destination=destination):
                with self.assertRaises(AuthorityBoundaryError):
                    self.store.backup(destination)
                self.assertEqual(self.store.get('record'), b'backup-fixture')

    def test_nested_destination_refused(self):
        destination = self.store.tenant_root / 'recursive-copy'
        with self.assertRaises(AuthorityBoundaryError):
            self.store.backup(destination)
        self.assertFalse(destination.exists())
        self.assertEqual(self.store.get('record'), b'backup-fixture')

    def test_new_snapshot_can_be_read_as_separate_store(self):
        destination = self.root / 'snapshot-parent' / 'tenant'
        self.store.backup(destination)
        reopened = compose(destination.parent, tenant='tenant', hmac_key=self.store.hmac_key)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.get('record'), b'backup-fixture')
        self.assertEqual(self.store.get('record'), b'backup-fixture')


if __name__ == '__main__':
    unittest.main()
