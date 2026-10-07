"""Planar surface code over GF(2): exact algebra, exact distance, decoders.

The distance-d planar code is the hypergraph product of two length-d
repetition codes (H the (d-1) x d parity-check matrix):

    Hx = [H (x) I_d | I_(d-1) (x) H^T]      (d-1)d X checks
    Hz = [I_d (x) H | H^T (x) I_(d-1)]      d(d-1) Z checks

on n = d^2 + (d-1)^2 qubits, with k = n - rank Hx - rank Hz = 1. Pauli
operators are GF(2) vectors (Python int bitsets); commutation is the parity
of the shared support. Everything here is decided, not sampled:

* every X/Z check pair commutes;
* the logicals commute with every check, anticommute with each other, and
  are not stabilizers;
* the distance is computed exactly as the shortest odd-parity boundary walk
  in the matching graph (parity BFS), so ``correction_bound = (d - 1) // 2``
  is a theorem for any minimum-weight decoder.

Decoders: ``decode_exact`` is minimum-weight matching by subset dynamic
programming (exact, for up to 18 defects); ``decode_union_find`` is the
Delfosse-Nickerson union-find decoder, which scales.

``edge_star_report`` reproduces the convention with a star on every vertex
and a plaquette on every face of a (d+1) x (d+1) grid: its checks commute
((d+1)^2 d^2 pairs) but rank arithmetic gives k = 0, so it encodes no
logical qubit and its distance and correction bound are undefined.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple


class SurfaceCodeError(ValueError):
    """A surface-code contract was violated or a decoder cannot run."""


def popcount(x: int) -> int:
    return bin(x).count("1")


def gf2_rank(rows: Sequence[int]) -> int:
    pivots: Dict[int, int] = {}
    rank = 0
    for r in rows:
        while r:
            h = r.bit_length() - 1
            if h in pivots:
                r ^= pivots[h]
            else:
                pivots[h] = r
                rank += 1
                break
    return rank


def in_span(rows: Sequence[int], vector: int) -> bool:
    return gf2_rank(list(rows) + [vector]) == gf2_rank(rows)


def _repetition(d: int) -> List[List[int]]:
    return [[1 if j in (i, i + 1) else 0 for j in range(d)] for i in range(d - 1)]


def _kron(a: List[List[int]], b: List[List[int]]) -> List[List[int]]:
    return [
        [a[i][j] * b[k][l] for j in range(len(a[0])) for l in range(len(b[0]))]
        for i in range(len(a))
        for k in range(len(b))
    ]


def _eye(n: int) -> List[List[int]]:
    return [[int(i == j) for j in range(n)] for i in range(n)]


def _t(m: List[List[int]]) -> List[List[int]]:
    return [list(col) for col in zip(*m)]


def _rows_to_ints(left: List[List[int]], right: List[List[int]]) -> List[int]:
    out = []
    for lr, rr in zip(left, right):
        bits = lr + rr
        out.append(sum(1 << i for i, b in enumerate(bits) if b))
    return out


@dataclass(frozen=True)
class SurfaceCodeReport:
    distance: int
    qubits: int
    x_checks: int
    z_checks: int
    logical_qubits: int
    mixed_pairs_checked: int
    noncommuting_pairs: int
    logicals_commute_with_checks: bool
    logicals_anticommute: bool
    logicals_nontrivial: bool
    exact_x_distance: int
    exact_z_distance: int
    correction_bound: int
    verified: bool
    digest: str


class CSSCode:
    """A CSS code from GF(2) check rows, verified and decoded exactly.

    ``hx`` and ``hz`` are X- and Z-check rows as int bitsets over ``n``
    qubits; ``logical_x`` / ``logical_z`` are declared representatives and
    ``distance`` is the declared distance that ``verify`` must reproduce.
    Exact distance and the decoders need every column of a check matrix to
    have weight 1 or 2 (a matching graph), which holds for surface codes.
    """

    def __init__(
        self,
        n: int,
        hx: Sequence[int],
        hz: Sequence[int],
        logical_x: int,
        logical_z: int,
        distance: int,
    ) -> None:
        self.n = int(n)
        self.hx = list(hx)
        self.hz = list(hz)
        self.logical_x = int(logical_x)
        self.logical_z = int(logical_z)
        self.d = int(distance)
        self._graphs: Dict[str, Tuple] = {}

    # -- algebra -----------------------------------------------------------

    def logical_qubits(self) -> int:
        return self.n - gf2_rank(self.hx) - gf2_rank(self.hz)

    def noncommuting_pairs(self) -> int:
        return sum(1 for x in self.hx for z in self.hz if popcount(x & z) % 2)

    def syndrome(self, checks: Sequence[int], error: int) -> int:
        return sum(1 << i for i, c in enumerate(checks) if popcount(c & error) % 2)

    def _graph(self, kind: str):
        """Matching graph: checks are vertices, qubits are edges; weight-one
        columns get their own boundary vertex."""
        if kind in self._graphs:
            return self._graphs[kind]
        checks = self.hz if kind == "x_errors" else self.hx
        m = len(checks)
        edges: List[Tuple[int, int]] = []
        boundary: List[int] = []
        for q in range(self.n):
            owners = [i for i, c in enumerate(checks) if (c >> q) & 1]
            if len(owners) == 2:
                edges.append((owners[0], owners[1]))
            elif len(owners) == 1:
                b = m + len(boundary)
                boundary.append(b)
                edges.append((owners[0], b))
            else:
                raise SurfaceCodeError("matching graph needs column weight 1 or 2")
        adj: List[List[Tuple[int, int]]] = [[] for _ in range(m + len(boundary))]
        for q, (u, v) in enumerate(edges):
            adj[u].append((v, q))
            adj[v].append((u, q))
        self._graphs[kind] = (m, edges, set(boundary), adj)
        return self._graphs[kind]

    def exact_distance(self, kind: str) -> int:
        """Shortest odd-parity boundary-to-boundary walk (parity BFS), exactly.

        Boundary vertices are terminals of degree one. A walk's parity is its
        overlap with the conjugate logical, so odd walks are exactly the
        nontrivial logical operators and the shortest one is the distance.
        """
        _, _, boundary, adj = self._graph(kind)
        label = self.logical_z if kind == "x_errors" else self.logical_x
        best: Optional[int] = None
        for start in boundary:
            dist: Dict[Tuple[int, int], int] = {}
            queue: deque = deque()
            for v, q in adj[start]:
                state = (v, (label >> q) & 1)
                dist[state] = 1
                queue.append(state)
            while queue:
                node, par = queue.popleft()
                dcur = dist[(node, par)]
                if best is not None and dcur + 1 >= best:
                    continue
                for nxt, q in adj[node]:
                    np_ = par ^ ((label >> q) & 1)
                    if nxt in boundary:
                        if np_ == 1:
                            best = dcur + 1 if best is None else min(best, dcur + 1)
                        continue
                    if (nxt, np_) not in dist:
                        dist[(nxt, np_)] = dcur + 1
                        queue.append((nxt, np_))
        if best is None:
            raise SurfaceCodeError("no nontrivial logical path")
        return best

    def verify(self) -> SurfaceCodeReport:
        k = self.logical_qubits()
        bad = self.noncommuting_pairs()
        lz_ok = all(popcount(self.logical_z & x) % 2 == 0 for x in self.hx)
        lx_ok = all(popcount(self.logical_x & z) % 2 == 0 for z in self.hz)
        anti = popcount(self.logical_x & self.logical_z) % 2 == 1
        nontrivial = not in_span(self.hz, self.logical_z) and not in_span(self.hx, self.logical_x)
        dx, dz = self.exact_distance("x_errors"), self.exact_distance("z_errors")
        unsigned = {
            "distance": self.d,
            "qubits": self.n,
            "x_checks": len(self.hx),
            "z_checks": len(self.hz),
            "logical_qubits": k,
            "mixed_pairs_checked": len(self.hx) * len(self.hz),
            "noncommuting_pairs": bad,
            "logicals_commute_with_checks": lz_ok and lx_ok,
            "logicals_anticommute": anti,
            "logicals_nontrivial": nontrivial,
            "exact_x_distance": dx,
            "exact_z_distance": dz,
            "correction_bound": (min(dx, dz) - 1) // 2,
        }
        unsigned["verified"] = (
            k == 1 and bad == 0 and lz_ok and lx_ok and anti and nontrivial and dx == dz == self.d
        )
        digest = hashlib.sha256(json.dumps(unsigned, sort_keys=True).encode()).hexdigest()
        return SurfaceCodeReport(**unsigned, digest=digest)

    # -- decoding (X errors against Z checks; Z errors are symmetric) -------

    def _distances_from(self, kind: str, source: int) -> Tuple[Dict[int, int], Dict[int, Tuple[int, int]]]:
        _, _, boundary, adj = self._graph(kind)
        dist = {source: 0}
        parent: Dict[int, Tuple[int, int]] = {}
        queue = deque([source])
        while queue:
            u = queue.popleft()
            if u in boundary and u != source:
                continue
            for v, q in adj[u]:
                if v not in dist:
                    dist[v] = dist[u] + 1
                    parent[v] = (u, q)
                    queue.append(v)
        return dist, parent

    @staticmethod
    def _path(parent: Dict[int, Tuple[int, int]], target: int) -> int:
        out = 0
        node = target
        while node in parent:
            prev, q = parent[node]
            out ^= 1 << q
            node = prev
        return out

    def decode_exact(self, syndrome: int, kind: str = "x_errors", max_defects: int = 18) -> int:
        """Minimum-weight correction by exact matching over defect subsets."""
        defects = [i for i in range(syndrome.bit_length()) if (syndrome >> i) & 1]
        if len(defects) > max_defects:
            raise SurfaceCodeError(f"{len(defects)} defects exceed the exact decoder's {max_defects}")
        if not defects:
            return 0
        _, _, boundary, _ = self._graph(kind)
        info = [self._distances_from(kind, s) for s in defects]
        pair = [[info[i][0].get(defects[j], 10**9) for j in range(len(defects))] for i in range(len(defects))]
        to_b = []
        for dist, _ in info:
            options = [(dist[b], b) for b in boundary if b in dist]
            to_b.append(min(options) if options else (10**9, None))
        k = len(defects)

        @lru_cache(maxsize=None)
        def best(mask: int) -> Tuple[int, Tuple]:
            if mask == 0:
                return 0, ()
            i = (mask & -mask).bit_length() - 1
            rest = mask & ~(1 << i)
            cost_b, tail = best(rest)
            choice = (to_b[i][0] + cost_b, (("B", i),) + tail)
            j_mask = rest
            while j_mask:
                j = (j_mask & -j_mask).bit_length() - 1
                j_mask &= j_mask - 1
                c, t = best(rest & ~(1 << j))
                if pair[i][j] + c < choice[0]:
                    choice = (pair[i][j] + c, (("P", i, j),) + t)
            return choice

        _, plan = best((1 << k) - 1)
        correction = 0
        for step in plan:
            if step[0] == "B":
                i = step[1]
                correction ^= self._path(info[i][1], to_b[i][1])
            else:
                _, i, j = step
                correction ^= self._path(info[i][1], defects[j])
        return correction

    def decode_union_find(self, syndrome: int, kind: str = "x_errors") -> int:
        """Union-find decoder: grow odd clusters by half-edges, then peel."""
        m, edges, boundary, adj = self._graph(kind)
        total = len(adj)
        parent = list(range(total))
        parity = [0] * total
        touches = [False] * total
        for b in boundary:
            touches[b] = True
        defect = [0] * total
        for i in range(m):
            if (syndrome >> i) & 1:
                defect[i] = 1
                parity[i] = 1
        support = [0] * len(edges)
        members: Dict[int, set] = {v: {v} for v in range(total)}

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra == rb:
                return
            if len(members[ra]) < len(members[rb]):
                ra, rb = rb, ra
            parent[rb] = ra
            members[ra] |= members.pop(rb)
            parity[ra] ^= parity[rb]
            touches[ra] = touches[ra] or touches[rb]

        def odd_roots() -> List[int]:
            roots = {find(v) for v in range(m) if defect[v]}
            return [r for r in roots if parity[r] == 1 and not touches[r]]

        rounds = 0
        while True:
            roots = odd_roots()
            if not roots:
                break
            rounds += 1
            if rounds > 4 * total:
                raise SurfaceCodeError("union-find growth did not converge")
            grown: List[int] = []
            for r in roots:
                for v in list(members[r]):
                    for _, q in adj[v]:
                        if support[q] < 2:
                            support[q] += 1
                            if support[q] == 2:
                                grown.append(q)
            for q in grown:
                u, v = edges[q]
                union(u, v)
        erased = [q for q in range(len(edges)) if support[q] == 2]
        return self._peel(erased, defect, m, edges, boundary)

    def _peel(self, erased: List[int], defect: List[int], m: int, edges, boundary) -> int:
        nbrs: Dict[int, List[Tuple[int, int]]] = {}
        for q in erased:
            u, v = edges[q]
            nbrs.setdefault(u, []).append((v, q))
            nbrs.setdefault(v, []).append((u, q))
        seen: set = set()
        correction = 0
        flags = dict(enumerate(defect))
        nodes = sorted(nbrs, key=lambda x: (x not in boundary, x))
        for root in nodes:
            if root in seen:
                continue
            order: List[Tuple[int, int, int]] = []
            seen.add(root)
            queue = deque([root])
            while queue:
                u = queue.popleft()
                for v, q in nbrs[u]:
                    if v not in seen and not (v in boundary and u in boundary):
                        seen.add(v)
                        order.append((v, u, q))
                        queue.append(v)
            for child, par, q in reversed(order):
                if flags.get(child, 0):
                    correction ^= 1 << q
                    flags[child] = 0
                    if par not in boundary:
                        flags[par] = flags.get(par, 0) ^ 1
        return correction

    def corrected(self, error: int, correction: int, kind: str = "x_errors") -> bool:
        """Residual has no syndrome and acts trivially on the logical qubit."""
        residual = error ^ correction
        checks = self.hz if kind == "x_errors" else self.hx
        label = self.logical_z if kind == "x_errors" else self.logical_x
        return self.syndrome(checks, residual) == 0 and popcount(residual & label) % 2 == 0

    def correction_trials(self, weight: int, trials: int, seed: int, decoder: str = "union_find") -> dict:
        rng = random.Random(seed)
        ok = 0
        for _ in range(trials):
            error = sum(1 << q for q in rng.sample(range(self.n), weight))
            syn = self.syndrome(self.hz, error)
            fix = self.decode_union_find(syn) if decoder == "union_find" else self.decode_exact(syn)
            ok += self.corrected(error, fix)
        return {"distance": self.d, "weight": weight, "trials": trials, "corrected": ok, "seed": seed}


class PlanarSurfaceCode(CSSCode):
    """Distance-d planar code: hypergraph product of two repetition codes."""

    def __init__(self, distance: int) -> None:
        d = int(distance)
        if d < 2:
            raise SurfaceCodeError("distance must be at least 2")
        h = _repetition(d)
        ones = [1] * d
        e0 = [1] + [0] * (d - 1)
        super().__init__(
            n=d * d + (d - 1) * (d - 1),
            hx=_rows_to_ints(_kron(h, _eye(d)), _kron(_eye(d - 1), _t(h))),
            hz=_rows_to_ints(_kron(_eye(d), h), _kron(_t(h), _eye(d - 1))),
            logical_x=sum(1 << i for i, b in enumerate(_kron([e0], [ones])[0]) if b),
            logical_z=sum(1 << i for i, b in enumerate(_kron([ones], [e0])[0]) if b),
            distance=d,
        )


def edge_star_report(d: int) -> dict:
    """The all-vertex-star / all-face-plaquette convention, counted exactly."""
    hor = [("h", r, c) for r in range(d + 1) for c in range(d)]
    ver = [("v", r, c) for r in range(d) for c in range(d + 1)]
    index = {e: i for i, e in enumerate(hor + ver)}
    stars = []
    for r in range(d + 1):
        for c in range(d + 1):
            sup = []
            if c > 0:
                sup.append(("h", r, c - 1))
            if c < d:
                sup.append(("h", r, c))
            if r > 0:
                sup.append(("v", r - 1, c))
            if r < d:
                sup.append(("v", r, c))
            stars.append(sum(1 << index[e] for e in sup))
    plaquettes = [
        sum(1 << index[e] for e in (("h", r, c), ("h", r + 1, c), ("v", r, c), ("v", r, c + 1)))
        for r in range(d)
        for c in range(d)
    ]
    n = len(index)
    k = n - gf2_rank(stars) - gf2_rank(plaquettes)
    return {
        "convention": "star on every vertex, plaquette on every face",
        "distance_label": d,
        "qubits": n,
        "x_checks": len(stars),
        "z_checks": len(plaquettes),
        "mixed_pairs": len(stars) * len(plaquettes),
        "noncommuting_pairs": sum(1 for s in stars for p in plaquettes if popcount(s & p) % 2),
        "logical_qubits": k,
        "encodes_a_qubit": k > 0,
    }


__all__ = [
    "CSSCode",
    "PlanarSurfaceCode",
    "SurfaceCodeError",
    "SurfaceCodeReport",
    "edge_star_report",
    "gf2_rank",
    "in_span",
    "popcount",
]
