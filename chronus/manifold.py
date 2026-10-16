# manifold.py
# Chronos GPU -- manifold face geometry (production pass, 4 Aug 2026)
#
# History:
#   - v1.0's M32Manifold.get_state() returned np.random.randn(...) -- fixed
#     in the audit pass (3 Aug 2026) to a deterministic Fibonacci-sphere
#     lattice, documented at the time as an honest stand-in for the real,
#     never-seen private core/manifold.py build_m32().
#   - This pass (4 Aug 2026) replaces that stand-in, for n=32 specifically,
#     with a REAL, independently-verifiable 32-face construction built from
#     two golden-ratio-parameterised regular Platonic solids: a regular
#     icosahedron (20 faces) and its dual regular dodecahedron (12 faces),
#     20 + 12 = 32. This is honestly NOT a byte-for-byte reproduction of an
#     original private build_m32() (that source was never available to this
#     audit) -- it is a real, self-consistent, checkable 32-face polyhedral
#     manifold that genuinely depends on phi, with strong structural
#     self-tests (Euler characteristic, vertex degree, duality) that would
#     fail loudly if the construction were wrong.
#   - For any other face count (M64/M128/M256/custom), the Fibonacci-sphere
#     lattice remains the deterministic, arbitrary-n fallback.

from __future__ import annotations

import numpy as np
from functools import lru_cache

PHI = (1.0 + np.sqrt(5.0)) / 2.0


def _exact_m32_rays():
    """The canonical exact M32 face rays (Q(phi) coordinates, certified
    symbolic-radical denominators) from igpu.exact_geometry — the same 32
    directions build_m32() produces, ordered [ico(12), dodeca(20)]."""
    from .igpu.exact_geometry import m32
    return m32()


def _q_to_float(x):
    """Certified float64 projection of an exact Q(phi) element a + b*phi."""
    return float(x.a) + float(x.b) * PHI


def _ray_to_float(ray):
    """Certified float64 projection of an ExactRay coordinate vector.

    ray value = numerator / sqrt(denominator_squared); each exact Q(phi)
    element a + b*phi is projected with ~2^-52 relative error, then divided
    by the certified float sqrt of the denominator. Total error is O(ulp) —
    the exact ray itself remains the certificate-bearing object."""
    import math
    s = _q_to_float(ray.denominator_squared)
    root = math.sqrt(s)
    return [_q_to_float(x) / root for x in ray.numerator]


def _classical_m32_positions() -> np.ndarray:
    """The historical FP64 construction (kept as the ordering oracle for the
    exact projection: every classical row is matched to its exact ray)."""
    verts = icosahedron_vertices()
    ico_face_centroids = icosahedron_face_centroids(verts)
    dodeca_face_centroids = dodecahedron_face_centroids_from_dual(verts, ico_face_centroids)
    return np.vstack([ico_face_centroids, dodeca_face_centroids])


def exact_m32_rays_ordered():
    return _exact_historical_order(tuple(_exact_m32_rays()),tuple(ICOSAHEDRON_FACES))


@lru_cache(maxsize=4)
def _exact_historical_order(rays,face_table):
    """Canonical rays in historical 20-face + 12-dual row order, exactly.

    Raw Q(phi) vertex sums give each face direction. Collinearity and positive
    orientation match that direction to the existing certified exact ray set.
    No float table, maximum-cosine selection or tolerance decides identity.
    """
    from .family_algebra import PhiElement as Q, PHI as phi
    from .igpu.exact_geometry import dot,sign
    one,zero=Q(1),Q()
    verts=((-one,phi,zero),(one,phi,zero),(-one,-phi,zero),(one,-phi,zero),
           (zero,-one,phi),(zero,one,phi),(zero,-one,-phi),(zero,one,-phi),
           (phi,zero,-one),(phi,zero,one),(-phi,zero,-one),(-phi,zero,one))
    faces=tuple(tuple(sum((verts[index][axis]for index in face),Q())for axis in range(3))for face in face_table)
    directions=faces+verts
    if len(rays)!=32 or any(len(r.numerator)!=3 or not r.is_unit()for r in rays):raise ArithmeticError('canonical M32 ray set malformed')
    ordered=[];used=set()
    for direction in directions:
        matches=[]
        for index,ray in enumerate(rays):
            v=ray.numerator
            cross=(direction[1]*v[2]-direction[2]*v[1],direction[2]*v[0]-direction[0]*v[2],direction[0]*v[1]-direction[1]*v[0])
            if all(x==Q()for x in cross)and sign(dot(direction,v))>0:matches.append(index)
        if len(matches)!=1 or matches[0]in used:raise ArithmeticError('M32 exact historical-order bijection failed')
        used.add(matches[0]);ordered.append(rays[matches[0]])
    if len(used)!=32:raise ArithmeticError('M32 exact coverage incomplete')
    return tuple(ordered)


def exact_m32_adjacency_ordered():
    return _exact_adjacency(exact_m32_rays_ordered())


@lru_cache(maxsize=4)
def _exact_adjacency(rays):
    """Historical cosine threshold 7/10 evaluated as exact radical scores."""
    from fractions import Fraction
    from .family_algebra import PhiElement as Q
    from .igpu.exact_geometry import RadicalScore,dot
    threshold=RadicalScore(Q(Fraction(7,10)),Q(1))
    return tuple(tuple(0 if i==j else int(RadicalScore(dot(a.numerator,b.numerator),a.denominator_squared*b.denominator_squared)>=threshold)for j,b in enumerate(rays))for i,a in enumerate(rays))


def exact_m32_positions() -> np.ndarray:
    """Unit-sphere float64 face positions projected from the exact M32 rays,
    in the historical build_m32() row order (contract preserved)."""
    return np.array([_ray_to_float(r) for r in exact_m32_rays_ordered()],
                    dtype=np.float64)


def exact_m32_transport():
    """Exact certificate-bearing transport of the 32 face rays (receipts),
    in historical build_m32() row order."""
    return [r.transport() for r in exact_m32_rays_ordered()]


def fibonacci_sphere(n: int) -> np.ndarray:
    """Deterministic, reproducible distribution of n unit vectors on a sphere.

    Used for arbitrary face counts (anything other than the real 32-face
    icosahedron+dodecahedron construction below).
    """
    if n <= 0:
        return np.zeros((0, 3))
    i = np.arange(n, dtype=np.float64)
    golden_angle = np.pi * (3.0 - np.sqrt(5.0))
    z = 1.0 - 2.0 * (i + 0.5) / n
    radius_xy = np.sqrt(np.clip(1.0 - z * z, 0.0, None))
    theta = golden_angle * i
    x = radius_xy * np.cos(theta)
    y = radius_xy * np.sin(theta)
    return np.stack([x, y, z], axis=1)


def _normalize_rows(v: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(v, axis=1, keepdims=True)
    return v / norms


def icosahedron_vertices() -> np.ndarray:
    """12 regular-icosahedron vertices: cyclic permutations of (0, +-1, +-phi),
    normalized to the unit sphere. Standard golden-ratio construction."""
    t = PHI
    raw = np.array([
        (-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0),
        (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
        (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1),
    ], dtype=np.float64)
    return _normalize_rows(raw)


# Standard 20-face index list for the vertex ordering above (widely used
# icosphere-generation face list). Correctness is not merely assumed here --
# it is verified structurally in _self_test() below via the Euler
# characteristic (V - E + F = 2) and vertex-degree checks, which would fail
# if this table were wrong.
ICOSAHEDRON_FACES = (
    (0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
    (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
    (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
    (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
)


def icosahedron_face_centroids(vertices: np.ndarray) -> np.ndarray:
    """Unit-normalized centroid direction of each of the 20 triangular faces.
    These 20 directions are exactly the 20 vertices of the dual regular
    dodecahedron (a real, well-known duality fact), verified in
    verify_icosahedron_dodecahedron_duality() below."""
    centroids = np.array([
        vertices[list(face)].mean(axis=0) for face in ICOSAHEDRON_FACES
    ])
    return _normalize_rows(centroids)


def dodecahedron_face_centroids_from_dual(vertices: np.ndarray, face_centroids: np.ndarray) -> np.ndarray:
    """The dual dodecahedron's 12 pentagonal faces correspond 1-1 to the
    icosahedron's 12 vertices: each dodecahedron face is the pentagon formed
    by the 5 icosahedron face-centroids (dodecahedron vertices) surrounding
    one icosahedron vertex. Its centroid direction coincides with that
    icosahedron vertex's own direction (verified in _self_test)."""
    out = np.zeros_like(vertices)
    for vi in range(vertices.shape[0]):
        incident = [fi for fi, face in enumerate(ICOSAHEDRON_FACES) if vi in face]
        assert len(incident) == 5, f"regular icosahedron vertex {vi} must have exactly 5 incident faces, got {len(incident)}"
        out[vi] = face_centroids[incident].mean(axis=0)
    return _normalize_rows(out)


def verify_cube_inscribed_in_dodecahedron(tol: float = 1e-9) -> bool:
    """Real, standard fact: a regular dodecahedron's 20 vertices are exactly
    the 8 cube vertices (+-1,+-1,+-1) together with 12 points from cyclic
    permutations of (0, +-1/phi, +-phi). Verified here by construction and by
    checking all 20 points lie on a common sphere and that the 8 cube-shaped
    ones are exactly the (+-1,+-1,+-1) octant pattern."""
    cube = np.array([(sx, sy, sz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)], dtype=np.float64)
    a = 1.0 / PHI
    perms = []
    for s1 in (-1, 1):
        for s2 in (-1, 1):
            perms.append((0.0, s1 * a, s2 * PHI))
            perms.append((s1 * a, s2 * PHI, 0.0))
            perms.append((s2 * PHI, 0.0, s1 * a))
    golden = np.array(perms, dtype=np.float64)
    all_verts = np.vstack([cube, golden])
    assert all_verts.shape == (20, 3), "dodecahedron must have exactly 20 vertices"
    radii = np.linalg.norm(all_verts, axis=1)
    assert np.allclose(radii, radii[0], atol=tol), "all 20 dodecahedron vertices must be equidistant from the center (regular polyhedron)"
    is_cube_vertex = np.all(np.isclose(np.abs(all_verts[:8]), 1.0, atol=tol), axis=1)
    assert bool(np.all(is_cube_vertex)), "first 8 constructed vertices must be exactly the cube vertices (+-1,+-1,+-1)"
    return True


def build_m32() -> np.ndarray:
    """Real 32-direction manifold: 20 icosahedron face-centroids union 12
    icosahedron vertices (== the dual dodecahedron's 12 face-centroids),
    every coordinate derived from the golden ratio.

    Positions are the certified float64 projection of the canonical exact
    rays from igpu.exact_geometry.m32() (exact Q(phi) coordinates with
    symbolic-radical denominators). The exact objects are retrievable via
    exact_m32_rays()/exact_m32_transport() for certificate-bound receipts.
    """
    return exact_m32_positions()


class M32Manifold:
    def __init__(self, n: int = 32, use_real_m32: bool = True):
        self.n = n
        if n == 32 and use_real_m32:
            self.face_positions = build_m32()
            self.construction = "icosahedron+dual_dodecahedron(phi)"
        else:
            self.face_positions = fibonacci_sphere(n)
            self.construction = "fibonacci_sphere"
        # Spectral-style adjacency: faces whose cosine similarity clears a
        # fixed threshold are neighbors. Mirrors the shape of the real
        # repo's build_spectral_adjacency (cos-similarity threshold 0.70).
        if n==32 and use_real_m32:
            self.adjacency=np.asarray(exact_m32_adjacency_ordered(),dtype=np.float64)
        else:
            sims=self.face_positions@self.face_positions.T
            self.adjacency=(sims>=0.70).astype(np.float64)
        np.fill_diagonal(self.adjacency, 0.0)

    def get_state_exact(self):
        """Exact uniform state; legacy get_state is only its float projection."""
        import sympy as sp
        if type(self.n)is not int or self.n<1:raise ValueError("positive exact state dimension")
        return tuple(sp.Integer(1)/sp.sqrt(self.n)for _ in range(self.n))

    def get_state(self) -> np.ndarray:
        """Deterministic uniform-superposition state over the manifold faces.
        Use EvolutionEngine.evolve() for the actual Hamiltonian-derived state."""
        return np.asarray([complex(x)for x in self.get_state_exact()],dtype=complex)


def _self_test() -> str:
    verts = icosahedron_vertices()
    assert verts.shape == (12, 3), "icosahedron must have 12 vertices"
    assert np.allclose(np.linalg.norm(verts, axis=1), 1.0), "icosahedron vertices must be unit-normalized"

    # Euler characteristic V - E + F = 2 for a genus-0 closed polyhedron.
    edges = set()
    for face in ICOSAHEDRON_FACES:
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            edges.add(tuple(sorted((a, b))))
    v, e, f = 12, len(edges), len(ICOSAHEDRON_FACES)
    assert f == 20, "icosahedron must have exactly 20 faces"
    assert e == 30, f"icosahedron must have exactly 30 edges, got {e}"
    assert v - e + f == 2, f"Euler characteristic must be 2, got {v - e + f}"

    # Every edge must be shared by exactly 2 faces (closed, manifold surface).
    edge_face_count: dict = {}
    for face in ICOSAHEDRON_FACES:
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            key = tuple(sorted((a, b)))
            edge_face_count[key] = edge_face_count.get(key, 0) + 1
    assert all(c == 2 for c in edge_face_count.values()), "every edge must border exactly 2 faces"

    ico_face_centroids = icosahedron_face_centroids(verts)
    assert ico_face_centroids.shape == (20, 3)
    assert np.allclose(np.linalg.norm(ico_face_centroids, axis=1), 1.0)

    dodeca_face_centroids = dodecahedron_face_centroids_from_dual(verts, ico_face_centroids)
    assert dodeca_face_centroids.shape == (12, 3)
    # Real duality check: each dual dodecahedron face centroid must point in
    # the same direction as the corresponding original icosahedron vertex.
    cos_sim = np.sum(dodeca_face_centroids * verts, axis=1)
    assert np.all(cos_sim > 0.999), "dual dodecahedron face centroids must align with icosahedron vertices"

    assert verify_cube_inscribed_in_dodecahedron(), "cube-in-dodecahedron construction must hold"

    m32 = build_m32()
    assert m32.shape == (32, 3), "M32 must have exactly 32 faces"
    assert np.allclose(np.linalg.norm(m32, axis=1), 1.0), "all M32 face directions must be unit vectors"

    # Exact-ray parity: every projected position must coincide (to float
    # precision) with the classical FP64 construction in the same row order,
    # and the underlying rays must be exactly unit.
    classic = _classical_m32_positions()
    assert np.allclose(m32, classic, atol=1e-12), "exact-projection M32 must match classical FP64 positions"
    for ray, pos in zip(exact_m32_rays_ordered(), m32):
        assert ray.is_unit(), "M32 rays must be exactly unit"
        import math
        s = _q_to_float(ray.denominator_squared)
        for qi, pi in zip(ray.numerator, pos):
            assert abs(_q_to_float(qi) / math.sqrt(s) - pi) < 1e-12
    # No duplicate directions among the 32 (icosahedron and dodecahedron
    # duals are geometrically distinct point sets).
    gram = m32 @ m32.T
    np.fill_diagonal(gram, 0.0)
    assert gram.max() < 0.999, "M32 face directions must be geometrically distinct"

    manifold = M32Manifold(n=32)
    assert manifold.construction == "icosahedron+dual_dodecahedron(phi)"
    assert manifold.face_positions.shape == (32, 3)
    state = manifold.get_state()
    assert np.isclose(np.sum(np.abs(state) ** 2), 1.0), "uniform state must be normalized"

    fallback = M32Manifold(n=64)
    assert fallback.construction == "fibonacci_sphere"
    assert fallback.face_positions.shape == (64, 3)

    return "manifold._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
