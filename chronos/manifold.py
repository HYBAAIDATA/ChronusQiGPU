# manifold.py
# Chronos GPU -- M32 manifold face geometry (audit fix, 3 Aug 2026)
#
# Fix vs v1.0:
#   - v1.0's M32Manifold.get_state() returned np.random.randn(...) -- a fresh
#     random vector on every call, unrelated to any Hamiltonian, scene, or
#     prior state. It was not a "manifold state" in any real sense.
#   - v2.0 gives the manifold a deterministic, reproducible geometry (a
#     Fibonacci sphere lattice of n unit vectors) that downstream modules use
#     for real geometric projections (Hamiltonian construction, per-pixel
#     shading). This is NOT a reproduction of the real core/manifold.py
#     build_m32() (dodecahedron + cube + icosahedron composition via the
#     golden ratio, fixed at exactly 32 faces); it is an honest, documented,
#     deterministic stand-in that supports an arbitrary face count. See
#     AUDIT_NOTES.md.

from __future__ import annotations

import numpy as np


def fibonacci_sphere(n: int) -> np.ndarray:
    """Deterministic, reproducible distribution of n unit vectors on a sphere."""
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
    def __init__(self, n: int = 32):
        self.n = n
        self.face_positions = fibonacci_sphere(n)
        # Spectral-style adjacency: faces whose cosine similarity clears a
        # fixed threshold are neighbors. This mirrors the shape of the real
        # repo's build_spectral_adjacency (cos-similarity threshold 0.70,
        # which the real M32 uses because it is dense enough to be
        # connected), not its exact numbers -- an earlier, stricter 35 degree
        # (cos=0.82) threshold used in this fix pass produced a fragmented,
        # near-matching graph that pathologically localized the Hamiltonian's
        # ground state onto a single small graph component, which happened to
        # sit entirely outside the camera's field of view. Using the same
        # 0.70 threshold as the real repo fixes that.
        cos_thresh = 0.70
        sims = self.face_positions @ self.face_positions.T
        self.adjacency = (sims >= cos_thresh).astype(np.float64)
        np.fill_diagonal(self.adjacency, 0.0)

    def get_state(self) -> np.ndarray:
        """Deterministic uniform-superposition state over the manifold faces.

        v1.0 returned fresh random noise on every call. There is no
        Hamiltonian in scope at this layer to derive a real state from, so
        rather than fabricate one, this returns the maximally-uninformative
        (uniform) state, which is at least deterministic and honestly
        labeled. Use EvolutionEngine.evolve() for the actual,
        Hamiltonian-derived state.
        """
        return np.ones(self.n, dtype=complex) / np.sqrt(self.n)
