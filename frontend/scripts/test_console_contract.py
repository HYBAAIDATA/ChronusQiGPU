"""Isolated current-source producer/auth contract tests; no device qualification.

Extract real functions via AST, inject deterministic owner fixtures only at
owner boundaries. This does NOT import/boot the complete control service.
"""
import ast
import hashlib
import hmac
import json
import os
import re
import sys
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from console_schema import ConsoleStatus

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "chronus/mla1517_platform/python/control_api.py"
FUNCTIONS = {"_operator_principals", "authenticate_control_principal", "console_read_authorization", "console_sources_payload", "status_payload"}

def module():
    tree = ast.parse(SOURCE.read_text())
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in FUNCTIONS | {"ControlPrincipal"}]
    names = {"ADMIN_KEY_ENV", "UNAUTHENTICATED_ENV", "OPERATOR_PRINCIPALS_ENV", "OPERATOR_PRINCIPAL_HEADER", "_CONTROL_ROLES", "_PRINCIPAL_ID_RE", "_CEO_READ_PATHS", "_PRIVILEGED_PREFIXES"}
    nodes += [n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets)]
    scope = {"__name__": "isolated_control_contract", "Any": object, "dataclass": dataclass, "os": os, "re": re, "json": json, "hashlib": hashlib, "hmac": hmac, "HTTPStatus": HTTPStatus, "_is_truthy": lambda v: str(v).lower() in ("true", "1")}
    # dataclasses resolves annotations through sys.modules.
    import types
    mod = types.ModuleType(scope["__name__"]); mod.__dict__.update(scope);sys.modules[mod.__name__] = mod
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), mod.__dict__)
    return mod.__dict__

def sources(scope, fail=False):
    factory = lambda: {"schema": "fixture-owner/1"}
    def failure(): raise RuntimeError("fixture source failed")
    scope.update({"_fabric_map_payload": failure if fail else factory, "telemetry_summary_payload": factory, "audit_tail_payload": lambda n: {"records": []}, "system_fabric": SimpleNamespace(**{k: factory for k in ("verification_status", "selftest_status", "agentic_status", "campaign_status", "intelligence_status", "euclid_cognition_status")})})

def fixture(scope):
    # Actual status_payload executes with bounded, test-only owner dependencies.
    control = SimpleNamespace(records=lambda: [], mining_device_bound=lambda: False, identity=SimpleNamespace(profile="fixture", public=lambda: {}))
    scope.update({"_control_plane": lambda: control, "_stratum_status_payload": lambda c,r: {}, "_ready_to_mine_reason": lambda r,s: (False, "fixture_no_device"), "_total_hashrate": lambda r: None, "gpu_payload": lambda: {}, "now_iso": lambda: "2026-10-20T23:00:00Z", "_SCHEMA_VERSION": "chronus.mla1517.status/1", "_STATUS_BACKEND": "Python/C/OpenCL", "_EXACT_LADDER": [], "_desired_arms": lambda: 1, "_config_public_payload": lambda: {}, "_CANONICAL_DEVICE": "fixture-unbound", "_identity_payload": lambda: {"ok": False}})
    sources(scope)
    payload = scope["status_payload"]();payload["console"] = scope["console_sources_payload"]()
    return payload

def test_actual_status_and_aggregate_validate():
    payload = fixture(module()); ConsoleStatus.model_validate(payload)
    out = ROOT / "frontend/contracts";out.mkdir(exist_ok=True)
    (out / "console.fixture.json").write_text(json.dumps(payload, indent=2) + "\n")
    (out / "console.schema.json").write_text(json.dumps(ConsoleStatus.model_json_schema(), indent=2) + "\n")

def test_optional_failure_is_null_not_fake_value():
    scope = module();sources(scope, True); value = scope["console_sources_payload"]()
    assert value["fabric"] is None and value["unavailable"]["fabric"] == "RuntimeError"
    assert "mining_evidence" not in value  # no guardian bypass

@pytest.mark.parametrize("ready", [0, 1, "true", "false", {}, []])
def test_readiness_is_strict_boolean(ready):
    payload=fixture(module());payload["ready_to_mine"]["ready"]=ready
    with pytest.raises(ValidationError): ConsoleStatus.model_validate(payload)

@pytest.mark.parametrize("role,allowed", [("ceo", True), ("operator", False)])
def test_actual_server_role_policy(monkeypatch, role, allowed):
    scope=module();token="test-only-token";monkeypatch.setenv("PYTHIA_OPERATOR_PRINCIPALS_JSON", json.dumps({"owner": {"role": role, "token_sha256": hashlib.sha256(token.encode()).hexdigest()}}))
    headers={"Authorization": "Bearer " + token, "X-PYTHIA-Principal": "owner"}
    assert (scope["console_read_authorization"]("/api/v1/mla1517/status",headers) is None) == allowed

def test_guardian_read_requires_independent_control_bearer(monkeypatch):
    scope=module();token="test-only-control";monkeypatch.setenv("PYTHIA_OPERATOR_PRINCIPALS_JSON", json.dumps({"owner": {"role":"ceo", "token_sha256":hashlib.sha256(token.encode()).hexdigest()}}))
    headers={"Authorization":"Bearer subscription-is-not-control", "X-PYTHIA-Principal":"owner"}
    assert scope["console_read_authorization"]("/api/v1/mining/evidence",headers) is not None
    headers["X-PYTHIA-Control-Authorization"]="Bearer "+token
    assert scope["console_read_authorization"]("/api/v1/mining/evidence",headers) is None
    assert headers["Authorization"] == "Bearer subscription-is-not-control"

def test_wrong_principal_denied(monkeypatch):
    scope=module();monkeypatch.setenv("PYTHIA_OPERATOR_PRINCIPALS_JSON",json.dumps({"owner":{"role":"ceo","token_sha256":"a"*64}}))
    assert scope["console_read_authorization"]("/api/v1/status", {"X-PYTHIA-Principal":"forged", "Authorization":"Bearer nope"}) is not None

def test_health_probe_remains_unprivileged():
    assert module()["console_read_authorization"]("/healthz", {}) is None

def test_status_route_checks_role_before_producer():
    text=SOURCE.read_text();route=text[text.index("    def _route_get("):text.index("    _POST_TABLE:")]
    assert route.index("console_read_authorization(path, self.headers)") < route.index("payload = status_payload()")
    assert route.index("console_read_authorization(path, self.headers)") < route.index("self._guardian_preflight(path)")
