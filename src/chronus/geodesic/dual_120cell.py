"""Exact H4 dual geometry for Chronus's shared geometric substrate.

The regular 600-cell has 120 vertices and 600 tetrahedral cells.
Its dual 120-cell has 600 vertices, 1,200 edges, 720 pentagonal
faces and 120 dodecahedral cells.  Dual vertices here are *exact*
tetrahedral centroids, not a floating-point nearest-neighbour guess.

Coordinates (a, b) denote (a + b*sqrt(5))/16.  The primal vertices
used here are scaled by 4 in chronus.ns_dec; summing four primal
vertex coordinate pairs therefore yields the dual centroid in /16 units.
No claims about a continuous 11D manifold or quantum dynamics are made.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations

from chronus.ns_dec import build_h4_600_cell_polytope

Q5Pair = tuple[int, int]
Point4 = tuple[Q5Pair, Q5Pair, Q5Pair, Q5Pair]


def _q5_mul(x: Q5Pair, y: Q5Pair) -> Q5Pair:
    return (x[0] * y[0] + 5 * x[1] * y[1],
            x[0] * y[1] + x[1] * y[0])


def _centroid_sq_norm_numerator(point: Point4) -> Q5Pair:
    """Squared Euclidean norm times 256, with no rounding."""
    a = b = 0
    for coordinate in point:
        x, y = _q5_mul(coordinate, coordinate)
        a += x
        b += y
    return a, b


@dataclass(frozen=True)
class Dual120Cell:
    """Combinatorial dual with verified incidences and exact centroids.

    vertices: 600 distinct tetrahedron centroids, numerator /16.
    edges: pairs of adjacent tetrahedron indices (shared triangular face).
    faces: 720 ordered pentagons (each around a primal edge).
    cells: 120 dodecahedra, each represented by its 20 vertex indices.
    primal_tetrahedra: reversible identification of each dual vertex.
    """
    vertices: tuple[Point4, ...]
    edges: tuple[tuple[int, int], ...]
    faces: tuple[tuple[int, int, int, int, int], ...]
    cells: tuple[tuple[int, ...], ...]
    primal_tetrahedra: tuple[tuple[int, int, int, int], ...]

    def invariants(self) -> dict[str, object]:
        return {
            "dimension": 4,
            "coordinate_field": "Q(sqrt(5))",
            "coordinate_denominator": 16,
            "vertices": len(self.vertices),
            "edges": len(self.edges),
            "pentagonal_faces": len(self.faces),
            "dodecahedral_cells": len(self.cells),
            "vertex_degree": 4,
            "euler_characteristic_boundary": (
                len(self.vertices) - len(self.edges) + len(self.faces) - len(self.cells)
            ),
        }


def _ordered_cycle(nodes: set[int], adjacency: list[set[int]]) -> tuple[int, ...]:
    if not nodes:
        raise AssertionError("empty dual face")
    start = min(nodes)
    neighbours = sorted(adjacency[start] & nodes)
    if len(neighbours) != 2:
        raise AssertionError("dual face is not a cycle")
    order = [start, neighbours[0]]
    while len(order) < len(nodes):
        options = (adjacency[order[-1]] & nodes) - {order[-2]}
        if len(options) != 1:
            raise AssertionError("dual face has ambiguous boundary")
        nxt = options.pop()
        if nxt in order:
            raise AssertionError("dual face repeats a vertex")
        order.append(nxt)
    if start not in adjacency[order[-1]]:
        raise AssertionError("dual face is open")
    return tuple(order)


@lru_cache(maxsize=1)
def build_dual_120_cell() -> Dual120Cell:
    """Derive all 600 dual vertices from the maintained exact H4 graph."""
    primal = build_h4_600_cell_polytope()
    n = primal["vertices"]
    adjacency: list[set[int]] = [set() for _ in range(n)]
    for i, j in primal["edge_index_pairs"]:
        adjacency[i].add(j)
        adjacency[j].add(i)

    tetrahedra: list[tuple[int, int, int, int]] = []
    for i in range(n):
        for j in sorted(v for v in adjacency[i] if v > i):
            common = adjacency[i] & adjacency[j]
            for k in sorted(v for v in common if v > j):
                for ell in sorted(v for v in common & adjacency[k] if v > k):
                    tetrahedra.append((i, j, k, ell))
    tetra = tuple(sorted(tetrahedra))
    if len(tetra) != 600 or len(set(tetra)) != 600:
        raise AssertionError("expected 600 distinct H4 tetrahedra")

    # Each tetrahedral cell has 4 triangles; each triangle is incident to
    # exactly two tetrahedra. This defines the 1,200 edges of the dual.
    triangle_owners: dict[tuple[int, int, int], list[int]] = {}
    for index, cell in enumerate(tetra):
        for triangle in combinations(cell, 3):
            triangle_owners.setdefault(triangle, []).append(index)
    if len(triangle_owners) != 1200 or any(len(v) != 2 for v in triangle_owners.values()):
        raise AssertionError("H4 triangular face incidence mismatch")
    edges = tuple(sorted(
        tuple(sorted(owners)) for owners in triangle_owners.values()
    ))
    dual_adjacency: list[set[int]] = [set() for _ in range(600)]
    for a, b in edges:
        dual_adjacency[a].add(b)
        dual_adjacency[b].add(a)
    if any(len(x) != 4 for x in dual_adjacency):
        raise AssertionError("120-cell must have four edges at each vertex")

    source_vertices = primal.get("vertex_coordinates")
    if source_vertices is None:
        # The canonical graph builder describes connectivity but does not
        # expose its coordinates. Recover precisely the same ordering and
        # scale by reusing the canonical cyclotomic builder would risk two
        # inconsistent vertex indices. Obtain the geometry from an exact,
        # index-preserving source instead.
        source_vertices = _indexed_h4_vertices()
    if len(source_vertices) != 120:
        raise AssertionError("primal coordinate count mismatch")

    points: list[Point4] = []
    for cell in tetra:
        point = tuple(
            (sum(source_vertices[index][axis][0] for index in cell),
             sum(source_vertices[index][axis][1] for index in cell))
            for axis in range(4)
        )
        points.append(point)
    if len(set(points)) != 600:
        raise AssertionError("dual centroid coordinates are not injective")
    norms = {_centroid_sq_norm_numerator(p) for p in points}
    if len(norms) != 1:
        raise AssertionError("dual vertices are not cospherical")

    # A primal edge belongs to five tetrahedra, yielding one pentagon.
    edge_members: dict[tuple[int, int], set[int]] = {
        edge: set() for edge in primal["edge_index_pairs"]
    }
    for i, cell in enumerate(tetra):
        for e in combinations(cell, 2):
            edge_members[e].add(i)
    faces: list[tuple[int, int, int, int, int]] = []
    for edge in primal["edge_index_pairs"]:
        members = edge_members[edge]
        if len(members) != 5:
            raise AssertionError("expected five tetrahedra around primal edge")
        cycle = _ordered_cycle(members, dual_adjacency)
        faces.append(cycle)  # type: ignore[arg-type]

    # Each primal vertex is dual to a dodecahedral cell with 20 vertices.
    cells: list[tuple[int, ...]] = []
    for vertex in range(120):
        incident = tuple(i for i, cell in enumerate(tetra) if vertex in cell)
        if len(incident) != 20:
            raise AssertionError("expected 20 dual vertices per dodecahedral cell")
        cells.append(incident)
    dual = Dual120Cell(tuple(points), edges, tuple(faces), tuple(cells), tetra)
    if (len(dual.edges), len(dual.faces), len(dual.cells)) != (1200, 720, 120):
        raise AssertionError("120-cell f-vector mismatch")
    if dual.invariants()["euler_characteristic_boundary"] != 0:
        raise AssertionError("four-polytope boundary Euler characteristic mismatch")
    return dual


def _indexed_h4_vertices() -> tuple[Point4, ...]:
    """Exact coordinates in the same tuple-sorted index order as ns_dec.

    Each pair represents (a+b*sqrt(5))/4 for the primal H4 vertices.
    """
    from itertools import permutations, product

    vertices: set[Point4] = set()
    zero = (0, 0)
    for axis in range(4):
        for sign in (-1, 1):
            p = [zero] * 4
            p[axis] = (4 * sign, 0)
            vertices.add(tuple(p))  # type: ignore[arg-type]
    for signs in product((-1, 1), repeat=4):
        vertices.add(tuple((2 * s, 0) for s in signs))  # type: ignore[arg-type]
    for perm in permutations(range(4)):
        inversions = sum(perm[i] > perm[j] for i in range(4) for j in range(i + 1, 4))
        if inversions % 2:
            continue
        for sp, sh, si in product((-1, 1), repeat=3):
            base = ((sp, sp), (2 * sh, 0), (-si, si), zero)
            vertices.add(tuple(base[perm[i]] for i in range(4)))  # type: ignore[arg-type]
    ordered = tuple(sorted(vertices))
    if len(ordered) != 120:
        raise AssertionError("reconstruction of canonical H4 vertex order failed")
    return ordered


class Polychoron120Cell:
    """Stable exact public 120-cell facade over the verified dual incidence.

    Vertices are exact Q(sqrt(5)) quadruples as (a,b) integer numerator
    pairs over a common denominator 16. No float approximations.
    """

    def __init__(self) -> None:
        self._dual = build_dual_120_cell()
        self._primal_tetra_lookup = {
            tetra: index
            for index, tetra in enumerate(self._dual.primal_tetrahedra)
        }

    @property
    def vertices(self) -> tuple[Point4, ...]:
        return self._dual.vertices

    @property
    def edges(self) -> tuple[tuple[int, int], ...]:
        return self._dual.edges

    @property
    def pentagonal_faces(self) -> tuple[tuple[int, int, int, int, int], ...]:
        return self._dual.faces

    @property
    def dodecahedral_cells(self) -> tuple[tuple[int, ...], ...]:
        return self._dual.cells

    @property
    def coordinate_denominator(self) -> int:
        return 16

    def index_of_tetrahedron(self, tetrahedron: tuple[int, int, int, int]) -> int:
        """Exact 600-cell tetrahedron / dual-vertex bijection, no proximity."""
        if len(tetrahedron) != 4 or len(set(tetrahedron)) != 4:
            raise ValueError("expected four distinct primal indices")
        key = tuple(sorted(tetrahedron))
        try:
            return self._primal_tetra_lookup[key]
        except KeyError:
            raise ValueError("input is not a canonical H4 tetrahedral cell") from None

    def invariants(self) -> dict[str, object]:
        return self._dual.invariants()
