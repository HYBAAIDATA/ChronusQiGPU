"""Real script, real subprocess and filesystem regressions; no runtime substitution.

Temporary private keys here are test credentials, not external assurance.
"""
import copy
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(os.environ.get("CUSTODY_SCRIPT_UNDER_TEST", str(
    Path(__file__).resolve().parents[2] / "scripts/generate_validation_custody_artifact.py"
)))
spec = importlib.util.spec_from_file_location("custody_script", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class CustodyRegression(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "scripts").mkdir()
        shutil.copyfile(SCRIPT, self.root / "scripts/generate_validation_custody_artifact.py")
        (self.root / "Intelligence").mkdir()
        (self.root / "Intelligence/registry.py").write_text("VALUE = 1\n")
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "-c", "user.name=Unit", "-c", "user.email=unit@example.invalid",
                        "commit", "-qm", "fixture"], cwd=self.root, check=True)
        self.key = secrets.token_bytes(32)
        self.env = {"EUCLID_VALIDATION_CUSTODY_KEY_HEX": self.key.hex(),
                    "EUCLID_VALIDATION_CUSTODY_SIGNER": "unit-local-custodian"}

    def generate(self, code="print('real child execution')"):
        with patch.dict(os.environ, self.env):
            p = m.generate_custody_artifact(root=self.root,
                    commands=[[sys.executable, "-c", code]], timeout=5)
        return json.loads(p.read_text())

    def test_private_key_required_before_any_write_or_command(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                m.generate_custody_artifact(root=self.root, commands=[])
        self.assertFalse((self.root / "docs").exists())
        self.assertFalse((self.root / "evidence").exists())

    def test_public_historical_key_refused(self):
        with self.assertRaises(ValueError):
            m.validate_key(b"euclid-validation-custody-salt-20261014")

    def test_short_and_invalid_keys_refused(self):
        for value in (b"", b"a" * 31):
            with self.assertRaises(ValueError):
                m.validate_key(value)
        with patch.dict(os.environ, {**self.env, "EUCLID_VALIDATION_CUSTODY_KEY_HEX": "zz"}):
            with self.assertRaises(ValueError):
                m.credentials()

    def test_real_generation_and_roundtrip(self):
        artifact = self.generate()
        self.assertTrue(artifact["payload"]["all_commands_passed"])
        self.assertTrue(m.verify_artifact(artifact, self.key, self.root))
        cmd = artifact["payload"]["commands"][0]
        self.assertIn("real child execution", (self.root / cmd["log_path"]).read_text())
        self.assertIn("Intelligence/registry.py", artifact["payload"]["sha256"])
        self.assertIn("scripts/generate_validation_custody_artifact.py", artifact["payload"]["sha256"])

    def test_payload_tampering_rejected(self):
        artifact = self.generate()
        artifact["payload"]["all_commands_passed"] = False
        self.assertFalse(m.verify_artifact(artifact, self.key, self.root))

    def test_signer_metadata_tampering_rejected(self):
        artifact = self.generate()
        artifact["custody"]["signer_identity"] = "forged-independent-authority"
        self.assertFalse(m.verify_artifact(artifact, self.key, self.root))

    def test_wrong_private_key_rejected(self):
        self.assertFalse(m.verify_artifact(self.generate(), secrets.token_bytes(32), self.root))

    def test_source_drift_rejected(self):
        artifact = self.generate()
        (self.root / "Intelligence/registry.py").write_text("VALUE = 2\n")
        self.assertFalse(m.verify_artifact(artifact, self.key, self.root))

    def test_added_source_rejected(self):
        artifact = self.generate()
        (self.root / "Intelligence/added.py").write_text("VALUE = 2\n")
        self.assertFalse(m.verify_artifact(artifact, self.key, self.root))

    def test_log_tampering_rejected(self):
        artifact = self.generate()
        (self.root / artifact["payload"]["commands"][0]["log_path"]).write_text("forged")
        self.assertFalse(m.verify_artifact(artifact, self.key, self.root))

    def test_failed_command_is_recorded_not_success(self):
        artifact = self.generate("import sys; print('real failure'); sys.exit(7)")
        self.assertFalse(artifact["payload"]["all_commands_passed"])
        self.assertEqual(artifact["payload"]["commands"][0]["exit_code"], 7)
        # A failed result can have valid custody without becoming a passing validation.
        self.assertTrue(m.verify_artifact(artifact, self.key, self.root))

    def test_empty_command_list_cannot_pass(self):
        with patch.dict(os.environ, self.env):
            p = m.generate_custody_artifact(root=self.root, commands=[])
        artifact = json.loads(p.read_text())
        self.assertFalse(artifact["payload"]["all_commands_passed"])

    def test_source_mutation_during_command_cannot_pass(self):
        artifact = self.generate("from pathlib import Path; Path('Intelligence/registry.py').write_text('changed')")
        self.assertFalse(artifact["payload"]["source_stable"])
        self.assertFalse(artifact["payload"]["all_commands_passed"])
        self.assertFalse(m.verify_artifact(artifact, self.key, self.root))

    def test_signing_key_not_in_child_environment_or_logs(self):
        artifact = self.generate("import os; assert 'EUCLID_VALIDATION_CUSTODY_KEY_HEX' not in os.environ; print('clean')")
        self.assertTrue(artifact["payload"]["all_commands_passed"])
        self.assertNotIn(self.key.hex(), json.dumps(artifact))

    def test_actual_child_timeout(self):
        log = self.root / "timeout.log"
        out = m.run_command([sys.executable, "-c", "import time; time.sleep(2)"], self.root, log, .1)
        self.assertTrue(out["timed_out"])
        self.assertEqual(out["exit_code"], 124)
        self.assertIn("TIMEOUT", log.read_text())

    def test_missing_executable_recorded(self):
        out = m.run_command([str(self.root / "not-an-executable")], self.root, self.root / "missing.log")
        self.assertEqual(out["exit_code"], 127)

    def test_symlink_source_refused(self):
        external = self.root / "outside.py"
        external.write_text("outside")
        (self.root / "Intelligence/link.py").symlink_to(external)
        with self.assertRaises(ValueError):
            m.source_hashes(self.root)

    def test_symlink_publication_refused_without_overwrite(self):
        (self.root / "docs").mkdir()
        protected = self.root / "protected"
        protected.write_text("preserve")
        (self.root / "docs/euclid_frontier_local_validation.json").symlink_to(protected)
        with patch.dict(os.environ, self.env):
            with self.assertRaises(ValueError):
                m.generate_custody_artifact(root=self.root, commands=[])
        self.assertEqual(protected.read_text(), "preserve")

    def test_signed_traversal_log_rejected(self):
        artifact = self.generate()
        artifact["payload"]["commands"][0]["log_path"] = "../outside.log"
        forged = m.sign_artifact(artifact["payload"], self.key, "unit")
        self.assertFalse(m.verify_artifact(forged, self.key, self.root))

    def test_cli_missing_key_nonzero_preserves_existing_artifact(self):
        (self.root / "docs").mkdir()
        target = self.root / "docs/euclid_frontier_local_validation.json"
        target.write_text("preserve")
        env = {k: v for k, v in os.environ.items() if not k.startswith("EUCLID_VALIDATION_CUSTODY_")}
        proc = subprocess.run([sys.executable, str(self.root / "scripts/generate_validation_custody_artifact.py")],
                              cwd=self.root, env=env, capture_output=True)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(target.read_text(), "preserve")

    def test_cli_failed_validation_returns_nonzero(self):
        env = {**os.environ, **self.env}
        proc = subprocess.run([sys.executable, str(self.root / "scripts/generate_validation_custody_artifact.py")],
                              cwd=self.root, env=env, capture_output=True, timeout=30)
        self.assertEqual(proc.returncode, 1)
        artifact = json.loads((self.root / "docs/euclid_frontier_local_validation.json").read_text())
        self.assertFalse(artifact["payload"]["all_commands_passed"])
        self.assertTrue(m.verify_artifact(artifact, self.key, self.root))

    def test_cli_verification_valid_then_tampered(self):
        self.generate()
        target = self.root / "docs/euclid_frontier_local_validation.json"
        command = [sys.executable, str(self.root / "scripts/generate_validation_custody_artifact.py"),
                   "--verify", str(target)]
        env = {**os.environ, **self.env}
        self.assertEqual(subprocess.run(command, env=env, capture_output=True).returncode, 0)
        artifact = json.loads(target.read_text())
        artifact["custody"]["signer_identity"] = "other"
        target.write_text(json.dumps(artifact))
        self.assertEqual(subprocess.run(command, env=env, capture_output=True).returncode, 1)

    def test_publication_failure_preserves_existing_directory_and_cleans_temp(self):
        target = self.root / "docs/euclid_frontier_local_validation.json"
        target.mkdir(parents=True)
        (target / "preserved").write_text("unchanged")
        with patch.dict(os.environ, self.env):
            with self.assertRaises(OSError):
                m.generate_custody_artifact(root=self.root, commands=[[sys.executable, "-c", "print('ok')"]])
        self.assertEqual((target / "preserved").read_text(), "unchanged")
        self.assertEqual(list(target.parent.glob(".custody-*")), [])

    def test_legacy_public_key_artifact_not_accepted(self):
        payload = {"all_commands_passed": True, "commands": []}
        signature = hmac.new(b"euclid-validation-custody-salt-20261014",
                             json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(),
                             hashlib.sha256).hexdigest()
        legacy = {"payload": payload, "custody": {"signature": signature,
                  "signature_scheme": "HMAC-SHA256", "signer_identity": "authority"}}
        self.assertFalse(m.verify_artifact(legacy, self.key, self.root))

    def test_resigned_inconsistent_success_rejected(self):
        artifact = self.generate("import sys; sys.exit(7)")
        payload = copy.deepcopy(artifact["payload"])
        payload["all_commands_passed"] = True
        self.assertFalse(m.verify_artifact(m.sign_artifact(payload, self.key, "unit"), self.key, self.root))


if __name__ == "__main__":
    unittest.main()
