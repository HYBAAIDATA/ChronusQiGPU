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
            icosa.extend(_cyclic((Z, a, b)))

    if len(dodeca) != 12 or len(icosa) != 20:
        raise AssertionError("unexpected dodecahedral / icosahedral orbit sizes")
    if len(set(dodeca + icosa)) != 32:
        raise AssertionError("M32 directions are not distinct")
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
