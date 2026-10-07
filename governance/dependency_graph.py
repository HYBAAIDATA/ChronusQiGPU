#!/usr/bin/env python3
"""Executable validator for the API dependency graph.

Loads ``docs/DEPENDENCY_GRAPH.yaml`` (rendered from the constitution
overlay) together with ``governance/api_registry.yaml`` and enforces the
graph's declared invariants:

* every edge endpoint is a registered api_id or external authority;
* the api-edge graph is acyclic;
* an R0 (constitutional) API never depends on an R3/R4 API — recovery and
  experience tiers may degrade, constitutional verdicts may not wait on them;
* every entry whose ``authorisation_authority`` is bare ``AL_HARAS``
  carries an ``al_haras.guardian`` edge (privileged routes cannot lose
  mediation; ``caller-side`` mediation is declared on the caller's edge,
  and the guardian itself is the authority so it needs no self-edge);
* every entry whose ``custody_requirement`` mentions THESEUS carries a
  ``theseus.custody`` edge (durable results cannot lose custody);
* every entry whose ``custody_requirement`` mentions ``guardian_mediated``
  carries an ``al_haras.guardian`` edge;
* RESERVED_NAMESPACE entries depend only on ``al_haras.guardian``.

``validate()`` returns a sorted list of violation strings; empty means the
graph is consistent.  The module also runs as a CLI::

    python governance/dependency_graph.py          # validate
    python governance/dependency_graph.py --reachable pythia.mining.control
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
GRAPH_DOC = REPO_ROOT / "docs" / "DEPENDENCY_GRAPH.yaml"
REGISTRY = REPO_ROOT / "governance" / "api_registry.yaml"

_TIER_ORDER = {"R0": 0, "R1": 1, "R2": 2, "R3": 3, "R4": 4}


def load() -> tuple[dict, dict]:
    graph = yaml.safe_load(GRAPH_DOC.read_text(encoding="utf-8"))
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    return graph, registry


def _apis(registry: dict) -> dict[str, dict]:
    return {e["api_id"]: e for e in registry.get("apis") or []}


def api_edges(graph: dict) -> dict[str, list[str]]:
    """Adjacency restricted to api->api edges (external edges excluded)."""
    adj: dict[str, list[str]] = {}
    for edge in graph.get("edges") or []:
        if edge.get("kind") == "api":
            adj.setdefault(edge["from"], []).append(edge["to"])
    return adj


def reachable(graph: dict, start: str) -> set[str]:
    adj: dict[str, list[str]] = {}
    for edge in graph.get("edges") or []:
        adj.setdefault(edge["from"], []).append(edge["to"])
    seen: set[str] = set()
    stack = [start]
    while stack:
        node = stack.pop()
        for nxt in adj.get(node, []):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def _find_cycle(adj: dict[str, list[str]]) -> list[str] | None:
    """Return one cycle as a node list if the graph is cyclic, else None."""
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {n: WHITE for n in adj}
    path: list[str] = []

    def visit(node: str) -> list[str] | None:
        colour[node] = GREY
        path.append(node)
        for nxt in adj.get(node, []):
            if colour.get(nxt, WHITE) == GREY:
                return path[path.index(nxt) :] + [nxt]
            if colour.get(nxt, WHITE) == WHITE:
                found = visit(nxt)
                if found:
                    return found
        path.pop()
        colour[node] = BLACK
        return None

    for node in adj:
        if colour[node] == WHITE:
            found = visit(node)
            if found:
                return found
    return None


def validate(graph: dict, registry: dict) -> list[str]:
    violations: list[str] = []
    apis = _apis(registry)
    nodes = graph.get("nodes") or {}
    externals = set((graph.get("external_authorities") or {}).keys())
    edges = graph.get("edges") or []

    for api_id in apis:
        if api_id not in nodes:
            violations.append(f"graph node missing for registry api {api_id}")
    for node in nodes:
        if node not in apis:
            violations.append(f"graph node {node} is not a registered api")

    for edge in edges:
        src, dst = edge.get("from"), edge.get("to")
        if src not in apis:
            violations.append(f"edge source {src!r} is not a registered api")
        if dst not in apis and dst not in externals:
            violations.append(
                f"edge target {dst!r} (from {src}) is neither a registered "
                "api nor an external authority"
            )
        if src == dst:
            violations.append(f"self-edge on {src}")

    adj = api_edges(graph)
    cycle = _find_cycle(adj)
    if cycle:
        violations.append("dependency cycle: " + " -> ".join(cycle))

    tier_of = {n: (nodes.get(n) or {}).get("criticality") for n in nodes}
    for edge in edges:
        src_tier = tier_of.get(edge.get("from"))
        dst_tier = tier_of.get(edge.get("to"))
        if src_tier == "R0" and dst_tier in {"R3", "R4"} and edge.get("kind") == "api":
            violations.append(f"R0 api {edge['from']} depends on {dst_tier} api {edge['to']}")

    for api_id, entry in apis.items():
        deps = set(adj.get(api_id, []))
        itype = entry.get("interface_type")
        auth = str(entry.get("authorisation_authority") or "")
        custody = str(entry.get("custody_requirement") or "")

        if itype == "RESERVED_NAMESPACE":
            extra = deps - {"al_haras.guardian"}
            if extra:
                violations.append(
                    f"reserved namespace {api_id} declares non-boundary "
                    f"dependencies: {sorted(extra)}"
                )
        if auth == "AL_HARAS" and api_id != "al_haras.guardian" and "al_haras.guardian" not in deps:
            violations.append(
                f"{api_id}: authorisation_authority AL_HARAS without an "
                "al_haras.guardian dependency"
            )
        if "guardian_mediated" in custody and "al_haras.guardian" not in deps:
            violations.append(
                f"{api_id}: guardian_mediated custody without an " "al_haras.guardian dependency"
            )
        if (
            "THESEUS" in custody.upper()
            and "self" not in custody.split(" ")[0].lower()
            and "theseus.custody" not in deps
        ):
            violations.append(
                f"{api_id}: THESEUS custody requirement without a " "theseus.custody dependency"
            )

    return sorted(violations)


def main(argv: list[str]) -> int:
    graph, registry = load()
    if argv and argv[0] == "--reachable":
        targets = sorted(reachable(graph, argv[1]))
        print("\n".join(targets) or "(no dependencies)")
        return 0
    violations = validate(graph, registry)
    for v in violations:
        print(f"VIOLATION {v}")
    print(f"{len(violations)} violation(s)")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
