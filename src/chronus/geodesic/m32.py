"""32 exact golden-ratio directions used by the Chronus geometric search layer.

Twelve directions are dodecahedral face normals (the vertices of its
dual icosahedron). Twenty are icosahedral face normals (the vertices
of its dual dodecahedron). These are *directions* and lane labels;
a 32-domain spherical Voronoi arrangement has not acquired 32
differential dimensions. We do not infer edge adjacency by a guessed
fixed angular threshold.
"""
from __future__ import annotations

from dataclasses import dataclass

from chronus.geodesic.embedding_11d import PHI, PHI_INV, Q5

Vector3 = tuple[Q5, Q5, Q5]
Z = Q5(0)
ONE = Q5(1)


def _cyclic(point: Vector3) -> tuple[Vector3, Vector3, Vector3]:
    a, b, c = point
    return ((a, b, c), (b, c, a), (c, a, b))


def _norm2(v: Vector3) -> Q5:
    return sum((x*x for x in v), Z)


def _dot(a: Vector3, b: Vector3) -> Q5:
    return sum((a[i] * b[i] for i in range(3)), Z)


@dataclass(frozen=True)
class M32Domain:
    lane: int
    polyhedral: str
    index: int
    normal: Vector3


def build_m32_domains() -> tuple[M32Domain, ...]:
    """Return the full 12+20 dual-pair orbits in canonical deterministic order."""
    dodeca: list[Vector3] = []
    # 12 vertices of the icosahedron = 12 dodecahedron face normals.
    for a in (-ONE, ONE):
        for b in (-PHI, PHI):
            dodeca.extend(_cyclic((Z, a, b)))

    icosa: list[Vector3] = []
    # 8 cube vertices + 12 golden vertices = 20 dodecahedron vertices;
    # these are the 20 icosahedron face-normal directions.
    for a in (-ONE, ONE):
        for b in (-ONE, ONE):
            for c in (-ONE, ONE):
                icosa.append((a, b, c))
    for a in (-PHI_INV, PHI_INV):
        for b in (-PHI, PHI):
            # Face-normal golden orbit of the icosahedron, not its vertices:
            # swapping the golden coordinates aligns each direction with
            # exactly three supporting vertices in the twelve-point orbit.
            icosa.extend(_cyclic((Z, b, a)))

    if len(dodeca) != 12 or len(icosa) != 20:
        raise AssertionError("unexpected dodecahedral / icosahedral orbit sizes")
    if len(set(dodeca + icosa)) != 32:
        raise AssertionError("M32 directions are not distinct")
    # Exact supporting-face certificate: every icosahedron face normal
    # maximizes its dot product on exactly three of the 12 primal vertices.
    # This verifies the 8 cube + 12 golden directions are *face normals*,
    # rather than just 20 otherwise plausible vectors.
    for normal in icosa:
        dot_products = [_dot(normal, vertex) for vertex in dodeca]
        maximum = dot_products[0]
        for value in dot_products[1:]:
            if (value - maximum).sign() > 0:
                maximum = value
        support = tuple(i for i, value in enumerate(dot_products)
                        if (value - maximum).is_zero())
        if len(support) != 3:
            raise AssertionError("icosahedron face normal does not support one triangular face")
    if any(_norm2(v).sign() <= 0 for v in dodeca + icosa):
        raise AssertionError("zero-norm M32 direction")
    domains = tuple(
        [M32Domain(i, "dodecahedron-face", i, n)
         for i, n in enumerate(dodeca)] +
        [M32Domain(12+i, "icosahedron-face", i, n)
         for i, n in enumerate(icosa)]
    )
    return domains


def assign_domain(vector: Vector3) -> M32Domain:
    """Nearest spherical direction with entirely exact Q(sqrt(5)) comparisons.

    Compare signed dot products divided by their positive direction norms.
    Both orbits are antipodally symmetric; for every nonzero vector at least
    one direction has positive dot product.
    """
    if len(vector) != 3 or any(not isinstance(x, Q5) for x in vector):
        raise TypeError("vector must contain three exact Q5 coordinates")
    if _norm2(vector).is_zero():
        raise ValueError("zero vector has no spherical direction")
    best = None
    best_dot = Z
    best_norm = ONE
    for domain in build_m32_domains():
        candidate_dot = _dot(vector, domain.normal)
        if candidate_dot.sign() <= 0:
            continue
        candidate_norm = _norm2(domain.normal)
        if best is None or (
            (candidate_dot * candidate_dot / candidate_norm -
             best_dot * best_dot / best_norm).sign() > 0
        ):
            best = domain
            best_dot = candidate_dot
            best_norm = candidate_norm
    if best is None:
        raise AssertionError("complete antipodal orbit did not contain a positive dot")
    return best


class M32DomainPartition:
    """Executable 12+20 exact face-normal domain partition.

    Decision assignments use exact Q(sqrt5) comparisons. The optional
    adjacency diagnostic is computed geometrically from SciPy's FLOAT64
    spherical Voronoi cells, NOT an independently certified exact graph.
    """

    def __init__(self) -> None:
        self.domains = build_m32_domains()
        self.dodeca_faces = tuple(d.normal for d in self.domains[:12])
        self.icosa_faces = tuple(d.normal for d in self.domains[12:])
        self.all_normals = tuple(d.normal for d in self.domains)
        self.adjacency_classification = "UNCOMPUTED_FLOAT64_VORONOI_DIAGNOSTIC"
        self._adjacency = None

    def assign_lane(self, vector: Vector3) -> int:
        """Exact nearest spherical domain; no float/tolerance."""
        return assign_domain(vector).lane

    @property
    def adjacency(self):
        """Float64 spherical-Voronoi ridge graph, explicitly diagnostic."""
        if self._adjacency is not None:
            return self._adjacency
        import numpy as np
        from scipy.spatial import SphericalVoronoi

        root5 = np.sqrt(5.0)
        points = np.array([
            [float(x.a) + float(x.b) * root5 for x in domain.normal]
            for domain in self.domains
        ], dtype=np.float64)
        points /= np.linalg.norm(points, axis=1)[:, None]
        voronoi = SphericalVoronoi(points)
        voronoi.sort_vertices_of_regions()
        incident: dict[tuple[int, int], set[int]] = {}
        for region_id, region in enumerate(voronoi.regions):
            for a, b in zip(region, region[1:] + region[:1]):
                incident.setdefault(tuple(sorted((a, b))), set()).add(region_id)
        adjacency = np.zeros((32, 32), dtype=bool)
        for owners in incident.values():
            if len(owners) != 2:
                raise ArithmeticError("Voronoi ridge does not have two incident cells")
            a, b = sorted(owners)
            adjacency[a, b] = adjacency[b, a] = True
        if not np.array_equal(adjacency, adjacency.T) or np.any(np.diag(adjacency)):
            raise ArithmeticError("numerical M32 Voronoi adjacency invariant failed")
        self._adjacency = adjacency
        self.adjacency_classification = "APPROXIMATE_FLOAT64_SPHERICAL_VORONOI"
        return adjacency
