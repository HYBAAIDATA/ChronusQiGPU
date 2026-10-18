"""Parity-surface tests for the HYBA operator-applet routes.

Covers the four surfaces elevated into the canonical control API for applet
parity: /api/v1/veritas/status, /api/v1/customer/health,
/api/v1/substrate/proxy-latency, and the /ws/telemetry WebSocket stream.

Contract under test:
* every route answers 200 with the X-Request-Id correlation envelope;
* an absent/unreadable Veritas ledger is reported honestly (never fabricated);
* the substrate latency is measured per-request (never cached/synthesised);
* /ws/telemetry performs a spec-correct RFC 6455 handshake and streams
  ops-telemetry frames, and a plain GET documents the contract without
  hanging a probe.
"""

from __future__ import annotations

import base64
import os
import socket
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_PLATFORM_DIR = REPO_ROOT / "chronus" / "mla1517_platform" / "python"
for _p in (str(_PLATFORM_DIR), str(REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import control_api  # noqa: E402 - path-bootstrap above is intentional


class _ParityServerBase(unittest.TestCase):
    """Boots a real ThreadingHTTPServer with a throwaway env, like the
    constitution/contract wire suites do."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        (root / "index.html").write_text("<html>pythia</html>", encoding="utf-8")
        env_patch = {
            "MLA1517_STRATUM_USER": "parity.surface",
            "MLA1517_STRATUM_PASSWORD": "x",
            "MLA1517_VIABTC_ENDPOINT": "127.0.0.1:9",
            "PYTHIA_POOL_PROFILE": "viabtc",
            "PYTHIA_AUTOSTART_WORKERS": "0",
            "PYTHIA_BOOT_AUDIT": str(root / "BOOT_AUDIT.log"),
            "PYTHIA_BOOT_LOCK": str(root / "pythia-main.lock"),
            "PYTHIA_WORKER_HEARTBEAT_DIR": str(root / "hb"),
            "PYTHIA_ALLOW_UNAUTHENTICATED_CONTROL": "1",
        }
        self._saved = {k: os.environ.get(k) for k in env_patch}
        os.environ.update(env_patch)
        self.addCleanup(self._restore_env)
        self.addCleanup(self.tempdir.cleanup)
        self._reset_control_plane()
        self.addCleanup(self._reset_control_plane)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), control_api._Handler)
        self.server.web_root = root
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._close_server)
        self.port = self.server.server_address[1]

    def _restore_env(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _reset_control_plane(self) -> None:
        api = control_api
        if api._CONTROL is not None:
            api._CONTROL.shutdown()
        if api._BOOT_LOCK is not None:
            api._BOOT_LOCK.release()
        api._CONTROL = None
        api._AUDIT = None
        api._BOOT_LOCK = None
        api._LOCK_HELD = False
        api._TENSOR_RUNTIME = None
        api._TOE_BRIDGE = None
        if api.pythia_guardian_api is not None:
            api.pythia_guardian_api.cache_clear()

    def _close_server(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()


class VeritasStatusTests(_ParityServerBase):
    def test_absent_ledger_is_reported_honestly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            control_api._VERITAS_LEDGER_PATH = Path(tmp) / "absent.phi"
            payload = control_api.veritas_status_payload()
        self.assertEqual(payload["schema_version"], "pythia.veritas.status/1")
        self.assertTrue(payload["available"])
        self.assertEqual(payload["load_status"], "NO_LEDGER_FILE")
        self.assertEqual(payload["entries_total"], 0)
        self.assertIsNone(payload["verification_ratio"])
        self.assertIn("no self-repair cycle", payload["reason"])

    def test_corrupt_ledger_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            corrupt = Path(tmp) / "corrupt.phi"
            corrupt.write_bytes(b"\x00\x01not-a-real-ledger")
            control_api._VERITAS_LEDGER_PATH = corrupt
            payload = control_api.veritas_status_payload()
        self.assertFalse(payload["available"])
        self.assertIn("reason", payload)
        self.assertNotIn("integrity_report", payload)

    def test_recorded_entry_is_counted_and_verified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            control_api._VERITAS_LEDGER_PATH = Path(tmp) / "ledger.phi"
            from Intelligence.self_healing.veritas_ledger import VeritasLedger

            ledger = VeritasLedger(ledger_path=str(control_api._VERITAS_LEDGER_PATH))
            ledger.record_action("probe", "SUCCESS", {"test_passed": True})
            payload = control_api.veritas_status_payload()
        self.assertTrue(payload["available"])
        self.assertEqual(payload["entries_total"], 1)
        self.assertEqual(payload["entries_verified"], 1)
        self.assertEqual(payload["verification_ratio"], 1.0)
        self.assertEqual(payload["statuses"], {"SUCCESS": 1})

    def test_route_answers_200_with_correlation(self) -> None:
        from urllib.request import Request, urlopen

        url = f"http://127.0.0.1:{self.port}/api/v1/veritas/status"
        with urlopen(Request(url), timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("x-request-id", {k.lower() for k in resp.headers})


class CustomerHealthTests(_ParityServerBase):
    def test_summary_shape_and_honest_degradation(self) -> None:
        payload = control_api.customer_health_payload()
        self.assertEqual(payload["schema_version"], "pythia.customer.health/1")
        self.assertIn(payload["status"], ("ok", "degraded"))
        components = payload["components"]
        self.assertEqual(components["api"]["state"], "serving")
        self.assertIn("state", components["identity"])
        self.assertIn("ready", components["readiness"])
        self.assertIn("connected", components["stratum"])
        self.assertIn("live", components["worker"])
        # No mining worker is live here, so an "ok" verdict would be a lie.
        self.assertEqual(payload["status"], "degraded")

    def test_route_answers_200_with_correlation(self) -> None:
        from urllib.request import Request, urlopen

        url = f"http://127.0.0.1:{self.port}/api/v1/customer/health"
        with urlopen(Request(url), timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("x-request-id", {k.lower() for k in resp.headers})


class SubstrateLatencyTests(_ParityServerBase):
    def test_latency_is_measured_not_cached(self) -> None:
        first = control_api.substrate_latency_payload()
        second = control_api.substrate_latency_payload()
        self.assertEqual(first["schema_version"], "pythia.substrate.latency/1")
        self.assertEqual(first["probe"], "chronus.mla1517.status/1")
        self.assertTrue(first["measured"])
        self.assertTrue(first["ok"])
        self.assertIsInstance(first["latency_ms"], float)
        self.assertGreaterEqual(first["latency_ms"], 0.0)
        self.assertGreaterEqual(second["latency_ms"], 0.0)

    def test_route_answers_200_with_correlation(self) -> None:
        from urllib.request import Request, urlopen

        url = f"http://127.0.0.1:{self.port}/api/v1/substrate/proxy-latency"
        with urlopen(Request(url), timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("x-request-id", {k.lower() for k in resp.headers})


class WsHandshakeUnitTests(unittest.TestCase):
    def test_accept_key_matches_rfc6455_vector(self) -> None:
        # RFC 6455 §1.3 worked example.
        self.assertEqual(
            control_api.ws_accept_key("dGhlIHNhbXBsZSBub25jZQ=="),
            "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=",
        )

    def test_frame_layout(self) -> None:
        # Small payload: single length byte.
        self.assertEqual(control_api.ws_frame(0x1, b"hi"), b"\x81\x02hi")
        # Medium payload: 16-bit extended length, network order.
        frame = control_api.ws_frame(0x1, b"x" * 200)
        self.assertEqual(frame[:2], b"\x81\x7e")
        self.assertEqual(int.from_bytes(frame[2:4], "big"), 200)


class WsTelemetryTests(_ParityServerBase):
    def test_plain_get_documents_the_contract(self) -> None:
        from urllib.request import Request, urlopen

        url = f"http://127.0.0.1:{self.port}/ws/telemetry"
        with urlopen(Request(url), timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("x-request-id", {k.lower() for k in resp.headers})
            body = resp.read().decode("utf-8")
        self.assertIn('"protocol": "websocket"', body)
        self.assertIn("pythia.ops_telemetry/1", body)

    def _client_frame(self, opcode: int, payload: bytes = b"") -> bytes:
        """A masked client→server frame (RFC 6455 §5.3)."""
        mask = b"\x37\xfa\x21\x3d"
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        header = bytearray([0x80 | opcode])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        else:
            header.append(0x80 | 126)
            header.extend(length.to_bytes(2, "big"))
        return bytes(header) + mask + masked

    def _read_server_frame(
        self, sock: socket.socket, pending: bytes = b""
    ) -> tuple[int, bytes]:
        buffer = bytearray(pending)

        def read_exact(n: int) -> bytes:
            while len(buffer) < n:
                chunk = sock.recv(4096)
                if not chunk:
                    raise ConnectionError("server closed")
                buffer.extend(chunk)
            out = bytes(buffer[:n])
            del buffer[:n]
            return out

        head = read_exact(2)
        opcode = head[0] & 0x0F
        length = head[1] & 0x7F
        if length == 126:
            length = int.from_bytes(read_exact(2), "big")
        elif length == 127:
            length = int.from_bytes(read_exact(8), "big")
        return opcode, read_exact(length)

    def test_upgrade_streams_ops_frame_and_closes_cleanly(self) -> None:
        from urllib.request import Request, urlopen

        # The route must answer plain probes before any upgrade attempt.
        url = f"http://127.0.0.1:{self.port}/ws/telemetry"
        with urlopen(Request(url), timeout=10) as resp:
            self.assertEqual(resp.status, 200)

        key = base64.b64encode(os.urandom(16)).decode("ascii")
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=10)
        try:
            handshake = (
                "GET /ws/telemetry HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{self.port}\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\n"
                "Sec-WebSocket-Version: 13\r\n"
                "\r\n"
            )
            sock.sendall(handshake.encode("ascii"))
            head = b""
            while b"\r\n\r\n" not in head:
                chunk = sock.recv(4096)
                self.assertTrue(chunk, "connection closed before handshake")
                head += chunk
            header, _, pending = head.partition(b"\r\n\r\n")
            header_text = header.decode("latin-1")
            self.assertIn("HTTP/1.1 101", header_text)
            self.assertIn(
                control_api.ws_accept_key(key),
                header_text,
                "Sec-WebSocket-Accept must be the RFC 6455 digest",
            )
            # The first ops frame arrives without any client trigger.
            opcode, payload = self._read_server_frame(sock, pending)
            self.assertEqual(opcode, 0x1, "expected a text frame")
            self.assertIn(b'"type": "ws"', payload)
            self.assertIn(b"ops", payload)
            # Client close → server replies with a close frame, then drops.
            sock.settimeout(10)
            sock.sendall(self._client_frame(0x8, b"\x03\xe8"))
            opcode, _ = self._read_server_frame(sock)
            self.assertEqual(opcode, 0x8, "expected a close frame reply")
        finally:
            sock.close()


if __name__ == "__main__":
    unittest.main()