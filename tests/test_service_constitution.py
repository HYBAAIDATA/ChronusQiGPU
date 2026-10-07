"""Service-constitution and API-governance drift gates (Phase 2B).

The constitution layer binds every registered API to the fifteen-field
managed-product record (capability, authority, interface, consumer,
schema, dependency, criticality, slo, failure_mode, retry_idempotency,
evidence_owner, observability, lifecycle_owner, version,
deprecation_policy), rendered by ``governance/render_service_constitution.py``
into ``docs/SERVICE_CONSTITUTION.yaml`` and ``docs/DEPENDENCY_GRAPH.yaml``.

This suite is the machine-enforced half of API governance.  Coverage map
against the master workflow's drift list:

* unregistered routes / declared-but-unimplemented routes — covered by
  tests/test_production_api_contract.py (AST parity + implemented-surface
  gates); this suite adds the constitution coverage gate;
* wrong authority — every entry's owner is in the frozen authority
  register, and cross-owner api_ids are limited to a frozen exception set;
* wrong dependency — the executable dependency graph is validated
  (endpoints exist, acyclic, tier rules, custody/mediation edges);
* unversioned breaking changes — every canonical entry carries
  schema_version; aliases keep their canonical_successor;
* privileged routes without AL HARAS — the contract suite gates prefix
  membership; this suite gates the dependency edge;
* durable results without THESEUS — custody_requirement text that mentions
  THESEUS requires a theseus.custody edge;
* frontend calls with no backend contract — contract suite;
* silent fallbacks — the payload builders are scanned for except-paths
  that fabricate success fields;
* responses claiming another service's truth — truth_class is declared
  and owners are validated against the frozen register;
* standard error taxonomy — every emitted error/denial code must be
  registered in docs/ERROR_TAXONOMY.yaml and vice versa;
* correlation — X-Request-Id is emitted on every response including
  denials (live voyage covered by the contract suite); the constitution
  additionally requires the observability field to name the correlation
  mechanism for HTTP entries.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "governance"))

import dependency_graph  # noqa: E402
import render_service_constitution as rsc  # noqa: E402

REGISTRY = REPO_ROOT / "governance" / "api_registry.yaml"
OVERLAY = REPO_ROOT / "governance" / "service_constitution.yaml"
CONSTITUTION_DOC = REPO_ROOT / "docs" / "SERVICE_CONSTITUTION.yaml"
GRAPH_DOC = REPO_ROOT / "docs" / "DEPENDENCY_GRAPH.yaml"
TAXONOMY_DOC = REPO_ROOT / "docs" / "ERROR_TAXONOMY.yaml"
CONTROL_API = REPO_ROOT / "chronus" / "mla1517_platform" / "python" / "control_api.py"
AL_HARAS_DIR = REPO_ROOT / "al_haras"
FABRIC_PATH = REPO_ROOT / "governance" / "service_fabric.yaml"

_FIFTEEN_FIELDS = {
    "capability",
    "authority",
    "interface",
    "consumer",
    "schema",
    "dependency",
    "criticality",
    "slo",
    "failure_mode",
    "retry_idempotency",
    "evidence_owner",
    "observability",
    "lifecycle_owner",
    "version",
    "deprecation_policy",
}

# api_id prefix -> owner is deliberately not 1:1: the PYTHIA transport
# fronts truth owned by other subsystems.  The exceptions are frozen here;
# a NEW cross-owner api_id without registry+constitution review fails.
_CROSS_OWNER_EXCEPTIONS = {
    "pythia.intelligence.status": "EUCLID",
    "pythia.intelligence.selftest": "EUCLID",
    "pythia.intelligence.maintenance": "EUCLID",
    "pythia.intelligence.autonomous": "EUCLID",
    "pythia.intelligence.engineer": "EUCLID",
    "pythia.intelligence.cognition_solve": "EUCLID",
    "pythia.agentic": "EUCLID",
    "pythia.campaign": "EUCLID",
    "pythia.knowledge": "EUCLID",
    "pythia.gpu": "CHRONUS",
    "pythia.hardware.status": "CHRONUS",
    "namespace.quantum": "TURING",
}

_PREFIX_TO_OWNER = {
    "pythia": "PYTHIA",
    "al_haras": "AL_HARAS",
    "kellogg": "KELLOGG",
    "toe": "EUCLID",
    "salamander": "SALAMANDER",
    "namespace": "AL_HARAS",
    "turing": "TURING",
    "theseus": "THESEUS",
    "ovid": "OVID",
    "chronus": "CHRONUS",
    "euclid": "EUCLID",
    "hyba_db": "HYBA_DB",
    "stratum": "POOL",
    "legacy": "PYTHIA",
}

_TIER_OWNER_RULES = {
    # owner -> required tier (the frozen tier table binds services)
    "AL_HARAS": "R0",
    "THESEUS": "R0",
    "SALAMANDER": "R3",
    "POOL": "R1",
}

_SNAKE = re.compile(r"^[a-z0-9_]+$")


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _registry() -> dict:
    return _load(REGISTRY)


def _overlay() -> dict:
    return _load(OVERLAY)


def _apis(reg: dict) -> dict[str, dict]:
    return {e["api_id"]: e for e in reg.get("apis") or []}


def _constitution_records(doc: dict) -> dict[str, dict]:
    return {c["api_id"]: c for c in doc.get("constitutions") or []}


class TestConstitutionMerge(unittest.TestCase):
    """Overlay + registry merge is complete and well-formed."""

    def test_overlay_schema_is_frozen(self):
        overlay = _overlay()
        self.assertEqual(overlay["schema"], "pythia.service_constitution_overlay/1")

    def test_every_registry_api_has_a_governance_record(self):
        reg_apis = set(_apis(_registry()))
        gov_apis = set((_overlay().get("apis") or {}).keys())
        self.assertEqual(reg_apis - gov_apis, set())
        self.assertEqual(gov_apis - reg_apis, set())

    def test_every_governance_record_has_capability_criticality_dependencies(self):
        gov = _overlay().get("apis") or {}
        for api_id, entry in gov.items():
            with self.subTest(api_id=api_id):
                self.assertTrue(str(entry.get("capability") or "").strip())
                self.assertIn(entry.get("criticality"), ("R0", "R1", "R2", "R3", "R4"))
                self.assertIn("dependencies", entry)

    def test_rendered_constitution_carries_all_fifteen_fields(self):
        doc = _load(CONSTITUTION_DOC)
        self.assertEqual(doc["schema"], "pythia.service_constitution/1")
        records = _constitution_records(doc)
        self.assertEqual(set(records), set(_apis(_registry())))
        for api_id, rec in records.items():
            with self.subTest(api_id=api_id):
                self.assertEqual(set(rec), _FIFTEEN_FIELDS | {"api_id", "slo_state"})
                for field in _FIFTEEN_FIELDS - {"dependency", "consumer"}:
                    self.assertNotIn(rec.get(field), (None, "", [], {}))

    def test_lifecycle_owner_is_named(self):
        doc = _load(CONSTITUTION_DOC)
        for api_id, rec in _constitution_records(doc).items():
            with self.subTest(api_id=api_id):
                owner = rec["lifecycle_owner"]
                self.assertTrue(owner.get("accountable"))
                self.assertTrue(owner.get("authority"))

    def test_tier_rules_bind_services(self):
        doc = _load(CONSTITUTION_DOC)
        for api_id, rec in _constitution_records(doc).items():
            required = _TIER_OWNER_RULES.get(rec["authority"])
            if required:
                with self.subTest(api_id=api_id):
                    self.assertEqual(rec["criticality"], required)

    def test_authority_is_registered(self):
        reg = _registry()
        register = set(reg.get("authority_register") or {})
        for api_id, entry in _apis(reg).items():
            with self.subTest(api_id=api_id):
                self.assertIn(entry.get("owner"), register)

    def test_cross_owner_apis_are_frozen(self):
        reg = _registry()
        for api_id, entry in _apis(reg).items():
            prefix = api_id.split(".")[0]
            expected = _PREFIX_TO_OWNER[prefix]
            owner = entry.get("owner")
            with self.subTest(api_id=api_id):
                if owner == expected:
                    self.assertNotIn(api_id, _CROSS_OWNER_EXCEPTIONS)
                else:
                    self.assertEqual(
                        _CROSS_OWNER_EXCEPTIONS.get(api_id),
                        owner,
                        f"{api_id} claims {owner} truth outside the frozen " "cross-owner set",
                    )

    def test_consumer_inventory_is_nonempty(self):
        for api_id, entry in _apis(_registry()).items():
            with self.subTest(api_id=api_id):
                self.assertTrue(entry.get("consumers"))

    def test_version_guard(self):
        for api_id, entry in _apis(_registry()).items():
            with self.subTest(api_id=api_id):
                if entry.get("interface_type") == "LEGACY":
                    self.assertTrue(entry.get("canonical_successor"))
                elif entry.get("interface_type") == "RESERVED_NAMESPACE":
                    # reserved prefixes claim a wildcard route and stay
                    # explicitly unversioned — the boundary owns every method
                    self.assertEqual(entry.get("method"), "*")
                    self.assertTrue(
                        all(str(r).startswith("* ") for r in entry.get("routes") or []),
                        f"{api_id} declares a non-wildcard route under a " "reserved namespace",
                    )
                    self.assertEqual(entry.get("schema_version"), "none")
                else:
                    self.assertTrue(entry.get("schema_version"))
                    self.assertIn(
                        entry.get("deprecation_state"),
                        ("CANONICAL", "DEPRECATED", "COMPATIBILITY_ALIAS"),
                    )


class TestRenderedDocsSync(unittest.TestCase):
    """The rendered artifacts cannot drift from registry + overlay."""

    def test_constitution_doc_is_in_sync(self):
        reg, overlay = _registry(), _overlay()
        self.assertEqual(
            CONSTITUTION_DOC.read_text(encoding="utf-8"),
            rsc.render_constitution(reg, overlay),
        )

    def test_dependency_graph_doc_is_in_sync(self):
        reg, overlay = _registry(), _overlay()
        self.assertEqual(
            GRAPH_DOC.read_text(encoding="utf-8"),
            rsc.render_dependency_graph(reg, overlay),
        )


class TestDependencyGraph(unittest.TestCase):
    """The executable graph enforces its declared invariants."""

    def test_graph_validates_clean(self):
        graph, registry = dependency_graph.load()
        self.assertEqual(dependency_graph.validate(graph, registry), [])

    def test_graph_is_acyclic(self):
        graph, _ = dependency_graph.load()
        self.assertIsNone(dependency_graph._find_cycle(dependency_graph.api_edges(graph)))

    def test_graph_detects_a_phantom_edge(self):
        graph, registry = dependency_graph.load()
        fake = {
            "schema": graph["schema"],
            "external_authorities": graph.get("external_authorities"),
            "nodes": graph.get("nodes"),
            "edges": list(graph.get("edges") or [])
            + [{"from": "pythia.health", "to": "no.such.api", "kind": "api"}],
        }
        violations = dependency_graph.validate(fake, registry)
        self.assertTrue(any("no.such.api" in v for v in violations))

    def test_graph_detects_a_dropped_custody_edge(self):
        graph, registry = dependency_graph.load()
        edges = [
            e
            for e in graph.get("edges") or []
            if not (e["from"] == "hyba_db.store" and e["to"] == "theseus.custody")
        ]
        fake = dict(graph, edges=edges)
        violations = dependency_graph.validate(fake, registry)
        self.assertTrue(any("hyba_db.store" in v for v in violations))

    def test_graph_detects_a_tier_violation(self):
        graph, registry = dependency_graph.load()
        fake = dict(
            graph,
            edges=list(graph.get("edges") or [])
            + [{"from": "theseus.custody", "to": "pythia.health", "kind": "api"}],
        )
        violations = dependency_graph.validate(fake, registry)
        self.assertTrue(any("R0" in v for v in violations))

    def test_reserved_namespaces_only_depend_on_the_boundary(self):
        graph, _ = dependency_graph.load()
        for edge in graph.get("edges") or []:
            if edge["from"].startswith("namespace."):
                self.assertEqual(edge["to"], "al_haras.guardian")


class TestErrorTaxonomy(unittest.TestCase):
    """Every emitted code is registered; every registered code is emitted."""

    def _taxonomy(self) -> dict:
        return _load(TAXONOMY_DOC)

    def _emitted_operational(self) -> set[str]:
        src = CONTROL_API.read_text(encoding="utf-8")
        codes = set(re.findall(r'"error":\s*"([a-z0-9_]+)"', src))
        codes |= {m for m in re.findall(r'"reason":\s*"([^"]+)"', src) if _SNAKE.match(m)}
        return codes

    def _emitted_dynamic(self) -> list[str]:
        src = CONTROL_API.read_text(encoding="utf-8")
        out = list(re.findall(r'"error":\s*(f"[^"]+")', src))
        out += re.findall(r'"reason":\s*(f"[^"]+")', src)
        return out

    def _emitted_denials(self) -> set[str]:
        codes: set[str] = set()
        for path in AL_HARAS_DIR.glob("*.py"):
            src = path.read_text(encoding="utf-8")
            for m in re.findall(r'reason\s*=\s*f?"([A-Z][^"]*)"', src):
                codes.add(m.split(":")[0])
            for m in re.findall(r'"reason":\s*"([A-Z][^"]*)"', src):
                codes.add(m.split(":")[0])
            for m in re.findall(r'intelligence_error\s*=\s*f?"([^"]+)"', src):
                codes.add(m.split(":")[0])
        return codes

    def test_emitted_operational_codes_are_registered(self):
        tax = self._taxonomy()
        registered = {c["code"] for c in tax["codes"] if c["class"] == "OPERATIONAL_ERROR"}
        emitted = self._emitted_operational()
        self.assertEqual(emitted - registered, set())

    def test_emitted_denial_codes_are_registered(self):
        tax = self._taxonomy()
        registered = {c["code"] for c in tax["codes"] if c["class"] == "BOUNDARY_DENIAL"}
        registered |= set(tax.get("non_error_codes") or [])
        wildcard = {c["code"].rstrip("*").rstrip(":") for c in tax["codes"] if "*" in c["code"]}
        emitted = self._emitted_denials()
        unregistered = {
            c for c in emitted if c not in registered and not any(c.startswith(w) for w in wildcard)
        }
        self.assertEqual(unregistered, set())

    def test_emitted_dynamic_details_are_registered(self):
        tax = self._taxonomy()
        templates = [
            c.get("emitted_as", "")
            for c in tax["codes"]
            if c["class"] in {"DYNAMIC_DETAIL", "AVAILABILITY_PROSE"}
        ]

        def segments(template: str) -> list[str]:
            return re.split(r"\{[^}]*\}", template)

        for emitted in self._emitted_dynamic():
            body = emitted[2:-1]  # strip f" and closing "
            with self.subTest(emitted=body):
                self.assertTrue(
                    any(segments(body) == segments(t) for t in templates),
                    f"unregistered dynamic detail template: {body}",
                )

    def test_registered_codes_are_still_emitted(self):
        tax = self._taxonomy()
        emitted = (
            self._emitted_operational() | self._emitted_denials() | set(self._emitted_dynamic())
        )
        al_sources = ""
        for path in AL_HARAS_DIR.glob("*.py"):
            al_sources += path.read_text(encoding="utf-8")
        control_src = CONTROL_API.read_text(encoding="utf-8")
        for entry in tax["codes"]:
            code = entry["code"].rstrip("*")
            emitted_as = entry.get("emitted_as", "")
            with self.subTest(code=entry["code"]):
                if emitted_as:
                    probe = emitted_as.split("{")[0].strip().strip('"')
                    self.assertTrue(
                        probe in control_src or probe in al_sources,
                        f"registered template {emitted_as!r} not emitted",
                    )
                else:
                    self.assertTrue(
                        code in emitted or code in control_src or code in al_sources,
                        f"registered code {entry['code']!r} not emitted anywhere",
                    )


class TestSilentFallbacks(unittest.TestCase):
    """No except-path may fabricate a success field in the payload builders."""

    def test_no_except_path_fabricates_success(self):
        src = CONTROL_API.read_text(encoding="utf-8")
        blocks = re.findall(r"except[^\n]*\n((?:\s{8,}.*\n){0,12})", src)
        for block in blocks:
            self.assertIsNone(
                re.search(
                    r'"(ok|ready|available|healthy|accepted)":\s*True'
                    r'|"status":\s*"(ok|healthy|accepted|CONNECTED)"',
                    block,
                ),
                f"except-path fabricates a success claim:\n{block}",
            )

    def test_correlation_mechanism_is_declared_for_http(self):
        doc = _load(CONSTITUTION_DOC)
        for api_id, rec in _constitution_records(doc).items():
            if str(rec["interface"]).startswith("HTTP"):
                with self.subTest(api_id=api_id):
                    self.assertIn("X-Request-Id", rec["observability"])


# ---------------------------------------------------------------------------
# Live HTTP surface — the constitution is exercised over the wire, not just
# declared.  Same harness as tests/test_production_api_contract.py.
# ---------------------------------------------------------------------------

_SUB_KEYRING = {"test": "k" * 32}


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
        classes = set(_load(FABRIC_PATH)["failure_classes"])
        voyages = [
            ("GET", "/api/v1/no-such-route", None, None),  # 404
            ("POST", "/api/v1/mining/stop", {}, None),  # guardian deny (no creds)
            ("POST", "/api/v1/security/evaluate", {"x": 1}, None),  # guardian verdict w/o creds
            ("PUT", "/api/v1/config", {"bogus": {}}, None),  # invalid request
            ("DELETE", "/api/v1/healthz", None, None),  # 405
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


if __name__ == "__main__":
    unittest.main()
