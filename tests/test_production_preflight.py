from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import production_preflight as preflight


def _importer(_name: str):
    return object()


class ProductionPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def env(self, **extra):
        return {"PYTHIA_RUNTIME_CONFIG": str(self.root / "runtime.json"), **extra}

    def test_application_profile_passes_with_imports_and_writable_config(self):
        report = preflight.evaluate("application", env=self.env(), importer=_importer, modules=("a", "b"))
        self.assertEqual(report["state"], "PASS")
        self.assertEqual(report["side_effects"], "none")

    def test_device_profile_blocks_without_opencl_backend(self):
        report = preflight.evaluate("device", env=self.env(), importer=_importer, modules=())
        self.assertEqual(report["state"], "BLOCKED")
        self.assertTrue(any(c["name"] == "device_backend" for c in report["checks"]))

    def test_device_profile_requires_an_enumerated_device(self):
        env = self.env(MLA1517_GPU_BACKEND="opencl")
        blocked = preflight.evaluate("device", env=env, importer=_importer, modules=(), opencl_probe=lambda: (0, "none"))
        self.assertEqual(blocked["state"], "BLOCKED")
        passed = preflight.evaluate("device", env=env, importer=_importer, modules=(), opencl_probe=lambda: (1, "one"))
        self.assertEqual(passed["state"], "PASS")

    def test_live_profile_names_missing_inputs_without_leaking_values(self):
        env = self.env(MLA1517_GPU_BACKEND="opencl", MLA1517_STRATUM_PASSWORD="top-secret")
        report = preflight.evaluate("live", env=env, importer=_importer, modules=(), opencl_probe=lambda: (1, "one"))
        rendered = json.dumps(report)
        self.assertEqual(report["state"], "BLOCKED")
        self.assertNotIn("top-secret", rendered)
        self.assertIn("MLA1517_STRATUM_USER", rendered)
        self.assertEqual(report["side_effects"], "none")

    def test_live_profile_passes_only_when_canonical_m3_and_identity_are_configured(self):
        import hashlib

        endpoint, worker = "pool.example:3333", "real-account.worker"
        approval = hashlib.sha256(f"{endpoint}|{worker}".encode()).hexdigest()
        (self.root / "runtime.json").write_text(json.dumps({
            "pools": [{
                "enabled": True, "endpoint": endpoint, "worker": worker,
                "password": "secret-not-printed",
            }],
            "live_submit": {"enabled": True, "approval_id": approval},
        }))
        env = self.env(
            MLA1517_GPU_BACKEND="opencl",
            MLA1517_STRATUM_USER=worker,
            MLA1517_STRATUM_PASSWORD="secret",
            MLA1517_BRAIINS_ENDPOINT=endpoint,
            PYTHIA_M3_REQUIRED="1",
            PYTHIA_STORAGE_DB="/persist/mining.db",
            PYTHIA_STORAGE_ROOT="/persist/cas",
            PYTHIA_STORAGE_CUSTODY_ROOT="/persist/custody",
            PYTHIA_STORAGE_TENANT="real-mining-tenant",
            PYTHIA_STORAGE_INTEGRITY_KEY_HEX="ab" * 32,
            PYTHIA_STORAGE_CUSTODY_KEY_HEX="cd" * 32,
            PYTHIA_M3_ACTOR="real-actor",
            PYTHIA_M3_AL_HARAS_TOKEN="secret-subscription",
        )
        report = preflight.evaluate(
            "live", env=env, importer=_importer, modules=(),
            opencl_probe=lambda: (1, "one"),
        )
        self.assertEqual(report["state"], "PASS")
        self.assertNotIn("secret", json.dumps(report))
        self.assertEqual(report["side_effects"], "none")

        # Wrong pool identity revokes the gate even with all secrets present.
        (self.root / "runtime.json").write_text(json.dumps({
            "pools": [{"enabled": True, "endpoint": endpoint,
                       "worker": "another.worker"}],
            "live_submit": {"enabled": True, "approval_id": approval},
        }))
        rejected = preflight.evaluate(
            "live", env=env, importer=_importer, modules=(),
            opencl_probe=lambda: (1, "one"),
        )
        self.assertEqual(rejected["state"], "BLOCKED")

    def test_legacy_bridge_env_gates_cannot_qualify_canonical_live(self):
        env = self.env(
            MLA1517_GPU_BACKEND="opencl",
            MLA1517_STRATUM_USER="worker",
            MLA1517_STRATUM_PASSWORD="secret",
            MLA1517_BRAIINS_ENDPOINT="pool.example:3333",
            HYBA_ENABLE_LIVE_SHARE_SUBMIT="true",
            HYBA_LIVE_SHARE_APPROVAL_ID="approval",
            HYBA_AUTONOMOUS_EXTERNAL_ACTIONS="1",
        )
        report = preflight.evaluate(
            "live", env=env, importer=_importer, modules=(),
            opencl_probe=lambda: (1, "one"),
        )
        self.assertEqual(report["state"], "BLOCKED")
        self.assertIn("strict_m3", [r["name"] for r in report["checks"]
                                    if r["state"] == "BLOCKED"])


if __name__ == "__main__":
    unittest.main()
