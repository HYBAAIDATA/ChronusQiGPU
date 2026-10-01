import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from chronus.mla1517.store import PrimeDB
from chronus.mla1517.runtime import MLA1517Runtime
from chronus.mla1517.behavior import load_behavior
from chronus.mla1517.connectors import BackendConnector
from chronus.mla1517.scale import ScaleBudget


class RuntimeTests(unittest.TestCase):
    def test_default_own_gpu_with_reference_fallback(self):
        with patch.dict(
            os.environ,
            {
                "MLA1517_GPU_CONNECTED": "0",
                "MLA1517_HOST_GPU_CONNECTED": "1",
                "MLA1517_HOST_GPU_ASSIST": "0",
            },
            clear=False,
        ):
            caps = BackendConnector().capabilities()
            self.assertEqual(caps.requested_mode, "mla1517_gpu")
            self.assertEqual(caps.selected_mode, "mla1517_gpu")
            self.assertEqual(caps.execution_backend, "cpu_reference")
            self.assertFalse(caps.scaling_applied)

    def test_connected_mla_gpu_with_host_assist_scales(self):
        with patch.dict(
            os.environ,
            {
                "MLA1517_GPU_CONNECTED": "1",
                "MLA1517_HOST_GPU_CONNECTED": "1",
                "MLA1517_HOST_GPU_ASSIST": "1",
            },
            clear=False,
        ):
            caps = BackendConnector("mla1517_gpu").capabilities()
            self.assertTrue(caps.connected)
            self.assertTrue(caps.host_assist_connected)
            self.assertTrue(caps.scaling_applied)
            self.assertEqual(caps.scaling_mode, "mla1517_native_plus_host_assist")
            self.assertEqual(caps.capacity_mode, "candidate_exponential_measured_only")

    def test_host_only_is_not_own_gpu(self):
        with patch.dict(
            os.environ,
            {
                "MLA1517_GPU_CONNECTED": "0",
                "MLA1517_HOST_GPU_CONNECTED": "1",
                "MLA1517_HOST_GPU_ASSIST": "1",
            },
            clear=False,
        ):
            caps = BackendConnector("mla1517_gpu").capabilities()
            self.assertEqual(caps.selected_mode, "mla1517_gpu")
            self.assertFalse(caps.connected)
            self.assertTrue(caps.degraded)

    def test_auto_can_use_host_only_when_explicitly_requested(self):
        with patch.dict(
            os.environ,
            {
                "MLA1517_GPU_CONNECTED": "0",
                "MLA1517_HOST_GPU_CONNECTED": "1",
                "MLA1517_HOST_GPU_ASSIST": "0",
            },
            clear=False,
        ):
            caps = BackendConnector("auto").capabilities()
            self.assertEqual(caps.selected_mode, "host_gpu_overlay")
            self.assertTrue(caps.connected)
            self.assertTrue(caps.scaling_applied)

    def test_host_gpu_required_fails_closed(self):
        with patch.dict(os.environ, {"MLA1517_HOST_GPU_CONNECTED": "0"}, clear=False):
            c = BackendConnector(
                "host_gpu_overlay", allow_cpu_fallback=False, require_host_gpu=True
            )
            with self.assertRaises(RuntimeError):
                c.execute([1, 2], 2, lambda x: x)

    def test_runtime_reports_scaling_state(self):
        with (
            tempfile.TemporaryDirectory() as d,
            patch.dict(
                os.environ,
                {
                    "MLA1517_GPU_CONNECTED": "1",
                    "MLA1517_HOST_GPU_CONNECTED": "1",
                    "MLA1517_HOST_GPU_ASSIST": "1",
                },
                clear=False,
            ),
        ):
            db = PrimeDB(Path(d) / "prime.db")
            obj = db.put({"kind": "workload", "family": "fibonacci"}, sequence_index=15, scale=15)
            report = MLA1517Runtime(db, mode="mla1517_gpu", lanes=7).execute(
                obj, range(101), lambda x: x + 1
            )
            self.assertTrue(report["connected"])
            self.assertTrue(report["host_assist_connected"])
            self.assertTrue(report["scaling_applied"])
            self.assertEqual(report["scaling_mode"], "mla1517_native_plus_host_assist")
            self.assertFalse(report["unlimited_speed_or_capacity"])
            db.close()

    def test_runtime_scale_control_is_reported(self):
        with (
            tempfile.TemporaryDirectory() as d,
            patch.dict(
                os.environ,
                {"MLA1517_GPU_CONNECTED": "0", "MLA1517_HOST_GPU_CONNECTED": "0"},
                clear=False,
            ),
        ):
            db = PrimeDB(Path(d) / "prime.db")
            obj = db.put({"kind": "workload"}, sequence_index=15, scale=15)
            report = MLA1517Runtime(
                db, mode="cpu_reference", scale_budget=ScaleBudget(max_index=20)
            ).execute(obj, [1], lambda x: x)
            self.assertTrue(report["scale_control"]["accepted"])
            self.assertEqual(report["scale_control"]["reason"], "accepted")
            db.close()

    def test_runtime_rejects_scale_budget(self):
        with tempfile.TemporaryDirectory() as d:
            db = PrimeDB(Path(d) / "prime.db")
            obj = db.put({"kind": "workload"}, sequence_index=15, scale=15)
            with self.assertRaises(RuntimeError):
                MLA1517Runtime(
                    db, mode="cpu_reference", scale_budget=ScaleBudget(max_index=10)
                ).execute(obj, [1], lambda x: x)
            db.close()

    def test_behavior_defaults(self):
        b = load_behavior()
        self.assertEqual(b["mode"], "mla1517_gpu")
        self.assertEqual(b["host_gpu_role"], "optional_scale_assist")
        self.assertEqual(b["scaling_claim"], "candidate_exponential_measured_only")
        self.assertFalse(b["unlimited_speed_or_capacity_claim"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
