import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import control_api


class GPUTruthTests(unittest.TestCase):
    def setUp(self):
        control_api._GPU_CACHE.update({"at": 0.0, "payload": None})

    def test_opencl_cpu_is_a_valid_host_for_the_logical_substrate(self):
        report = {
            "opencl": {
                "devices": [
                    {
                        "name": "PoCL CPU",
                        "vendor": "PoCL",
                        "is_gpu": False,
                    }
                ]
            },
            "hasher": {"backend": "opencl:cpu"},
        }
        with patch("chronus.report.report", return_value=report):
            payload = control_api.gpu_payload()
        self.assertTrue(payload["available"])
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["opencl_device_count"], 1)
        self.assertFalse(payload["physical_gpu_available"])
        self.assertEqual(payload["physical_gpu_count"], 0)
        self.assertFalse(payload["backend_active"])
        self.assertFalse(payload["logical_substrate"]["active"])
        self.assertEqual(payload["detected_backend"], "opencl:cpu")
        self.assertEqual(payload["logical_substrate"]["host_backend"], "opencl:cpu")
        self.assertTrue(payload["logical_substrate"]["available"])
        self.assertFalse(payload["logical_substrate"]["fallback_used"])
        self.assertNotIn("running_backend", payload)

    def test_physical_gpu_count_excludes_other_opencl_devices(self):
        report = {
            "opencl": {
                "devices": [
                    {"name": "PoCL CPU", "vendor": "PoCL", "is_gpu": False},
                    {"name": "Discrete GPU", "vendor": "Vendor", "is_gpu": True},
                ]
            },
            "hasher": {"backend": "opencl:gpu"},
        }
        with patch("chronus.report.report", return_value=report):
            payload = control_api.gpu_payload()
        self.assertTrue(payload["available"])
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["opencl_device_count"], 2)
        self.assertTrue(payload["physical_gpu_available"])
        self.assertEqual(payload["physical_gpu_count"], 1)
        self.assertTrue(payload["backend_active"])
        self.assertTrue(payload["logical_substrate"]["active"])

    def test_named_punch_backend_must_match_a_gpu_class_device(self):
        # opencl:<device name> has no class suffix — active only when the
        # bound name matches a GPU-class device in the enumeration.
        devices = [
            {"name": "PoCL CPU", "vendor": "PoCL", "is_gpu": False},
            {"name": "Discrete GPU", "vendor": "Vendor", "is_gpu": True},
        ]
        with patch(
            "chronus.report.report",
            return_value={"opencl": {"devices": devices}, "punch": {"backend": "opencl:PoCL CPU"}},
        ):
            payload = control_api.gpu_payload()
        self.assertTrue(payload["physical_gpu_available"])
        self.assertFalse(payload["backend_active"])
        self.assertFalse(payload["logical_substrate"]["active"])
        control_api._GPU_CACHE.update({"at": 0.0, "payload": None})
        with patch(
            "chronus.report.report",
            return_value={"opencl": {"devices": devices}, "punch": {"backend": "opencl:Discrete GPU"}},
        ):
            payload = control_api.gpu_payload()
        self.assertTrue(payload["backend_active"])

    def test_cpu_reference_keeps_the_logical_substrate_available(self):
        report = {
            "opencl": {"devices": []},
            "hasher": {
                "backend": "cpu",
                "device": "CPU (hashlib)",
                "fallback_reason": "no OpenCL device",
            },
        }
        with patch("chronus.report.report", return_value=report):
            payload = control_api.gpu_payload()
        self.assertTrue(payload["available"])
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["opencl_device_count"], 0)
        self.assertFalse(payload["physical_gpu_available"])
        self.assertFalse(payload["backend_active"])
        self.assertFalse(payload["logical_substrate"]["active"])
        self.assertEqual(payload["logical_substrate"]["host_backend"], "cpu")
        self.assertTrue(payload["logical_substrate"]["fallback_used"])

    def test_cpu_reference_does_not_impersonate_a_bound_mining_device(self):
        control = type("Control", (), {"mmio_device": None})()
        with patch(
            "control_api.gpu_payload",
            return_value={"available": True, "opencl_device_count": 0},
        ):
            reason = control_api._mining_device_reason(control)
        self.assertIn("no mining device", reason)


if __name__ == "__main__":
    unittest.main()
