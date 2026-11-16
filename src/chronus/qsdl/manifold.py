# manifold.py
# Chronos GPU -- M32 manifold face geometry (production pass, certified Platonic construction)

from __future__ import annotations

import numpy as np

PHI = (1.0 + np.sqrt(5.0)) / 2.0


def _normalize_rows(v: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(v, axis=1, keepdims=True)
    return v / np.clip(norms, 1e-15, None)


def icosahedron_vertices() -> np.ndarray:
    """12 regular-icosahedron vertices: cyclic permutations of (0, +-1, +-phi),
    normalized to the unit sphere. Standard golden-ratio construction."""
    t = PHI
    raw = np.array(
        [
            (-1, t, 0),
            (1, t, 0),
            (-1, -t, 0),
            (1, -t, 0),
            (0, -1, t),
            (0, 1, t),
            (0, -1, -t),
            (0, 1, -t),
            (t, 0, -1),
            (t, 0, 1),
            (-t, 0, -1),
            (-t, 0, 1),
        ],
        dtype=np.float64,
    )
    return _normalize_rows(raw)


ICOSAHEDRON_FACES = (
    (0, 11, 5),
    (0, 5, 1),
    (0, 1, 7),
    (0, 7, 10),
    (0, 10, 11),
    (1, 5, 9),
    (5, 11, 4),
    (11, 10, 2),
    (10, 7, 6),
    (7, 1, 8),
    (3, 9, 4),
    (3, 4, 2),
    (3, 2, 6),
    (3, 6, 8),
    (3, 8, 9),
    (4, 9, 5),
    (2, 4, 11),
    (6, 2, 10),
    (8, 6, 7),
    (9, 8, 1),
)


def icosahedron_face_centroids(vertices: np.ndarray) -> np.ndarray:
    """Unit-normalized centroid direction of each of the 20 triangular faces."""
    centroids = np.array(
        [vertices[list(face)].mean(axis=0) for face in ICOSAHEDRON_FACES]
    )
    return _normalize_rows(centroids)


def dodecahedron_face_centroids_from_dual(
    vertices: np.ndarray, face_centroids: np.ndarray
) -> np.ndarray:
    """The dual dodecahedron's 12 pentagonal faces correspond 1-1 to the
    icosahedron's 12 vertices: each dodecahedron face is the pentagon formed
    by the 5 icosahedron face-centroids surrounding one icosahedron vertex."""
    out = np.zeros_like(vertices)
    for vi in range(vertices.shape[0]):
        incident = [fi for fi, face in enumerate(ICOSAHEDRON_FACES) if vi in face]
        assert (
            len(incident) == 5
        ), f"regular icosahedron vertex {vi} must have exactly 5 incident faces, got {len(incident)}"
        out[vi] = face_centroids[incident].mean(axis=0)
    return _normalize_rows(out)


def build_m32() -> np.ndarray:
    """Real 32-direction manifold: 20 icosahedron face-centroids union 12
    icosahedron vertices (the dual dodecahedron's 12 face-centroids),
    every coordinate derived from the golden ratio phi."""
    verts = icosahedron_vertices()
    ico_face_centroids = icosahedron_face_centroids(verts)
    dodeca_face_centroids = dodecahedron_face_centroids_from_dual(
        verts, ico_face_centroids
    )
    return np.vstack([ico_face_centroids, dodeca_face_centroids])


def fibonacci_sphere(n: int) -> np.ndarray:
    """Deterministic, reproducible distribution of n unit vectors on a sphere.
    Used for arbitrary face counts (anything other than the certified 32-face
    icosahedron+dodecahedron construction)."""
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
        cos_thresh = 0.70
        sims = self.face_positions @ self.face_positions.T
        self.adjacency = (sims >= cos_thresh).astype(np.float64)
        np.fill_diagonal(self.adjacency, 0.0)

    def get_state(self) -> np.ndarray:
        """Deterministic uniform-superposition state over the manifold faces.
        Use EvolutionEngine.evolve() for the actual Hamiltonian-derived state."""
        return np.ones(self.n, dtype=complex) / np.sqrt(self.n)


def _self_test() -> str:
    verts = icosahedron_vertices()
    assert verts.shape == (12, 3), "icosahedron must have 12 vertices"
    assert np.allclose(
        np.linalg.norm(verts, axis=1), 1.0
    ), "icosahedron vertices must be unit-normalized"

    # Euler characteristic V - E + F = 2 for a genus-0 closed polyhedron.
    edges = set()
    for face in ICOSAHEDRON_FACES:
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            edges.add(tuple(sorted((a, b))))
    v, e, f = 12, len(edges), len(ICOSAHEDRON_FACES)
    assert f == 20, "icosahedron must have exactly 20 faces"
    assert e == 30, f"icosahedron must have exactly 30 edges, got {e}"
    assert v - e + f == 2, f"Euler characteristic must be 2, got {v - e + f}"

    ico_face_centroids = icosahedron_face_centroids(verts)
    assert ico_face_centroids.shape == (20, 3)
    assert np.allclose(np.linalg.norm(ico_face_centroids, axis=1), 1.0)

    dodeca_face_centroids = dodecahedron_face_centroids_from_dual(
        verts, ico_face_centroids
    )
    assert dodeca_face_centroids.shape == (12, 3)
    cos_sim = np.sum(dodeca_face_centroids * verts, axis=1)
    assert np.all(
        cos_sim > 0.999
    ), "dual dodecahedron face centroids must align with icosahedron vertices"

    m32 = build_m32()
    assert m32.shape == (32, 3), "M32 must have exactly 32 faces"
    assert np.allclose(
        np.linalg.norm(m32, axis=1), 1.0
    ), "all M32 face directions must be unit vectors"

    manifold = M32Manifold(n=32)
    assert manifold.construction == "icosahedron+dual_dodecahedron(phi)"
    assert manifold.face_positions.shape == (32, 3)

    fallback = M32Manifold(n=64)
    assert fallback.construction == "fibonacci_sphere"
    assert fallback.face_positions.shape == (64, 3)

    return "manifold._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
