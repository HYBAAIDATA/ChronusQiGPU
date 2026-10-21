import os
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_PYTHIA_ROOT = Path(__file__).resolve().parents[1]
if str(_PYTHIA_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHIA_ROOT))

import turing_core

from Intelligence.four_layer_stack import _double_sha256
from Intelligence.unified_manifold_device import (
    UnifiedManifoldHashingDevice,
)
try:
    from chronus.mla1517.mining.opencl_driver import OpenCLDevice, OpenCLDriver, OpenCLExecutionResult
    from chronus.mla1517.mining.pow import sha256d
except ImportError:
    from mla1517.mining.opencl_driver import OpenCLDevice, OpenCLDriver, OpenCLExecutionResult
    from mla1517.mining.pow import sha256d

HEADER = bytes(range(80))
TARGET_EASY = b"\xff" * 31 + b"\x7f"
TARGET_HARD = b"\x00" * 32


class UnifiedManifoldDeviceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.driver = OpenCLDriver()
        cls.device = UnifiedManifoldHashingDevice(
            nonce_space=4096,
            opencl_driver=cls.driver,
        )

    def test_compass_has_32_cassini_certified_faces(self):
        compass = self.device.compass
        self.assertEqual(len(compass), 32)
        self.assertEqual(sum(face.solid == "dodecahedron" for face in compass.faces), 12)
        self.assertEqual(sum(face.solid == "icosahedron" for face in compass.faces), 20)
        for face in compass.faces:
            self.assertIn(face.cassini_determinant, (-1, 1))
            self.assertTrue(turing_core.cassini_check(face.cassini_order))

    def test_fold_unfold_roundtrip_below_1e_14(self):
        folded = self.device.fold_state(HEADER)
        self.assertLess(folded.roundtrip_max_abs_error, 1e-14)
        self.assertLess(folded.folded_norm_sq, 1.0)
        other = self.device.fold_state(bytes(reversed(HEADER)))
        self.assertTrue(
            folded.zeckendorf_token != other.zeckendorf_token
            or folded.zeckendorf_token.startswith("ZECK-")
        )

    def test_shard_order_is_complete_permutation_no_pruning(self):
        order = self.device.shard_order(HEADER)
        nonces = list(order.iter_nonces())
        expected = list(range(self.device.nonce_start, self.device.nonce_start + 4096))
        self.assertEqual(sorted(nonces), expected)
        self.assertEqual(len(nonces), 4096)
        self.assertEqual(len(set(nonces)), 4096)
        self.assertEqual(sorted(order.face_order), list(range(32)))
        self.assertEqual(order.faces_pruned, 0)

        same = self.device.shard_order(HEADER)
        changed_header = bytearray(HEADER)
        changed_header[0] ^= 0x01
        changed = self.device.shard_order(bytes(changed_header))
        self.assertEqual(order.face_order, same.face_order)
        self.assertEqual(order.schedule_digest, same.schedule_digest)
        self.assertEqual(set(nonces), set(changed.iter_nonces()))

    def test_no_device_is_honestly_unavailable_no_share_accepted(self):
        if self.driver.available:
            self.skipTest("OpenCL device is available")
        result = self.device.run(HEADER, TARGET_EASY)
        self.assertEqual(result["hardware"]["status"], "NOT_RUN")
        self.assertEqual(result["truth_class"], "unavailable")
        self.assertEqual(result["measured_hashrate"], 0.0)
        self.assertEqual(result["hashes_computed"], 0)
        self.assertFalse(result["accepted"])
        self.assertIsNone(result["winning_nonce"])
        self.assertIsNone(result["igpu"])
        self.assertEqual(result["compass"]["faces"], 32)
        self.assertIn("manifold_fold", result)
        self.assertIn("shard_order", result)

    def test_fabricated_hashrate_impossible(self):
        with self.assertRaises(ValueError):
            OpenCLExecutionResult(
                requested_backend="opencl",
                selected_backend=None,
                actual_backend=None,
                device_name=None,
                device_available=False,
                hardware_execution=True,
                degraded=True,
                fallback_used=False,
                hashes_computed=1,
                elapsed_seconds=1.0,
                measured_hashrate=1.0,
                truth_class="unavailable",
            )

    def test_only_accept_path_is_sha256d_le_target(self):
        result = self.device.run(
            HEADER,
            TARGET_EASY,
            n_candidates=256,
            allow_cpu_reference=True,
        )
        self.assertTrue(result["accepted"], result)
        self.assertEqual(result["truth_class"], "measured_cpu_reference")
        self.assertFalse(result["hardware"]["hardware_execution"])
        nonce = result["winning_nonce"]
        self.assertIsNotNone(nonce)
        blob = HEADER[:76] + struct.pack("<I", nonce)
        self.assertLessEqual(
            int.from_bytes(sha256d(blob), "little"),
            int.from_bytes(TARGET_EASY, "big"),
        )
        self.assertEqual(_double_sha256(blob), bytes.fromhex(result["winning_hash"]))

        impossible = self.device.run(
            HEADER,
            TARGET_HARD,
            n_candidates=256,
            max_hashes=64,
            allow_cpu_reference=True,
        )
        self.assertFalse(impossible["accepted"])
        self.assertIsNone(impossible["winning_nonce"])
        self.assertLessEqual(impossible["hashes_computed"], 64)
        self.assertGreater(impossible["hashes_computed"], 0)

    def test_invalid_lengths_raise(self):
        with self.assertRaises(ValueError):
            self.device.run(b"\x00" * 79, TARGET_EASY)
        with self.assertRaises(ValueError):
            self.device.run(HEADER, b"\x00" * 31)

    def test_hyba_requirement_fails_closed_for_non_hyba_device(self):
        fake_driver = type(
            "FakeDriver",
            (),
            {
                "available": True,
                "devices": (
                    OpenCLDevice(
                        platform="p",
                        name="Intel(R) UHD Graphics 620",
                        vendor="Intel",
                        version="3.0",
                    ),
                ),
            },
        )()
        with patch.dict(os.environ, {"HYBA_REQUIRE_HYBA": "1"}):
            device = UnifiedManifoldHashingDevice(
                nonce_space=4096,
                opencl_driver=fake_driver,
                stack=self.device.stack,
            )
            result = device.run(HEADER, TARGET_EASY)
            self.assertFalse(device.hardware_available)
            self.assertEqual(result["hardware"]["status"], "NOT_RUN")
            self.assertEqual(result["truth_class"], "unavailable")
            self.assertFalse(result["accepted"])

    def test_hyba_device_is_available_under_strict_requirement(self):
        fake_driver = type(
            "FakeDriver",
            (),
            {
                "available": True,
                "devices": (
                    OpenCLDevice(
                        platform="p",
                        name="HYBA-MLA1517 iGPU",
                        vendor="HYBA",
                        version="3.0",
                    ),
                ),
            },
        )()
        with patch.dict(os.environ, {"HYBA_REQUIRE_HYBA": "1"}):
            device = UnifiedManifoldHashingDevice(
                nonce_space=4096,
                opencl_driver=fake_driver,
                stack=self.device.stack,
            )
            self.assertTrue(device.hardware_available)
            self.assertEqual(len(device.status()["hyba_devices"]), 1)

    def test_cpu_fallback_is_rejected_without_explicit_reference_permission(self):
        winning_nonce = next(
            nonce
            for nonce in range(4096)
            if int.from_bytes(
                sha256d(HEADER[:76] + struct.pack("<I", nonce)),
                "little",
            )
            <= int.from_bytes(TARGET_EASY, "big")
        )
        winning_hash = sha256d(HEADER[:76] + struct.pack("<I", winning_nonce)).hex()

        class FakeAethel:
            def store(self, key, value):
                return {"key": key, "size": len(value)}

        class FakeIGpu:
            def mine(self, header80, target_be, probe, *, max_hashes=None):
                return {
                    "winning_nonce": winning_nonce,
                    "winning_hash": winning_hash,
                    "recheck_bit_exact": True,
                    "hashes_computed": 1,
                    "elapsed_seconds": 0.1,
                    "measured_hps": 10.0,
                    "hasher_backend": "cpu",
                }

        class FakeStack:
            aethel = FakeAethel()
            igpu = FakeIGpu()

        fake_driver = type(
            "FakeDriver",
            (),
            {
                "available": True,
                "devices": (
                    OpenCLDevice(
                        platform="p",
                        name="HYBA-MLA1517 iGPU",
                        vendor="HYBA",
                        version="3.0",
                    ),
                ),
            },
        )()
        with patch.dict(os.environ, {"HYBA_REQUIRE_HYBA": ""}):
            device = UnifiedManifoldHashingDevice(
                nonce_space=4096,
                opencl_driver=fake_driver,
                stack=FakeStack(),
            )
            rejected = device.run(HEADER, TARGET_EASY)
            accepted = device.run(
                HEADER,
                TARGET_EASY,
                allow_cpu_reference=True,
            )

        self.assertEqual(rejected["truth_class"], "rejected")
        self.assertFalse(rejected["accepted"])
        self.assertIsNone(rejected["winning_nonce"])
        self.assertEqual(
            rejected["hardware"]["rejected_reason"],
            "cpu fallback without allow_cpu_reference",
        )
        self.assertEqual(accepted["truth_class"], "measured_cpu_reference")
        self.assertTrue(accepted["accepted"])
        self.assertEqual(accepted["winning_nonce"], winning_nonce)


if __name__ == "__main__":
    unittest.main()
