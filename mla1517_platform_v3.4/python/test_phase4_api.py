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


class Phase4ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.env = {
            "MLA1517_STRATUM_USER": "PYTHIA.001",
            "MLA1517_STRATUM_PASSWORD": "x",
            "MLA1517_VIABTC_ENDPOINT": "btc.viabtc.io:3333",
            "PYTHIA_POOL_PROFILE": "viabtc",
            "PYTHIA_AUTOSTART_WORKERS": "0",
            "PYTHIA_BOOT_AUDIT": str(root / "BOOT_AUDIT.log"),
            "PYTHIA_BOOT_LOCK": str(root / "pythia-main.lock"),
            "PYTHIA_WORKER_HEARTBEAT_DIR": str(root / "hb"),
        }
        self.patch = patch.dict(os.environ, self.env, clear=False)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.tempdir.cleanup)
        self.addCleanup(self._reset_control_plane)
        self._reset_control_plane()

    def _reset_control_plane(self) -> None:
        if control_api._CONTROL is not None:
            control_api._CONTROL.shutdown()
        if control_api._BOOT_LOCK is not None:
            control_api._BOOT_LOCK.release()
        control_api._CONTROL = None
        control_api._AUDIT = None
        control_api._BOOT_LOCK = None
        control_api._LOCK_HELD = False

    def test_status_payload_exposes_canonical_backend_contract(self) -> None:
        payload = control_api.status_payload()
        self.assertEqual(payload["backend"], "Python/C/OpenCL")
        self.assertEqual(payload["host"]["stratum"]["profile"], "viabtc")
        self.assertEqual(payload["canonicalEngine"]["execution"], "canonical_python_control_api")
        self.assertFalse(payload["canonicalEngine"]["fallback"])
        self.assertEqual(sorted(payload["workers"]), ["agentic-mining", "discovery", "salamander"])
        self.assertEqual(payload["workers"]["agentic-mining"]["state"], "disabled")
        self.assertFalse(payload["stratum"]["connected"])
        self.assertFalse(payload["stratum"]["ready"])
        self.assertEqual(payload["stratum"]["state"], "CONFIGURED")

    def test_stratum_transport_is_not_collapsed_into_worker_readiness(self) -> None:
        control_api.status_payload()
        metrics_path = Path(self.env["PYTHIA_WORKER_HEARTBEAT_DIR"]) / "agentic-mining.metrics.json"
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot = {
            "state": "READY",
            "ready": True,
            "primary": {
                "transport": "CONNECTED",
                "subscribed": True,
                "authorized": True,
            },
            "job": {
                "active": True,
                "generation": 7,
                "share_target": "ff" * 32,
            },
            "submission": {"state": "IDLE"},
            "counters": {},
        }
        metrics_path.write_text(
            json.dumps({"counters": {"stratum_status": json.dumps(snapshot)}}),
            encoding="utf-8",
        )

        payload = control_api.status_payload()
        self.assertTrue(payload["stratum"]["connected"])
        self.assertTrue(payload["stratum"]["primary"]["authorized"])
        self.assertFalse(payload["stratum"]["ready"])
        self.assertFalse(payload["ready_to_mine"]["ready"])

    def test_ready_to_mine_alias_routes_to_same_backend(self) -> None:
        web_root = Path(self.tempdir.name)
        server = ThreadingHTTPServer(("127.0.0.1", 0), control_api._Handler)
        server.web_root = web_root
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def close_server() -> None:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.addCleanup(close_server)
        port = server.server_address[1]
        with self.assertRaises(HTTPError) as ctx:
            urlopen(f"http://127.0.0.1:{port}/api/v1/ready-to-mine")
        self.assertEqual(ctx.exception.code, 503)
        body = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertEqual(body["schema_version"], "mla1517.ready/1")
        self.assertEqual(body["reason"], "worker_unavailable")

    def test_maintenance_status_is_exposed_by_control_api(self) -> None:
        expected = {
            "schema": "pythia.maintenance/1",
            "state": "running",
            "progress": {"phase": "diagnosing"},
        }
        with patch.object(control_api.system_fabric, "self_repair_status", return_value=expected):
            server = ThreadingHTTPServer(("127.0.0.1", 0), control_api._Handler)
            server.web_root = Path(self.tempdir.name)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            def close_server() -> None:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()

            self.addCleanup(close_server)
            with urlopen(
                f"http://127.0.0.1:{server.server_address[1]}/api/v1/intelligence/maintenance"
            ) as response:
                self.assertEqual(json.loads(response.read().decode("utf-8")), expected)

    def test_maintenance_cycle_summarizes_results_without_applying_by_default(self) -> None:
        from types import SimpleNamespace

        from system_fabric import _Runner, _ensure_repo_path, _run_self_repair

        _ensure_repo_path()

        report = SimpleNamespace(
            session_id="test-session",
            started_at=1.0,
            finished_at=2.0,
            classified=[object()],
            proposals=[object(), object()],
            apply_results=[SimpleNamespace(applied=False)],
            llm_enabled=False,
            auto_apply_enabled=False,
            summary=lambda: "one finding, two proposals",
        )
        with patch(
            "Intelligence.self_healing.self_repair.run_self_repair_cycle", return_value=report
        ):
            result = _run_self_repair(_Runner("test"), interval_s=0)

        self.assertEqual(result["session_id"], "test-session")
        self.assertEqual(result["failure_count"], 1)
        self.assertEqual(result["proposal_count"], 2)
        self.assertEqual(result["applied_count"], 0)
        self.assertFalse(result["auto_apply_enabled"])

    def test_startup_diagnosis_is_one_shot_by_default(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("HYBA_SELF_REPAIR_INTERVAL_S", None)
            self.assertEqual(control_api.system_fabric._self_repair_interval_s(), 0)

    def test_maintenance_start_dispatches_a_cycle_immediately(self) -> None:
        from threading import Event

        called = Event()

        def fake_cycle(runner, interval_s):
            called.set()
            return {"started": True, "interval_s": interval_s}

        with patch.dict(
            os.environ,
            {
                "HYBA_SELF_REPAIR_INTERVAL_S": "0",
                "HYBA_SKIP_STARTUP_SELF_HEALING": "false",
            },
        ):
            with patch.object(control_api.system_fabric, "_run_self_repair", fake_cycle):
                self.assertTrue(control_api.system_fabric.start_self_repair(startup=True))
                thread = control_api.system_fabric.SELF_REPAIR._thread
                self.assertIsNotNone(thread)
                thread.join(timeout=2)

        self.assertTrue(called.is_set())
        self.assertEqual(control_api.system_fabric.SELF_REPAIR.status()["state"], "done")

    def test_control_api_boot_skips_full_diagnosis_by_default(self) -> None:
        from types import SimpleNamespace

        server = SimpleNamespace(serve_forever=lambda: None, server_close=lambda: None)
        boot_lock = SimpleNamespace(release=lambda: None)
        with patch.dict(os.environ, {"HYBA_STARTUP_SELF_HEALING_ENABLED": "false"}):
            with (
                patch.object(control_api, "_control_plane"),
                patch.object(control_api.system_fabric, "initialize_repo_engineer") as initialize,
                patch.object(control_api, "announce_skills"),
                patch.object(control_api, "ThreadingHTTPServer", return_value=server),
                patch.object(control_api, "_boot_lock", return_value=boot_lock),
                patch.object(control_api.system_fabric, "start_self_repair") as start_repair,
            ):
                control_api.serve(host="127.0.0.1", port=0, web_root=self.tempdir.name)

        start_repair.assert_not_called()
        initialize.assert_called_once_with()

    def test_control_api_boot_can_opt_in_to_full_diagnosis(self) -> None:
        from types import SimpleNamespace

        server = SimpleNamespace(serve_forever=lambda: None, server_close=lambda: None)
        boot_lock = SimpleNamespace(release=lambda: None)
        with patch.dict(os.environ, {"HYBA_STARTUP_SELF_HEALING_ENABLED": "true"}):
            with (
                patch.object(control_api, "_control_plane"),
                patch.object(control_api.system_fabric, "initialize_repo_engineer") as initialize,
                patch.object(control_api, "announce_skills"),
                patch.object(control_api, "ThreadingHTTPServer", return_value=server),
                patch.object(control_api, "_boot_lock", return_value=boot_lock),
                patch.object(control_api.system_fabric, "start_self_repair") as start_repair,
            ):
                control_api.serve(host="127.0.0.1", port=0, web_root=self.tempdir.name)

        start_repair.assert_called_once_with(startup=True)
        initialize.assert_called_once_with()

    def test_security_status_fails_closed_when_guardian_dependency_is_missing(self) -> None:
        if control_api.pythia_guardian_api is not None:
            self.skipTest("AL HARAS guardian dependency is installed")
        server = ThreadingHTTPServer(("127.0.0.1", 0), control_api._Handler)
        server.web_root = Path(self.tempdir.name)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def close_server() -> None:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.addCleanup(close_server)
        with self.assertRaises(HTTPError) as ctx:
            urlopen(f"http://127.0.0.1:{server.server_address[1]}/api/v1/security/status")
        self.assertEqual(ctx.exception.code, 503)
        body = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertEqual(body["reason"], "guardian_dependency_unavailable")

    def test_repo_engineer_requires_provider_configuration(self) -> None:
        with patch.object(
            control_api.system_fabric,
            "repo_engineer_status",
            return_value={"ready": False, "provider": "openai"},
        ):
            code, payload = control_api._repo_engineer_ask({"prompt": "Inspect startup"})

        self.assertEqual(code, control_api.HTTPStatus.SERVICE_UNAVAILABLE)
        self.assertEqual(payload["error"], "repo_engineer_not_configured")
        self.assertEqual(payload["readiness"]["provider"], "openai")

    def test_repo_engineer_validates_and_dispatches_prompt(self) -> None:
        with patch.object(
            control_api.system_fabric,
            "repo_engineer_status",
            return_value={"ready": True},
        ), patch.object(control_api.system_fabric, "start_repo_engineer", return_value=True) as start:
            invalid_code, _ = control_api._repo_engineer_ask({"prompt": " "})
            code, payload = control_api._repo_engineer_ask(
                {"prompt": "Find the highest-value runtime cleanup"}
            )

        self.assertEqual(invalid_code, control_api.HTTPStatus.BAD_REQUEST)
        self.assertEqual(code, control_api.HTTPStatus.ACCEPTED)
        self.assertEqual(payload["state"], "running")
        start.assert_called_once_with("Find the highest-value runtime cleanup")


if __name__ == "__main__":
    unittest.main()
