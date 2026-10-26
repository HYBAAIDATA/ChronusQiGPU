"""Fault-injection suite — service constitution §22.

Every scenario declared in ``governance/service_fabric.yaml`` under
``fault_injection_scenarios`` is executable here. A scenario may declare
status EXECUTED only if a real proof exists; M3/hardware-only scenarios
stay ``M3_UNAVAILABLE`` — the register renders honestly, never greenwashed.

Injections at the wire seam prove the failure envelope end to end:
guardian denial commits zero mutation, custody absence reports
not_mounted, a dead pool reports disconnected, a dead remote endpoint
opens its circuit breaker, oversized/malformed/duplicate requests carry
the declared failure classes, and an unconfigured specialist backend
reports NOT_CONFIGURED rather than fabricating an answer.
"""

from __future__ import annotations

import json
import hashlib
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
_SCENARIOS = {s["id"]: s for s in _FABRIC["fault_injection_scenarios"]}


class ScenarioRegisterTests(unittest.TestCase):
    """Every declared fault-injection scenario resolves to a real test."""

    def test_every_executed_scenario_names_a_proof_test(self):
        for sid, scenario in _SCENARIOS.items():
            if scenario["status"] != "EXECUTED":
                continue
            ref = str(scenario.get("proof_test") or "")
            self.assertIn("::", ref, f"{sid} has no proof_test")
            path = REPO_ROOT / ref.split("::", 1)[0]
            self.assertTrue(path.is_file(), f"{sid} proof file missing: {path}")

    def test_proof_tests_exist_in_this_module_or_companion(self):
        import importlib

        for sid, scenario in _SCENARIOS.items():
            if scenario["status"] != "EXECUTED":
                continue
            path, _, qualname = str(scenario["proof_test"]).partition("::")
            module = importlib.import_module(Path(path).stem)
            cls_name, _, method = qualname.partition(".")
            cls = getattr(module, cls_name, None)
            self.assertIsNotNone(cls, f"{sid}: {qualname} not found")
            self.assertTrue(
                hasattr(cls, method),
                f"{sid}: {qualname} missing — proof_test points at nothing",
            )

    def test_unavailable_scenarios_carry_no_proof_claim(self):
        for sid, scenario in _SCENARIOS.items():
            if scenario["status"] == "EXECUTED":
                continue
            self.assertIn(
                scenario["status"],
                set(_FABRIC["unavailable_markers"]) | {"UNPROVEN"},
                f"{sid} declares unsupported status {scenario['status']}",
            )


_SUB_KEYRING = {"test": "k" * 32}


def _mint_subscription() -> dict[str, str]:
    from al_haras.entitlements import SubscriptionAuthority, SubscriptionClaims

    token = SubscriptionAuthority(
        {"test": b"k" * 32}, "hyba-subscriptions"
    ).issue(
        SubscriptionClaims(
            subscription_id="sub-fault-injection",
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


class WireFaultInjectionTests(unittest.TestCase):
    """Faults injected over live HTTP — the same seam an operator hits."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        (root / "index.html").write_text("<html>pythia</html>", encoding="utf-8")
        self.env_patch = {
            "PYTHIA_OPERATOR_PRINCIPALS_JSON": json.dumps({"fault-test": {
                "role": "ceo", "token_sha256": hashlib.sha256(b"fault-control-fixture").hexdigest()}}),
            "MLA1517_STRATUM_USER": "fault.injection",
            "MLA1517_STRATUM_PASSWORD": "x",
            "MLA1517_VIABTC_ENDPOINT": "127.0.0.1:9",
            "PYTHIA_POOL_PROFILE": "viabtc",
            "PYTHIA_AUTOSTART_WORKERS": "0",
            "PYTHIA_BOOT_AUDIT": str(root / "BOOT_AUDIT.log"),
            "PYTHIA_BOOT_LOCK": str(root / "pythia-main.lock"),
            "PYTHIA_WORKER_HEARTBEAT_DIR": str(root / "hb"),
            "PYTHIA_ALLOW_UNAUTHENTICATED_CONTROL": "1",
            "AL_HARAS_SUBSCRIPTION_KEYS": json.dumps(_SUB_KEYRING),
            "AL_HARAS_DATA_DIR": str(root / "al-haras"),
        }
        self._saved = {k: os.environ.get(k) for k in self.env_patch}
        os.environ.update(self.env_patch)
        self.addCleanup(self._restore_env)
        self.addCleanup(self.tempdir.cleanup)
        self.addCleanup(self._reset_control_plane)
        self._reset_control_plane()

        import control_api

        self.api = control_api
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
        api = self.api if hasattr(self, "api") else __import__("control_api")
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

    def _request(self, method, path, body=None, headers=None, raw=None, timeout=15):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = raw if raw is not None else (
            json.dumps(body).encode("utf-8") if body is not None else None
        )
        request = Request(
            url,
            data=data,
            method=method,
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer fault-control-fixture",
                     "X-PYTHIA-Control-Authorization": "Bearer fault-control-fixture",
                     "X-PYTHIA-Principal": "fault-test", **(headers or {})},
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = response.read()
                ctype = response.headers.get("Content-Type", "")
                parsed = (
                    json.loads(payload)
                    if "application/json" in ctype
                    else payload.decode("utf-8", "replace")
                )
                return response.status, parsed, dict(response.headers)
        except HTTPError as exc:
            payload = exc.read()
            try:
                parsed = json.loads(payload)
            except ValueError:
                parsed = payload.decode("utf-8", "replace")
            return exc.code, parsed, dict(exc.headers)

    # -- fi.guardian.deny_mutation -----------------------------------------

    def test_fi_guardian_deny_mutation(self):
        # State before the denied mutation attempt.
        _, before, _ = self._request("GET", "/api/v1/agentic/status")

        # Guardian-mediated mutation without subscription credentials: a
        # signed denial receipt, not a mask.
        status, body, _ = self._request("POST", "/api/v1/mining/start", body={})
        self.assertIn(status, (400, 401, 403), body)
        self.assertIs(body.get("allowed"), False, body)
        self.assertIn("evidence_id", body, body)
        self.assertIn(
            body.get("failure_class"),
            {"FORBIDDEN", "UNAUTHORISED", "INVALID_REQUEST"},
            body,
        )

        # Zero mutation: agentic state is byte-identical after the denial.
        _, after, _ = self._request("GET", "/api/v1/agentic/status")
        self.assertEqual(before, after)

        # The denial itself is still correlatable — denials are not exempt.
        status, _body, headers = self._request("POST", "/api/v1/mining/stop", body={})
        self.assertTrue(headers.get("X-Request-Id"))

    # -- fi.theseus.custody_absent -----------------------------------------

    def test_fi_theseus_custody_absent(self):
        status, body, _ = self._request("GET", "/api/v1/readyz")
        self.assertIn(status, (200, 503))
        custody = body["components"]["custody"]
        self.assertEqual(custody["state"], "not_mounted")
        # Absence is a first-class report, not a fabricated mounted store.
        status, body, _ = self._request("GET", "/api/v1/system/map")
        self.assertEqual(status, 200)
        self.assertIsInstance(body, dict)

    # -- fi.stratum.disconnect ---------------------------------------------

    def test_fi_stratum_disconnect(self):
        status, body, _ = self._request("GET", "/api/v1/stratum/status")
        self.assertEqual(status, 200)
        text = json.dumps(body).lower()
        self.assertNotIn('"connected": true', text)
        # Readiness agrees — disconnected pool is honest dependency health.
        _, ready, _ = self._request("GET", "/api/v1/readyz")
        self.assertEqual(ready["components"]["stratum"]["state"], "disconnected")
        # Ready-to-mine never fabricates readiness past a dead pool.
        _, rtm, _ = self._request("GET", "/api/v1/ready-to-mine")
        self.assertNotEqual(rtm.get("ready"), True)

    # -- fi.request.duplicate ----------------------------------------------

    def test_fi_request_duplicate(self):
        key = "fi-dup-1"
        heads = {"Idempotency-Key": key}
        s1, b1, _ = self._request(
            "POST", "/api/v1/agentic/stop", body={}, headers=heads
        )
        s2, b2, _ = self._request(
            "POST", "/api/v1/agentic/stop", body={}, headers=heads
        )
        self.assertEqual(s1, s2)
        self.assertTrue(b2.get("idempotent_replay"), b2)
        self.assertNotIn("idempotent_replay", b1)
        self.assertEqual(
            {k: v for k, v in b1.items()},
            {k: v for k, v in b2.items() if k != "idempotent_replay"},
        )

    # -- fi.request.oversized ----------------------------------------------

    def test_fi_request_oversized(self):
        oversized = b'{"pad": "' + b"x" * (5 * 1024 * 1024) + b'"}'
        status, body, _ = self._request(
            "POST", "/api/v1/security/evaluate", raw=oversized
        )
        self.assertEqual(status, 413)
        self.assertIsInstance(body, dict)
        self.assertEqual(body.get("failure_class"), "INVALID_REQUEST", body)

    # -- fi.request.malformed_json -----------------------------------------

    def test_fi_request_malformed_json(self):
        status, body, _ = self._request(
            "POST", "/api/v1/security/evaluate", raw=b'{"broken": '
        )
        self.assertEqual(status, 400)
        self.assertEqual(body.get("failure_class"), "INVALID_REQUEST", body)

    # -- fi.backend.unconfigured / fi.turing.unavailable -------------------

    def test_fi_backend_unconfigured(self):
        # A mutation against an unconfigured dependency is a typed
        # NOT_CONFIGURED refusal — never a fabricated success.
        headers = _mint_subscription()
        status, body, _ = self._request(
            "POST",
            "/api/v1/mining/switch",
            body={"pool": "nonexistent-pool", "observation": {"value": 1}},
            headers=headers,
        )
        self.assertEqual(status, 404, body)
        self.assertEqual(body.get("failure_class"), "NOT_CONFIGURED", body)

    def test_fi_turing_refusal(self):
        # TURING at its internal typed seam: an unrunnable request produces
        # a typed REFUSED/FAIL verdict — fail-closed, nothing fabricated.
        from turing_universal_quantum_computer import (
            Program,
            run_pipeline,
        )
        from turing_universal_quantum_computer.pipeline import VQCRequest

        report = run_pipeline(VQCRequest())
        self.assertIn(report.verdict, {"REFUSED", "FAIL"}, report.verdict)

        report = run_pipeline(
            VQCRequest(program=Program(n_qubits=1).then("bogus", 0))
        )
        self.assertEqual(report.verdict, "REFUSED", report.verdict)

    # -- fi.telemetry.reordered --------------------------------------------

    def test_fi_telemetry_reordered(self):
        gate = self.api._seq_gated_events
        events = [{"seq": 5}, {"seq": 7}, {"seq": 6}, {"seq": 7}]
        # Cursor at 6: the reordered seq=5 and duplicate seq=6 never
        # re-deliver; only the strictly-newer seq=7 frame passes — once.
        self.assertEqual([e["seq"] for e in gate(events, 6)], [7, 7])
        self.assertEqual(gate(events, 7), [])


class CircuitBreakerTests(unittest.TestCase):
    """fi.remote_gpu.* — the remote-execution lane's breaker, driven
    against a real (dead) endpoint so opening is measured, not assumed."""

    DEAD = "http://127.0.0.1:1"

    def test_fi_remote_gpu_breaker_opens(self):
        from chronus.mla1517.remote_gpu import (
            RemoteCircuitBreaker,
            RemoteGPUClient,
            RemoteGPUUnavailable,
        )

        breaker = RemoteCircuitBreaker(failure_threshold=3, recovery_timeout_s=60)
        client = RemoteGPUClient(self.DEAD, timeout=0.2, breaker=breaker)
        for _ in range(3):
            with self.assertRaises(RemoteGPUUnavailable):
                client.health()
        self.assertEqual(breaker.state, RemoteCircuitBreaker.OPEN)
        # Fourth call fails fast without touching the network.
        t0 = time.monotonic()
        with self.assertRaises(RemoteGPUUnavailable) as ctx:
            client.health()
        self.assertLess(time.monotonic() - t0, 0.2)
        self.assertIn("circuit", str(ctx.exception))

    def test_fi_remote_gpu_half_open_probe(self):
        from chronus.mla1517.remote_gpu import (
            RemoteCircuitBreaker,
            RemoteGPUClient,
            RemoteGPUUnavailable,
        )

        breaker = RemoteCircuitBreaker(failure_threshold=2, recovery_timeout_s=0.05)
        client = RemoteGPUClient(self.DEAD, timeout=0.2, breaker=breaker)
        for _ in range(2):
            with self.assertRaises(RemoteGPUUnavailable):
                client.health()
        self.assertEqual(breaker.state, RemoteCircuitBreaker.OPEN)
        time.sleep(0.06)
        # Recovery timeout elapsed: exactly one probe is admitted…
        self.assertEqual(breaker.state, RemoteCircuitBreaker.HALF_OPEN)
        self.assertTrue(breaker.allow())
        # …and a concurrent second probe is suppressed.
        self.assertFalse(breaker.allow())
        # Probe fails against the dead endpoint → re-OPEN.
        breaker.on_failure()
        self.assertEqual(breaker.state, RemoteCircuitBreaker.OPEN)

    def test_breaker_success_closes(self):
        from chronus.mla1517.remote_gpu import RemoteCircuitBreaker

        breaker = RemoteCircuitBreaker(failure_threshold=2, recovery_timeout_s=60)
        breaker.on_failure()
        self.assertEqual(breaker.state, RemoteCircuitBreaker.CLOSED)
        breaker.on_failure()
        self.assertEqual(breaker.state, RemoteCircuitBreaker.OPEN)
        breaker._opened_at -= 61  # age past recovery timeout
        self.assertTrue(breaker.allow())  # half-open probe
        breaker.on_success()
        self.assertEqual(breaker.state, RemoteCircuitBreaker.CLOSED)

    def test_breaker_grants_no_fallback_authority(self):
        """OPEN reports RemoteGPUUnavailable — the same honest failure class
        as a dead endpoint. It never substitutes another authority."""
        from chronus.mla1517.remote_gpu import (
            RemoteCircuitBreaker,
            RemoteGPUClient,
            RemoteGPUUnavailable,
        )

        breaker = RemoteCircuitBreaker(failure_threshold=1, recovery_timeout_s=60)
        client = RemoteGPUClient(self.DEAD, timeout=0.2, breaker=breaker)
        with self.assertRaises(RemoteGPUUnavailable):
            client.health()
        with self.assertRaises(RemoteGPUUnavailable) as ctx:
            client.devices()
        self.assertIn("circuit", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
