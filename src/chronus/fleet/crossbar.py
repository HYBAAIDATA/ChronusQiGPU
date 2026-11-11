# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""H4 600-cell crossbar used to order work stealing between fleet nodes (spec 2.2, P2).

The graph is the exact 120-vertex, 720-edge 600-cell built by the existing
``chronus.ns_dec.build_h4_600_cell_polytope`` (the module that
``chronus.geodesic.routing`` exports). Everything the fleet relies on is
computed from that graph rather than asserted: vertex degree, triangular
faces and tetrahedral cells (cliques of size 3 and 4), shortest geodesics and
the diameter, which resolves placeholder P2 (MAX_H4_DIAMETER).

Each node is placed on a vertex. An idle node steals queued work from other
nodes in order of geodesic distance, so thieves spread across victims
deterministically instead of all draining the same queue. The crossbar is a
scheduling topology over a LAN or WAN; it is not a hardware interconnect and
carries no bandwidth claim.
"""

from __future__ import annotations

import hashlib
from collections import deque
from functools import lru_cache
from typing import Any, Iterable, Mapping, Sequence

from chronus.fleet.errors import FleetError


class CrossbarError(FleetError, ValueError):
    """A route was requested to or from a point that is not a 600-cell vertex."""


@lru_cache(maxsize=1)
def _topology() -> dict[str, Any]:
    from chronus.ns_dec import build_h4_600_cell_polytope

    topology = build_h4_600_cell_polytope()
    count = topology["vertices"]
    adjacency: list[set[int]] = [set() for _ in range(count)]
    for u, v in topology["edge_index_pairs"]:
        adjacency[u].add(v)
        adjacency[v].add(u)
    distances = [_bfs(adjacency, source) for source in range(count)]
    triangles = sum(
        len(adjacency[u] & adjacency[v]) for u in range(count) for v in adjacency[u] if u < v
    ) // 3
    cells = 0
    for u in range(count):
        for v in adjacency[u]:
            if v <= u:
                continue
            common = adjacency[u] & adjacency[v]
            cells += sum(1 for w in common if w > v for x in common & adjacency[w] if x > w)
    return {
        "vertices": count,
        "edges": len(topology["edge_index_pairs"]),
        "degrees": tuple(sorted({len(a) for a in adjacency})),
        "faces": triangles,
        "cells": cells,
        "adjacency": tuple(frozenset(a) for a in adjacency),
        "distances": tuple(tuple(row) for row in distances),
        "diameter": max(max(row) for row in distances),
    }


def _bfs(adjacency: Sequence[Iterable[int]], source: int) -> list[int]:
    dist = [-1] * len(adjacency)
    dist[source] = 0
    queue = deque([source])
    while queue:
        u = queue.popleft()
        for v in sorted(adjacency[u]):
            if dist[v] < 0:
                dist[v] = dist[u] + 1
                queue.append(v)
    if min(dist) < 0:
        raise CrossbarError("the 600-cell graph is not connected")
    return dist


def max_h4_diameter() -> int:
    """P2: the diameter of the 600-cell graph, computed by breadth-first search."""
    return _topology()["diameter"]


def geometry_report() -> dict[str, Any]:
    """Counts computed from the graph (ASSERT_ONCE H4_GEOMETRY_VERIFIED, as far as a graph can show)."""
    t = _topology()
    return {
        "vertices": t["vertices"],
        "edges": t["edges"],
        "vertex_degrees": list(t["degrees"]),
        "triangular_faces": t["faces"],
        "tetrahedral_cells": t["cells"],
        "diameter": t["diameter"],
        "coxeter_group_order": "14400 per the spec; not recomputed from the graph",
    }


class H4Crossbar:
    """Places nodes on 600-cell vertices and routes along shortest geodesics."""

    def __init__(self) -> None:
        t = _topology()
        self._adjacency = t["adjacency"]
        self._distances = t["distances"]
        self.vertex_count = t["vertices"]
        self.diameter = t["diameter"]
        self._placement: dict[str, int] = {}

    def _check(self, vertex: Any) -> int:
        if not isinstance(vertex, int) or isinstance(vertex, bool) or not 0 <= vertex < self.vertex_count:
            raise CrossbarError(f"{vertex!r} is not a 600-cell vertex index")
        return vertex

    def place(self, node_id: str) -> int:
        """Deterministic placement: hash to a vertex, then the nearest free vertex by index."""
        if node_id in self._placement:
            return self._placement[node_id]
        start = int.from_bytes(hashlib.sha256(node_id.encode("utf-8")).digest()[:8], "big") % self.vertex_count
        taken = set(self._placement.values())
        vertex = start
        if len(taken) < self.vertex_count:
            for step in range(self.vertex_count):
                candidate = (start + step) % self.vertex_count
                if candidate not in taken:
                    vertex = candidate
                    break
        self._placement[node_id] = vertex
        return vertex

    def release(self, node_id: str) -> None:
        self._placement.pop(node_id, None)

    def placed(self, node_id: str) -> bool:
        return node_id in self._placement

    def vertex_of(self, node_id: str) -> int:
        return self._placement[node_id]

    def distance(self, src: int, dst: int) -> int:
        return self._distances[self._check(src)][self._check(dst)]

    def route(self, src: int, dst: int) -> list[int]:
        """Shortest geodesic src -> dst; ties broken towards the lowest vertex index."""
        src, dst = self._check(src), self._check(dst)
        path = [src]
        while path[-1] != dst:
            here = path[-1]
            path.append(min(v for v in self._adjacency[here] if self._distances[v][dst] == self._distances[here][dst] - 1))
        if len(path) - 1 > self.diameter:
            raise CrossbarError("route longer than the 600-cell diameter")
        for u, v in zip(path, path[1:]):
            if v not in self._adjacency[u]:
                raise CrossbarError("route uses a non-edge")
        return path

    def steal_order(self, thief: str, victims: Mapping[str, int]) -> list[str]:
        """Victims ordered by geodesic distance from the thief, then by node id."""
        origin = self._placement.get(thief)
        if origin is None:
            origin = self.place(thief)
        return sorted(victims, key=lambda node: (self.distance(origin, victims[node]), node))
