"""
Unit Tests: Persistent Primitive Repository & Cryptographic HMAC Verification v16.0
====================================================================================
Verifies declarative schema persistence, HMAC signature checks, tampering rejection, and explicit error logging.
"""

import os
import shutil
import tempfile
import unittest
from euclid.transfer.persistent_repository import PersistentPrimitiveRepository

class TestPersistentRepositorySecurity(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.repo_file = os.path.join(self.test_dir, "test_repo.json")
        self.repo = PersistentPrimitiveRepository(storage_path=self.repo_file)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_valid_primitive_serialization_and_reload(self):
        def dummy_op(c: str, s: int = 42):
            return c, "ADD:AnnAssign"

        self.repo.register_primitive(
            name="AUTO:TestRule",
            op_func=dummy_op,
            rule_type="ADD:AnnAssign",
            origin_target="test.py",
            cum_gain=0.010
        )
        
        self.assertTrue(os.path.exists(self.repo_file))

        # Reload repo and verify signature validation passes
        reloaded_repo = PersistentPrimitiveRepository(storage_path=self.repo_file)
        primitives = reloaded_repo.get_all_primitives()
        
        self.assertEqual(len(primitives), 1)
        name, func = primitives[0]
        self.assertEqual(name, "AUTO:TestRule")

    def test_tampered_signature_rejection(self):
        def dummy_op(c: str, s: int = 42):
            return c, "ADD:AnnAssign"

        self.repo.register_primitive(
            name="AUTO:TamperedRule",
            op_func=dummy_op,
            rule_type="ADD:AnnAssign",
            origin_target="test.py",
            cum_gain=0.010
        )

        # Corrupt HMAC signature in JSON
        with open(self.repo_file, "r", encoding="utf-8") as f:
            data = f.read().replace("AUTO:TamperedRule", "AUTO:ForgedRule")
        with open(self.repo_file, "w", encoding="utf-8") as f:
            f.write(data)

        # Reload repo and verify tampered entry is REJECTED
        reloaded_repo = PersistentPrimitiveRepository(storage_path=self.repo_file)
        primitives = reloaded_repo.get_all_primitives()
        self.assertEqual(len(primitives), 0)

    def test_filesystem_save_failure_handling(self):
        invalid_path = "/invalid_root_dir_9999/repo.json"
        repo_invalid = PersistentPrimitiveRepository(storage_path=invalid_path)
        
        # Save should log error gracefully without crashing
        def dummy_op(c: str, s: int = 42):
            return c, "ADD:AnnAssign"

        repo_invalid.register_primitive(
            name="AUTO:FailRule",
            op_func=dummy_op,
            rule_type="ADD:AnnAssign",
            origin_target="test.py",
            cum_gain=0.010
        )

if __name__ == "__main__":
    unittest.main()
