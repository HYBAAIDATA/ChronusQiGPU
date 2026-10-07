"""Operational topological/geometric intelligence — §32.

The question the brief asks: what can topology/geometry ANSWER
operationally? On a declared state-transition graph the answers are
concrete and checkable: connected components, reachability, boundary
states, articulation/bottleneck states, path existence — questions a
feature-distance baseline cannot answer (two states can be
metric-close and topologically disconnected, e.g. separated by a wall).

``StateTopology`` is domain-general: feed any transition relation.
``reachability_task`` is the ground-truth test harness comparing it to
the honest non-topological baseline (greedy Euclidean descent), which
fails exactly when geometry is not topology.

``TopologicalAnalytics`` is the point-cloud side: Vietoris-Rips homology
(Betti numbers over GF(2)) at a declared scale. Its canonical home is
here; ``millennium.yang_mills_data`` re-exports it.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

import numpy as np

TOPOLOGY_VERSION = "toe.topology/v1"


class StateTopology:
    """Discrete topology over a declared transition relation.

    ``states``: hashable state identifiers. ``transitions``: iterable of
    (from, to) directed edges — the system's neighbourhood structure.
    """

    def __init__(
        self,
        states: List[Any],
        transitions: List[Tuple[Any, Any]],
    ) -> None:
        self.states = list(states)
        self.adj: Dict[Any, Set[Any]] = {s: set() for s in states}
        self.rev: Dict[Any, Set[Any]] = {s: set() for s in states}
        for a, b in transitions:
            self.adj.setdefault(a, set()).add(b)
            self.rev.setdefault(b, set()).add(a)
            self.adj.setdefault(b, set())
            self.rev.setdefault(a, set())

    def components(self) -> List[Set[Any]]:
        """Weakly-connected components of the state space."""
        seen: Set[Any] = set()
        comps: List[Set[Any]] = []
        for s in self.states:
            if s in seen:
                continue
            comp: Set[Any] = set()
            q = deque([s])
            while q:
                u = q.popleft()
                if u in comp:
                    continue
                comp.add(u)
                q.extend(self.adj.get(u, ()) | self.rev.get(u, ()) - comp)
            comps.append(comp)
            seen |= comp
        return comps

    def reachable(self, source: Any) -> Set[Any]:
        """Directed reachability — states enterable from ``source``."""
        seen: Set[Any] = set()
        q = deque([source])
        while q:
            u = q.popleft()
            if u in seen:
                continue
            seen.add(u)
            q.extend(self.adj.get(u, ()) - seen)
        return seen

    def path_exists(self, source: Any, target: Any) -> bool:
        return target in self.reachable(source)

    def shortest_path(self, source: Any, target: Any) -> Optional[List[Any]]:
        q = deque([(source, [source])])
        seen = {source}
        while q:
            u, path = q.popleft()
            if u == target:
                return path
            for v in self.adj.get(u, ()) - seen:
                seen.add(v)
                q.append((v, path + [v]))
        return None

    def boundary_states(self) -> List[Any]:
        """Frontier states: have an outgoing edge but no incoming one
        (entry-only boundaries), or vice-versa (exit-only)."""
        return [
            s
            for s in self.states
            if bool(self.adj.get(s)) != bool(self.rev.get(s))
        ]

    def articulation_points(self) -> List[Any]:
        """States whose removal increases the component count — the
        bottlenecks any plan crossing components must pass through."""
        base = len(self.components())
        out = []
        for s in self.states:
            rest = [x for x in self.states if x != s]
            sub = StateTopology(
                rest,
                [(a, b) for a, outs in self.adj.items()
                 for b in outs if a != s and b != s],
            )
            if len(sub.components()) > base:
                out.append(s)
        return out


def reachability_task(
    states: List[Any],
    transitions: List[Tuple[Any, Any]],
    source: Any,
    target: Any,
    *,
    coords: Optional[Mapping[Any, Tuple[float, float]]] = None,
) -> Dict[str, Any]:
    """Ground-truth task: is ``target`` reachable from ``source``?

    The topological answer is exact (directed reachability). The
    non-topological baseline is greedy Euclidean descent on ``coords``:
    it declares reachability iff greedy descent reaches the target —
    and fails on wall-separated points where geometry misleads.
    """
    topo = StateTopology(states, transitions)
    truth = topo.path_exists(source, target)
    path = topo.shortest_path(source, target)

    baseline_answer: Optional[bool] = None
    baseline_path: Optional[List[Any]] = None
    if coords is not None:
        cur, seen_b, walk = source, {source}, [source]
        while cur != target:
            nxt = min(
                (n for n in topo.adj.get(cur, set()) if n not in seen_b),
                key=lambda n: (coords[n][0] - coords[target][0]) ** 2
                + (coords[n][1] - coords[target][1]) ** 2,
                default=None,
            )
            if nxt is None:
                break
            seen_b.add(nxt)
            walk.append(nxt)
            cur = nxt
        baseline_answer = cur == target
        baseline_path = walk
    return {
        "version": TOPOLOGY_VERSION,
        "reachable": truth,
        "topological_path": path,
        "baseline_answer": baseline_answer,
        "baseline_path": baseline_path,
        "baseline_correct": (
            baseline_answer == truth if baseline_answer is not None else None
        ),
        "components": [sorted(c, key=str) for c in topo.components()],
        "articulation_points": topo.articulation_points(),
    }


class TopologicalAnalytics:
    """Topological analytics: simplicial complexes and persistent homology.

    Builds a Vietoris-Rips simplicial complex from a point cloud at scale
    ``epsilon`` and computes the first three Betti numbers (b0 connected
    components, b1 loops, b2 voids) via integer rank reductions of the
    boundary matrices. The Euler characteristic and a topological complexity
    measure are reported alongside.
    """

    def __init__(self, manifold_dimension: int = 5):
        self.manifold_dimension = int(manifold_dimension)
        self.last_complex: Optional[Dict[str, Any]] = None

    def construct_simplicial_complex(self, points: np.ndarray, epsilon: float) -> Dict[str, Any]:
        """Construct the Vietoris-Rips complex up to dimension 2.

        Returns a dict with the simplices (vertices, edges, triangles, tetrahedra)
        and the pairwise distance matrix.
        """
        P = np.asarray(points, dtype=float)
        if P.ndim == 1:
            P = P.reshape(-1, 1)
        n = P.shape[0]
        # Pairwise distances.
        diff = P[:, None, :] - P[None, :, :]
        dist = np.linalg.norm(diff, axis=2)
        edges = [(i, j) for i in range(n) for j in range(i + 1, n) if dist[i, j] <= epsilon]
        # Triangles: (i,j,k) all pairwise within epsilon.
        triangles: list[tuple[int, int, int]] = []
        for i in range(n):
            for j in range(i + 1, n):
                if dist[i, j] > epsilon:
                    continue
                for k in range(j + 1, n):
                    if dist[i, k] <= epsilon and dist[j, k] <= epsilon:
                        triangles.append((i, j, k))
        # Tetrahedra: all 6 pairwise within epsilon.
        tetrahedra: list[tuple[int, int, int, int]] = []
        for i in range(n):
            for j in range(i + 1, n):
                if dist[i, j] > epsilon:
                    continue
                for k in range(j + 1, n):
                    if not (dist[i, k] <= epsilon and dist[j, k] <= epsilon):
                        continue
                    for l in range(k + 1, n):
                        if (
                            dist[i, l] <= epsilon
                            and dist[j, l] <= epsilon
                            and dist[k, l] <= epsilon
                        ):
                            tetrahedra.append((i, j, k, l))
        complex_data = {
            "vertices": list(range(n)),
            "edges": edges,
            "triangles": triangles,
            "tetrahedra": tetrahedra,
            "distances": dist,
        }
        self.last_complex = complex_data
        return complex_data

    def compute_persistent_homology(self, points: np.ndarray, epsilon: float) -> Dict[str, Any]:
        """Compute Betti numbers b0, b1, b2 for the VR complex at epsilon.

        Uses integer boundary-matrix rank reduction (Smith normal form is
        overkill for the small complexes we build; we use Gaussian elimination
        over GF(2) on the boundary matrices).
        """
        cx = self.construct_simplicial_complex(points, epsilon)
        vertices = cx["vertices"]
        edges = cx["edges"]
        triangles = cx["triangles"]
        tetrahedra = cx["tetrahedra"]

        def _rank_gf2(M: np.ndarray) -> int:
            if M.size == 0:
                return 0
            A = np.array(M, dtype=np.int8) % 2
            rows, cols = A.shape
            rank = 0
            for col in range(cols):
                pivot = None
                for row in range(rank, rows):
                    if A[row, col]:
                        pivot = row
                        break
                if pivot is None:
                    continue
                A[[rank, pivot]] = A[[pivot, rank]]
                for row in range(rows):
                    if row != rank and A[row, col]:
                        A[row] = (A[row] + A[rank]) % 2
                rank += 1
                if rank == rows:
                    break
            return rank

        # Boundary matrices over GF(2).
        # d1: edges -> vertices
        d1 = np.zeros((len(vertices), len(edges)), dtype=np.int8)
        for j, (i, k) in enumerate(edges):
            d1[i, j] = 1
            d1[k, j] = 1
        # d2: triangles -> edges
        edge_index = {e: idx for idx, e in enumerate(edges)}
        d2 = np.zeros((len(edges), len(triangles)), dtype=np.int8)
        for j, (a, b, c) in enumerate(triangles):
            for u, v in ((a, b), (a, c), (b, c)):
                if (u, v) in edge_index:
                    d2[edge_index[(u, v)], j] = 1
        # d3: tetrahedra -> triangles
        tri_index = {t: idx for idx, t in enumerate(triangles)}
        d3 = np.zeros((len(triangles), len(tetrahedra)), dtype=np.int8)
        for j, (a, b, c, d) in enumerate(tetrahedra):
            for u, v, w in ((a, b, c), (a, b, d), (a, c, d), (b, c, d)):
                if (u, v, w) in tri_index:
                    d3[tri_index[(u, v, w)], j] = 1

        rank_d1 = _rank_gf2(d1)
        rank_d2 = _rank_gf2(d2)
        rank_d3 = _rank_gf2(d3)

        b0 = len(vertices) - rank_d1
        b1 = len(edges) - rank_d1 - rank_d2
        b2 = len(triangles) - rank_d2 - rank_d3
        b0 = max(0, b0)
        b1 = max(0, b1)
        b2 = max(0, b2)
        euler = b0 - b1 + b2

        points_arr = np.asarray(points, dtype=float)
        complexity = float(np.linalg.norm(points_arr)) if points_arr.size else 0.0

        return {
            "betti_numbers": {"b0": int(b0), "b1": int(b1), "b2": int(b2)},
            "euler_characteristic": int(euler),
            "topological_complexity": complexity,
            "n_vertices": len(vertices),
            "n_edges": len(edges),
            "n_triangles": len(triangles),
            "n_tetrahedra": len(tetrahedra),
        }


__all__ = [
    "TOPOLOGY_VERSION",
    "TopologicalAnalytics",
    "StateTopology",
    "reachability_task",
]
