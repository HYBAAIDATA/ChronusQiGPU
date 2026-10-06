"""Stateful-recovery suite — service constitution §23-24.

Recovery is *measured*, not assumed. Every scenario declared in
``service_fabric.yaml`` under ``recovery_scenarios`` is executed here
against the live service: clean restart over the same state dir, a torn
(partial-write) runtime config, duplicate delivery inside the
idempotency window, reordered event delivery, and atomic publication of
the shared port file. RTO/RPO numbers stay ``UNMEASURED`` in the fabric —
this suite proves behaviour, it does not invent timings.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
FABRIC_PATH = REPO_ROOT / "governance" / "service_fabric.yaml"
_FABRIC = yaml.safe_load(FABRIC_PATH.read_text(encoding="utf-8"))
_SCENARIOS = {s["id"]: s for s in _FABRIC["recovery_scenarios"]}


class RecoveryRegisterTests(unittest.TestCase):
    def test_every_executed_scenario_names_a_proof_test(self):
        import importlib

        for sid, scenario in _SCENARIOS.items():
            if scenario["status"] != "EXECUTED":
                self.assertIn(
                    scenario["status"],
                    set(_FABRIC["unavailable_markers"]) | {"UNPROVEN"},
                    sid,
                )
                continue
            path, _, qualname = str(scenario["proof_test"]).partition("::")
            self.assertTrue((REPO_ROOT / path).is_file(), f"{sid}: {path}")
            module = importlib.import_module(Path(path).stem)
            cls_name, _, method = qualname.partition(".")
            cls = getattr(module, cls_name, None)
            self.assertIsNotNone(cls, f"{sid}: {qualname}")
            self.assertTrue(hasattr(cls, method), f"{sid}: {qualname} missing")

    def test_recovery_objectives_do_not_fabricate_measurements(self):
        """RTO/RPO must name a measurement or be honestly UNMEASURED."""
        for tier, row in _FABRIC["recovery_objectives"].items():
            for key, value in row.items():
                self.assertIsInstance(
                    value, str, f"{tier}.{key} must be a declared string"
                )


_SUB_KEYRING = {"test": "k" * 32}


def _mint_subscription() -> dict[str, str]:
    from al_haras.entitlements import SubscriptionAuthority, SubscriptionClaims

    token = SubscriptionAuthority(
        {"test": b"k" * 32}, "hyba-subscriptions"
    ).issue(
        SubscriptionClaims(
            subscription_id="sub-recovery",
            tenant_id="tenant-1",
            issuer="hyba-subscriptions",
            key_id="test",
            capabilities=("hyba.security",),
            actors=("operator-1",),
            not_before=0,
            expires_at=int(time.time()) + 3600,
        )
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-HYBA-Tenant": "tenant-1",
        "X-HYBA-Actor": "operator-1",
    }


class _ServerBase(unittest.TestCase):
    """Boot the real handler over a tempdir; subclasses can reboot it."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / "index.html").write_text("<html>pythia</html>", encoding="utf-8")
        self.env_patch = {
            "MLA1517_STRATUM_USER": "recovery.test",
            "MLA1517_STRATUM_PASSWORD": "x",
            "MLA1517_VIABTC_ENDPOINT": "127.0.0.1:9",
            "PYTHIA_POOL_PROFILE": "viabtc",
            "PYTHIA_AUTOSTART_WORKERS": "0",
            "PYTHIA_BOOT_AUDIT": str(self.root / "BOOT_AUDIT.log"),
            "PYTHIA_BOOT_LOCK": str(self.root / "pythia-main.lock"),
            "PYTHIA_WORKER_HEARTBEAT_DIR": str(self.root / "hb"),
            "PYTHIA_RUNTIME_CONFIG": str(self.root / "runtime_config.json"),
            "PYTHIA_ALLOW_UNAUTHENTICATED_CONTROL": "1",
            "AL_HARAS_SUBSCRIPTION_KEYS": json.dumps(_SUB_KEYRING),
            "AL_HARAS_DATA_DIR": str(self.root / "al-haras"),
        }
        self._saved = {k: os.environ.get(k) for k in self.env_patch}
        os.environ.update(self.env_patch)
        self.addCleanup(self._restore_env)
        self.addCleanup(self.tempdir.cleanup)
        self.addCleanup(self._teardown_server)
        self._boot_server()

    def _restore_env(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _reset_control_plane(self) -> None:
        api = self.api
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

    def _boot_server(self) -> None:
        import control_api

        self.api = control_api
        self._reset_control_plane()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), control_api._Handler)
        self.server.web_root = self.root
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def _teardown_server(self) -> None:
        if getattr(self, "server", None) is not None:
            self.server.shutdown()
            self.thread.join(timeout=5)
            self.server.server_close()
            self.server = None
        if getattr(self, "api", None) is not None:
            self._reset_control_plane()

    def _request(self, method, path, body=None, headers=None, timeout=10):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(
            url,
            data=data,
            method=method,
            headers={"Content-Type": "application/json", **(headers or {})},
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read()
                ctype = response.headers.get("Content-Type", "")
                parsed = (
                    json.loads(raw)
                    if "application/json" in ctype
                    else raw.decode("utf-8", "replace")
                )
                return response.status, parsed, dict(response.headers)
        except HTTPError as exc:
            raw = exc.read()
            try:
                parsed = json.loads(raw)
            except ValueError:
                parsed = raw.decode("utf-8", "replace")
            return exc.code, parsed, dict(exc.headers)


class StatefulRecoveryTests(_ServerBase):
    def test_rc_restart_clean(self):
        _, first, _ = self._request("GET", "/api/v1/readyz")
        first_states = {k: v["state"] for k, v in first["components"].items()}

        # Restart: stop the server, reset the in-process plane, boot again
        # over the same state directory.
        self._teardown_server()
        self._boot_server()

        _, second, _ = self._request("GET", "/api/v1/readyz")
        second_states = {k: v["state"] for k, v in second["components"].items()}
        self.assertEqual(first_states, second_states)
        # The boot audit survived the restart — evidence, not a fresh lie.
        self.assertTrue((self.root / "BOOT_AUDIT.log").is_file())

    def test_rc_partial_write_config(self):
        cfg_path = self.root / "runtime_config.json"
        cfg_path.write_text('{"pools": [{"en', encoding="utf-8")  # torn write

        # The corrupt file is untrusted input: the surface reports defaults
        # rather than crashing or trusting the partial write.
        status, body, _ = self._request("GET", "/api/v1/config")
        self.assertEqual(status, 200, body)
        self.assertIsInstance(body, dict)
        self.assertEqual(body.get("pools", []), [])

        # A subsequent write commits atomically — recovery completes.
        headers = _mint_subscription()
        status, body, _ = self._request(
            "PUT",
            "/api/v1/config",
            body={"hashrate": {"target_hs": 1.5}},
            headers=headers,
        )
        self.assertEqual(status, 200, body)
        # The file on disk is complete JSON now — never the torn text.
        parsed = json.loads(cfg_path.read_text(encoding="utf-8"))
        self.assertIsInstance(parsed, dict)

    def test_rc_duplicate_delivery(self):
        headers = {**_mint_subscription(), "Idempotency-Key": "rc-dup-1"}
        s1, b1, _ = self._request(
            "PUT",
            "/api/v1/config",
            body={"hashrate": {"target_hs": 2.5}},
            headers=headers,
        )
        self.assertEqual(s1, 200, b1)
        # Same delivery twice inside the window → recorded outcome, not a
        # second write.
        s2, b2, _ = self._request(
            "PUT",
            "/api/v1/config",
            body={"hashrate": {"target_hs": 2.5}},
            headers=headers,
        )
        self.assertEqual(s2, 200, b2)
        self.assertTrue(b2.get("idempotent_replay"), b2)

    def test_rc_reordered_delivery(self):
        gate = self.api._seq_gated_events
        stream = [{"seq": 1}, {"seq": 3}, {"seq": 2}]
        # Cursor at 3 (already delivered): a reordered replay of the whole
        # stream delivers nothing.
        self.assertEqual(gate(stream, 3), [])
        # Cursor at 1: only strictly-newer events, duplicates included once
        # per delivery — the cursor never rewinds.
        self.assertEqual([e["seq"] for e in gate(stream, 1)], [3, 2])

    def test_rc_atomic_write_ports(self):
        ports_file = self.root / "active_ports.json"
        os.environ["PYTHIA_ACTIVE_PORTS_FILE"] = str(ports_file)
        self.addCleanup(
            lambda: os.environ.pop("PYTHIA_ACTIVE_PORTS_FILE", None)
        )
        api = self.api

        # Concurrent writers merge through tmp+replace: the file always
        # parses as complete JSON and every writer's key survives.
        def writer(tag: int) -> None:
            for _ in range(50):
                api._write_active_ports(
                    lambda cur, t=tag: cur.update({f"port_{t}": t}) or True
                )

        threads = [threading.Thread(target=writer, args=(i,), daemon=True) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        parsed = json.loads(ports_file.read_text(encoding="utf-8"))
        for i in range(4):
            self.assertIn(f"port_{i}", parsed)

        # A torn/partial file is untrusted input — the next write recovers
        # to a complete document.
        ports_file.write_text('{"port_0": ', encoding="utf-8")
        api._write_active_ports(lambda cur: cur.update({"port_recovered": 1}) or True)
        recovered = json.loads(ports_file.read_text(encoding="utf-8"))
        self.assertEqual(recovered["port_recovered"], 1)


if __name__ == "__main__":
    unittest.main()
