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

    def test_live_profile_passes_only_when_all_gates_are_armed(self):
        env = self.env(
            MLA1517_GPU_BACKEND="opencl",
            MLA1517_STRATUM_USER="worker",
            MLA1517_STRATUM_PASSWORD="secret",
            MLA1517_BRAIINS_ENDPOINT="pool.example:3333",
            HYBA_ENABLE_LIVE_SHARE_SUBMIT="true",
            HYBA_LIVE_SHARE_APPROVAL_ID="approval",
            HYBA_AUTONOMOUS_EXTERNAL_ACTIONS="1",
        )
        report = preflight.evaluate("live", env=env, importer=_importer, modules=(), opencl_probe=lambda: (1, "one"))
        self.assertEqual(report["state"], "PASS")


if __name__ == "__main__":
    unittest.main()
