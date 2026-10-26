"""Normal-package acceptance; no initializer bypass, provider double or monkeypatch.

Requires the complete supported repository installation. These tests do not
establish identity, network service, hardware or whole-launch qualification.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from aethel.theseus import TheseusError
from aethel.enterprise_bridge import (
    compute_envelope_provenance_hash,
    open_enterprise_store,
    smoke_measured_put,
)


class EnterpriseBridgeDurable(unittest.TestCase):
    def test_default_durable_requires_directory(self):
        with self.assertRaisesRegex(ValueError, "durable_dir"):
            open_enterprise_store()

    def test_empty_directory_string_refused(self):
        with self.assertRaisesRegex(ValueError, "durable_dir"):
            open_enterprise_store(durable_dir="")

    def test_memory_mode_is_explicit(self):
        db = open_enterprise_store(durable=False)
        rec = db.put(b"explicit-memory", durable=False)
        self.assertEqual(db.get(rec.uuid), b"explicit-memory")
        self.assertEqual(db.health()["status"], "memory_only")

    def test_conflicting_mode_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "durable=False"):
                open_enterprise_store(durable=False, durable_dir=directory)

    def test_smoke_requires_retained_directory(self):
        with self.assertRaisesRegex(ValueError, "durable_dir"):
            smoke_measured_put()

    def test_durable_smoke_and_envelope_integrity(self):
        with tempfile.TemporaryDirectory() as directory:
            env = smoke_measured_put(b"bridge-durable", durable_dir=directory)
            self.assertIs(env["payload"]["ok"], True)
            self.assertEqual(env["payload"]["custody"]["authority"], "theseus")
            self.assertIs(env["payload"]["custody"]["disk_bound"], True)
            self.assertEqual(env["payload"]["restart_evidence"], "reattach_same_process")
            self.assertEqual(env["provenance_hash"], compute_envelope_provenance_hash(env))
            self.assertTrue((Path(directory) / "theseus_index.json").is_file())

    def test_acknowledged_commit_survives_fresh_process(self):
        payload = b"fresh-process-custody"
        with tempfile.TemporaryDirectory() as directory:
            db = open_enterprise_store(durable_dir=directory)
            rec = db.put(payload, durable=True)
            script = '''import hashlib, json, sys
from aethel.enterprise_bridge import open_enterprise_store
store = open_enterprise_store(durable_dir=sys.argv[1])
payload = store.get(sys.argv[2])
if hashlib.sha256(payload).hexdigest() != sys.argv[3] or store.verify() is not True:
    raise RuntimeError("restart verification failed")
print(json.dumps({"digest": hashlib.sha256(payload).hexdigest(), "verified": True}))
'''
            child = subprocess.run(
                [sys.executable, "-I", "-c", script, directory, rec.uuid, rec.digest],
                text=True, capture_output=True, timeout=60,
            )
            # -I deliberately removes source/PYTHONPATH fallbacks: installed package required.
            self.assertEqual(child.returncode, 0, child.stdout + child.stderr)
            self.assertEqual(json.loads(child.stdout)["digest"], hashlib.sha256(payload).hexdigest())

    def test_nonempty_unindexed_store_refused_without_deletion(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "preserve.me"
            marker.write_bytes(b"do-not-migrate")
            with self.assertRaises(TheseusError):
                open_enterprise_store(durable_dir=directory)
            self.assertEqual(marker.read_bytes(), b"do-not-migrate")


if __name__ == "__main__":
    unittest.main()
