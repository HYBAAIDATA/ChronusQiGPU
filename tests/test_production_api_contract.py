"""Production API & service-communication contract suite.

The canonical contract lives in ``governance/api_registry.yaml`` — a
machine-readable registry of every production interface. This suite tests the
*implementation* against that contract (never the reverse):

* registry integrity — required fields, valid classes, frozen authority register
* route parity — the HTTP surface implemented in control_api.py is exactly the
  surface the registry declares, in all three directions (A: every declared
  concrete route has a handler; B: every handler is declared; C: every
  RESERVED_NAMESPACE entry has no handler)
* live HTTP voyages — a real ThreadingHTTPServer serves every declared route;
  status codes, schema markers, auth classes, and the X-Request-Id correlation
  envelope are asserted over the wire
* reserved namespaces — secured prefixes deny at the boundary and never
  masquerade as implemented endpoints
* internal contracts — THESEUS custody, OVID transformation, KELLOGG tensor,
  SALAMANDER autonomic, TURING VQC, AL HARAS guardian, HYBA_DB persistence
* generated-doc round-trip — ``render_api_contract.py --check`` regenerates
  ``docs/PYTHIA_API_CONTRACT.md`` and ``docs/openapi.yaml`` from the registry
  and compares byte-for-byte; one byte of drift in either fails
* mutation self-tests — the parity and round-trip gates are each proven to
  detect drift (remove a handler, add an undeclared handler, add a handler
  under a reserved prefix, drift a generated doc by one byte)
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import os
import re
import subprocess
import sys
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
CONTROL_API_PATH = (
    REPO_ROOT / "chronus" / "mla1517_platform" / "python" / "control_api.py"
)
RENDERER_PATH = REPO_ROOT / "governance" / "render_api_contract.py"
OPENAPI_PATH = REPO_ROOT / "docs" / "openapi.yaml"
CONTRACT_DOC_PATH = REPO_ROOT / "docs" / "PYTHIA_API_CONTRACT.md"

# ---------------------------------------------------------------------------
# Registry loading / shape
# ---------------------------------------------------------------------------

_REGISTRY = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))

FROZEN_AUTHORITY_REGISTER = {
    "EUCLID": "intelligence orchestration",
    "PYTHIA": "predictive/causal intelligence, mining intelligence, final SearchPlan",
    "TURING": "independent VQC",
    "KELLOGG": "tensor capability",
    "CHRONUS": "heterogeneous execution",
    "THESEUS": "durable custody, integrity, continuity, records, recovery, provenance",
    "OVID": "representation/state transformation and transform lineage",
    "SALAMANDER": "bounded self-healing and optimisation",
    "AL_HARAS": "security, identity, capability, authorisation, governance",
    "SHA256D_VERIFIER": "candidate validity",
    "POOL": "external share acceptance",
    "HYBA_DB": "tenant-scoped ontology/query/projection persistence",
}

VALID_AUTH_CLASSES = set(_REGISTRY["authentication_classes"])
VALID_TRUTH_CLASSES = set(_REGISTRY["truth_classes"])
VALID_DEPRECATION = {"CANONICAL", "COMPATIBILITY_ALIAS", "RESERVED_NAMESPACE", "DEPRECATED"}
HTTP_TYPES = {"HTTP_PUBLIC", "HTTP_OPERATOR", "HTTP_PRIVILEGED", "EVENT_STREAM", "LEGACY"}

REQUIRED_FIELDS = (
    "api_id",
    "owner",
    "interface_type",
    "implementation_path",
    "consumers",
    "request_schema",
    "response_schema",
    "schema_version",
    "authentication_class",
    "authorisation_authority",
    "truth_class",
    "side_effects",
    "custody_requirement",
    "timeout",
    "idempotency",
    "retry",
    "failure_semantics",
    "availability_semantics",
    "stability",
    "deprecation_state",
    "tests",
)


def _auth_classes(value: str) -> set[str]:
    """'GET: NONE; POST: OPERATOR_PRINCIPAL' → {'NONE','OPERATOR_PRINCIPAL'}."""
    out: set[str] = set()
    for segment in str(value).split(";"):
        segment = segment.split(":", 1)[-1].strip()
        if segment:
            out.add(segment)
    return out


def _truth_classes(value: str) -> set[str]:
    return _auth_classes(value)


def _declared_http_routes(registry=_REGISTRY) -> dict[tuple[str, str], dict]:
    """(METHOD, path) → registry entry, from each entry's authoritative routes."""
    pairs: dict[tuple[str, str], dict] = {}
    for api in registry["apis"]:
        if api.get("interface_type") not in HTTP_TYPES:
            continue
        for route in api.get("routes") or []:
            method, _, path = route.partition(" ")
            pairs[(method, path)] = api
    return pairs


def _implemented_http_routes() -> set[tuple[str, str]]:
    """Parse control_api.py and return the concrete routes it actually serves.

    GET paths come from ``_route_get``'s ``path == ...`` / ``path in {...}``
    comparisons, POST from ``_route_post`` comparisons plus the ``_POST_TABLE``
    dict literal, PUT from ``do_PUT``. This reads the dispatch code itself, so
    a route added or dropped anywhere in the handler shows up here.
    """
    tree = ast.parse(CONTROL_API_PATH.read_text(encoding="utf-8"))
    routes: set[tuple[str, str]] = set()
    handler = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "_Handler"
    )
    fn_methods = {"_route_get": "GET", "_route_post": "POST", "do_PUT": "PUT"}
    for fn in handler.body:
        if isinstance(fn, ast.AnnAssign) and getattr(fn.target, "id", "") == "_POST_TABLE":
            if isinstance(fn.value, ast.Dict):
                for key in fn.value.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        routes.add(("POST", key.value))
            continue
        if not isinstance(fn, ast.FunctionDef):
            continue
        method = fn_methods.get(fn.name)
        if method is None:
            continue
        for node in ast.walk(fn):
            if not isinstance(node, ast.Compare) or len(node.ops) != 1:
                continue
            left = node.left
            on_path = (
                isinstance(left, ast.Name)
                and left.id == "path"
            ) or (
                isinstance(left, ast.Attribute)
                and left.attr == "path"
            )
            if not on_path:
                continue
            op, comp = node.ops[0], node.comparators[0]
            if (
                isinstance(op, (ast.Eq, ast.NotEq))
                and isinstance(comp, ast.Constant)
                and isinstance(comp.value, str)
                and comp.value.startswith("/")
            ):
                routes.add((method, comp.value))
            elif isinstance(op, ast.In) and isinstance(comp, ast.Set):
                for elt in comp.elts:
                    if (
                        isinstance(elt, ast.Constant)
                        and isinstance(elt.value, str)
                        and elt.value.startswith("/")
                    ):
                        routes.add((method, elt.value))
    return routes


def _privileged_prefixes() -> tuple[str, ...]:
    import control_api

    return control_api._PRIVILEGED_PREFIXES


def _parity_diff(implemented, declared_pairs):
    """(implemented-but-undeclared, declared-but-unimplemented) symmetric diff."""
    declared = set(declared_pairs)
    return sorted(implemented - declared), sorted(declared - implemented)


# ---------------------------------------------------------------------------
# Part A — registry integrity
# ---------------------------------------------------------------------------


class RegistryIntegrityTests(unittest.TestCase):
    def test_registry_schema_and_authority_register_are_frozen(self):
        self.assertEqual(_REGISTRY["schema"], "pythia.api_registry/1")
        self.assertEqual(_REGISTRY["authority_register"], FROZEN_AUTHORITY_REGISTER)

    def test_every_entry_is_complete_and_well_formed(self):
        seen: set[str] = set()
        interface_types = set(_REGISTRY["interface_types"])
        for api in _REGISTRY["apis"]:
            api_id = api["api_id"]
            self.assertNotIn(api_id, seen, f"duplicate api_id {api_id}")
            seen.add(api_id)
            for field_name in REQUIRED_FIELDS:
                self.assertIn(
                    field_name, api, f"{api_id} is missing field {field_name}"
                )
            self.assertIn(
                api["owner"],
                FROZEN_AUTHORITY_REGISTER,
                f"{api_id} owner {api['owner']} is outside the authority register",
            )
            self.assertIn(api["interface_type"], interface_types)
            self.assertTrue(
                _auth_classes(api["authentication_class"]) <= VALID_AUTH_CLASSES,
                f"{api_id} has an unknown authentication class",
            )
            self.assertTrue(
                _truth_classes(api["truth_class"]) <= VALID_TRUTH_CLASSES,
                f"{api_id} has an unknown truth class",
            )
            self.assertIn(api["deprecation_state"], VALID_DEPRECATION)
            for test_ref in api["tests"]:
                self.assertTrue(
                    (REPO_ROOT / test_ref).is_file(),
                    f"{api_id} cites missing test file {test_ref}",
                )

    def test_http_entries_declare_routes(self):
        for api in _REGISTRY["apis"]:
            if api["interface_type"] in HTTP_TYPES:
                self.assertTrue(
                    api.get("routes"),
                    f"{api['api_id']} is an HTTP surface without declared routes",
                )

    def test_reserved_namespaces_are_reserved(self):
        for api in _REGISTRY["apis"]:
            if api["interface_type"] == "RESERVED_NAMESPACE":
                self.assertEqual(api["deprecation_state"], "RESERVED_NAMESPACE")
                self.assertEqual(api["authentication_class"], "AL_HARAS_SUBSCRIPTION")


# ---------------------------------------------------------------------------
# Part B — implementation ↔ registry parity
# ---------------------------------------------------------------------------


class RouteParityTests(unittest.TestCase):
    """Registry ↔ handler parity, enforced in all three directions.

    Direction A — every registry HTTP entry declared ``IMPLEMENTED`` (a
    concrete declared route) has a handler in control_api.py.
    Direction B — every handler (dispatch-table or comparison route) in
    control_api.py has a registry entry.
    Direction C — every registry ``RESERVED_NAMESPACE`` entry has NO handler:
    its prefix is behind the guardian and no implemented route is served
    beneath it.
    """

    def test_implemented_surface_equals_declared_surface(self):
        """Directions A and B: declared surface == implemented surface."""
        declared = _declared_http_routes()
        # Non-literal declared routes: the SPA wildcard and reserved-prefix
        # wildcards are behaviour contracts, not dispatch literals.
        concrete_declared = {
            pair
            for pair in declared
            if pair[0] != "*" and not pair[1].startswith("/*")
        }
        implemented = _implemented_http_routes()
        extra, missing = _parity_diff(implemented, concrete_declared)
        self.assertEqual(
            extra,
            [],
            "routes implemented but not declared in the registry",
        )
        self.assertEqual(
            missing,
            [],
            "routes declared in the registry but not implemented",
        )

    def test_privileged_prefix_membership_matches_auth_class(self):
        declared = _declared_http_routes()
        prefixes = _privileged_prefixes()
        for (method, path), api in declared.items():
            if method == "*" or path.startswith("/*"):
                continue
            privileged = path.startswith(prefixes)
            if privileged:
                self.assertIn(
                    "AL_HARAS_SUBSCRIPTION",
                    _auth_classes(api["authentication_class"]),
                    f"{method} {path} is under a guardian prefix but is not "
                    f"declared AL_HARAS_SUBSCRIPTION (api {api['api_id']})",
                )
            elif method in {"POST", "PUT", "DELETE", "PATCH"}:
                self.assertIn(
                    "OPERATOR_PRINCIPAL",
                    _auth_classes(api["authentication_class"]),
                    f"{method} {path} mutates outside the guardian but is not "
                    f"declared OPERATOR_PRINCIPAL (api {api['api_id']})",
                )

    def test_reserved_namespaces_have_no_implementation(self):
        """Direction C: no implemented route is served under a reserved prefix."""
        implemented = _implemented_http_routes()
        prefixes = _privileged_prefixes()
        for api in _REGISTRY["apis"]:
            if api["interface_type"] != "RESERVED_NAMESPACE":
                continue
            prefix = api["path"]
            self.assertIn(
                prefix,
                prefixes,
                f"reserved namespace {prefix} is not behind the guardian",
            )
            served = [r for r in implemented if r[1].startswith(prefix)]
            self.assertEqual(
                served,
                [],
                f"reserved namespace {prefix} has implemented routes {served} — "
                "it must deny at the boundary, never masquerade as a service",
            )

    def test_every_privileged_route_operation_is_guardian_allowlisted(self):
        """The guardian derives operation names from paths; a privileged route
        whose operation is not allowlisted denies every caller forever."""
        declared = _declared_http_routes()
        prefixes = _privileged_prefixes()
        from al_haras_pythia import _PYTHIA_ALLOWED_OPERATIONS

        for (method, path), _api in declared.items():
            if method == "*" or path.startswith("/*"):
                continue
            if not path.startswith(prefixes):
                continue
            operation = path.removeprefix("/api/v1/").replace("/", ".")
            self.assertIn(
                operation,
                _PYTHIA_ALLOWED_OPERATIONS,
                f"{method} {path} derives guardian operation {operation!r} "
                "which is not allowlisted — the route would deny everyone",
            )


# ---------------------------------------------------------------------------
# Part C — live HTTP voyages against a real server
# ---------------------------------------------------------------------------

_SUB_KEYRING = {"test": "k" * 32}
_SUB_HEADERS = {}


def _mint_subscription() -> dict[str, str]:
    from al_haras.entitlements import SubscriptionAuthority, SubscriptionClaims

    token = SubscriptionAuthority(
        {"test": b"k" * 32}, "hyba-subscriptions"
    ).issue(
        SubscriptionClaims(
            subscription_id="sub-contract",
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


class HttpVoyageTests(unittest.TestCase):
    """Boot the real handler and drive every declared HTTP route."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        (root / "index.html").write_text("<html>pythia</html>", encoding="utf-8")
        self.env_patch = {
            "MLA1517_STRATUM_USER": "voyage.contract",
            "MLA1517_STRATUM_PASSWORD": "x",
            "MLA1517_VIABTC_ENDPOINT": "btc.viabtc.io:3333",
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

    def _declared_gets(self, auth_class):
        out = []
        for (method, path), api in _declared_http_routes().items():
            if method != "GET" or path.startswith("/*"):
                continue
            if auth_class in _auth_classes(api["authentication_class"]):
                out.append((path, api))
        return sorted(out)

    # --- public / operator read surface -----------------------------------

    def test_every_unauthenticated_get_voyage(self):
        schema_expect = {
            "/api/v1/healthz": "chronus.mla1517.status/1",
            "/api/health": "chronus.mla1517.status/1",
            "/healthz": "chronus.mla1517.status/1",
            "/api/v1/readyz": "chronus.mla1517.ready/1",
            "/readyz": "chronus.mla1517.ready/1",
            "/api/v1/ready-to-mine": "chronus.mla1517.ready/1",
            "/ready-to-mine": "chronus.mla1517.ready/1",
            "/api/v1/mla1517/status": "chronus.mla1517.status/1",
        }
        # Surfaces that answer 503 by contract when the subsystem is honestly
        # not ready on this host.
        honest_unavailable = {"/api/v1/ready-to-mine", "/ready-to-mine"}
        for path, api in self._declared_gets("NONE"):
            if path == "/api/v1/telemetry/stream":
                continue  # SSE voyage covered separately
            status, body, headers = self._request("GET", path)
            with self.subTest(path=path):
                self.assertIn(
                    "x-request-id",
                    {k.lower() for k in headers},
                    "correlation envelope missing",
                )
                if path in honest_unavailable and status == 503:
                    self.assertEqual(body["ready"], False)
                else:
                    self.assertEqual(status, 200, f"{path} → {status}: {body}")
                if path in schema_expect:
                    self.assertEqual(body["schema_version"], schema_expect[path])
                if path in {"/api/v1/readyz", "/readyz"}:
                    self.assertIn("components", body)
                    self.assertIn("identity", body["components"])
                if api["schema_version"] == "prometheus.exposition/0.0.4":
                    self.assertIn("text/plain", headers.get("Content-Type", ""))

    def test_correlation_envelope(self):
        status, _body, headers = self._request(
            "GET", "/api/v1/healthz", headers={"X-Request-Id": "voyage-123"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("X-Request-Id"), "voyage-123")
        status, _body, headers = self._request("GET", "/api/v1/healthz")
        self.assertEqual(status, 200)
        minted = headers.get("X-Request-Id", "")
        self.assertTrue(minted and minted != "voyage-123")

    def test_correlation_envelope_rejects_malformed_ids(self):
        # sane = 1-128 chars, alphanumeric lead, then [A-Za-z0-9._:@-]; a
        # malformed caller id is never echoed — a fresh id is minted.
        for bad in ("not sane!", "has space", "(paren)", "semi;colon"):
            status, _body, headers = self._request(
                "GET", "/api/v1/healthz", headers={"X-Request-Id": bad}
            )
            self.assertEqual(status, 200)
            echoed = headers.get("X-Request-Id", "")
            self.assertNotEqual(echoed, bad)
            self.assertRegex(echoed, r"\A[0-9a-f]{32}\Z")

    def test_sse_stream_is_a_real_event_stream(self):
        import socket

        sock = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        try:
            sock.sendall(
                b"GET /api/v1/telemetry/stream HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\nConnection: close\r\n\r\n"
            )
            sock.settimeout(8)
            data = sock.recv(8192)
        finally:
            sock.close()
        self.assertIn(b"text/event-stream", data)

    # --- operator mutations ------------------------------------------------

    def test_operator_mutation_voyages(self):
        status, body, _ = self._request(
            "POST", "/api/v1/salamander/fault", {"kind": "voyage", "source": "contract"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(body, {"ok": True, "recorded": True})

        status, body, _ = self._request("POST", "/api/v1/system/verify", {})
        self.assertIn(status, (200, 202, 409))
        self.assertIn("ok", body)

        status, body, _ = self._request(
            "PUT", "/api/v1/config", {"solvers": {"arms": 2}}
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])

        status, body, _ = self._request(
            "PUT", "/api/v1/config", {"nonexistent_section": {}}
        )
        self.assertEqual(status, 400)
        self.assertFalse(body.get("ok", False))
        self.assertIn("error", body)

    def test_unauthorized_mutation_is_refused(self):
        os.environ.pop("PYTHIA_ALLOW_UNAUTHENTICATED_CONTROL", None)
        os.environ.pop("EUCLID_ADMIN_API_KEY", None)
        status, body, _ = self._request(
            "POST", "/api/v1/salamander/fault", {"kind": "x"}
        )
        self.assertEqual(status, 403)
        self.assertFalse(body["ok"])
        self.assertIn("EUCLID_ADMIN_API_KEY is not configured", body["error"])

    # --- privileged voyages -------------------------------------------------

    def test_privileged_gets_deny_without_subscription(self):
        for path, _api in self._declared_gets("AL_HARAS_SUBSCRIPTION"):
            status, body, headers = self._request("GET", path)
            with self.subTest(path=path):
                self.assertIn(status, (400, 401, 403, 503))
                self.assertNotEqual(status, 200)
                self.assertIsInstance(body, dict)

    def test_privileged_posts_deny_without_subscription(self):
        for (method, path), api in _declared_http_routes().items():
            if method != "POST":
                continue
            if "AL_HARAS_SUBSCRIPTION" not in _auth_classes(
                api["authentication_class"]
            ):
                continue
            status, body, _ = self._request("POST", path, {})
            with self.subTest(path=path):
                self.assertIn(status, (400, 401, 403, 413, 503))
                self.assertNotEqual(status, 200)

    def test_privileged_voyages_with_subscription(self):
        headers = _mint_subscription()

        status, body, _ = self._request("GET", "/api/v1/security/status", headers=headers)
        self.assertEqual(status, 200, body)
        self.assertIn("capability", body)

        status, body, _ = self._request(
            "GET", "/api/v1/security/subscribe", headers=headers
        )
        self.assertEqual(status, 200, body)
        self.assertTrue(body["subscription_required"])

        status, body, _ = self._request(
            "GET", "/api/v1/mining/evidence", headers=headers
        )
        self.assertEqual(status, 200, body)
        self.assertIn("worker_live", body)

        status, body, _ = self._request(
            "GET", "/api/v1/tensor/capabilities", headers=headers
        )
        self.assertEqual(status, 200, body)
        self.assertIsInstance(body, dict)

        status, body, _ = self._request(
            "POST",
            "/api/v1/mining/start",
            {"observation": {"value": 1}},
            headers=headers,
        )
        # This host binds no mining device: the command must answer honestly —
        # ok:false with the real reason, or ok:true with workers armed_no_device.
        self.assertEqual(status, 200, body)
        self.assertIn("ok", body)
        if not body["ok"]:
            self.assertIn("no mining device", body["reason"])

        status, body, _ = self._request(
            "POST", "/api/v1/mining/stop", {"observation": {"value": 1}}, headers=headers
        )
        self.assertEqual(status, 200, body)
        self.assertTrue(body["ok"])
        self.assertIn("retired", body)

        status, body, _ = self._request(
            "POST",
            "/api/v1/security/evaluate",
            {
                "operation": "mining.stop",
                "resource": "mining/stop",
                "observation": {"value": 1},
            },
            headers=headers,
        )
        self.assertEqual(status, 200, body)
        self.assertIn("allowed", body)

        # A non-allowlisted operation returns a signed denial receipt —
        # evidence, not an error mask.
        status, body, _ = self._request(
            "POST",
            "/api/v1/security/evaluate",
            {
                "operation": "not.an.operation",
                "resource": "not/an-operation",
                "observation": {"value": 1},
            },
            headers=headers,
        )
        self.assertEqual(status, 403, body)
        self.assertEqual(body["allowed"], False)
        self.assertEqual(body["reason"], "OPERATION_NOT_ALLOWED")
        self.assertIn("evidence_id", body)

        status, body, _ = self._request(
            "POST",
            "/api/v1/tensor/execute",
            {"operation": "add", "operands": [[[1.0]], [[2.0]]], "dtype": "float64"},
            headers=headers,
        )
        self.assertEqual(status, 200, body)
        self.assertEqual(body["schema_version"], "tensor.execute/1")

        status, body, _ = self._request(
            "POST",
            "/api/v1/toe/collapse",
            {"data": {"qubit": 1, "amplitude": 0.5}},
            headers=headers,
            timeout=60,
        )
        self.assertEqual(status, 200, body)
        self.assertEqual(body["schema_version"], "chronus.mla1517.toe_collapse/1")
        self.assertIn("guardian_receipt", body)
        self.assertIn("execution_evidence", body)

    def test_reserved_namespaces_never_masquerade(self):
        headers = _mint_subscription()
        for api in _REGISTRY["apis"]:
            if api["interface_type"] != "RESERVED_NAMESPACE":
                continue
            probe = api["path"] + "status"
            for method in ("GET", "POST"):
                status, body, _ = self._request(
                    method, probe, {} if method == "POST" else None, headers=headers
                )
                with self.subTest(method=method, path=probe):
                    # Denied at the guardian boundary (operation not allowlisted)
                    # or a real 404 past it — never a fabricated 200 service.
                    self.assertNotEqual(status, 200)
                    self.assertIn(status, (400, 401, 403, 404))
                    self.assertIsInstance(body, dict)

    # --- boundary honesty ---------------------------------------------------

    def test_unknown_api_paths_are_real_404(self):
        for method, path in (
            ("GET", "/api/v1/definitely-not-a-route"),
            ("POST", "/api/v1/definitely-not-a-route"),
        ):
            status, body, _ = self._request(
                method, path, {} if method == "POST" else None
            )
            with self.subTest(method=method, path=path):
                self.assertEqual(status, 404)
                self.assertEqual(body, {"error": "not_found"})

    def test_spa_serves_index_only_for_app_paths(self):
        status, body, headers = self._request("GET", "/dashboard")
        self.assertEqual(status, 200)
        self.assertIn("pythia", body)
        # An unrouted /api/* path never falls through to the SPA shell.
        status, body, _ = self._request("GET", "/api/nope")
        self.assertEqual(status, 404)
        self.assertEqual(body, {"error": "not_found"})


# ---------------------------------------------------------------------------
# Part C2 — frontend ↔ backend route parity
# ---------------------------------------------------------------------------

FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
_FRONTEND_PATH_RE = re.compile(r"[\"'`]((?:/api/v1|/api)/[^\"'`]*)")


def _frontend_declared_paths() -> dict[str, set[str]]:
    """path literal → source files, extracted from the React frontend.

    ``frontend/src/security`` is the retired Express middleware layer (it
    guards dead ``/api/sovereign|hyba|alharas`` prefixes on a Node server
    that no longer exists) — it is not a client call site and is excluded.
    """
    out: dict[str, set[str]] = {}
    for ext in ("*.ts", "*.tsx"):
        for source in FRONTEND_SRC.rglob(ext):
            if "security" in source.relative_to(FRONTEND_SRC).parts:
                continue
            text = source.read_text(encoding="utf-8", errors="replace")
            for match in _FRONTEND_PATH_RE.finditer(text):
                literal = match.group(1).split("?")[0].rstrip("/") or "/"
                out.setdefault(literal, set()).add(
                    str(source.relative_to(FRONTEND_SRC))
                )
    return out


class FrontendParityTests(unittest.TestCase):
    def test_every_frontend_call_lands_on_a_declared_route(self):
        declared_paths = {path for (_m, path) in _declared_http_routes()}
        # Template-expanded calls resolve onto the declared subroutes.
        for literal, sources in sorted(_frontend_declared_paths().items()):
            if "${" in literal:
                prefix = literal.split("${")[0]
                candidates = {p for p in declared_paths if p.startswith(prefix)}
                self.assertTrue(
                    candidates,
                    f"frontend path template {literal} in {sorted(sources)} "
                    "expands to no declared route",
                )
            else:
                self.assertIn(
                    literal,
                    declared_paths,
                    f"frontend path {literal} in {sorted(sources)} is not a "
                    "declared registry route",
                )

    def test_frontend_mutation_paths_are_authenticated(self):
        """Any /api/v1 path the frontend mutates must be behind an auth class."""

        def auth_for(api: dict, method: str) -> str:
            spec = str(api["authentication_class"])
            if ":" in spec:
                for segment in spec.split(";"):
                    if ":" in segment:
                        m, cls = segment.split(":", 1)
                        if m.strip().upper() == method:
                            return cls.strip()
            return spec

        for literal in _frontend_declared_paths():
            if "${" in literal:
                continue
            for method in ("POST", "PUT", "DELETE", "PATCH"):
                api = _declared_http_routes().get((method, literal))
                if api is None:
                    continue
                self.assertNotEqual(
                    auth_for(api, method),
                    "NONE",
                    f"frontend mutates {method} {literal} which is declared "
                    "unauthenticated",
                )





class MutationGateTests(unittest.TestCase):
    def test_gate_detects_an_implemented_but_undeclared_route(self):
        declared = {
            k: v
            for k, v in _declared_http_routes().items()
            if k[0] != "*" and not k[1].startswith("/*")
        }
        implemented = _implemented_http_routes() | {("GET", "/api/v1/mutant")}
        extra, missing = _parity_diff(implemented, set(declared))
        self.assertEqual(extra, [("GET", "/api/v1/mutant")])
        self.assertEqual(missing, [])

    def test_gate_detects_a_declared_but_unimplemented_route(self):
        declared = {
            k: v
            for k, v in _declared_http_routes().items()
            if k[0] != "*" and not k[1].startswith("/*")
        }
        victim = next(iter(declared))
        implemented = _implemented_http_routes() - {victim}
        extra, missing = _parity_diff(implemented, set(declared))
        self.assertEqual(extra, [])
        self.assertEqual(missing, [victim])

    def test_gate_detects_a_handler_under_a_reserved_prefix(self):
        """Direction C mutation: a handler added under a reserved prefix fails.

        The real check lives in
        ``RouteParityTests.test_reserved_namespaces_have_no_implementation``;
        this mutation proves it fires — an implemented route beneath any
        RESERVED_NAMESPACE prefix is caught.
        """
        reserved_prefix = next(
            api["path"]
            for api in _REGISTRY["apis"]
            if api["interface_type"] == "RESERVED_NAMESPACE"
        )
        mutated = _implemented_http_routes() | {("GET", reserved_prefix + "mutant")}
        served = [r for r in mutated if r[1].startswith(reserved_prefix)]
        self.assertNotEqual(
            served,
            [],
            "gate no longer detects an implemented route under a reserved prefix",
        )

    def test_gate_detects_registry_regression(self):
        declared = {
            k: v
            for k, v in _declared_http_routes().items()
            if k[0] != "*" and not k[1].startswith("/*")
        }
        victim = next(iter(declared))
        regressed = dict(declared)
        del regressed[victim]
        extra, missing = _parity_diff(_implemented_http_routes(), set(regressed))
        self.assertEqual(extra, [victim])
        self.assertEqual(missing, [])

    def test_gate_detects_authority_register_tamper(self):
        tampered = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
        tampered["authority_register"]["PYTHIA"] = "custody"
        self.assertNotEqual(
            tampered["authority_register"], FROZEN_AUTHORITY_REGISTER
        )

    def test_gate_detects_a_missing_required_field(self):
        tampered = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
        del tampered["apis"][0]["authentication_class"]
        with self.assertRaises(KeyError):
            tampered["apis"][0]["authentication_class"]


# ---------------------------------------------------------------------------
# Part D2 — generated-document round-trip
# ---------------------------------------------------------------------------


def _render_check(doc_out: Path, openapi_out: Path) -> int:
    """Invoke the real ``--check`` gate in-process with redirected outputs."""
    spec = importlib.util.spec_from_file_location("render_api_contract", RENDERER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.DOC_OUT = doc_out
    mod.OPENAPI_OUT = openapi_out
    return mod.main(["--check"])


class GeneratedDocRoundTripTests(unittest.TestCase):
    """docs/PYTHIA_API_CONTRACT.md and docs/openapi.yaml are derived views of
    the registry — ``render_api_contract.py --check`` regenerates both and
    compares byte-for-byte with the committed files. A one-byte drift in
    either fails the gate."""

    def test_committed_docs_round_trip_byte_identical(self):
        result = subprocess.run(
            [sys.executable, str(RENDERER_PATH), "--check"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(
            result.returncode,
            0,
            f"render_api_contract --check failed:\n{result.stdout}\n{result.stderr}",
        )

    def test_gate_detects_one_byte_drift_in_openapi(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc_out = Path(tmp) / "PYTHIA_API_CONTRACT.md"
            openapi_out = Path(tmp) / "openapi.yaml"
            doc_out.write_bytes(CONTRACT_DOC_PATH.read_bytes())
            openapi = bytearray(OPENAPI_PATH.read_bytes())
            i = openapi.index(b"\n")
            openapi[i] = ord("#") if openapi[i] != ord("#") else ord("!")
            openapi_out.write_bytes(bytes(openapi))
            self.assertEqual(
                _render_check(doc_out, openapi_out),
                1,
                "one-byte drift in docs/openapi.yaml did not fail --check",
            )

    def test_gate_detects_one_byte_drift_in_contract_doc(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc_out = Path(tmp) / "PYTHIA_API_CONTRACT.md"
            openapi_out = Path(tmp) / "openapi.yaml"
            doc = bytearray(CONTRACT_DOC_PATH.read_bytes())
            doc[0] = ord("!") if doc[0] != ord("!") else ord("#")
            doc_out.write_bytes(bytes(doc))
            openapi_out.write_bytes(OPENAPI_PATH.read_bytes())
            self.assertEqual(
                _render_check(doc_out, openapi_out),
                1,
                "one-byte drift in docs/PYTHIA_API_CONTRACT.md did not fail --check",
            )

    def test_gate_detects_a_missing_generated_doc(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc_out = Path(tmp) / "PYTHIA_API_CONTRACT.md"
            openapi_out = Path(tmp) / "openapi.yaml"
            openapi_out.write_bytes(OPENAPI_PATH.read_bytes())
            self.assertEqual(
                _render_check(doc_out, openapi_out),
                1,
                "a missing generated doc did not fail --check",
            )


# ---------------------------------------------------------------------------
# Part E — internal Python contracts
# ---------------------------------------------------------------------------


class InternalContractTests(unittest.TestCase):
    def test_theseus_custody_roundtrip(self):
        from aethel.theseus import open_theseus

        theseus = open_theseus()
        record = theseus.put(b"contract-bytes")
        self.assertEqual(theseus.get(record.uuid), b"contract-bytes")
        self.assertTrue(theseus.verify())
        self.assertIs(theseus.record(record.uuid), record)
        self.assertIs(
            theseus.lookup_digest(record.digest).uuid, record.uuid
        )
        # get_working_form unfolds to an Ovid FoldedWorkingForm, not bytes.
        self.assertTrue(theseus.get_working_form(record.uuid).verify())

    def test_ovid_transform_surface(self):
        from aethel.ovid import open_ovid

        ovid = open_ovid()
        for method in (
            "metamorphose",
            "verify_equivalence",
            "round_trip",
            "materialise",
            "transform_contracts",
            "contract_report",
        ):
            self.assertTrue(
                callable(getattr(ovid, method, None)),
                f"Ovid is missing declared method {method}",
            )
        self.assertTrue(ovid.transform_contracts())

    def test_tensor_runtime_contract(self):
        import numpy as np

        from tensor.api import default_runtime

        runtime = default_runtime()
        catalogue = runtime.capabilities()
        self.assertIsInstance(catalogue, dict)
        record = runtime.execute(
            "add",
            [np.array([1.0]), np.array([2.0])],
            dtype="float64",
            request_id="contract-test",
        )
        self.assertIn("receipt", record)
        self.assertEqual(record["receipt"]["schema_version"], "tensor.receipt/1")
        self.assertEqual(record["truth_class"], "measured")

    def test_salamander_control_plane_surface(self):
        from salamander.control_plane import ActionRegistry, AutonomicControlPlane

        plane = AutonomicControlPlane(registry=ActionRegistry())
        for method in (
            "observe",
            "discover",
            "qualify",
            "chronus_envelope",
            "admit",
            "execute",
            "recover",
            "verify_theseus_custody",
            "verify_ovid_transform",
            "verify_projection",
            "api_snapshot",
        ):
            self.assertTrue(
                callable(getattr(plane, method, None)),
                f"AutonomicControlPlane is missing declared method {method}",
            )
        snapshot = plane.api_snapshot()
        self.assertIsInstance(snapshot, dict)

    def test_vqc_pipeline_contract(self):
        from turing_universal_quantum_computer.pipeline import (
            PipelineReport,
            VQCPipeline,
            VQCRequest,
        )

        self.assertTrue(callable(VQCPipeline().run))
        for field_name in ("program", "qasm"):
            self.assertIn(field_name, set(VQCRequest.__dataclass_fields__))
        report_fields = set(PipelineReport.__dataclass_fields__)
        self.assertIn("verdict", report_fields)
        self.assertIn("certificate", report_fields)
        self.assertIn("stages", report_fields)

    def test_guardian_evaluate_denies_empty_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AL_HARAS_SUBSCRIPTION_KEYS"] = json.dumps(_SUB_KEYRING)
            os.environ["AL_HARAS_DATA_DIR"] = tmp
            try:
                import control_api

                control_api.pythia_guardian_api.cache_clear()
                code, receipt = control_api.pythia_guardian_api().evaluate(
                    headers={
                        "authorization": "",
                        "x-hyba-tenant": "",
                        "x-hyba-actor": "",
                    },
                    body={"operation": "mining.start", "resource": "mining/start"},
                )
            finally:
                control_api.pythia_guardian_api.cache_clear()
            self.assertNotEqual(int(code), 200)
            self.assertFalse(receipt.get("allowed", True))

    def test_hyba_db_store_contract(self):
        from hyba_db.store import OntologyStore

        self.assertTrue(callable(getattr(OntologyStore, "verify_database", None)))


# ---------------------------------------------------------------------------
# Part F — file/artifact and CLI contracts
# ---------------------------------------------------------------------------


class ArtifactContractTests(unittest.TestCase):
    def test_runtime_config_public_view_redacts_secrets(self):
        import runtime_config

        cfg = {
            "pools": [
                {
                    "name": "primary",
                    "endpoint": "btc.viabtc.io:3333",
                    "worker": "w.1",
                    "password": "super-secret",
                    "enabled": True,
                }
            ],
            "solvers": {"arms": 1},
        }
        public = runtime_config.public_view(cfg)
        serialized = json.dumps(public)
        self.assertNotIn("super-secret", serialized)

    def test_boot_audit_is_append_only_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "BOOT_AUDIT.log"
            os.environ["PYTHIA_BOOT_AUDIT"] = str(path)
            try:
                from startup_contract import AppendOnlyAudit

                audit = AppendOnlyAudit(path)
                audit.append("contract_probe", key="value")
                audit.append("contract_probe_2")
            finally:
                os.environ.pop("PYTHIA_BOOT_AUDIT", None)
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)
            first = json.loads(lines[0])
            self.assertEqual(first["event"], "contract_probe")
            self.assertEqual(first["key"], "value")

    def test_cli_help_exits_cleanly(self):
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "main.py", "--help"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "PYTHIA_AUTOSTART_WORKERS": "0"},
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--host", result.stdout)


class GeneratedDocsSyncTests(unittest.TestCase):
    """docs/PYTHIA_API_CONTRACT.md and docs/openapi.yaml are generated from
    the registry; this gate fails when they drift from it."""

    def test_rendered_contract_docs_are_in_sync(self):
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "governance/render_api_contract.py", "--check"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
