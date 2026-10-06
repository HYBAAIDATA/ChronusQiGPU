#!/usr/bin/env python3
"""Render the canonical API contract documents from the registry.

``governance/api_registry.yaml`` is the machine-readable contract; this
renderer produces its human-readable form (``docs/PYTHIA_API_CONTRACT.md``)
and the OpenAPI description of the HTTP surface (``docs/openapi.yaml``).
Both are generated artifacts — edit the registry, then re-render. The
contract suite asserts byte-identical regeneration so the docs cannot
drift from the contract.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY = REPO_ROOT / "governance" / "api_registry.yaml"
DOC_OUT = REPO_ROOT / "docs" / "PYTHIA_API_CONTRACT.md"
OPENAPI_OUT = REPO_ROOT / "docs" / "openapi.yaml"


def _load() -> dict:
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))


_HTTP_TYPES = {"HTTP_PUBLIC", "HTTP_OPERATOR", "HTTP_PRIVILEGED", "EVENT_STREAM", "LEGACY"}
_SECTION_ORDER = [
    ("HTTP_PUBLIC", "Unauthenticated read-only operational truth"),
    ("HTTP_OPERATOR", "Operator-console surface"),
    ("HTTP_PRIVILEGED", "AL HARAS guardian-mediated surface"),
    ("EVENT_STREAM", "Event streams"),
    ("RESERVED_NAMESPACE", "Reserved namespaces (no implementation, by design)"),
    ("INTERNAL_PYTHON", "Internal typed Python contracts"),
    ("WIRE_PROTOCOL", "External wire protocols"),
    ("FILE/ARTIFACT_CONTRACT", "File and artifact contracts"),
    ("CLI", "Command-line entrypoints"),
    ("LEGACY", "Legacy compatibility aliases"),
]


def _route_lines(api: dict) -> list[str]:
    return list(api.get("routes") or [])


def _md_escape(text: object) -> str:
    return str(text).replace("|", "\\|")


def render_markdown(reg: dict) -> str:
    lines: list[str] = []
    a = lines.append
    a("# PYTHIA production API & service-communication contract")
    a("")
    a("Generated from [`governance/api_registry.yaml`](../governance/api_registry.yaml) —")
    a("the machine-readable canonical registry — by `governance/render_api_contract.py`.")
    a("Do not edit by hand; change the registry and re-render.")
    a("")
    a("The implementation is tested against this contract by")
    a("`tests/test_production_api_contract.py`: route parity, live HTTP voyages,")
    a("auth-class enforcement, reserved-namespace non-masquerade, internal")
    a("contracts, and mutation self-tests proving the gate detects drift.")
    a("")
    a("Schema `pythia.api_registry/2` elevates this registry to the service")
    a("constitution: every interface carries authority, tier, SLO, dependency,")
    a("fallback, security, observability, lifecycle and evidence declarations.")
    a("`governance/service_fabric.yaml` holds the shared fabric (failure")
    a("taxonomy, dependency graph, journeys, SLOs, degradation matrix, recovery")
    a("objectives); `tests/test_service_constitution.py` enforces it.")
    a("")
    a("## Canonical authority register")
    a("")
    a("| Authority | Owns |")
    a("| --- | --- |")
    for owner, owns in reg["authority_register"].items():
        a(f"| {owner} | {_md_escape(owns)} |")
    a("")
    a("## Cross-cutting envelope")
    a("")
    a("* Every HTTP response carries `X-Request-Id` — the caller's")
    a("  `X-Request-Id`/`X-Correlation-Id` is echoed when it is a sane token,")
    a("  otherwise a fresh id is minted. Denials are never exempt.")
    a("* JSON bodies carry `schema_version` where the entry declares one.")
    a("* Every mutating route is behind `OPERATOR_PRINCIPAL` or")
    a("  `AL_HARAS_SUBSCRIPTION`; guardian-mediated routes return signed")
    a("  denial receipts rather than bare error codes.")
    a("* `unavailable`/`not_configured`/`armed_no_device` are first-class")
    a("  honest states, never masked as success.")
    a("")
    for itype, heading in _SECTION_ORDER:
        entries = [x for x in reg["apis"] if x["interface_type"] == itype]
        if not entries:
            continue
        a(f"## {heading}")
        a("")
        for api in entries:
            a(f"### `{api['api_id']}` — {api['owner']}")
            a("")
            routes = _route_lines(api)
            if routes:
                a("**Routes**")
                a("")
                for route in routes:
                    a(f"- `{route}`")
                a("")
            elif api.get("method"):
                a(f"- `{api['method']}`")
                a("")
            rows = [
                ("Capability", _md_escape(api["capability"])),
                ("Interface", api["interface_type"]),
                ("Implementation", f"`{_md_escape(api['implementation_path'])}`"),
                ("Consumers", ", ".join(api["consumers"])),
                ("Authority", api["authority"]),
                ("Reliability tier", api["reliability_tier"]),
                ("Lifecycle", api["lifecycle"]),
                ("SLO", f"`{api['slo']}`"),
                ("Auth", api["authentication_class"]),
                ("Authorisation authority", api["authorisation_authority"]),
                ("Truth class", api["truth_class"]),
                ("Request", _md_escape(api["request_schema"])),
                ("Response", _md_escape(api["response_schema"])),
                ("Timeout", api["timeout"]),
                ("Idempotency", api["idempotency"]),
                ("Retry", api["retry"]),
                ("Failure semantics", _md_escape(api["failure_semantics"])),
                ("Availability semantics", _md_escape(api["availability_semantics"])),
                ("Fallback policy", _md_escape(api["fallback_policy"])),
                ("Dependencies", ", ".join(f"`{d}`" for d in api["dependencies"]) or "none"),
                ("Security classification", api["security_classification"]),
                ("Observability", _md_escape(api["observability_requirement"])),
                ("Compatibility window", _md_escape(api["compatibility_window"])),
                ("Support owner", api["support_owner"]),
                ("Runtime evidence", api["runtime_evidence"]),
                ("Side effects", _md_escape(api["side_effects"])),
                ("Custody", _md_escape(api["custody_requirement"])),
                ("Stability", api["stability"]),
                ("Deprecation", api["deprecation_state"]),
                ("Tests", ", ".join(f"`{t}`" for t in api["tests"])),
            ]
            a("| Field | Value |")
            a("| --- | --- |")
            for key, value in rows:
                a(f"| {key} | {_md_escape(value)} |")
            a("")
    a("## Mining authority")
    a("")
    a("`chronus/mla1517/mining/stratum_adapter.py` is the proof boundary. It")
    a("consumes a live subscription and `mining.notify` job, constructs the")
    a("coinbase, Merkle root, 80-byte header, and SHA256d digest, and returns")
    a("`mining.submit` parameters only after the negotiated target check")
    a("succeeds. The frontend is not a mining client: it must not contain")
    a("Stratum methods, Bitcoin hashing, target comparisons, synthetic pool")
    a("acknowledgements, or fabricated hashrate values.")
    a("")
    return "\n".join(lines)


def render_openapi(reg: dict) -> str:
    """Minimal OpenAPI 3.1 surface: every declared concrete HTTP route with
    method, auth scheme tag, and contract metadata. Schema bodies stay in the
    registry — this document binds routes to their api_ids."""
    paths: dict[str, dict[str, dict]] = {}
    security_schemes = {
        "OperatorBearer": {
            "type": "http",
            "scheme": "bearer",
            "description": "PYTHIA operator principal or EUCLID_ADMIN_API_KEY",
        },
        "AlHarasSubscription": {
            "type": "http",
            "scheme": "bearer",
            "description": "AL HARAS subscription token + X-HYBA-Tenant/X-HYBA-Actor",
        },
    }
    for api in reg["apis"]:
        if api["interface_type"] not in _HTTP_TYPES:
            continue
        for route in api.get("routes") or []:
            method, _, path = route.partition(" ")
            if method == "*" or path.startswith("/*"):
                continue
            method_key = {"GET": "get", "POST": "post", "PUT": "put"}[method]
            auth = str(api["authentication_class"])
            security = []
            if "AL_HARAS_SUBSCRIPTION" in auth:
                security = [{"AlHarasSubscription": []}]
            elif "OPERATOR_PRINCIPAL" in auth:
                security = [{"OperatorBearer": []}]
            entry = {
                "summary": api["api_id"],
                "description": (
                    f"owner: {api['owner']} | truth_class: {api['truth_class']} | "
                    f"schema: {api['schema_version']} | failure: {api['failure_semantics']}"
                ),
                "x-pythia-api-id": api["api_id"],
                "x-pythia-truth-class": api["truth_class"],
                "x-pythia-deprecation-state": api["deprecation_state"],
                "x-pythia-reliability-tier": api["reliability_tier"],
                "x-pythia-lifecycle": api["lifecycle"],
                "x-pythia-slo": api["slo"],
            }
            if security:
                entry["security"] = security
            paths.setdefault(path, {})[method_key] = entry
    document = {
        "openapi": "3.1.0",
        "info": {
            "title": "PYTHIA production control API",
            "version": reg["schema"],
            "description": (
                "Generated from governance/api_registry.yaml. Route/auth parity "
                "is enforced by tests/test_production_api_contract.py."
            ),
        },
        "components": {"securitySchemes": security_schemes},
        "paths": dict(sorted(paths.items())),
    }
    return yaml.safe_dump(document, sort_keys=False)


def main(argv: list[str]) -> int:
    reg = _load()
    check = "--check" in argv
    rendered = {
        DOC_OUT: render_markdown(reg),
        OPENAPI_OUT: render_openapi(reg),
    }
    drifted = []
    for path, content in rendered.items():
        if check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                drifted.append(path.name)
        else:
            path.write_text(content, encoding="utf-8")
            print(f"wrote {path.relative_to(REPO_ROOT)}")
    if check:
        if drifted:
            print(f"contract docs out of date: {', '.join(drifted)} — re-render")
            return 1
        print("contract docs are in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
