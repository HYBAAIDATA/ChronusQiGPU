"""Operational-observability routes: ops contract, history, causal, session, stream.

Every route answers JSON built only from real worker channels and persisted
stores — unavailable sources answer ``available=false`` plus a reason rather
than a synthesized value (spec §2/§17).
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


class OpsTelemetryRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.hb = root / "hb"
        self.data = root / "data"
        env = {
            "MLA1517_STRATUM_USER": "rig.telemetry",
            "MLA1517_STRATUM_PASSWORD": "x",
            "PYTHIA_POOL_PROFILE": "braiins",
            "PYTHIA_AUTOSTART_WORKERS": "0",
            "PYTHIA_BOOT_AUDIT": str(root / "BOOT_AUDIT.log"),
            "PYTHIA_BOOT_LOCK": str(root / "pythia-main.lock"),
            "PYTHIA_WORKER_HEARTBEAT_DIR": str(self.hb),
            "PYTHIA_ACTIVE_PORTS_FILE": str(root / "active_ports.json"),
            "PYTHIA_TELEMETRY_HISTORY_PATH": str(self.data / "telemetry_history.jsonl"),
            "PYTHIA_CAUSAL_LOG_PATH": str(self.data / "causal_ledger.jsonl"),
            "PYTHIA_MINING_SESSION_PATH": str(self.data / "mining_session.json"),
            "PYTHIA_RUNTIME_CONFIG": str(root / "runtime_config.json"),
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

    def _stratum_snapshot(self) -> dict:
        return {
            "state": "READY",
            "primary": {
                "transport": "CONNECTED",
                "subscribed": True,
                "authorized": True,
                "endpoint": "stratum.test:3333",
                "worker": "ri***",
            },
            "job": {
                "active": True,
                "generation": 7,
                "job_id": "abc",
                "difficulty": 8192,
                "share_target": "00" * 4 + "ff" * 28,
                "prevhash": "11" * 32,
                "nbits": "1d00ffff",
                "ntime": "65abcdef",
                "extranonce1": "01020304",
                "extranonce2_size": 4,
            },
            "submission": {"state": "IDLE", "rtt_ms": {"last": 41.2, "samples": 3}},
            "counters": {"submitted": 3, "accepted": 2, "rejected": 0, "unknown": 1},
            "session_id": "sess-1",
            "protocol": "stratum_v1",
            "outcomes": {"candidate_total": 4, "stale_dropped": 1},
            "lifecycle": {"transport_connected": True, "submission_ready": False},
            "effective_stratum_hashrate_hs": 450_000.0,
            "retarget_window": {"effective_stratum_hashrate_hs": 450_000.0},
            "pool": {
                "schema": "pythia.pool_topology/1",
                "endpoints": [
                    {
                        "index": 0,
                        "name": "braiins",
                        "endpoint": "stratum.test:3333",
                        "tls": False,
                        "extranonce_subscribe": False,
                        "worker": "ri***",
                        "active": True,
                    },
                    {
                        "index": 1,
                        "name": "viabtc",
                        "endpoint": "stratum2.test:3333",
                        "tls": True,
                        "extranonce_subscribe": False,
                        "worker": "ri***",
                        "active": False,
                    },
                ],
                "endpoint_index": 0,
                "active": "braiins",
                "connect_attempts": 2,
                "last_error": "viabtc: refused",
                "last_selected": {"pool": "braiins", "index": 0, "attempt": 2},
                "history": [
                    {"event": "refused", "pool": "viabtc", "stage": "connect"},
                    {"event": "selected", "pool": "braiins", "index": 0},
                ],
            },
        }

    def test_ops_contract_reports_unavailable_without_evidence(self) -> None:
        base = self._serve()
        code, ops = self._get(base, "/api/v1/telemetry/ops")
        self.assertEqual(code, 200)
        self.assertEqual(ops["schema"], "pythia.ops_telemetry/1")
        self.assertFalse(ops["pool"]["available"])
        self.assertFalse(ops["job"]["available"])
        self.assertEqual(ops["job"]["reason"], "waiting for telemetry")
        self.assertIsNone(ops["execution"]["hashing"])
        self.assertFalse(ops["events"]["available"])
        self.assertFalse(ops["history"]["telemetry_history"]["exists"])
        self.assertIn("ready_reason", ops["system"])

    def test_ops_contract_projects_the_published_snapshot(self) -> None:
        snapshot = self._stratum_snapshot()
        self._metrics(
            stratum_status=snapshot,
            hashrate_hs=450_000.0,
            hashes_total=10**9,
            executions_total=40,
            shares_accepted=2,
        )
        base = self._serve()
        code, ops = self._get(base, "/api/v1/telemetry/ops")
        self.assertEqual(code, 200)

        pool = ops["pool"]
        self.assertTrue(pool["available"])
        self.assertEqual(pool["state"], "READY")
        self.assertEqual(pool["session_id"], "sess-1")
        self.assertEqual(pool["topology"]["active"], "braiins")
        self.assertEqual(len(pool["topology"]["endpoints"]), 2)
        self.assertEqual(pool["topology"]["connect_attempts"], 2)
        self.assertEqual(pool["topology"]["last_error"], "viabtc: refused")
        self.assertEqual([e["event"] for e in pool["topology"]["history"]], ["refused", "selected"])
        self.assertTrue(pool["lifecycle"]["transport_connected"])

        job = ops["job"]
        self.assertTrue(job["available"])
        self.assertEqual(job["prevhash"], "11" * 32)
        self.assertEqual(job["extranonce2_size"], 4)

        shares = ops["shares"]
        self.assertEqual(shares["counters"]["submitted"], 3)
        self.assertEqual(shares["outcomes"]["stale_dropped"], 1)
        self.assertEqual(shares["submission"]["rtt_ms"]["last"], 41.2)

        self.assertEqual(ops["execution"]["hashing"]["hashrate_hs"], 450_000.0)

    def test_stratum_status_passes_the_enriched_keys(self) -> None:
        self._metrics(stratum_status=self._stratum_snapshot())
        base = self._serve()
        _code, stratum = self._get(base, "/api/v1/stratum/status")
        self.assertEqual(stratum["session_id"], "sess-1")
        self.assertEqual(stratum["protocol"], "stratum_v1")
        self.assertEqual(stratum["outcomes"]["candidate_total"], 4)
        self.assertEqual(stratum["lifecycle"]["submission_ready"], False)
        self.assertEqual(stratum["effective_stratum_hashrate_hs"], 450_000.0)
        self.assertEqual(stratum["job"]["prevhash"], "11" * 32)

    def test_history_and_causal_read_persisted_stores(self) -> None:
        self.data.mkdir(parents=True)
        history_records = [
            {"seq": n, "at": 1000.0 + n, "kind": "job", "data": {"job_id": f"j{n}"}}
            for n in range(1, 6)
        ] + [{"seq": 6, "at": 1006.0, "kind": "hashrate", "data": {"hashrate_hs": 1.0}}]
        (self.data / "telemetry_history.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in history_records), encoding="utf-8"
        )
        (self.data / "causal_ledger.jsonl").write_text(
            "".join(
                json.dumps(
                    {
                        "seq": n,
                        "at": 2000.0 + n,
                        "kind": "pool_endpoint_selected",
                        "coordinate": {"pool_session_id": "s"},
                        "detail": {"pool": "braiins"},
                    }
                )
                + "\n"
                for n in range(1, 4)
            ),
            encoding="utf-8",
        )
        base = self._serve()

        code, history = self._get(base, "/api/v1/telemetry/history")
        self.assertEqual(code, 200)
        self.assertTrue(history["available"])
        self.assertEqual(history["count"], 6)
        self.assertTrue(history["store"]["exists"])

        _code, jobs = self._get(base, "/api/v1/telemetry/history?kind=job&n=2")
        self.assertEqual([r["data"]["job_id"] for r in jobs["records"]], ["j4", "j5"])

        _code, causal = self._get(base, "/api/v1/telemetry/causal")
        self.assertTrue(causal["available"])
        self.assertEqual(causal["records"][-1]["kind"], "pool_endpoint_selected")

    def test_session_route_reads_the_durable_share_log(self) -> None:
        self.data.mkdir(parents=True)
        share = {
            "job_id": "abc",
            "block_hash": "00" * 32,
            "submission_id": "sub-1",
            "sent_at": 1000.0,
            "outcome": True,
            "state": "ACCEPTED",
        }
        (self.data / "mining_session.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "state": "SEARCHING",
                    "history": ["SEARCHING"],
                    "cycles": 0,
                    "share_log": [share],
                    "winners": [],
                    "last_block_hash": None,
                }
            ),
            encoding="utf-8",
        )
        base = self._serve()
        code, session = self._get(base, "/api/v1/telemetry/session")
        self.assertEqual(code, 200)
        self.assertTrue(session["available"])
        self.assertEqual(session["share_count"], 1)
        self.assertEqual(session["share_log"][0]["outcome"], True)

    def test_history_routes_report_absent_stores_honestly(self) -> None:
        base = self._serve()
        code, history = self._get(base, "/api/v1/telemetry/history")
        self.assertEqual(code, 200)
        self.assertFalse(history["available"])
        self.assertIn("not persisted", history["reason"])
        _code, causal = self._get(base, "/api/v1/telemetry/causal")
        self.assertFalse(causal["available"])
        _code, session = self._get(base, "/api/v1/telemetry/session")
        self.assertFalse(session["available"])

    def test_stream_emits_sse_frames_of_the_ops_contract(self) -> None:
        self._metrics(stratum_status=self._stratum_snapshot())
        base = self._serve()
        response = urlopen(base + "/api/v1/telemetry/stream", timeout=30)
        try:
            line = response.readline().decode("utf-8")
            self.assertTrue(line.startswith("data: "))
            frame = json.loads(line[6:])
            self.assertEqual(frame["type"], "ops")
            self.assertEqual(frame["ops"]["schema"], "pythia.ops_telemetry/1")
            self.assertEqual(frame["ops"]["pool"]["state"], "READY")
        finally:
            response.close()


if __name__ == "__main__":
    unittest.main()
