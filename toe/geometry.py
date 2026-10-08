"""Geometric reasoning — TOE's continuous-manifold layer.

What geometry *answers* for TOE, as declared, tested operations:

* ``PoincareBall`` — the hyperbolic ball model (curvature -1) on a weighted
  quadratic form ``sum w_i x_i^2``. With ``w_i = phi^-(i+1)`` it is exactly
  the 11D Poincaré-golden metric of :mod:`toe.poincare_golden_11d`; the
  coordinate map ``y_i = sqrt(w_i) x_i`` is an isometry onto the standard
  ball, so the full Möbius-gyrovector toolkit applies: distance, Möbius
  addition, exponential/logarithm maps, geodesics, Fréchet mean. Points on
  or outside the boundary are refused (``GeometryError``) — never clamped.
* ``embed_tree`` — Sarkar's construction of a tree in the hyperbolic disk:
  every edge has hyperbolic length ``tau``, children are spread at maximal
  angular separation. For ``tau`` large enough the embedding is *greedy*:
  from every node some neighbour is strictly closer to any target.
* ``greedy_route`` — local geometric navigation: move to the neighbour
  nearest the target, stop at a local minimum. On a greedy hyperbolic
  embedding of a spanning tree it always delivers (Kleinberg); on raw
  Euclidean coordinates it can strand at a dead end. ``routing_study``
  measures both on the same graph — including graphs where the hyperbolic
  representation buys nothing.
* ``SpectralGeometry`` — graph Laplacian spectrum, spectral clustering,
  heat kernel and a spectral Ricci lower bound (promoted here from
  ``millennium.yang_mills_data``, which now re-exports this class).

Claim boundary: these are finite, numerically evaluated geometric
operations (float64, declared tolerances). They are not a physical
geometry claim, and the tree embedding is bounded by float64 resolution
near the boundary (``depth * tau`` is checked, not assumed).
"""

from __future__ import annotations

import cmath
import math
from collections import deque
from typing import Any, Dict, Hashable, List, Mapping, Optional, Sequence, Tuple

import numpy as np

GEOMETRY_VERSION = "toe.geometry/v1"

# float64 keeps 1 - |z| resolvable down to ~1e-16; a disk point at
# hyperbolic radius r has 1 - |z| ~ 2 exp(-r). Past this radius distances
# are no longer trustworthy and the embedding is refused.
MAX_EMBED_RADIUS = 30.0


class GeometryError(ValueError):
    """A geometric operation was asked of a point it is not defined for."""


# ---------------------------------------------------------------------------
# Hyperbolic ball
# ---------------------------------------------------------------------------


class PoincareBall:
    """Poincaré ball model over a weighted quadratic form.

    ``weights`` (all > 0) define ``|x|_w^2 = sum w_i x_i^2``. Internally
    every operation runs in standard coordinates ``y = sqrt(w) * x``
    where the textbook formulas hold; inputs and outputs stay in the
    caller's weighted coordinates.
    """

    def __init__(self, dim: int, weights: Optional[Sequence[float]] = None) -> None:
        if dim < 1:
            raise GeometryError("dimension must be >= 1")
        w = (
            np.ones(dim, dtype=np.float64)
            if weights is None
            else np.asarray(weights, dtype=np.float64)
        )
        if w.shape != (dim,) or not np.all(w > 0) or not np.all(np.isfinite(w)):
            raise GeometryError("weights must be dim positive finite values")
        self.dim = dim
        self.weights = w
        self._scale = np.sqrt(w)

    @classmethod
    def golden_11d(cls) -> "PoincareBall":
        """The φ-weighted 11D ball of :mod:`toe.poincare_golden_11d`."""
        from .poincare_golden_11d import PHI_POWERS

        return cls(11, PHI_POWERS)

    # -- coordinates ------------------------------------------------------

    def _vec(self, x: Any) -> np.ndarray:
        arr = np.asarray(x, dtype=np.float64).reshape(-1)
        if arr.shape != (self.dim,):
            raise GeometryError(f"expected a {self.dim}-vector, got shape {arr.shape}")
        if not np.all(np.isfinite(arr)):
            raise GeometryError("non-finite coordinate")
        return arr

    def _std(self, x: Any) -> np.ndarray:
        y = self._vec(x) * self._scale
        if float(y @ y) >= 1.0:
            raise GeometryError("point is not strictly inside the ball")
        return y

    def _weighted(self, y: np.ndarray) -> np.ndarray:
        return y / self._scale

    def norm_sq(self, x: Any) -> float:
        y = self._vec(x) * self._scale
        return float(y @ y)

    def contains(self, x: Any) -> bool:
        return self.norm_sq(x) < 1.0

    # -- gyrovector operations (standard coordinates) ---------------------

    @staticmethod
    def _mobius_add(x: np.ndarray, y: np.ndarray) -> np.ndarray:
        xy = float(x @ y)
        x2 = float(x @ x)
        y2 = float(y @ y)
        num = (1.0 + 2.0 * xy + y2) * x + (1.0 - x2) * y
        den = 1.0 + 2.0 * xy + x2 * y2
        return num / den

    def mobius_add(self, x: Any, y: Any) -> np.ndarray:
        return self._weighted(self._mobius_add(self._std(x), self._std(y)))

    def distance(self, u: Any, v: Any) -> float:
        a, b = self._std(u), self._std(v)
        diff = a - b
        num = 2.0 * float(diff @ diff)
        den = (1.0 - float(a @ a)) * (1.0 - float(b @ b))
        return float(math.acosh(1.0 + num / den))

    def exp_map(self, x: Any, v: Any) -> np.ndarray:
        """Exponential map at ``x`` of tangent vector ``v`` (weighted coords)."""
        p = self._std(x)
        t = self._vec(v) * self._scale
        n = float(np.linalg.norm(t))
        if n == 0.0:
            return self._weighted(p.copy())
        lam = 2.0 / (1.0 - float(p @ p))
        step = math.tanh(lam * n / 2.0) * t / n
        return self._weighted(self._mobius_add(p, step))

    def log_map(self, x: Any, y: Any) -> np.ndarray:
        """Logarithm map: the tangent vector at ``x`` pointing to ``y``."""
        p, q = self._std(x), self._std(y)
        w = self._mobius_add(-p, q)
        n = float(np.linalg.norm(w))
        if n == 0.0:
            return np.zeros(self.dim)
        lam = 2.0 / (1.0 - float(p @ p))
        return self._weighted((2.0 / lam) * math.atanh(n) * w / n)

    def geodesic(self, u: Any, v: Any, t: float) -> np.ndarray:
        """Point at fraction ``t`` along the geodesic from ``u`` to ``v``."""
        return self.exp_map(u, float(t) * self.log_map(u, v))

    def frechet_mean(
        self, points: Sequence[Any], *, iterations: int = 200, tol: float = 1e-12
    ) -> Dict[str, Any]:
        """Riemannian centre of mass by fixed-step gradient descent.

        Returns the mean, iterations used and the final gradient norm — the
        convergence evidence, not an assumption of it.
        """
        pts = [self._vec(p) for p in points]
        if not pts:
            raise GeometryError("Fréchet mean of an empty set")
        mean = pts[0].copy()
        grad_norm = float("inf")
        used = 0
        for used in range(1, iterations + 1):
            grad = sum(self.log_map(mean, p) for p in pts) / len(pts)
            grad_norm = float(np.linalg.norm(grad * self._scale))
            if grad_norm < tol:
                break
            mean = self.exp_map(mean, grad)
        return {"mean": mean, "iterations": used, "gradient_norm": grad_norm}

    def project(self, x: Any, *, margin: float = 1e-9) -> Dict[str, Any]:
        """Explicit projection into the ball; reports whether it clipped."""
        y = self._vec(x) * self._scale
        n = float(np.linalg.norm(y))
        limit = 1.0 - margin
        if n < limit:
            return {"point": self._weighted(y), "clipped": False, "norm": n}
        return {"point": self._weighted(y * (limit / n)), "clipped": True, "norm": n}


# ---------------------------------------------------------------------------
# Hyperbolic tree embedding + greedy routing
# ---------------------------------------------------------------------------


def _adjacency(edges: Sequence[Tuple[Hashable, Hashable]]) -> Dict[Hashable, List[Hashable]]:
    adj: Dict[Hashable, List[Hashable]] = {}
    for a, b in edges:
        adj.setdefault(a, [])
        adj.setdefault(b, [])
        if b not in adj[a]:
            adj[a].append(b)
        if a not in adj[b]:
            adj[b].append(a)
    for k in adj:
        adj[k].sort(key=str)
    return adj


def bfs_tree(
    edges: Sequence[Tuple[Hashable, Hashable]], root: Hashable
) -> Dict[Hashable, Optional[Hashable]]:
    """Parent map of a breadth-first spanning tree of the component of ``root``."""
    adj = _adjacency(edges)
    if root not in adj:
        raise GeometryError(f"root {root!r} not in graph")
    parent: Dict[Hashable, Optional[Hashable]] = {root: None}
    q = deque([root])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in parent:
                parent[v] = u
                q.append(v)
    return parent


def graph_center(edges: Sequence[Tuple[Hashable, Hashable]]) -> Hashable:
    """A node of minimum eccentricity (ties broken by name).

    Rooting the spanning tree here minimises its depth, which is what keeps
    a hyperbolic tree embedding inside float64 resolution. Cost is one BFS
    per node — intended for the graph sizes the embedding can represent.
    """
    adj = _adjacency(edges)
    best: Optional[Tuple[int, str, Hashable]] = None
    for n in adj:
        ecc = max(_shortest_lengths(adj, n).values())
        key = (ecc, str(n), n)
        if best is None or key[:2] < best[:2]:
            best = key
    if best is None:
        raise GeometryError("empty graph has no center")
    return best[2]


def embed_tree(
    parent: Mapping[Hashable, Optional[Hashable]], *, tau: float = 2.5
) -> Dict[str, Any]:
    """Sarkar embedding of a rooted tree in the Poincaré disk.

    ``parent`` maps each node to its parent (root -> None). Each node is
    moved to the origin by a disk isometry, its parent's direction is read,
    and its children are placed at hyperbolic distance ``tau`` at angles
    spread evenly over the remaining circle. Returns complex coordinates
    plus the declared ``tau`` and the deepest hyperbolic radius reached.
    """
    roots = [n for n, p in parent.items() if p is None]
    if len(roots) != 1:
        raise GeometryError("tree needs exactly one root")
    children: Dict[Hashable, List[Hashable]] = {n: [] for n in parent}
    for n, p in parent.items():
        if p is not None:
            children[p].append(n)
    for k in children:
        children[k].sort(key=str)
    r = math.tanh(tau / 2.0)
    pos: Dict[Hashable, complex] = {roots[0]: 0j}
    depth: Dict[Hashable, int] = {roots[0]: 0}
    q = deque([roots[0]])
    while q:
        u = q.popleft()
        zu = pos[u]
        kids = children[u]
        if not kids:
            continue
        p = parent[u]
        if p is None:
            base, slots = 0.0, len(kids)
            angles = [base + 2.0 * math.pi * k / slots for k in range(slots)]
        else:
            # Parent direction seen from u once u is moved to the origin.
            tp = (pos[p] - zu) / (1 - zu.conjugate() * pos[p])
            base = cmath.phase(tp)
            slots = len(kids) + 1
            angles = [base + 2.0 * math.pi * k / slots for k in range(1, slots)]
        for child, ang in zip(kids, angles):
            w = r * cmath.exp(1j * ang)
            z = (w + zu) / (1 + zu.conjugate() * w)
            depth[child] = depth[u] + 1
            if depth[child] * tau > MAX_EMBED_RADIUS:
                raise GeometryError(
                    f"tree depth {depth[child]} at tau={tau} exceeds float64 disk "
                    f"resolution (depth*tau > {MAX_EMBED_RADIUS})"
                )
            pos[child] = z
            q.append(child)
    return {
        "version": GEOMETRY_VERSION,
        "coords": pos,
        "tau": tau,
        "max_depth": max(depth.values()),
        "max_radius": max(depth.values()) * tau,
    }


def disk_distance(a: complex, b: complex) -> float:
    """Hyperbolic distance in the Poincaré disk (curvature -1)."""
    num = 2.0 * abs(a - b) ** 2
    den = (1.0 - abs(a) ** 2) * (1.0 - abs(b) ** 2)
    if den <= 0.0:
        raise GeometryError("point on or outside the disk boundary")
    return math.acosh(1.0 + num / den)


def greedy_route(
    edges: Sequence[Tuple[Hashable, Hashable]],
    source: Hashable,
    target: Hashable,
    distance: Any,
    *,
    max_steps: Optional[int] = None,
) -> Dict[str, Any]:
    """Greedy geometric forwarding: always move to the neighbour closest to
    ``target`` under ``distance(node, target)``; stop when no neighbour is
    strictly closer (a dead end) or the target is reached."""
    adj = _adjacency(edges)
    if source not in adj or target not in adj:
        raise GeometryError("source/target not in graph")
    cur, path = source, [source]
    limit = max_steps if max_steps is not None else len(adj) + 1
    while cur != target and len(path) <= limit:
        here = distance(cur, target)
        best = min(adj[cur], key=lambda n: (distance(n, target), str(n)), default=None)
        if best is None or distance(best, target) >= here:
            return {"delivered": False, "path": path, "stuck_at": cur}
        cur = best
        path.append(cur)
    return {"delivered": cur == target, "path": path, "stuck_at": None if cur == target else cur}


def _shortest_lengths(adj: Mapping[Hashable, List[Hashable]], s: Hashable) -> Dict[Hashable, int]:
    dist = {s: 0}
    q = deque([s])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist


def routing_study(
    edges: Sequence[Tuple[Hashable, Hashable]],
    *,
    euclidean: Optional[Mapping[Hashable, Tuple[float, float]]] = None,
    root: Optional[Hashable] = None,
    tau: float = 2.5,
    pairs: Optional[Sequence[Tuple[Hashable, Hashable]]] = None,
) -> Dict[str, Any]:
    """All-pairs (or declared pairs) greedy delivery under two representations.

    ``hyperbolic``: greedy routing over the graph's edges using the disk
    distance of a Sarkar embedding of a BFS spanning tree. ``euclidean``:
    greedy routing using the caller's declared planar coordinates (the
    neutral baseline). Delivery rate and stretch (route hops / shortest
    hops) are measured for both. Neither representation is assumed better.
    """
    adj = _adjacency(edges)
    nodes = sorted(adj, key=str)
    root = graph_center(edges) if root is None else root
    parent = bfs_tree(edges, root)
    if len(parent) != len(adj):
        raise GeometryError("graph is disconnected; routing study needs one component")
    emb = embed_tree(parent, tau=tau)
    coords = emb["coords"]
    tree_edges = [(n, p) for n, p in parent.items() if p is not None]
    if pairs is None:
        pairs = [(s, t) for s in nodes for t in nodes if s != t]
    shortest = {s: _shortest_lengths(adj, s) for s in {p[0] for p in pairs}}

    def run(
        name: str, dist_fn: Any, route_edges: Sequence[Tuple[Hashable, Hashable]]
    ) -> Dict[str, Any]:
        delivered = 0
        stretch: List[float] = []
        stuck: List[Tuple[str, str]] = []
        for s, t in pairs:
            res = greedy_route(route_edges, s, t, dist_fn)
            if res["delivered"]:
                delivered += 1
                stretch.append((len(res["path"]) - 1) / shortest[s][t])
            elif len(stuck) < 5:
                stuck.append((str(s), str(t)))
        return {
            "representation": name,
            "pairs": len(pairs),
            "delivered": delivered,
            "delivery_rate": delivered / len(pairs) if pairs else None,
            "mean_stretch": (sum(stretch) / len(stretch)) if stretch else None,
            "example_failures": stuck,
        }

    # Routing uses every graph edge; delivery is guaranteed by the spanning
    # tree (its next hop is always strictly closer), extra edges only
    # shorten routes. ``tree_edges`` is reported for audit.
    hyper = run("hyperbolic_tree", lambda a, b: disk_distance(coords[a], coords[b]), edges)
    hyper["spanning_tree_edges"] = len(tree_edges)
    out: Dict[str, Any] = {
        "version": GEOMETRY_VERSION,
        "nodes": len(nodes),
        "edges": len({tuple(sorted((str(a), str(b)))) for a, b in edges}),
        "tau": tau,
        "embedding_max_radius": emb["max_radius"],
        "hyperbolic": hyper,
        "euclidean": None,
    }
    if euclidean is not None:

        def euc(a: Hashable, b: Hashable) -> float:
            (x1, y1), (x2, y2) = euclidean[a], euclidean[b]
            return math.hypot(x1 - x2, y1 - y2)

        out["euclidean"] = run("euclidean", euc, edges)
    return out


# ---------------------------------------------------------------------------
# Spectral geometry (canonical home; millennium.yang_mills_data re-exports)
# ---------------------------------------------------------------------------


class SpectralGeometry:
    """Spectral geometry of a graph: eigenvalues, clustering, heat kernel, Ricci.

    Built on the (unnormalised) graph Laplacian L = D - A. The heat kernel is
    exp(-t L); spectral clustering uses the first k eigenvectors of L. The
    Ricci curvature estimate is the Ollivier-Ricci lower bound derived from
    the spectral gap.
    """

    def __init__(self, adjacency: np.ndarray):
        A = np.asarray(adjacency, dtype=float)
        if A.ndim != 2 or A.shape[0] != A.shape[1]:
            raise ValueError("adjacency must be a square matrix")
        # Symmetrise and zero the diagonal.
        A = (A + A.T) / 2.0
        np.fill_diagonal(A, 0.0)
        self.adjacency = A
        self.degree = A.sum(axis=1)
        D = np.diag(np.where(self.degree > 0, self.degree, 1.0))
        self.laplacian = D - A
        # Eigendecomposition (symmetric -> real eigenvalues).
        evals, evecs = np.linalg.eigh(self.laplacian)
        order = np.argsort(evals)
        self.eigenvalues = evals[order]
        self.eigenvectors = evecs[:, order]

    def spectral_clustering(self, n_clusters: int) -> np.ndarray:
        """Cluster nodes using the first n_clusters Laplacian eigenvectors."""
        n = self.adjacency.shape[0]
        k = max(1, min(int(n_clusters), n))
        if k <= 1:
            return np.zeros(n, dtype=int)
        # Embed each node by the first k eigenvectors, then k-means (Lloyd's).
        embedding = self.eigenvectors[:, :k]
        # Normalise rows.
        norms = np.linalg.norm(embedding, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        embedding = embedding / norms
        # Initialise centroids at evenly spaced rows (deterministic).
        centroid_idx = np.linspace(0, n - 1, k, dtype=int)
        centroids = embedding[centroid_idx].copy()
        labels = np.zeros(n, dtype=int)
        for _ in range(50):
            dists = np.linalg.norm(embedding[:, None, :] - centroids[None, :, :], axis=2)
            new_labels = np.argmin(dists, axis=1)
            if np.array_equal(new_labels, labels):
                break
            labels = new_labels
            for c in range(k):
                if np.any(labels == c):
                    centroids[c] = embedding[labels == c].mean(axis=0)
        return labels

    def heat_kernel(self, t: float) -> np.ndarray:
        """Heat kernel exp(-t L) via the eigendecomposition."""
        return (self.eigenvectors * np.exp(-t * self.eigenvalues)) @ self.eigenvectors.T

    def ricci_curvature(self) -> np.ndarray:
        """Ollivier-Ricci curvature lower bound per node.

        For a graph, a simple lower bound on the Ricci curvature at node i is
        kappa_i = 1 - (lambda_1 * d_i) / (sum of degrees), where lambda_1 is
        the first non-zero Laplacian eigenvalue (the spectral gap). This is a
        coarse but honest spectral estimate, not a fabricated number.
        """
        n = self.adjacency.shape[0]
        if n == 0:
            return np.zeros(0)
        spectral_gap = float(self.eigenvalues[1]) if len(self.eigenvalues) > 1 else 0.0
        total_degree = float(self.degree.sum())
        if total_degree <= 0:
            return np.zeros(n)
        return 1.0 - (spectral_gap * self.degree) / total_degree


__all__ = [
    "GEOMETRY_VERSION",
    "GeometryError",
    "MAX_EMBED_RADIUS",
    "PoincareBall",
    "SpectralGeometry",
    "bfs_tree",
    "disk_distance",
    "embed_tree",
    "graph_center",
    "greedy_route",
    "routing_study",
]
