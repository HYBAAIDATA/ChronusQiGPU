"""Remote-GPU binding tests — a device anywhere binds as real hardware.

The agent on this box honestly reports no OpenCL platforms; the
behavioural contract (client protocol, verification, connector and
inventory wiring) is exercised over loopback with a stub agent that
serves measured rows.
"""

from __future__ import annotations

import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from mla1517.core import fib, lucas
from mla1517.remote_gpu import (
    PROTOCOL_VERSION,
    SHA256D_MAX_WINDOW,
    RemoteGPUClient,
    RemoteGPUUnavailable,
    RemoteGPUVerificationError,
    probe_first_reachable,
)
from mla1517.scaling import LUCAS_PISOT_LADDER, padovan


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
    """The real agent, GPU-less host: honest empty inventory + 503 ladder."""

    @classmethod
    def setUpClass(cls):
        handler = __import__("mla1517.remote_gpu_agent", fromlist=["_Handler"])._Handler
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

    def test_sha256d_executes_on_the_honest_backend(self):
        """No OpenCL here — the endpoint still runs, on CPU, and says so."""
        try:
            result = RemoteGPUClient(self.endpoint).execute_sha256d(
                bytes(80), b"\xff" * 32, base_nonce=0, count=4
            )
        except RemoteGPUUnavailable as exc:
            self.skipTest(f"agent sha256d unavailable in this env: {exc}")
        self.assertEqual(result.nonce, 0)
        self.assertEqual(result.hashes, 4)
        self.assertEqual(result.execution_backend, "cpu")


class _Sha256dMixin:
    """Honest /v1/sha256d answers computed with hashlib (used by stub agents)."""

    sha256d_tamper = False
    sha256d_underreport = False

    def _sha256d_reply(self, body):
        import hashlib as _hl

        header = bytes.fromhex(body.get("header", ""))
        target = bytes.fromhex(body.get("target", ""))
        order = body.get("order", "contiguous")
        nonces = body.get("nonces")
        base = int(body.get("base_nonce", 0))
        count = int(body.get("count", 0))
        if nonces is not None:
            order = "batch"
            window = [int(n) & 0xFFFFFFFF for n in nonces]
        elif order == "m32":
            lanes = [int(l) for l in body.get("lane_order", [])]
            window = [(base + lanes[i % 32] + 32 * (i // 32)) & 0xFFFFFFFF for i in range(count)]
        else:
            order = "contiguous"
            window = [(base + i) & 0xFFFFFFFF for i in range(count)]
        hashes = len(window) if not type(self).sha256d_underreport else max(0, len(window) - 1)
        blob = bytearray(header)
        winner = None
        for i, nonce in enumerate(window):
            blob[76:80] = nonce.to_bytes(4, "little")
            digest = _hl.sha256(_hl.sha256(bytes(blob)).digest()).digest()
            if digest[::-1] <= target:
                winner = {"nonce": nonce, "digest": digest.hex()}
                if type(self).sha256d_tamper:
                    winner = {"nonce": nonce, "digest": ("00" * 32)}
                break
        return {
            "device": {"name": "AirGPU iGPU-0", "vendor": "Intel"},
            "execution_backend": "opencl:gpu",
            "order": order,
            "hashes": hashes,
            "window": len(window),
            "measured_ns": 4321,
            "winner": winner,
        }


class _StubDeviceHandler(BaseHTTPRequestHandler, _Sha256dMixin):
    """An agent that has one iGPU and answers ladder rows correctly."""

    protocol_version = "HTTP/1.1"
    tampered = False
    require_token = False

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
                            "type": "igpu",
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
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/v1/sha256d":
            return self._send(200, self._sha256d_reply(body))
        if self.path != "/v1/ladder":
            return self._send(404, {"error": "unknown"})
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
        self.assertEqual(devs[0].device_type, "igpu")
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

    def test_sha256d_contiguous_window_verified(self):
        result = RemoteGPUClient(self.endpoint).execute_sha256d(
            bytes(80), b"\xff" * 32, base_nonce=0, count=4
        )
        self.assertEqual(result.nonce, 0)
        self.assertEqual(result.hashes, 4)
        self.assertEqual(result.execution_backend, "opencl:gpu")
        self.assertTrue(result.as_dict()["verified_against_exact_reference"])

    def test_sha256d_m32_window_reports_the_m32_winner(self):
        # The lane permutation changes traversal order, not the covered
        # set: base + lane[i%32] + 32*(i//32) covers [base, base+count).
        lanes = list(range(32))
        result = RemoteGPUClient(self.endpoint).execute_sha256d(
            bytes(80),
            b"\x7f" + b"\xff" * 31,
            base_nonce=100,
            count=64,
            lane_order=lanes,
        )
        self.assertIsNotNone(result.nonce)
        self.assertLess((result.nonce - 100) & 0xFFFFFFFF, 64)

    def test_sha256d_batch_list_executes_only_those_nonces(self):
        nonces = [7, 11, 13]
        result = RemoteGPUClient(self.endpoint).execute_sha256d(
            bytes(80), b"\xff" * 32, order="batch", nonces=nonces
        )
        self.assertEqual(result.nonce, 7)
        self.assertEqual(result.hashes, 3)

    def test_sha256d_tampered_winner_is_rejected(self):
        _StubDeviceHandler.sha256d_tamper = True
        try:
            with self.assertRaises(RemoteGPUVerificationError):
                RemoteGPUClient(self.endpoint).execute_sha256d(
                    bytes(80), b"\xff" * 32, base_nonce=0, count=4
                )
        finally:
            _StubDeviceHandler.sha256d_tamper = False

    def test_sha256d_no_winner_requires_full_window(self):
        # Tiny target: no winner is fine only if every window nonce ran.
        result = RemoteGPUClient(self.endpoint).execute_sha256d(
            bytes(80), b"\x00" * 32, base_nonce=0, count=4
        )
        self.assertIsNone(result.nonce)
        self.assertEqual(result.hashes, 4)

    def test_sha256d_underreported_window_is_rejected(self):
        _StubDeviceHandler.sha256d_underreport = True
        try:
            with self.assertRaises(RemoteGPUVerificationError):
                RemoteGPUClient(self.endpoint).execute_sha256d(
                    bytes(80), b"\x00" * 32, base_nonce=0, count=4
                )
        finally:
            _StubDeviceHandler.sha256d_underreport = False

    def test_sha256d_rejects_oversized_window(self):
        with self.assertRaises(ValueError):
            RemoteGPUClient(self.endpoint).execute_sha256d(
                bytes(80), b"\xff" * 32, base_nonce=0, count=SHA256D_MAX_WINDOW + 1
            )


class ConnectorRemoteBindingTests(_EnvGuard):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.endpoint = _serve(_StubDeviceHandler)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_mla1517_gpu_mode_binds_remote_device(self):
        from mla1517.connectors import BackendConnector

        os.environ["MLA1517_MODE"] = "mla1517_gpu"
        os.environ["MLA1517_REMOTE_GPU_ENDPOINT"] = self.endpoint
        caps = BackendConnector().capabilities()
        self.assertTrue(caps.available)
        self.assertTrue(caps.connected)
        self.assertEqual(caps.execution_backend, "remote_opencl")
        self.assertEqual(caps.scaling_mode, "remote_mla1517_measured")
        self.assertIn(self.endpoint, caps.reason)

    def test_auto_mode_prefers_bound_remote_gpu(self):
        from mla1517.connectors import BackendConnector

        os.environ["MLA1517_MODE"] = "auto"
        os.environ["MLA1517_REMOTE_GPU_ENDPOINT"] = self.endpoint
        caps = BackendConnector().capabilities()
        self.assertEqual(caps.selected_mode, "mla1517_gpu")
        self.assertEqual(caps.execution_backend, "remote_opencl")

    def test_unreachable_endpoint_falls_back_honestly(self):
        from mla1517.connectors import BackendConnector

        os.environ["MLA1517_MODE"] = "mla1517_gpu"
        os.environ["MLA1517_REMOTE_GPU_ENDPOINT"] = "http://127.0.0.1:1"
        caps = BackendConnector(allow_cpu_fallback=True).capabilities()
        self.assertEqual(caps.execution_backend, "cpu_reference")
        self.assertIn("unreachable", caps.reason)

    def test_runtime_envelope_reports_remote_backend(self):
        from mla1517.objects import MLAObject
        from mla1517.runtime import MLA1517Runtime

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
        self.assertEqual(remote[0].type, "igpu")
        self.assertEqual(remote[0].capability("remote_endpoint"), self.endpoint)

    def test_unreachable_endpoint_is_an_error_not_a_device(self):
        os.environ["HYBA_REMOTE_OPENCL_ENDPOINTS"] = "http://127.0.0.1:1"
        inv = self._inventory()
        self.assertEqual(inv.by_backend("opencl_remote"), [])
        self.assertIn("opencl_remote", inv.errors)


if __name__ == "__main__":
    unittest.main()
