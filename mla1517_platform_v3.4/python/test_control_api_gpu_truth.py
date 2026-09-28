import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import control_api


class GPUTruthTests(unittest.TestCase):
    def setUp(self):
        control_api._GPU_CACHE.update({"at": 0.0, "payload": None})

    def test_cpu_opencl_device_is_not_reported_as_gpu_available(self):
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
        with patch("hyba.gpureport.report", return_value=report):
            payload = control_api.gpu_payload()
        self.assertFalse(payload["available"])
        self.assertEqual(payload["count"], 0)
        self.assertEqual(payload["opencl_device_count"], 1)

    def test_gpu_count_excludes_other_opencl_devices(self):
        report = {
            "opencl": {
                "devices": [
                    {"name": "PoCL CPU", "vendor": "PoCL", "is_gpu": False},
                    {"name": "Discrete GPU", "vendor": "Vendor", "is_gpu": True},
                ]
            },
            "hasher": {"backend": "opencl:gpu"},
        }
        with patch("hyba.gpureport.report", return_value=report):
            payload = control_api.gpu_payload()
        self.assertTrue(payload["available"])
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["opencl_device_count"], 2)


if __name__ == "__main__":
    unittest.main()
