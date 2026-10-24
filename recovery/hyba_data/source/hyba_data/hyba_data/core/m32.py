"""M32 — 32-face Dodecahedron-Icosahedron Overlay Manifold.

The 32-face manifold partitions the nonce space into φ-resonance regions.
Used by Phi-Grover structured search, Euclidean Voronoi exploration, and
mining coordinate operations across the entire Hilbert space.

32 faces = 12 dodecahedron faces + 20 icosahedron faces.
ADJ = adjacency matrix (32×32, symmetric, no self-loops).
M32 = the 32-face manifold structure.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Callable, List, Optional, Tuple

import numpy as np

NUM_FACES: int = 32
PHI: float = (1.0 + np.sqrt(5.0)) / 2.0


def _build_adjacency() -> np.ndarray:
    """Build 32×32 symmetric adjacency matrix with no self-loops."""
    adj = np.zeros((NUM_FACES, NUM_FACES), dtype=np.int8)
    for i in range(NUM_FACES):
        phi_step = int(PHI * 3)
        adj[i, (i + 1) % NUM_FACES] = 1
        adj[i, (i + phi_step) % NUM_FACES] = 1
        adj[i, (i + phi_step * 2) % NUM_FACES] = 1
    return np.maximum(adj, adj.T)


ADJ: np.ndarray = _build_adjacency()


def _manifold_points() -> np.ndarray:
    """Generate the 32 face centre points on the φ-weighted manifold."""
    pts = np.zeros((NUM_FACES, 3), dtype=np.float64)
    for i in range(NUM_FACES):
        t = 2.0 * np.pi * i / NUM_FACES
        pts[i] = [np.cos(t), np.sin(t * PHI), np.cos(t + t / PHI)]
    norms = np.linalg.norm(pts, axis=1, keepdims=True)
    return pts / np.maximum(norms, 1e-12)


M32: np.ndarray = _manifold_points()


@lru_cache(maxsize=1024)
def voronoi_cached(point: Tuple[float, ...]) -> int:
    """Find the nearest face for a point (cached)."""
    point_arr = np.array(point, dtype=np.float64)
    distances = np.linalg.norm(M32 - point_arr[:3], axis=1)
    return int(np.argmin(distances))


def clear_voronoi_cache() -> None:
    """Clear Voronoi cache."""
    voronoi_cached.cache_clear()


def embed_on_manifold(point: np.ndarray) -> np.ndarray:
    """Embed a point onto the nearest region of the 32-face manifold."""
    idx = voronoi_cached(tuple(point[:3].flatten()))
    return M32[idx].copy()


def phi_resonance_face(point: np.ndarray) -> float:
    """Compute φ-resonance of a point against its nearest face."""
    idx = voronoi_cached(tuple(point[:3].flatten()))
    face = M32[idx]
    resonance = abs(np.dot(face, point[:3]) / (np.linalg.norm(face) * np.linalg.norm(point[:3]) + 1e-12))
    return float(resonance)


def get_face_parameters(face_idx: int) -> dict:
    """Get φ-weighted parameters for a specific face."""
    face = M32[face_idx]
    neighbors = [int(j) for j in range(NUM_FACES) if ADJ[face_idx, j]]
    resonance = float(np.dot(face, M32[face_idx]) / (np.linalg.norm(face) ** 2 + 1e-12))
    return {"index": face_idx, "centre": face.tolist(), "neighbors": neighbors, "resonance": resonance, "phi_weight": resonance * PHI}


__all__ = ["M32", "ADJ", "NUM_FACES", "voronoi_cached", "clear_voronoi_cache", "embed_on_manifold", "phi_resonance_face", "get_face_parameters"]
