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
        self.assertEqual(sorted(payload["workers"]), ["agentic-mining", "salamander"])
        self.assertEqual(payload["workers"]["agentic-mining"]["state"], "disabled")

    def test_ready_to_mine_alias_routes_to_same_backend(self) -> None:
        web_root = Path(self.tempdir.name)
        server = ThreadingHTTPServer(("127.0.0.1", 0), control_api._Handler)
        server.web_root = web_root
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        port = server.server_address[1]
        with self.assertRaises(HTTPError) as ctx:
            urlopen(f"http://127.0.0.1:{port}/api/v1/ready-to-mine")
        self.assertEqual(ctx.exception.code, 503)
        body = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertEqual(body["schema_version"], "mla1517.ready/1")
        self.assertEqual(body["reason"], "worker_unavailable")


if __name__ == "__main__":
    unittest.main()
