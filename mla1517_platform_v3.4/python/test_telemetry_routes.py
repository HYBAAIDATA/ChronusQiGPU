"""Control-plane routes for Stratum, telemetry events, hardware and security.

Every route answers JSON: 200 with an explicit ``available``/``bound`` truth
when the evidence is missing, and a failing route answers 500 JSON instead of
dropping the connection.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

import control_api

_GPU = {
    "available": True,
    "count": 1,
    "opencl_device_count": 1,
    "physical_gpu_count": 1,
    "devices": [
        {"name": "Intel(R) UHD Graphics 620", "vendor": "Intel", "family": "uhd", "is_gpu": True}
    ],
}


class TelemetryRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.hb = root / "hb"
        env = {
            "MLA1517_STRATUM_USER": "PYTHIA.001",
            "MLA1517_STRATUM_PASSWORD": "x",
            "PYTHIA_POOL_PROFILE": "braiins",
            "PYTHIA_AUTOSTART_WORKERS": "0",
            "PYTHIA_BOOT_AUDIT": str(root / "BOOT_AUDIT.log"),
            "PYTHIA_BOOT_LOCK": str(root / "pythia-main.lock"),
            "PYTHIA_WORKER_HEARTBEAT_DIR": str(self.hb),
            "PYTHIA_ACTIVE_PORTS_FILE": str(root / "active_ports.json"),
        }
        patcher = patch.dict(os.environ, env, clear=False)
        patcher.start()
        os.environ.pop("PYTHIA_EXECUTION_DEVICE", None)
        os.environ.pop("MLA1517_MMIO_DEVICE", None)
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tempdir.cleanup)
        self.addCleanup(self._reset)
        gpu = patch.object(control_api, "gpu_payload", return_value=_GPU)
        gpu.start()
        self.addCleanup(gpu.stop)
        self._reset()

    def _reset(self) -> None:
        if control_api._CONTROL is not None:
            control_api._CONTROL.shutdown()
        if control_api._BOOT_LOCK is not None:
            control_api._BOOT_LOCK.release()
        control_api._CONTROL = None
        control_api._AUDIT = None
        control_api._BOOT_LOCK = None
        control_api._LOCK_HELD = False

    def _serve(self) -> str:
        server = ThreadingHTTPServer(("127.0.0.1", 0), control_api._Handler)
        server.web_root = Path(self.tempdir.name)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def close() -> None:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.addCleanup(close)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def _get(self, base: str, path: str) -> tuple[int, dict]:
        try:
            with urlopen(base + path, timeout=30) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def _metrics(self, **counters) -> None:
        self.hb.mkdir(parents=True, exist_ok=True)
        encoded = {
            key: value if isinstance(value, (int, float)) else json.dumps(value)
            for key, value in counters.items()
        }
        (self.hb / "agentic-mining.metrics.json").write_text(
            json.dumps({"counters": encoded}), encoding="utf-8"
        )

    def test_routes_answer_json_without_worker_evidence(self) -> None:
        base = self._serve()
        code, stratum = self._get(base, "/api/v1/stratum/status")
        self.assertEqual(code, 200)
        self.assertFalse(stratum["evidence_available"])
        self.assertEqual(stratum["primary"]["transport"], "DISCONNECTED")
        self.assertFalse(stratum["worker_live"])

        code, events = self._get(base, "/api/v1/telemetry/events")
        self.assertEqual(code, 200)
        self.assertFalse(events["available"])
        self.assertEqual(events["events"], [])

        code, hardware = self._get(base, "/api/v1/hardware/status")
        self.assertEqual(code, 200)
        self.assertFalse(hardware["mining_device"]["bound"])
        self.assertIsNone(hardware["hashing"])
        self.assertEqual(hardware["opencl"]["device_count"], 1)
        self.assertEqual(hardware["workers"]["agentic-mining"]["state"], "disabled")

    def test_routes_carry_the_worker_telemetry(self) -> None:
        snapshot = {
            "state": "READY",
            "primary": {"transport": "CONNECTED", "subscribed": True, "authorized": True},
            "job": {
                "active": True,
                "generation": 3,
                "job_id": "abc",
                "difficulty": 8192,
                "share_target": "00" * 4 + "ff" * 28,
            },
            "submission": {"state": "IDLE"},
            "counters": {"accepted": 0},
        }
        events = {
            "schema": "pythia.telemetry_events/1",
            "last_seq": 3,
            "totals": {"accepted": 0},
            "events": [{"seq": n, "kind": "job", "job_id": f"j{n}"} for n in (1, 2, 3)],
        }
        evidence = {
            "schema": "pythia.mining_evidence/1",
            "execution_backend": {"backend": "opencl:gpu", "route": "opencl_m32"},
        }
        self._metrics(
            stratum_status=snapshot,
            stratum_events=events,
            mining_evidence=evidence,
            hashrate_hs=26_500_000.0,
            hashes_total=10**9,
            executions_total=40,
        )
        base = self._serve()
        _code, stratum = self._get(base, "/api/v1/stratum/status")
        self.assertEqual(stratum["primary"]["transport"], "CONNECTED")
        self.assertEqual(stratum["job"]["job_id"], "abc")
        self.assertEqual(stratum["job"]["difficulty"], 8192)

        _code, tail = self._get(base, "/api/v1/telemetry/events?n=2")
        self.assertTrue(tail["available"])
        self.assertEqual([e["seq"] for e in tail["events"]], [2, 3])

        _code, hardware = self._get(base, "/api/v1/hardware/status")
        self.assertEqual(hardware["hashing"]["hashrate_hs"], 26_500_000.0)
        self.assertEqual(hardware["execution"]["route"], "opencl_m32")

    def test_execution_device_binds_the_miner_but_not_salamander(self) -> None:
        os.environ["PYTHIA_EXECUTION_DEVICE"] = "opencl"
        control = control_api._control_plane()
        self.assertTrue(control.mining_device_bound())
        self.assertTrue(control._device_ready(control.handles["agentic-mining"]))
        self.assertFalse(control._device_ready(control.handles["salamander"]))
        self.assertTrue(control._device_ready(control.handles["discovery"]))
        self.assertIsNone(control_api._mining_device_reason(control))
        self.assertTrue(control_api.hardware_status_payload()["mining_device"]["bound"])

    def test_undeclared_execution_device_value_fails_startup(self) -> None:
        os.environ["PYTHIA_EXECUTION_DEVICE"] = "fpga"
        with self.assertRaises(control_api.StartupConfigError):
            control_api._control_plane()

    def test_security_status_never_drops_the_connection(self) -> None:
        def broken():
            raise RuntimeError("audit lock unavailable")

        base = self._serve()
        with patch.object(control_api, "pythia_guardian_api", broken):
            code, body = self._get(base, "/api/v1/security/status")
        self.assertEqual(code, 503)
        self.assertFalse(body["available"])
        self.assertIn("audit lock unavailable", body["reason"])

    def test_a_failing_route_answers_500_json(self) -> None:
        base = self._serve()
        with patch.object(control_api, "telemetry_summary_payload", side_effect=KeyError("x")):
            code, body = self._get(base, "/api/v1/telemetry/summary")
        self.assertEqual(code, 500)
        self.assertEqual(body["error"], "internal_error")
        self.assertEqual(body["detail"], "KeyError")

    def test_active_port_is_published_beside_other_writers(self) -> None:
        path = Path(os.environ["PYTHIA_ACTIVE_PORTS_FILE"])
        path.write_text(json.dumps({"node_port": 3100}), encoding="utf-8")
        control_api.publish_active_port("0.0.0.0", 8088)
        published = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(published["node_port"], 3100)
        self.assertEqual(published["python_url"], "http://127.0.0.1:8088")
        self.assertEqual(published["python_pid"], os.getpid())
        control_api.retract_active_port()
        retracted = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(retracted, {"node_port": 3100})


if __name__ == "__main__":
    unittest.main()
