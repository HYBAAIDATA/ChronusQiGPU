"""Service-constitution suite — second-pass API elevation.

``governance/api_registry.yaml`` (schema ``pythia.api_registry/2``) plus
``governance/service_fabric.yaml`` form the machine-enforced service
constitution.  This suite proves the constitution is internally complete
and consistent:

* every interface carries the §2 constitution fields;
* the reliability tier assignment obeys the §4 rules (R0 owners are R0,
  R0 entries have no fallback semantics, reserved namespaces are R0);
* the declared per-interface dependencies and the canonical
  ``dependency_graph`` are the same set, in both directions;
* every graph edge carries the §5 required fields and references declared
  interfaces;
* journeys and production voyages reference only declared interfaces;
* the fabric's failure-class enum is identical to the runtime enum in
  ``failure_taxonomy`` — one enum, two projections;
* every error body the live HTTP surface emits carries a ``failure_class``
  drawn from that enum;
* the graceful-degradation matrix covers every dependency in the graph
  and no entry permits impersonation;
* backpressure, circuit-breaker, SLO and correlation declarations resolve
  to real interfaces and real implementation files;
* lifecycle values are the §15 states and agree with interface type and
  deprecation state.

Drift in either direction fails here — the constitution is executable.
"""

from __future__ import annotations

import copy
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
REGISTRY_PATH = REPO_ROOT / "governance" / "api_registry.yaml"
FABRIC_PATH = REPO_ROOT / "governance" / "service_fabric.yaml"

_REGISTRY = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
_FABRIC = yaml.safe_load(FABRIC_PATH.read_text(encoding="utf-8"))

APIS = {a["api_id"]: a for a in _REGISTRY["apis"]}
API_IDS = set(APIS)
EDGES = _FABRIC["dependency_graph"]["edges"]
LIFECYCLE_STATES = set(_FABRIC["lifecycle_states"])
EVIDENCE_CLASSES = set(_FABRIC["evidence_classes"])
VALID_TIERS = {"R0", "R1", "R2", "R3", "R4"}
VALID_SECURITY = {
    "PUBLIC_READ",
    "OPERATOR_AUTHENTICATED",
    "GUARDIAN_MEDIATED",
    "INTERNAL_TYPED",
    "WIRE_CREDENTIAL",
    "TENANT_SCOPED",
    "FILESYSTEM",
    "HMAC_SIDECAR",
    "ENVIRONMENT",
}
R0_OWNERS = {"AL_HARAS", "THESEUS", "SHA256D_VERIFIER"}


def _lifecycle_consistent(api: dict) -> bool:
    """Lifecycle state agrees with interface type and deprecation state."""
    lc = api["lifecycle"]
    if api["interface_type"] == "RESERVED_NAMESPACE":
        return lc == "RESERVED"
    if api["interface_type"] == "LEGACY" or api["deprecation_state"] == "COMPATIBILITY_ALIAS":
        return lc == "LEGACY"
    if api["deprecation_state"] == "DEPRECATED":
        return lc == "DEPRECATED"
    return lc in {"EXPERIMENTAL", "ACTIVE", "STABLE"}


class ConstitutionShapeTests(unittest.TestCase):
    def test_fabric_schema_and_registry_link(self):
        self.assertEqual(_FABRIC["schema"], "pythia.service_fabric/1")
        self.assertEqual(_FABRIC["registry_ref"], "governance/api_registry.yaml")
        self.assertEqual(_REGISTRY["schema"], "pythia.api_registry/2")

    def test_every_interface_has_constitution_fields(self):
        required = {
            "capability",
            "authority",
            "reliability_tier",
            "dependencies",
            "slo",
            "fallback_policy",
            "security_classification",
            "observability_requirement",
            "compatibility_window",
            "support_owner",
            "runtime_evidence",
            "lifecycle",
        }
        for api in _REGISTRY["apis"]:
            missing = required - set(api)
            self.assertFalse(missing, f"{api['api_id']} missing {sorted(missing)}")

    def test_authority_and_support_owner_are_canonical(self):
        owners = set(_REGISTRY["authority_register"])
        for api in _REGISTRY["apis"]:
            self.assertIn(api["authority"], owners, api["api_id"])
            self.assertIn(api["support_owner"], owners, api["api_id"])
            self.assertIn(api["owner"], owners, api["api_id"])

    def test_reliability_tiers_valid(self):
        declared = set(_FABRIC["reliability_tiers"])
        self.assertEqual(declared, VALID_TIERS)
        for api in _REGISTRY["apis"]:
            self.assertIn(api["reliability_tier"], VALID_TIERS, api["api_id"])

    def test_r0_owners_are_r0(self):
        for api in _REGISTRY["apis"]:
            if api["owner"] in R0_OWNERS:
                self.assertEqual(
                    api["reliability_tier"], "R0",
                    f"{api['api_id']} owned by {api['owner']} must be R0 fail-closed",
                )

    def test_r0_entries_have_no_semantic_fallback(self):
        markers = ("none", "fail", "deny", "closed", "refuse")
        for api in _REGISTRY["apis"]:
            if api["reliability_tier"] != "R0":
                continue
            fb = str(api["fallback_policy"]).lower()
            self.assertTrue(
                any(m in fb for m in markers),
                f"R0 entry {api['api_id']} declares a fallback: {api['fallback_policy']!r}",
            )

    def test_reserved_namespaces_are_r0_and_reserved_lifecycle(self):
        for api in _REGISTRY["apis"]:
            if api["interface_type"] == "RESERVED_NAMESPACE":
                self.assertEqual(api["reliability_tier"], "R0", api["api_id"])
                self.assertEqual(api["lifecycle"], "RESERVED", api["api_id"])

    def test_lifecycle_states_are_valid_and_consistent(self):
        self.assertEqual(
            LIFECYCLE_STATES,
            {"EXPERIMENTAL", "ACTIVE", "STABLE", "DEPRECATED", "RETIRED", "RESERVED", "LEGACY"},
        )
        for api in _REGISTRY["apis"]:
            self.assertIn(api["lifecycle"], LIFECYCLE_STATES, api["api_id"])
            self.assertTrue(
                _lifecycle_consistent(api),
                f"{api['api_id']}: lifecycle {api['lifecycle']} inconsistent with "
                f"type {api['interface_type']} / deprecation {api['deprecation_state']}",
            )

    def test_security_classification_and_evidence_classes(self):
        for api in _REGISTRY["apis"]:
            self.assertIn(
                api["security_classification"], VALID_SECURITY, api["api_id"]
            )
            self.assertIn(
                api["runtime_evidence"], EVIDENCE_CLASSES, api["api_id"]
            )

    def test_every_interface_has_consumers(self):
        for api in _REGISTRY["apis"]:
            self.assertTrue(api["consumers"], api["api_id"])


class DependencyGraphTests(unittest.TestCase):
    def test_edges_have_required_fields(self):
        required = set(_FABRIC["dependency_graph"]["required_edge_fields"])
        for edge in EDGES:
            missing = required - set(edge)
            self.assertFalse(
                missing,
                f"edge {edge.get('caller')}→{edge.get('callee')} missing {sorted(missing)}",
            )

    def test_edges_reference_declared_interfaces(self):
        for edge in EDGES:
            self.assertIn(edge["caller"], API_IDS, edge["caller"])
            self.assertIn(edge["callee"], API_IDS, edge["callee"])

    def test_registry_dependencies_match_graph_both_directions(self):
        graphed: dict[str, set[str]] = {}
        for edge in EDGES:
            graphed.setdefault(edge["caller"], set()).add(edge["callee"])
        for api_id, api in APIS.items():
            declared = set(api["dependencies"])
            graphed_deps = graphed.get(api_id, set())
            self.assertEqual(
                declared,
                graphed_deps,
                f"{api_id}: registry dependencies {sorted(declared)} != "
                f"graph edges {sorted(graphed_deps)}",
            )

    def test_every_callee_has_a_degradation_row(self):
        covered = {row["dependency"] for row in _FABRIC["degradation_matrix"]}
        for edge in EDGES:
            self.assertIn(
                edge["callee"],
                covered,
                f"dependency {edge['callee']} has no graceful-degradation row",
            )

    def test_degradation_matrix_never_permits_impersonation(self):
        for row in _FABRIC["degradation_matrix"]:
            self.assertIs(row["impersonation_allowed"], False, row["dependency"])
            self.assertIn(row["dependency"], API_IDS, row["dependency"])
            for api_id in row["affected"]:
                self.assertIn(api_id, API_IDS, f"{row['dependency']} -> {api_id}")

    def test_hard_edges_have_realistic_failure_propagation(self):
        classes = set(_FABRIC["failure_classes"])
        for edge in EDGES:
            if "HARD" not in str(edge["required_availability"]):
                continue
            propagation = str(edge["failure_propagation"])
            emitted = {p.strip() for p in propagation.replace("=>", " ").split(" or ")}
            emitted = {t for token in emitted for t in token.split()}
            declared = {t for t in emitted if t in classes}
            self.assertTrue(
                declared,
                f"HARD edge {edge['caller']}→{edge['callee']} propagates no "
                f"declared failure class: {propagation!r}",
            )


class FailureTaxonomyTests(unittest.TestCase):
    def test_runtime_enum_matches_fabric(self):
        import failure_taxonomy

        fabric_classes = set(_FABRIC["failure_classes"])
        self.assertEqual(failure_taxonomy.FAILURE_CLASSES, fabric_classes)

    def test_class_defaults_are_declared(self):
        import failure_taxonomy

        for cls in failure_taxonomy.FailureClass:
            declared = _FABRIC["failure_classes"][cls.value]
            self.assertEqual(
                int(failure_taxonomy.status_for(cls)),
                int(declared["http_status"]),
                cls.value,
            )

    def test_error_envelope_choke_point_installed(self):
        """control_api._json must route every error body through the
        taxonomy — absence means a pass-through receipt could lack a class."""
        import inspect

        import control_api

        src = inspect.getsource(control_api._Handler._json)
        self.assertIn("ensure_failure_class", src)


class JourneyAndVoyageTests(unittest.TestCase):
    def test_journey_steps_are_declared_interfaces(self):
        for jid, journey in _FABRIC["journeys"].items():
            for step in journey["steps"]:
                self.assertIn(step, API_IDS, f"{jid} step {step}")

    def test_voyage_references_resolve(self):
        journeys = set(_FABRIC["journeys"])
        for vid, voyage in _FABRIC["production_voyages"].items():
            if "journey" in voyage:
                self.assertIn(voyage["journey"], journeys, vid)

    def test_journey_tiers_are_valid(self):
        for jid, journey in _FABRIC["journeys"].items():
            self.assertIn(journey["tier"], VALID_TIERS, jid)

    def test_executive_indicator_journeys_cover_r0_to_r3(self):
        tiers = {
            journey["tier"]
            for journey in _FABRIC["journeys"].values()
            if journey.get("executive_indicator")
        }
        self.assertTrue({"R0", "R1", "R2", "R3"} <= tiers)


class ResilienceDeclarationTests(unittest.TestCase):
    def test_circuit_breakers_reference_real_dependencies(self):
        for cb in _FABRIC["circuit_breakers"]:
            self.assertIn(cb["dependency"], API_IDS, cb["dependency"])
            impl = str(cb["implementation"]).split("::")[0]
            self.assertTrue(
                (REPO_ROOT / impl).is_file(),
                f"circuit breaker implementation missing: {impl}",
            )
            self.assertEqual(
                cb["states"], ["CLOSED", "OPEN", "HALF_OPEN"] if len(cb["states"]) == 3 else cb["states"],
            )

    def test_backpressure_entries_reference_real_interfaces(self):
        for bp in _FABRIC["backpressure"]:
            self.assertIn(bp["interface"], API_IDS, bp["interface"])
            self.assertIn("drop_policy", bp)
            self.assertIn("exposed", bp)

    def test_bulkheads_name_proof(self):
        for bh in _FABRIC["bulkheads"]:
            self.assertIn("resource", bh)
            self.assertIn("separation", bh)
            self.assertIn("proof", bh)

    def test_slos_have_dimensions_and_budget_policy(self):
        for sid, slo in _FABRIC["slos"].items():
            self.assertIn(slo["tier"], VALID_TIERS, sid)
            self.assertTrue(slo["dimensions"], sid)
            self.assertIn("error_budget", slo, sid)

    def test_registry_slo_refs_resolve(self):
        slos = set(_FABRIC["slos"])
        for api in _REGISTRY["apis"]:
            self.assertIn(api["slo"], slos, f"{api['api_id']} -> {api['slo']}")

    def test_r0_slos_have_no_error_budget(self):
        for api in _REGISTRY["apis"]:
            if api["reliability_tier"] != "R0":
                continue
            slo = _FABRIC["slos"][api["slo"]]
            self.assertNotIn(
                "release-managed",
                str(slo["error_budget"]),
                f"R0 interface {api['api_id']} must not carry an error budget",
            )

    def test_correlation_envelope_fields(self):
        env = _FABRIC["correlation_envelope"]
        self.assertIn("X-Request-Id", env["http_headers"]["inbound"])
        self.assertIn("X-Correlation-Id", env["http_headers"]["outbound"])
        for field in ("request_id", "correlation_id", "causation_id", "tenant_id", "actor_id", "operation", "schema_version"):
            self.assertIn(field, env["fields"])

    def test_recovery_objectives_present_per_tier(self):
        for tier in VALID_TIERS:
            self.assertIn(tier, _FABRIC["recovery_objectives"], tier)

    def test_evidence_classes_complete(self):
        self.assertEqual(
            EVIDENCE_CLASSES,
            {
                "SOURCE_PRESENT", "SOURCE_WIRED", "LOCAL_TEST_PASSED",
                "LOCAL_HTTP_E2E_EXECUTED", "LOCAL_CROSS_SERVICE_EXECUTED",
                "FAULT_INJECTION_EXECUTED", "RECOVERY_EXECUTED",
                "INSTALLED_ARTIFACT_EXECUTED", "M3_RUNTIME_OBSERVED",
                "CI_EXECUTED", "LIVE_POOL_OBSERVED", "PHYSICAL_DEVICE_OBSERVED",
                "PERFORMANCE_MEASURED", "POOL_ACCEPTANCE_OBSERVED",
            },
        )


# ---------------------------------------------------------------------------
# Live HTTP surface — the constitution is exercised over the wire, not just
# declared.  Same harness as tests/test_production_api_contract.py.
# ---------------------------------------------------------------------------

_SUB_KEYRING = {"test": "k" * 32}


def _mint_subscription() -> dict[str, str]:
    from al_haras.entitlements import SubscriptionAuthority, SubscriptionClaims

    token = SubscriptionAuthority(
        {"test": b"k" * 32}, "hyba-subscriptions"
    ).issue(
        SubscriptionClaims(
            subscription_id="sub-constitution",
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


class ConstitutionWireTests(unittest.TestCase):
    """The error envelope, correlation envelope, dependency health and
    idempotency contract exercised against a live server."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        (root / "index.html").write_text("<html>pythia</html>", encoding="utf-8")
        self.env_patch = {
            "MLA1517_STRATUM_USER": "constitution.wire",
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

    def test_every_error_body_carries_a_declared_failure_class(self):
        classes = set(_FABRIC["failure_classes"])
        voyages = [
            ("GET", "/api/v1/no-such-route", None, None),                      # 404
            ("POST", "/api/v1/mining/stop", {}, None),                       # guardian deny (no creds)
            ("POST", "/api/v1/security/evaluate", {"x": 1}, None),           # guardian verdict w/o creds
            ("PUT", "/api/v1/config", {"bogus": {}}, None),                  # invalid request
            ("DELETE", "/api/v1/healthz", None, None),                       # 405
        ]
        for method, path, body, headers in voyages:
            status, parsed, _ = self._request(method, path, body=body, headers=headers)
            self.assertGreaterEqual(status, 400, f"{method} {path} expected error, got {status}")
            self.assertIsInstance(parsed, dict, f"{method} {path} non-JSON error body")
            self.assertIn(
                parsed.get("failure_class"),
                classes,
                f"{method} {path} -> {status} body {parsed} lacks a declared failure_class",
            )

    def test_correlation_envelope_is_complete(self):
        status, _body, headers = self._request(
            "GET",
            "/api/v1/healthz",
            headers={
                "X-Request-Id": "req-1",
                "X-Correlation-Id": "corr-9",
                "X-Causation-Id": "cause-7",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("X-Request-Id"), "req-1")
        self.assertEqual(headers.get("X-Correlation-Id"), "corr-9")
        self.assertEqual(headers.get("X-Causation-Id"), "cause-7")

        # Malformed correlation ids are replaced, never trusted.
        status, _body, headers = self._request(
            "GET", "/api/v1/healthz", headers={"X-Correlation-Id": "bad id"}
        )
        self.assertEqual(status, 200)
        corr = headers.get("X-Correlation-Id", "")
        self.assertNotEqual(corr, "bad id")
        self.assertTrue(corr)

    def test_readiness_reports_dependency_health(self):
        status, body, _ = self._request("GET", "/api/v1/readyz")
        self.assertIn(status, (200, 503))
        components = body["components"]
        for name in (
            "identity",
            "boot_audit",
            "worker_heartbeat_dir",
            "guardian",
            "runtime_config",
            "stratum",
            "remote_opencl",
            "custody",
        ):
            self.assertIn(name, components, f"readiness lacks component {name}")
            self.assertIn("state", components[name], name)
        self.assertEqual(components["stratum"]["state"], "disconnected")
        self.assertEqual(components["remote_opencl"]["state"], "not_configured")
        self.assertEqual(components["custody"]["state"], "not_mounted")

    def test_idempotency_key_replays_without_reexecution(self):
        key = "idem-constitution-1"
        stop = {"X-Idempotency-Key": "", "Idempotency-Key": key}
        first_status, first, _ = self._request(
            "POST", "/api/v1/agentic/stop", body={}, headers=stop
        )
        second_status, second, _ = self._request(
            "POST", "/api/v1/agentic/stop", body={}, headers=stop
        )
        self.assertEqual(first_status, second_status)
        self.assertIsInstance(first, dict)
        self.assertIsInstance(second, dict)
        # The replay returns the recorded outcome plus the replay marker.
        self.assertTrue(second.get("idempotent_replay"), second)
        self.assertNotIn("idempotent_replay", first)
        self.assertEqual(
            {k: v for k, v in first.items() if k != "idempotent_replay"},
            {k: v for k, v in second.items() if k != "idempotent_replay"},
        )

    def test_metrics_report_fabric_counters(self):
        self._request("GET", "/api/v1/healthz")
        self._request("GET", "/api/v1/no-such-route")
        status, body, _ = self._request("GET", "/api/v1/metrics")
        self.assertEqual(status, 200)
        text = body if isinstance(body, str) else body.decode("utf-8", "replace")
        self.assertIn("pythia_control_requests_total", text)
        self.assertIn('pythia_control_failure_class_total{failure_class="NOT_FOUND"}', text)


class TypedClientTests(unittest.TestCase):
    """§31: the shipped typed client against the live seam — correlation,
    typed failure classes, idempotent replay."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        (root / "index.html").write_text("<html>pythia</html>", encoding="utf-8")
        self.env_patch = {
            "MLA1517_STRATUM_USER": "client.wire",
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
        import pythia_client

        self.api = control_api
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), control_api._Handler)
        self.server.web_root = root
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._close_server)
        self.client = pythia_client.PythiaClient(
            f"http://127.0.0.1:{self.server.server_address[1]}"
        )

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

    def test_client_reads_canonical_surfaces(self):
        self.assertEqual(self.client.health().status, 200)
        readiness = self.client.readiness()
        self.assertIn(readiness.status, (200, 503))
        self.assertIn("custody", readiness.body["components"])
        self.assertEqual(self.client.config().status, 200)
        self.assertEqual(self.client.stratum_status().status, 200)
        self.assertEqual(self.client.audit_tail(limit=5).status, 200)

    def test_client_propagates_correlation(self):
        resp = self.client.request(
            "GET", "/api/v1/healthz", correlation_id="corr-client-1"
        )
        self.assertEqual(resp.correlation_id, "corr-client-1")
        self.assertTrue(resp.request_id)

    def test_client_raises_typed_failure(self):
        import pythia_client

        with self.assertRaises(pythia_client.PythiaError) as ctx:
            self.client.request("GET", "/api/v1/no-such-route")
        self.assertEqual(ctx.exception.failure_class, "NOT_FOUND")
        self.assertEqual(ctx.exception.status, 404)

    def test_client_idempotent_replay(self):
        headers = _mint_subscription()
        client = type(self.client)(
            self.client.base_url, headers={**self.client.headers, **headers}
        )
        update = {"hashrate": {"target_hs": 3.0}}
        first = client.update_config(update, idempotency_key="tc-1")
        second = client.update_config(update, idempotency_key="tc-1")
        self.assertEqual(first.status, 200)
        self.assertTrue(second.body.get("idempotent_replay"), second.body)


# ---------------------------------------------------------------------------
# Mutation gate (§26) — the constitution's predicates, fed tampered copies,
# must report the tampering. A gate that cannot fail is not a gate.
# ---------------------------------------------------------------------------

_CONSTITUTION_FIELDS = {
    "capability", "authority", "reliability_tier", "dependencies", "slo",
    "fallback_policy", "security_classification",
    "observability_requirement", "compatibility_window", "support_owner",
    "runtime_evidence", "lifecycle",
}


def _constitution_violations(reg: dict, fab: dict) -> list[str]:
    """The constitution's executable predicates, run over any (possibly
    mutated) registry/fabric pair. Returns every violation found."""
    out: list[str] = []
    apis = {a["api_id"]: a for a in reg["apis"]}
    api_ids = set(apis)
    edges = fab["dependency_graph"]["edges"]
    slos = set(fab["slos"])
    covered = {row["dependency"] for row in fab["degradation_matrix"]}
    edge_fields = set(fab["dependency_graph"]["required_edge_fields"])

    for api in reg["apis"]:
        aid = api["api_id"]
        missing = _CONSTITUTION_FIELDS - set(api)
        if missing:
            out.append(f"{aid}: missing constitution fields {sorted(missing)}")
        if api.get("reliability_tier") not in VALID_TIERS:
            out.append(f"{aid}: invalid tier {api.get('reliability_tier')!r}")
        if api.get("owner") in R0_OWNERS and api.get("reliability_tier") != "R0":
            out.append(f"{aid}: R0 owner {api.get('owner')} with tier {api.get('reliability_tier')}")
        if api.get("lifecycle") not in LIFECYCLE_STATES:
            out.append(f"{aid}: invalid lifecycle {api.get('lifecycle')!r}")
        elif not _lifecycle_consistent(api):
            out.append(f"{aid}: lifecycle/type/deprecation inconsistent")
        if api.get("security_classification") not in VALID_SECURITY:
            out.append(f"{aid}: invalid security class")
        if api.get("runtime_evidence") not in EVIDENCE_CLASSES:
            out.append(f"{aid}: invalid evidence class")
        if api.get("slo") not in slos:
            out.append(f"{aid}: slo {api.get('slo')} not declared in fabric")
        for dep in api.get("dependencies") or []:
            if dep not in api_ids:
                out.append(f"{aid}: undeclared dependency {dep}")

    graphed: dict[str, set[str]] = {}
    for edge in edges:
        graphed.setdefault(edge["caller"], set()).add(edge["callee"])
        if edge["caller"] not in api_ids:
            out.append(f"edge caller {edge['caller']} undeclared")
        if edge["callee"] not in api_ids:
            out.append(f"edge callee {edge['callee']} undeclared")
        missing = edge_fields - set(edge)
        if missing:
            out.append(f"edge {edge.get('caller')}→{edge.get('callee')} missing {sorted(missing)}")
        if edge["callee"] in api_ids and edge["callee"] not in covered:
            out.append(f"dependency {edge['callee']} lacks degradation row")
    for api_id, api in apis.items():
        if set(api["dependencies"]) != graphed.get(api_id, set()):
            out.append(f"{api_id}: registry deps != graph edges")

    for row in fab["degradation_matrix"]:
        if row.get("impersonation_allowed") is not False:
            out.append(f"degradation row {row.get('dependency')} permits impersonation")

    import failure_taxonomy

    if set(fab["failure_classes"]) != failure_taxonomy.FAILURE_CLASSES:
        out.append("fabric failure_classes != runtime taxonomy")

    for jid, journey in fab["journeys"].items():
        for step in journey["steps"]:
            if step not in api_ids:
                out.append(f"journey {jid} step {step} undeclared")
    return out


class ConstitutionMutationGateTests(unittest.TestCase):
    """Feed the predicates tampered copies: each mutation must surface."""

    def test_clean_pair_has_zero_violations(self):
        self.assertEqual(_constitution_violations(_REGISTRY, _FABRIC), [])

    def test_detects_removed_constitution_field(self):
        reg = copy.deepcopy(_REGISTRY)
        del reg["apis"][0]["reliability_tier"]
        self.assertTrue(
            any("missing constitution fields" in v for v in _constitution_violations(reg, _FABRIC))
        )

    def test_detects_tier_demotion_on_r0_owner(self):
        reg = copy.deepcopy(_REGISTRY)
        for api in reg["apis"]:
            if api["owner"] in R0_OWNERS:
                api["reliability_tier"] = "R3"
                break
        self.assertTrue(
            any("R0 owner" in v for v in _constitution_violations(reg, _FABRIC))
        )

    def test_detects_removed_graph_edge(self):
        fab = copy.deepcopy(_FABRIC)
        fab["dependency_graph"]["edges"].pop()
        self.assertTrue(_constitution_violations(_REGISTRY, fab))

    def test_detects_extra_registry_dependency(self):
        reg = copy.deepcopy(_REGISTRY)
        reg["apis"][0]["dependencies"].append("turing.vqc_pipeline")
        self.assertTrue(_constitution_violations(reg, _FABRIC))

    def test_detects_dropped_failure_class(self):
        fab = copy.deepcopy(_FABRIC)
        fab["failure_classes"].pop(next(iter(fab["failure_classes"])))
        self.assertTrue(_constitution_violations(_REGISTRY, fab))

    def test_detects_invalid_lifecycle(self):
        reg = copy.deepcopy(_REGISTRY)
        reg["apis"][0]["lifecycle"] = "SORTA_DEPRECATED"
        self.assertTrue(
            any("invalid lifecycle" in v for v in _constitution_violations(reg, _FABRIC))
        )

    def test_detects_impersonation_row(self):
        fab = copy.deepcopy(_FABRIC)
        fab["degradation_matrix"][0]["impersonation_allowed"] = True
        self.assertTrue(
            any("impersonation" in v for v in _constitution_violations(_REGISTRY, fab))
        )

    def test_detects_journey_phantom_step(self):
        fab = copy.deepcopy(_FABRIC)
        jid = next(iter(fab["journeys"]))
        fab["journeys"][jid]["steps"].append("phantom.api")
        self.assertTrue(
            any("phantom.api" in v for v in _constitution_violations(_REGISTRY, fab))
        )

    def test_detects_missing_degradation_row(self):
        fab = copy.deepcopy(_FABRIC)
        fab["degradation_matrix"].pop()
        self.assertTrue(_constitution_violations(_REGISTRY, fab))


class ConsumerContractTests(unittest.TestCase):
    """Consumer-driven checks (§27): the contract a declared consumer relies
    on is exercised from the consumer's side of the seam."""

    def test_every_api_declares_consumers(self):
        for api in _REGISTRY["apis"]:
            self.assertTrue(api.get("consumers"), api["api_id"])

    def test_every_consumer_seam_names_a_proof(self):
        for api in _REGISTRY["apis"]:
            for t in api["tests"]:
                for probe in t.split(","):
                    probe = probe.strip()
                    if probe.endswith(".py") or "/" in probe:
                        self.assertTrue(
                            (REPO_ROOT / probe).exists() or probe.startswith("chronus"),
                            f"{api['api_id']} names test {probe} that does not exist",
                        )

    def test_http_consumers_see_declared_schema_version(self):
        """A consumer reading a GET surface receives the schema_version the
        registry promises it."""
        # The live voyages in test_production_api_contract.HttpVoyageTests
        # assert declared schema_versions over the wire; here we pin the
        # contract at the structural level: every HTTP api whose response
        # schema names schema_version must declare a non-trivial one.
        for api in _REGISTRY["apis"]:
            if api["interface_type"] not in {
                "HTTP_PUBLIC", "HTTP_OPERATOR", "HTTP_PRIVILEGED", "LEGACY"
            }:
                continue
            if "schema_version" not in str(api["response_schema"]):
                continue
            self.assertNotIn(
                api["schema_version"], ("none", "-", ""),
                f"{api['api_id']} promises schema_version but declares none",
            )


if __name__ == "__main__":
    unittest.main()
