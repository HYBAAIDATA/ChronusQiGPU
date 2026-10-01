"""Remote-GPU binding tests — a device anywhere binds as real hardware.

The agent on this box honestly reports no OpenCL platforms; the
behavioural contract (client protocol, verification, connector and
inventory wiring) is exercised over loopback with a stub agent that
serves measured rows.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from chronus.mla1517.core import fib, lucas
from chronus.mla1517.remote_gpu import (
    PROTOCOL_VERSION,
    SHA256D_MAX_WINDOW,
    RemoteGPUClient,
    RemoteGPUUnavailable,
    RemoteGPUVerificationError,
    probe_first_reachable,
    sha256d_share_attestation,
)
from chronus.mla1517.scaling import LUCAS_PISOT_LADDER, padovan


def _cpu_sha256d(header: bytes, nonce: int) -> bytes:
    blob = header[:76] + struct.pack("<I", nonce & 0xFFFFFFFF)
    return hashlib.sha256(hashlib.sha256(blob).digest()).digest()


def _meets_target(digest: bytes, target_be: bytes) -> bool:
    return int.from_bytes(digest, "little") <= int.from_bytes(target_be, "big")


def _serve(handler_cls):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


class _EnvGuard(unittest.TestCase):
    _VARS = (
        "MLA1517_REMOTE_GPU_ENDPOINT",
        "MLA1517_REMOTE_GPU_TOKEN",
        "HYBA_REMOTE_OPENCL_ENDPOINTS",
        "MLA1517_MODE",
        "MLA1517_GPU_CONNECTED",
        "MLA1517_HOST_GPU_CONNECTED",
        "MLA1517_HOST_GPU_BACKEND",
    )

    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in self._VARS}
        for k in self._VARS:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class RealAgentTests(_EnvGuard):
    """The real agent, GPU-less host: honest empty inventory + 503 work."""

    @classmethod
    def setUpClass(cls):
        handler = __import__("chronus.mla1517.remote_gpu_agent", fromlist=["_Handler"])._Handler
        cls.server, cls.endpoint = _serve(handler)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_health_reports_protocol_and_device_count(self):
        reply = RemoteGPUClient(self.endpoint).health()
        self.assertEqual(reply["protocol"], PROTOCOL_VERSION)
        self.assertEqual(reply["device_count"], 0)
        self.assertTrue(reply["opencl_error"])

    def test_devices_is_empty_and_honest(self):
        self.assertEqual(RemoteGPUClient(self.endpoint).devices(), [])

    def test_ladder_fails_closed_without_device(self):
        with self.assertRaises(RemoteGPUUnavailable):
            RemoteGPUClient(self.endpoint).execute_ladder()

    def test_sha256d_fails_closed_without_device(self):
        with self.assertRaises(RemoteGPUUnavailable):
            RemoteGPUClient(self.endpoint).execute_sha256d(
                bytes(range(80)), b"\xff" * 32, count=32
            )

    def test_sha256d_rejects_malformed_job_client_side(self):
        client = RemoteGPUClient(self.endpoint)
        with self.assertRaises(ValueError):
            client.execute_sha256d(b"short", b"\xff" * 32, count=32)
        with self.assertRaises(ValueError):
            client.execute_sha256d(bytes(80), b"\x00" * 16, count=32)
        with self.assertRaises(ValueError):
            client.execute_sha256d(bytes(80), b"\xff" * 32, count=0)
        with self.assertRaises(ValueError):
            client.execute_sha256d(
                bytes(80), b"\xff" * 32, count=SHA256D_MAX_WINDOW + 1
            )
        with self.assertRaises(ValueError):
            client.execute_sha256d(
                bytes(80), b"\xff" * 32, base_nonce=0x100000000, count=32
            )


class _StubDeviceHandler(BaseHTTPRequestHandler):
    """An agent that has one iGPU and answers ladder rows correctly.

    For /v1/sha256d it runs the serial-order window scan on the host CPU
    and returns a well-formed, correctly attested verdict — so the client
    exercises its real verification path. The ``*_sha256d`` flags flip
    individual honesty failures.
    """

    protocol_version = "HTTP/1.1"
    tampered = False
    require_token = False
    tampered_sha256d = False
    bad_attestation = False
    out_of_window_nonce = False

    @classmethod
    def _reset_sha256d_flags(cls):
        cls.tampered_sha256d = False
        cls.bad_attestation = False
        cls.out_of_window_nonce = False

    def log_message(self, *args):
        return

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_ok(self):
        if not type(self).require_token:
            return True
        return self.headers.get("Authorization") == "Bearer s3cret"

    def _sha256d(self, body):
        header = bytes.fromhex(body["header"])
        target = bytes.fromhex(body["target"])
        base = int(body.get("base_nonce", 0))
        count = int(body["count"])
        winner, digest, hashes = None, None, 0
        for i in range(count):
            nonce = (base + i) & 0xFFFFFFFF
            d = _cpu_sha256d(header, nonce)
            hashes += 1
            if _meets_target(d, target):
                winner, digest = nonce, d
                break
        device_name = "AirGPU iGPU-0"
        if winner is not None and type(self).out_of_window_nonce:
            winner = (base + count) & 0xFFFFFFFF
        if digest is not None and type(self).tampered_sha256d:
            digest = bytes([digest[0] ^ 0x01]) + digest[1:]
        digest_hex = digest.hex() if digest is not None else None
        attest_nonce = winner
        if type(self).bad_attestation and winner is not None:
            attest_nonce = (winner + 1) & 0xFFFFFFFF
        attestation = sha256d_share_attestation(
            header_hex=header.hex(),
            target_hex=target.hex(),
            base_nonce=base,
            count=count,
            hashes=hashes,
            nonce=attest_nonce,
            digest_hex=digest_hex,
            device=device_name,
        )
        return {
            "protocol": PROTOCOL_VERSION,
            "device": {"name": device_name, "vendor": "Intel"},
            "execution_backend": "opencl:gpu",
            "measured_ns": 4321,
            "window": {"base_nonce": base, "count": count},
            "hashes": hashes,
            "share": None
            if winner is None
            else {"nonce": winner, "hash": digest_hex},
            "attestation": attestation,
        }

    def do_GET(self):
        if not self._auth_ok():
            return self._send(401, {"error": "unauthorized"})
        if self.path == "/v1/health":
            return self._send(
                200,
                {
                    "status": "ok",
                    "protocol": PROTOCOL_VERSION,
                    "device_count": 1,
                    "opencl_error": None,
                },
            )
        if self.path == "/v1/devices":
            return self._send(
                200,
                {
                    "protocol": PROTOCOL_VERSION,
                    "devices": [
                        {
                            "name": "AirGPU iGPU-0",
                            "vendor": "Intel",
                            "type": "chronus",
                            "platform": "MockCloud",
                            "compute_units": 96,
                            "global_mem_mb": 16384,
                            "capabilities": {"fp64": True, "lucas_ladder_kernel": True},
                        }
                    ],
                    "error": None,
                },
            )
        return self._send(404, {"error": "unknown"})

    def do_POST(self):
        if not self._auth_ok():
            return self._send(401, {"error": "unauthorized"})
        if self.path not in ("/v1/ladder", "/v1/sha256d"):
            return self._send(404, {"error": "unknown"})
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/v1/sha256d":
            return self._send(200, self._sha256d(body))
        scales = body.get("scales", [])
        bad = [s for s in scales if s not in LUCAS_PISOT_LADDER]
        if bad:
            return self._send(400, {"error": f"unknown rungs {bad}"})
        results = []
        for n in scales:
            row = {"scale": n, "fibonacci": fib(n), "lucas": lucas(n), "padovan": padovan(n)}
            if _StubDeviceHandler.tampered:
                row["lucas"] += 1
            results.append(row)
        return self._send(
            200,
            {
                "protocol": PROTOCOL_VERSION,
                "device": {"name": "AirGPU iGPU-0", "vendor": "Intel"},
                "execution_backend": "opencl:gpu",
                "measured_ns": 1234,
                "results": results,
            },
        )


class StubAgentClientTests(_EnvGuard):
    @classmethod
    def setUpClass(cls):
        _StubDeviceHandler.tampered = False
        cls.server, cls.endpoint = _serve(_StubDeviceHandler)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_devices_imported_as_measured_remote(self):
        devs = RemoteGPUClient(self.endpoint).devices()
        self.assertEqual(len(devs), 1)
        self.assertEqual(devs[0].device_type, "chronus")
        self.assertEqual(devs[0].endpoint, self.endpoint)
        self.assertTrue(devs[0].capability("lucas_ladder_kernel"))

    def test_execute_ladder_verifies_against_exact_reference(self):
        results = RemoteGPUClient(self.endpoint).execute_ladder()
        self.assertEqual(len(results), len(LUCAS_PISOT_LADDER))
        for row, n in zip(results, LUCAS_PISOT_LADDER):
            self.assertEqual(row.lucas, lucas(n))
            self.assertEqual(row.device, "AirGPU iGPU-0")
            self.assertTrue(row.as_dict()["verified_against_exact_reference"])

    def test_tampered_result_is_rejected(self):
        _StubDeviceHandler.tampered = True
        try:
            with self.assertRaises(RemoteGPUVerificationError):
                RemoteGPUClient(self.endpoint).execute_ladder()
        finally:
            _StubDeviceHandler.tampered = False

    def test_probe_first_reachable_binds_the_device(self):
        client, devices, reason = probe_first_reachable([self.endpoint])
        self.assertIsNotNone(client)
        self.assertEqual(devices[0].name, "AirGPU iGPU-0")

    def test_token_gate_rejects_without_credentials(self):
        _StubDeviceHandler.require_token = True
        try:
            with self.assertRaises(RemoteGPUUnavailable):
                RemoteGPUClient(self.endpoint).devices()
            os.environ["MLA1517_REMOTE_GPU_TOKEN"] = "s3cret"
            self.assertEqual(len(RemoteGPUClient(self.endpoint).devices()), 1)
        finally:
            _StubDeviceHandler.require_token = False
            os.environ.pop("MLA1517_REMOTE_GPU_TOKEN", None)


class StubAgentSha256dTests(_EnvGuard):
    """Remote SHA-256d scans: verified shares, honest misses, hard rejects."""

    HEADER = bytes(range(80))

    @classmethod
    def setUpClass(cls):
        _StubDeviceHandler._reset_sha256d_flags()
        cls.server, cls.endpoint = _serve(_StubDeviceHandler)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def tearDown(self):
        _StubDeviceHandler._reset_sha256d_flags()

    def test_max_target_share_is_verified_byte_for_byte(self):
        # Max target: every digest wins, so nonce=base wins deterministically.
        result = RemoteGPUClient(self.endpoint).execute_sha256d(
            self.HEADER, b"\xff" * 32, base_nonce=0, count=64
        )
        self.assertTrue(result.found)
        self.assertTrue(result.share_verified)
        self.assertEqual(result.nonce, 0)
        self.assertEqual(result.digest, _cpu_sha256d(self.HEADER, 0))
        self.assertEqual(result.hashes, 1)
        self.assertEqual(result.device, "AirGPU iGPU-0")
        self.assertEqual(result.execution_backend, "opencl:gpu")
        self.assertTrue(result.attestation.startswith("RSHA256D-"))
        self.assertTrue(result.as_dict()["share_verified_against_exact_reference"])

    def test_share_found_later_in_window(self):
        # Tightest possible accepting target: the largest digest value in
        # the window (little-endian int, the CPU-path convention). At least
        # one nonce is guaranteed to win, and probably not nonce 0.
        target = max(
            int.from_bytes(_cpu_sha256d(self.HEADER, n), "little") for n in range(64)
        ).to_bytes(32, "big")
        result = RemoteGPUClient(self.endpoint).execute_sha256d(
            self.HEADER, target, base_nonce=0, count=64
        )
        self.assertTrue(result.found)
        self.assertEqual(result.digest, _cpu_sha256d(self.HEADER, result.nonce))
        self.assertTrue(_meets_target(result.digest, target))
        self.assertLessEqual(result.hashes, 64)

    def test_miss_reports_measured_hash_count(self):
        # Target zero: nothing wins — honest miss, full-window hash count.
        result = RemoteGPUClient(self.endpoint).execute_sha256d(
            self.HEADER, b"\x00" * 32, base_nonce=7, count=64
        )
        self.assertFalse(result.found)
        self.assertIsNone(result.nonce)
        self.assertEqual(result.hashes, 64)
        self.assertFalse(result.share_verified)

    def test_tampered_digest_is_rejected(self):
        _StubDeviceHandler.tampered_sha256d = True
        with self.assertRaises(RemoteGPUVerificationError):
            RemoteGPUClient(self.endpoint).execute_sha256d(
                self.HEADER, b"\xff" * 32, base_nonce=0, count=64
            )

    def test_attestation_mismatch_is_rejected(self):
        # The stub signs a different nonce — replay/binding must fail.
        _StubDeviceHandler.bad_attestation = True
        with self.assertRaises(RemoteGPUVerificationError):
            RemoteGPUClient(self.endpoint).execute_sha256d(
                self.HEADER, b"\xff" * 32, base_nonce=0, count=64
            )

    def test_out_of_window_nonce_is_rejected(self):
        _StubDeviceHandler.out_of_window_nonce = True
        with self.assertRaises(RemoteGPUVerificationError):
            RemoteGPUClient(self.endpoint).execute_sha256d(
                self.HEADER, b"\xff" * 32, base_nonce=0, count=64
            )


class ConnectorRemoteBindingTests(_EnvGuard):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.endpoint = _serve(_StubDeviceHandler)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_mla1517_gpu_mode_binds_remote_device(self):
        from chronus.mla1517.connectors import BackendConnector

        os.environ["MLA1517_MODE"] = "mla1517_gpu"
        os.environ["MLA1517_REMOTE_GPU_ENDPOINT"] = self.endpoint
        caps = BackendConnector().capabilities()
        self.assertTrue(caps.available)
        self.assertTrue(caps.connected)
        self.assertEqual(caps.execution_backend, "remote_opencl")
        self.assertEqual(caps.scaling_mode, "remote_mla1517_measured")
        self.assertIn(self.endpoint, caps.reason)

    def test_auto_mode_prefers_bound_remote_gpu(self):
        from chronus.mla1517.connectors import BackendConnector

        os.environ["MLA1517_MODE"] = "auto"
        os.environ["MLA1517_REMOTE_GPU_ENDPOINT"] = self.endpoint
        caps = BackendConnector().capabilities()
        self.assertEqual(caps.selected_mode, "mla1517_gpu")
        self.assertEqual(caps.execution_backend, "remote_opencl")

    def test_unreachable_endpoint_falls_back_honestly(self):
        from chronus.mla1517.connectors import BackendConnector

        os.environ["MLA1517_MODE"] = "mla1517_gpu"
        os.environ["MLA1517_REMOTE_GPU_ENDPOINT"] = "http://127.0.0.1:1"
        caps = BackendConnector(allow_cpu_fallback=True).capabilities()
        self.assertEqual(caps.execution_backend, "cpu_reference")
        self.assertIn("unreachable", caps.reason)

    def test_runtime_envelope_reports_remote_backend(self):
        from chronus.mla1517.objects import MLAObject
        from chronus.mla1517.runtime import MLA1517Runtime

        os.environ["MLA1517_MODE"] = "mla1517_gpu"
        os.environ["MLA1517_REMOTE_GPU_ENDPOINT"] = self.endpoint
        obj = MLAObject.create(
            payload={"data": "remote"}, family="fibonacci_lucas", scale=15, sequence_index=15
        )
        result = MLA1517Runtime(db=None, mode="mla1517_gpu").execute(obj, [1, 2], lambda x: x)
        self.assertEqual(result["execution_backend"], "remote_opencl")
        self.assertEqual(result["scaling_mode"], "remote_mla1517_measured")
        self.assertFalse(result["unlimited_speed_or_capacity"])


class InventoryRemoteTierTests(_EnvGuard):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.endpoint = _serve(_StubDeviceHandler)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _inventory(self):
        try:
            from hyba.inventory import ClusterInventory
        except Exception as exc:
            self.skipTest(f"hyba package not importable here: {exc}")
        return ClusterInventory.collect()

    def test_remote_device_joins_the_census(self):
        os.environ["HYBA_REMOTE_OPENCL_ENDPOINTS"] = self.endpoint
        inv = self._inventory()
        remote = inv.by_backend("opencl_remote")
        self.assertEqual(len(remote), 1)
        self.assertEqual(remote[0].name, "AirGPU iGPU-0")
        self.assertEqual(remote[0].type, "chronus")
        self.assertEqual(remote[0].capability("remote_endpoint"), self.endpoint)

    def test_unreachable_endpoint_is_an_error_not_a_device(self):
        os.environ["HYBA_REMOTE_OPENCL_ENDPOINTS"] = "http://127.0.0.1:1"
        inv = self._inventory()
        self.assertEqual(inv.by_backend("opencl_remote"), [])
        self.assertIn("opencl_remote", inv.errors)


if __name__ == "__main__":
    unittest.main()
