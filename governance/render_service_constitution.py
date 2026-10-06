#!/usr/bin/env python3
"""Render the service constitution and the dependency graph.

``governance/service_constitution.yaml`` is the authored governance overlay;
``governance/api_registry.yaml`` is the machine-readable interface contract.
This renderer merges them into two generated artifacts:

* ``docs/SERVICE_CONSTITUTION.yaml`` — the fifteen-field constitution
  record for every registered API (capability, authority, interface,
  consumer, schema, dependency, criticality, slo, failure_mode,
  retry_idempotency, evidence_owner, observability, lifecycle_owner,
  version, deprecation_policy).
* ``docs/DEPENDENCY_GRAPH.yaml`` — the executable dependency graph:
  every declared downstream API required for success, plus external
  authorities (POOL, OPERATOR, FILESYSTEM, REMOTE_DEVICE).

Both are generated artifacts — edit the overlay or the registry, then
re-render.  ``tests/test_service_constitution.py`` asserts byte-identical
regeneration so the documents cannot drift from their sources, and runs
the constitution/graph gates over the merged result.

Usage::

    python governance/render_service_constitution.py          # write
    python governance/render_service_constitution.py --check  # drift gate
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY = REPO_ROOT / "governance" / "api_registry.yaml"
OVERLAY = REPO_ROOT / "governance" / "service_constitution.yaml"
CONSTITUTION_OUT = REPO_ROOT / "docs" / "SERVICE_CONSTITUTION.yaml"
GRAPH_OUT = REPO_ROOT / "docs" / "DEPENDENCY_GRAPH.yaml"

_GENERATED = (
    "# GENERATED — do not edit.\n"
    "# sources: governance/service_constitution.yaml + governance/api_registry.yaml\n"
    "# regenerate: python governance/render_service_constitution.py\n"
)

_TIERS = ("R0", "R1", "R2", "R3", "R4")


class ConstitutionError(ValueError):
    """Raised when the overlay and registry cannot be merged honestly."""


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _registry_apis(reg: dict) -> dict[str, dict]:
    apis = {}
    for entry in reg.get("apis") or []:
        api_id = entry.get("api_id")
        if not api_id:
            raise ConstitutionError("registry entry without api_id")
        apis[api_id] = entry
    return apis


def _resolve(reg: dict, overlay: dict) -> list[dict]:
    """Merge registry + overlay into the fifteen-field constitution records.

    Hard-fails on any dishonesty: a registry API missing its governance
    record, an overlay record for an unknown API, an unknown criticality,
    an unknown dependency, or an owner with no lifecycle owner.
    """
    reg_apis = _registry_apis(reg)
    gov_apis = overlay.get("apis") or {}
    tiers = overlay.get("reliability_tiers") or {}
    externals = set((overlay.get("external_authorities") or {}).keys())
    owners = overlay.get("lifecycle_owners") or {}
    defaults = overlay.get("defaults") or {}
    obs_default = defaults.get("observability_by_interface") or {}
    dep_default = defaults.get("deprecation_policy_by_state") or {}

    missing = sorted(set(reg_apis) - set(gov_apis))
    if missing:
        raise ConstitutionError("registry APIs with no constitution record: " + ", ".join(missing))
    extra = sorted(set(gov_apis) - set(reg_apis))
    if extra:
        raise ConstitutionError("constitution records for unknown APIs: " + ", ".join(extra))

    records = []
    for api_id, entry in reg_apis.items():
        gov = dict(gov_apis[api_id])
        tier = gov.get("criticality")
        if tier not in _TIERS:
            raise ConstitutionError(f"{api_id}: criticality must be one of {_TIERS}, got {tier!r}")
        if tier not in tiers:
            raise ConstitutionError(f"{api_id}: tier {tier} not in reliability_tiers")

        deps = list(gov.get("dependencies") or [])
        for dep in deps:
            if dep not in reg_apis and dep not in externals:
                raise ConstitutionError(
                    f"{api_id}: dependency {dep!r} is not a registry api_id "
                    "or external authority"
                )

        owner = entry.get("owner")
        if owner not in owners:
            raise ConstitutionError(f"{api_id}: owner {owner!r} has no lifecycle owner record")
        itype = entry.get("interface_type")
        state = entry.get("deprecation_state")
        if itype not in obs_default:
            raise ConstitutionError(f"{api_id}: no observability default for interface {itype!r}")
        if state not in dep_default:
            raise ConstitutionError(f"{api_id}: no deprecation policy default for state {state!r}")

        records.append(
            {
                "api_id": api_id,
                "capability": gov.get("capability"),
                "authority": owner,
                "interface": itype,
                "consumer": list(entry.get("consumers") or []),
                "schema": {
                    "request": entry.get("request_schema"),
                    "response": entry.get("response_schema"),
                    "version": entry.get("schema_version"),
                },
                "dependency": deps,
                "criticality": tier,
                "slo": gov.get("slo") or tiers[tier]["slo"],
                "slo_state": "DECLARED_NOT_MEASURED (measured in Phase 4B)",
                "failure_mode": entry.get("failure_semantics"),
                "retry_idempotency": {
                    "retry": entry.get("retry"),
                    "idempotency": entry.get("idempotency"),
                },
                "evidence_owner": gov.get("evidence_owner") or owner,
                "observability": gov.get("observability") or obs_default[itype],
                "lifecycle_owner": gov.get("lifecycle_owner") or owners[owner],
                "version": entry.get("schema_version"),
                "deprecation_policy": gov.get("deprecation_policy") or dep_default[state],
            }
        )
    return records


def render_constitution(reg: dict, overlay: dict) -> str:
    records = _resolve(reg, overlay)
    document = {
        "schema": "pythia.service_constitution/1",
        "repository": overlay.get("repository"),
        "provenance": {
            "generated_by": "governance/render_service_constitution.py",
            "sources": [
                "governance/service_constitution.yaml",
                "governance/api_registry.yaml",
            ],
        },
        "reliability_tiers": overlay.get("reliability_tiers"),
        "external_authorities": overlay.get("external_authorities"),
        "constitutions": records,
    }
    return _GENERATED + yaml.safe_dump(document, sort_keys=False, width=100, allow_unicode=True)


def render_dependency_graph(reg: dict, overlay: dict) -> str:
    reg_apis = _registry_apis(reg)
    gov_apis = overlay.get("apis") or {}
    tiers = overlay.get("reliability_tiers") or {}
    externals = overlay.get("external_authorities") or {}

    nodes = {}
    for api_id in sorted(reg_apis):
        nodes[api_id] = {
            "owner": reg_apis[api_id].get("owner"),
            "criticality": (gov_apis.get(api_id) or {}).get("criticality"),
            "interface": reg_apis[api_id].get("interface_type"),
        }
    edges = []
    for api_id in sorted(gov_apis):
        for dep in gov_apis[api_id].get("dependencies") or []:
            edges.append(
                {
                    "from": api_id,
                    "to": dep,
                    "kind": "external" if dep in externals else "api",
                }
            )
    document = {
        "schema": "pythia.dependency_graph/1",
        "repository": overlay.get("repository"),
        "provenance": {
            "generated_by": "governance/render_service_constitution.py",
            "source": "governance/service_constitution.yaml",
        },
        "reliability_tiers": {k: v["name"] for k, v in tiers.items()},
        "external_authorities": externals,
        "nodes": nodes,
        "edges": edges,
        "invariants": [
            "every edge endpoint is a registered api_id or external authority",
            "the api-edge graph is acyclic",
            "an R0 API never depends on an R3/R4 API",
            "bare authorisation_authority: AL_HARAS requires an al_haras.guardian edge",
            "custody_requirement mentioning THESEUS requires a theseus.custody edge",
            "custody_requirement mentioning guardian_mediated requires an al_haras.guardian edge",
            "RESERVED_NAMESPACE entries depend only on al_haras.guardian",
        ],
    }
    return _GENERATED + yaml.safe_dump(document, sort_keys=False, width=100, allow_unicode=True)


def main(argv: list[str]) -> int:
    reg = _load_yaml(REGISTRY)
    overlay = _load_yaml(OVERLAY)
    check = "--check" in argv
    rendered = {
        CONSTITUTION_OUT: render_constitution(reg, overlay),
        GRAPH_OUT: render_dependency_graph(reg, overlay),
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
            print(f"constitution docs out of date: {', '.join(drifted)} — re-render")
            return 1
        print("constitution docs are in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
