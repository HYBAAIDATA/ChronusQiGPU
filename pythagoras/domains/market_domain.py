"""
PYTHAGORAS — MARKET DOMAIN
Causal dependency-graph evolution domain.

- Representation: directed-edge DSL "A -> B [weight]" / parsed digraph.
- Coherence: dependency coherence — acyclicity, degree consistency,
  and edge coverage, φ-composed.
- CGP primitives: add_hedge, remove_cycle_edge, rebalance_weight, split_node.
- Mutation primitives: ADD:Node, ADD:Edge, REFACTOR:Decycle,
  REFACTOR:Normalize, ADVERSARIAL:Perturb.
- Tests: the dependency graph must be acyclic and weakly connected with
  finite edge weights.
- Features: the abstract 8-dimensional basis instantiated on digraphs.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Set

import numpy as np

from ..domain import Domain, MutationPrimitive, WeightedPrimitive
from ..phi_resonance import PHI


_EDGE_RE = re.compile(
    r"^([A-Za-z_][\w.]*)\s*->\s*([A-Za-z_][\w.]*)(?:\s+(-?\d+(?:\.\d+)?))?\s*;?$"
)


# =============================================================================
# Directed-graph helpers
# =============================================================================

def _adjacency(rep: Dict[str, Any]) -> Dict[str, List[int]]:
    adj: Dict[str, List[int]] = {n: [] for n in rep["nodes"]}
    for ei, e in enumerate(rep["edges"]):
        adj[e["src"]].append(ei)
    return adj


def _has_path(rep: Dict[str, Any], src: str, dst: str) -> bool:
    """DFS: is dst reachable from src?"""
    if src == dst:
        return True
    adj = _adjacency(rep)
    seen: Set[str] = set()
    stack = [src]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        for ei in adj.get(node, []):
            nxt = rep["edges"][ei]["dst"]
            if nxt == dst:
                return True
            stack.append(nxt)
    return False


def _cyclic_edge_count(rep: Dict[str, Any]) -> int:
    """Kahn's algorithm — count edges surviving in the cyclic residue."""
    nodes = list(rep["nodes"])
    edges = rep["edges"]
    indeg = {n: 0 for n in nodes}
    for e in edges:
        indeg[e["dst"]] += 1
    remaining_edges = len(edges)
    queue = [n for n in nodes if indeg[n] == 0]
    adj = _adjacency(rep)
    while queue:
        node = queue.pop()
        for ei in adj[node]:
            e = edges[ei]
            remaining_edges -= 1
            indeg[e["dst"]] -= 1
            if indeg[e["dst"]] == 0:
                queue.append(e["dst"])
    return remaining_edges


def _find_cycle_edge(rep: Dict[str, Any]) -> Optional[int]:
    """Return the index of one edge lying on a directed cycle, or None."""
    for ei, e in enumerate(rep["edges"]):
        if _has_path(rep, e["dst"], e["src"]):
            return ei
    return None


def _longest_path(rep: Dict[str, Any]) -> int:
    """Longest path length (edges) via Kahn topological relaxation."""
    nodes = rep["nodes"]
    edges = rep["edges"]
    indeg = {n: 0 for n in nodes}
    for e in edges:
        indeg[e["dst"]] += 1
    dist = {n: 0 for n in nodes}
    adj = _adjacency(rep)
    queue = [n for n in nodes if indeg[n] == 0]
    while queue:
        node = queue.pop()
        for ei in adj[node]:
            e = edges[ei]
            dist[e["dst"]] = max(dist[e["dst"]], dist[node] + 1)
            indeg[e["dst"]] -= 1
            if indeg[e["dst"]] == 0:
                queue.append(e["dst"])
    return max(dist.values(), default=0)


def _weakly_connected(rep: Dict[str, Any]) -> bool:
    nodes = rep["nodes"]
    if len(nodes) <= 1:
        return True
    undirected: Dict[str, Set[str]] = {n: set() for n in nodes}
    for e in rep["edges"]:
        undirected[e["src"]].add(e["dst"])
        undirected[e["dst"]].add(e["src"])
    seen = {nodes[0]}
    stack = [nodes[0]]
    while stack:
        node = stack.pop()
        for nxt in undirected[node]:
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return len(seen) == len(nodes)


def _degrees(rep: Dict[str, Any]) -> Dict[str, int]:
    deg = {n: 0 for n in rep["nodes"]}
    for e in rep["edges"]:
        deg[e["src"]] += 1
        deg[e["dst"]] += 1
    return deg


# =============================================================================
# Parsing / serialization
# =============================================================================

def _parse_market(source: str) -> Dict[str, Any]:
    nodes: List[str] = []
    edges: List[Dict[str, Any]] = []
    for raw in source.splitlines():
        line = raw.split("#")[0].strip()
        if not line:
            continue
        m = _EDGE_RE.match(line)
        if not m:
            raise ValueError(f"unparseable line: {line}")
        src, dst = m.group(1), m.group(2)
        w = float(m.group(3)) if m.group(3) is not None else 1.0
        for n in (src, dst):
            if n not in nodes:
                nodes.append(n)
        edges.append({"src": src, "dst": dst, "weight": w})
    if not nodes:
        raise ValueError("dependency graph is empty")
    return {"nodes": nodes, "edges": edges}


def _unparse_market(rep: Dict[str, Any]) -> str:
    lines = [f"{e['src']} -> {e['dst']} {e['weight']:.6g}" for e in rep["edges"]]
    attached = {n for e in rep["edges"] for n in (e["src"], e["dst"])}
    for n in rep["nodes"]:
        if n not in attached:
            lines.append(f"{n} -> {n}_sink {PHI:.6g}")
    return "\n".join(lines) + "\n"


def _transform(source: str, fn) -> str:
    try:
        rep = _parse_market(source)
        rep = fn(rep)
        return _unparse_market(rep)
    except Exception:
        return source


def _fresh_node(rep: Dict[str, Any], base: str) -> str:
    i = 1
    while f"{base}_{i}" in rep["nodes"]:
        i += 1
    return f"{base}_{i}"


# =============================================================================
# CGP-layer primitives
# =============================================================================

def prim_add_hedge(source: str, weight: float) -> str:
    """add_hedge: add a diversification edge between two low-degree nodes
    (chosen so the graph stays acyclic)."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        deg = _degrees(rep)
        ordered = sorted(rep["nodes"], key=lambda n: deg[n])
        for i in range(len(ordered)):
            for j in range(len(ordered)):
                if i == j:
                    continue
                src, dst = ordered[i], ordered[j]
                if src == dst:
                    continue
                if any(e["src"] == src and e["dst"] == dst for e in rep["edges"]):
                    continue
                if _has_path(rep, dst, src):
                    continue
                rep["edges"].append({"src": src, "dst": dst, "weight": PHI})
                return rep
        return rep

    return _transform(source, go)


def prim_remove_cycle_edge(source: str, weight: float) -> str:
    """remove_cycle_edge: delete one edge lying on a directed cycle."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        ei = _find_cycle_edge(rep)
        if ei is not None:
            rep["edges"].pop(ei)
        return rep

    return _transform(source, go)


def prim_rebalance_weight(source: str, weight: float) -> str:
    """rebalance_weight: normalize each node's incoming weights to sum <= 1."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        incoming: Dict[str, List[int]] = {n: [] for n in rep["nodes"]}
        for ei, e in enumerate(rep["edges"]):
            incoming[e["dst"]].append(ei)
        for dst, eis in incoming.items():
            total = sum(rep["edges"][ei]["weight"] for ei in eis)
            if total > 1.0:
                for ei in eis:
                    rep["edges"][ei]["weight"] = rep["edges"][ei]["weight"] / total
        return rep

    return _transform(source, go)


def prim_split_node(source: str, weight: float) -> str:
    """split_node: split the highest out-degree node, moving half of its
    out-edges onto a new sibling node."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        adj = _adjacency(rep)
        if not rep["nodes"]:
            return rep
        hub = max(rep["nodes"], key=lambda n: len(adj[n]))
        out_eis = adj[hub]
        if len(out_eis) < 2:
            return rep
        sibling = _fresh_node(rep, hub)
        rep["nodes"].append(sibling)
        for ei in out_eis[1::2]:
            rep["edges"][ei]["src"] = sibling
        return rep

    return _transform(source, go)


# =============================================================================
# Mutation-layer primitives
# =============================================================================

def mut_add_node(source: str) -> str:
    """ADD:Node — attach a new node driven by the highest-degree hub."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        deg = _degrees(rep)
        hub = max(rep["nodes"], key=lambda n: deg[n])
        new = _fresh_node(rep, "N")
        rep["nodes"].append(new)
        rep["edges"].append({"src": hub, "dst": new, "weight": PHI})
        return rep

    return _transform(source, go)


def mut_add_edge(source: str) -> str:
    """ADD:Edge — connect two nodes, preserving acyclicity."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        for src in rep["nodes"]:
            for dst in rep["nodes"]:
                if src == dst:
                    continue
                if any(e["src"] == src and e["dst"] == dst for e in rep["edges"]):
                    continue
                if _has_path(rep, dst, src):
                    continue
                rep["edges"].append({"src": src, "dst": dst, "weight": 0.5})
                return rep
        return rep

    return _transform(source, go)


def mut_decycle(source: str) -> str:
    """REFACTOR:Decycle — remove all cycle-forming edges."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        for _ in range(len(rep["edges"]) + 1):
            ei = _find_cycle_edge(rep)
            if ei is None:
                break
            rep["edges"].pop(ei)
        return rep

    return _transform(source, go)


def mut_normalize(source: str) -> str:
    """REFACTOR:Normalize — cap incoming weight sums at 1."""
    return prim_rebalance_weight(source, 1.0)


def mut_adversarial(source: str) -> str:
    """ADVERSARIAL:Perturb — inject a cycle edge (negative-coherence probe)."""

    def go(rep: Dict[str, Any]) -> Dict[str, Any]:
        for src in rep["nodes"]:
            for dst in rep["nodes"]:
                if src != dst and _has_path(rep, dst, src):
                    rep["edges"].append({"src": src, "dst": dst, "weight": -0.5})
                    return rep
        if rep["nodes"]:
            n = rep["nodes"][0]
            rep["edges"].append({"src": n, "dst": n, "weight": -0.5})
        return rep

    return _transform(source, go)


# =============================================================================
# The Market Domain
# =============================================================================

class MarketDomain(Domain):
    """
    MarketDomain: causal dependency-graph evolution.

    Optimizes dependency coherence — acyclicity, degree consistency, and
    edge coverage of a causal dependency graph.
    """

    name = "market"
    file_extensions = (".mkt", ".dep")

    def __init__(self):
        self._primitives: Dict[str, WeightedPrimitive] = {
            "add_hedge": prim_add_hedge,
            "remove_cycle_edge": prim_remove_cycle_edge,
            "rebalance_weight": prim_rebalance_weight,
            "split_node": prim_split_node,
        }
        self._mutation_primitives: Dict[str, MutationPrimitive] = {
            "ADD:Node": mut_add_node,
            "ADD:Edge": mut_add_edge,
            "REFACTOR:Decycle": mut_decycle,
            "REFACTOR:Normalize": mut_normalize,
            "ADVERSARIAL:Perturb": mut_adversarial,
        }
        self._mutation_weights: Dict[str, float] = {
            "ADD:Node": 0.450,
            "ADD:Edge": 0.400,
            "REFACTOR:Decycle": 0.650,
            "REFACTOR:Normalize": 0.550,
            "ADVERSARIAL:Perturb": 0.100,
        }

    # -- representation -----------------------------------------------------

    def parse(self, source: str) -> Dict[str, Any]:
        return _parse_market(source)

    def unparse(self, rep: Dict[str, Any]) -> str:
        return _unparse_market(rep)

    def is_valid(self, source: str) -> bool:
        try:
            _parse_market(source)
            return True
        except Exception:
            return False

    # -- coherence ----------------------------------------------------------

    def coherence(self, source: str) -> float:
        return self.compute_components(source)["composite"]

    def compute_components(self, source: str) -> Dict[str, float]:
        try:
            rep = _parse_market(source)
        except Exception:
            return {
                "acyclicity": 0.0,
                "degree_consistency": 0.0,
                "edge_coverage": 0.0,
                "composite": 0.0,
            }

        n = len(rep["nodes"])
        e = len(rep["edges"])

        # Component 1: acyclicity — fraction of edges off the cyclic residue.
        cyclic = _cyclic_edge_count(rep)
        acyclicity = 1.0 - (cyclic / e) if e else 1.0

        # Component 2: degree consistency — 1 / (1 + variance).
        degs = list(_degrees(rep).values())
        consistency = 1.0 / (1.0 + float(np.var(degs))) if len(degs) > 1 else 1.0

        # Component 3: edge coverage — ~φ edges per node saturates at 1.
        coverage = min(1.0, e / max(1.0, n * (1.0 - PHI) * 4.0))

        composite = float(np.clip((acyclicity + consistency + coverage) / 3.0, 0.0, 1.0))
        return {
            "acyclicity": float(acyclicity),
            "degree_consistency": float(consistency),
            "edge_coverage": float(coverage),
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
        Dependency-graph test battery: the graph must parse, contain no
        directed cycles, be weakly connected, and carry finite weights.
        """
        try:
            rep = _parse_market(source)
        except Exception:
            return False
        if _cyclic_edge_count(rep) > 0:
            return False
        if not _weakly_connected(rep):
            return False
        return all(math.isfinite(e["weight"]) for e in rep["edges"])

    # -- features -----------------------------------------------------------

    def features(self, source: str) -> np.ndarray:
        """
        8-dimensional dependency-graph feature basis:
        log nodes, longest path, node count, edge count, cyclic edges,
        density, source-node ratio, coherence.
        """
        try:
            rep = _parse_market(source)
            n = len(rep["nodes"])
            e = len(rep["edges"])
            indeg = {nd: 0 for nd in rep["nodes"]}
            for ed in rep["edges"]:
                indeg[ed["dst"]] += 1
            sources = sum(1 for nd in rep["nodes"] if indeg[nd] == 0)
            return np.array(
                [
                    math.log1p(n),
                    float(_longest_path(rep)),
                    float(n),
                    float(e),
                    float(_cyclic_edge_count(rep)),
                    min(1.0, e / max(1, n * (n - 1))),
                    sources / max(1, n),
                    self.coherence(source),
                ],
                dtype=float,
            )
        except Exception:
            return np.zeros(8, dtype=float)

    # -- hooks --------------------------------------------------------------

    def normalize(self, source: str) -> str:
        try:
            rep = _parse_market(source)
            return _unparse_market(rep)
        except Exception:
            return source

    def sample_source(self) -> str:
        return (
            "GDP -> CPI 0.8\n"
            "CPI -> RATES 0.6\n"
            "RATES -> EQUITIES 0.7\n"
            "OIL -> CPI 0.3\n"
            "EQUITIES -> VOLATILITY 0.5\n"
        )
