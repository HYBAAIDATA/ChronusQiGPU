"""
PYTHAGORAS — NETWORK DOMAIN
Network topology evolution domain.

- Representation: undirected edge-list DSL "a -- b [weight]" / parsed graph.
- Coherence: topology coherence — connectivity, degree consistency, and
  average-degree balance, φ-composed.
- CGP primitives: add_edge, remove_edge, rewire_edge, add_node.
- Mutation primitives: ADD:Node, ADD:Edge, REFACTOR:Rewire,
  REFACTOR:Prune, ADVERSARIAL:Perturb.
- Tests: the topology must be connected, loopless, and have >= 2 nodes.
- Features: the abstract 8-dimensional basis instantiated on graphs.
"""

from __future__ import annotations

import math
import re
from collections import deque
from typing import Any, Dict, List, Set

import numpy as np

from ..domain import Domain, MutationPrimitive, WeightedPrimitive
from ..phi_resonance import PHI


_EDGE_RE = re.compile(
    r"^([A-Za-z_][\w.]*)\s*(?:--|\s)\s*([A-Za-z_][\w.]*)(?:\s+(-?\d+(?:\.\d+)?))?\s*;?$"
)


# =============================================================================
# Undirected-graph helpers
# =============================================================================

def _adjacency(rep: Dict[str, Any]) -> Dict[str, Set[str]]:
    adj: Dict[str, Set[str]] = {n: set() for n in rep["nodes"]}
    for e in rep["edges"]:
        adj[e["a"]].add(e["b"])
        adj[e["b"]].add(e["a"])
    return adj


def _component_sizes(rep: Dict[str, Any]) -> List[int]:
    adj = _adjacency(rep)
    seen: Set[str] = set()
    sizes: List[int] = []
    for n in rep["nodes"]:
        if n in seen:
            continue
        size = 0
        queue = deque([n])
        seen.add(n)
        while queue:
            node = queue.popleft()
            size += 1
            for nxt in adj[node]:
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        sizes.append(size)
    return sizes


def _is_connected(rep: Dict[str, Any]) -> bool:
    return len(_component_sizes(rep)) <= 1


def _is_bridge(rep: Dict[str, Any], edge_index: int) -> bool:
    """Would removing edge_index disconnect the graph?"""
    nodes = rep["nodes"]
    adj: Dict[str, Set[str]] = {n: set() for n in nodes}
    for i, e in enumerate(rep["edges"]):
        if i == edge_index:
            continue
        adj[e["a"]].add(e["b"])
        adj[e["b"]].add(e["a"])
    seen = {nodes[0]}
    queue = deque([nodes[0]])
    while queue:
        node = queue.popleft()
        for nxt in adj[node]:
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return len(seen) < len(nodes)


def _degrees(rep: Dict[str, Any]) -> Dict[str, int]:
    deg = {n: 0 for n in rep["nodes"]}
    for e in rep["edges"]:
        deg[e["a"]] += 1
        deg[e["b"]] += 1
    return deg


def _diameter(rep: Dict[str, Any]) -> int:
    """BFS eccentricity max over the largest connected component."""
    adj = _adjacency(rep)
    best = 0
    for start in rep["nodes"]:
        dist = {start: 0}
        queue = deque([start])
        while queue:
            node = queue.popleft()
            for nxt in adj[node]:
                if nxt not in dist:
                    dist[nxt] = dist[node] + 1
                    queue.append(nxt)
        if dist:
            best = max(best, max(dist.values()))
    return best


# =============================================================================
# Parsing / serialization
# =============================================================================

def _parse_network(source: str) -> Dict[str, Any]:
    nodes: List[str] = []
    edges: List[Dict[str, Any]] = []
    for raw in source.splitlines():
        line = raw.split("#")[0].strip()
        if not line:
            continue
        m = _EDGE_RE.match(line)
        if not m:
            raise ValueError(f"unparseable line: {line}")
        a, b = m.group(1), m.group(2)
        w = float(m.group(3)) if m.group(3) is not None else 1.0
        for n in (a, b):
            if n not in nodes:
                nodes.append(n)
        edges.append({"a": a, "b": b, "weight": w})
    if not nodes:
        raise ValueError("topology is empty")
    return {"nodes": nodes, "edges": edges}


def _unparse_network(rep: Dict[str, Any]) -> str:
    lines = [f"{e['a']} -- {e['b']} {e['weight']:.6g}" for e in rep["edges"]]
    return "\n".join(lines) + ("\n" if lines else "")


def _transform(source: str, fn) -> str:
    try:
        rep = _parse_network(source)
        rep = fn(rep)
        return _unparse_network(rep)
    except Exception:
        return source


def _fresh_node(rep: Dict[str, Any], base: str = "n") -> str:
    i = 0
    while f"{base}{i}" in rep["nodes"]:
        i += 1
    return f"{base}{i}"


# =============================================================================
# CGP-layer primitives
# =============================================================================

def prim_add_edge(source: str, weight: float) -> str:
    """add_edge: connect the two lowest-degree non-adjacent nodes."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        deg = _degrees(rep)
        ordered = sorted(rep["nodes"], key=lambda n: deg[n])
        existing = {(e["a"], e["b"]) for e in rep["edges"]} | {
            (e["b"], e["a"]) for e in rep["edges"]
        }
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                a, b = ordered[i], ordered[j]
                if (a, b) not in existing:
                    rep["edges"].append({"a": a, "b": b, "weight": 1.0})
                    return rep
        return rep

    return _transform(source, go)


def prim_remove_edge(source: str, weight: float) -> str:
    """remove_edge: remove the highest-degree-endpoint non-bridge edge."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        deg = _degrees(rep)
        ranked = sorted(
            range(len(rep["edges"])),
            key=lambda i: deg[rep["edges"][i]["a"]] + deg[rep["edges"][i]["b"]],
            reverse=True,
        )
        for ei in ranked:
            if not _is_bridge(rep, ei):
                rep["edges"].pop(ei)
                return rep
        return rep

    return _transform(source, go)


def prim_rewire_edge(source: str, weight: float) -> str:
    """rewire_edge: move one endpoint from the highest-degree node to the
    lowest-degree non-adjacent node (degree-variance reduction)."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        deg = _degrees(rep)
        ordered = sorted(rep["nodes"], key=lambda n: deg[n])
        if len(ordered) < 2:
            return rep
        hub, leaf = ordered[-1], ordered[0]
        for ei, e in enumerate(rep["edges"]):
            if hub not in (e["a"], e["b"]):
                continue
            other = e["b"] if e["a"] == hub else e["a"]
            if other == leaf:
                continue
            existing = {(x["a"], x["b"]) for x in rep["edges"]} | {
                (x["b"], x["a"]) for x in rep["edges"]
            }
            if (other, leaf) in existing:
                continue
            # Rewire hub <-> other to other <-> leaf.
            rep["edges"][ei] = {"a": other, "b": leaf, "weight": e["weight"]}
            return rep
        return rep

    return _transform(source, go)


def prim_add_node(source: str, weight: float) -> str:
    """add_node: attach a new leaf node to the median-degree node."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        deg = _degrees(rep)
        ordered = sorted(rep["nodes"], key=lambda n: deg[n])
        anchor = ordered[len(ordered) // 2]
        new = _fresh_node(rep)
        rep["nodes"].append(new)
        rep["edges"].append({"a": anchor, "b": new, "weight": 1.0})
        return rep

    return _transform(source, go)


# =============================================================================
# Mutation-layer primitives
# =============================================================================

def mut_add_node(source: str) -> str:
    """ADD:Node — attach a new leaf to the median-degree node."""
    return prim_add_node(source, 1.0)


def mut_add_edge(source: str) -> str:
    """ADD:Edge — connect the two lowest-degree non-adjacent nodes."""
    return prim_add_edge(source, 1.0)


def mut_rewire(source: str) -> str:
    """REFACTOR:Rewire — shift an endpoint from hub to leaf."""
    return prim_rewire_edge(source, 1.0)


def mut_prune(source: str) -> str:
    """REFACTOR:Prune — remove the highest-degree non-bridge edge."""
    return prim_remove_edge(source, 1.0)


def mut_adversarial(source: str) -> str:
    """ADVERSARIAL:Perturb — sever a bridge edge, isolating a component."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        for ei in range(len(rep["edges"])):
            if _is_bridge(rep, ei):
                rep["edges"].pop(ei)
                return rep
        return rep

    return _transform(source, go)


# =============================================================================
# The Network Domain
# =============================================================================

class NetworkDomain(Domain):
    """
    NetworkDomain: undirected topology evolution.

    Optimizes topology coherence — connectivity, degree consistency, and
    average-degree balance of a network graph.
    """

    name = "network"
    file_extensions = (".net", ".edges")

    def __init__(self):
        self._primitives: Dict[str, WeightedPrimitive] = {
            "add_edge": prim_add_edge,
            "remove_edge": prim_remove_edge,
            "rewire_edge": prim_rewire_edge,
            "add_node": prim_add_node,
        }
        self._mutation_primitives: Dict[str, MutationPrimitive] = {
            "ADD:Node": mut_add_node,
            "ADD:Edge": mut_add_edge,
            "REFACTOR:Rewire": mut_rewire,
            "REFACTOR:Prune": mut_prune,
            "ADVERSARIAL:Perturb": mut_adversarial,
        }
        self._mutation_weights: Dict[str, float] = {
            "ADD:Node": 0.450,
            "ADD:Edge": 0.550,
            "REFACTOR:Rewire": 0.600,
            "REFACTOR:Prune": 0.350,
            "ADVERSARIAL:Perturb": 0.100,
        }

    # -- representation -----------------------------------------------------

    def parse(self, source: str) -> Dict[str, Any]:
        return _parse_network(source)

    def unparse(self, rep: Dict[str, Any]) -> str:
        return _unparse_network(rep)

    def is_valid(self, source: str) -> bool:
        try:
            _parse_network(source)
            return True
        except Exception:
            return False

    # -- coherence ----------------------------------------------------------

    def coherence(self, source: str) -> float:
        return self.compute_components(source)["composite"]

    def compute_components(self, source: str) -> Dict[str, float]:
        try:
            rep = _parse_network(source)
        except Exception:
            return {
                "connectivity": 0.0,
                "degree_consistency": 0.0,
                "degree_balance": 0.0,
                "composite": 0.0,
            }

        n = len(rep["nodes"])
        e = len(rep["edges"])

        # Component 1: connectivity — largest component coverage.
        connectivity = max(_component_sizes(rep)) / n

        # Component 2: degree consistency — 1 / (1 + variance).
        degs = list(_degrees(rep).values())
        consistency = 1.0 / (1.0 + float(np.var(degs))) if len(degs) > 1 else 1.0

        # Component 3: degree balance — average degree vs 2φ saturation.
        avg_deg = (2.0 * e) / n
        balance = min(1.0, avg_deg / (2.0 * PHI))

        composite = float(np.clip((connectivity + consistency + balance) / 3.0, 0.0, 1.0))
        return {
            "connectivity": float(connectivity),
            "degree_consistency": float(consistency),
            "degree_balance": float(balance),
            "composite": composite,
        }

    # -- primitives ---------------------------------------------------------

    def primitives(self) -> Dict[str, WeightedPrimitive]:
        return self._primitives

    def mutation_primitives(self) -> Dict[str, MutationPrimitive]:
        return self._mutation_primitives

    def mutation_weights(self) -> Dict[str, float]:
        return dict(self._mutation_weights)

    # -- tests --------------------------------------------------------------

    def tests(self, source: str) -> bool:
        """
        Topology test battery: parses, >= 2 nodes, no self-loops,
        and fully connected (single component).
        """
        try:
            rep = _parse_network(source)
        except Exception:
            return False
        if len(rep["nodes"]) < 2:
            return False
        if any(e["a"] == e["b"] for e in rep["edges"]):
            return False
        return _is_connected(rep)

    # -- features -----------------------------------------------------------

    def features(self, source: str) -> np.ndarray:
        """
        8-dimensional topology feature basis:
        log nodes, diameter, node count, edge count, leaf count,
        density, average-degree ratio, coherence.
        """
        try:
            rep = _parse_network(source)
            n = len(rep["nodes"])
            e = len(rep["edges"])
            deg = _degrees(rep)
            leaves = sum(1 for nd in rep["nodes"] if deg[nd] == 1)
            avg_deg = (2.0 * e) / n
            return np.array(
                [
                    math.log1p(n),
                    float(_diameter(rep)),
                    float(n),
                    float(e),
                    float(leaves),
                    min(1.0, (2.0 * e) / max(1, n * (n - 1))),
                    min(1.0, avg_deg / max(1, n - 1)),
                    self.coherence(source),
                ],
                dtype=float,
            )
        except Exception:
            return np.zeros(8, dtype=float)

    # -- hooks --------------------------------------------------------------

    def normalize(self, source: str) -> str:
        try:
            rep = _parse_network(source)
            return _unparse_network(rep)
        except Exception:
            return source

    def sample_source(self) -> str:
        return (
            "n0 -- n1 1.0\n"
            "n1 -- n2 1.0\n"
            "n2 -- n3 1.0\n"
            "n3 -- n4 1.0\n"
            "n4 -- n5 1.0\n"
            "n5 -- n0 1.0\n"
            "n1 -- n4 0.5\n"
        )
