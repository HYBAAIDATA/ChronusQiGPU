"""
Concrete Manifold Implementations.

This module provides concrete implementations of the Manifold abstract class,
including the M_32 manifold used in phi-Grover, as well as general-purpose
manifolds like Grassmannians and Stiefel manifolds.

Author: Phi-Grover Development Team
Version: 8.0.0
"""

from __future__ import annotations

import math
import os

# Import existing phi-Grover components
import sys

import numpy as np

from .manifold import Manifold, ManifoldConfig

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.m32 import ADJ, M32, NUM_FACES, embed_on_manifold, voronoi_cached


class M32Manifold(Manifold):
    """
    M_32 manifold - dodecahedron-icosahedron compound.

    This is the original manifold used in phi-Grover, providing a 32-face
    Voronoi partition of the search space based on golden ratio geometry.
    """

    def __init__(self, config: ManifoldConfig | None = None) -> None:
        """
        Initialize M_32 manifold.

        Args:
            config: Manifold configuration (uses defaults if None)
        """
        if config is None:
            config = ManifoldConfig(
                dimension=32,
                embedding_dim=3,
                curvature_type="variable",
                metric_type="riemannian",
                cache_enabled=True,
                cache_size=150000,
                metadata={
                    "name": "M_32",
                    "description": "Dodecahedron-icosahedron compound",
                },
            )

        super().__init__(config)

        # Precompute face normals from existing M32
        self.face_normals = M32
        self.num_faces = NUM_FACES

    def embed(self, point: int) -> np.ndarray:
        """Embed nonce onto M_32 manifold."""
        if self._cache is not None and point in self._cache:
            return self._cache[point]

        # Convert integer to 3D point using byte decomposition (same as PhiResonanceOracle)
        point_arr = np.array([
            float(point & 0xFF),
            float((point >> 8) & 0xFF),
            float((point >> 16) & 0xFF),
        ])
        embedded = np.array(embed_on_manifold(point_arr))

        if self._cache is not None:
            if len(self._cache) >= self.config.cache_size:
                self._cache.clear()
            self._cache[point] = embedded

        return embedded

    def project_to_tangent(self, point: int, vector: np.ndarray) -> np.ndarray:
        """
        Project vector to tangent space at point.

        For M_32, we project onto the tangent plane of the sphere
        at the embedded point.
        """
        embedded = self.embed(point)

        # Project onto tangent space of sphere: v_tangent = v - (v·n)n
        dot_product = np.dot(vector, embedded)
        return vector - dot_product * embedded

    def retract(self, point: int, tangent_vector: np.ndarray) -> int:
        """
        Retract from tangent space back to manifold.

        For M_32, we move along the sphere surface and find the nearest
        face domain.
        """
        embedded = self.embed(point)

        # Exponential map on sphere: exp_p(v) = cos(|v|)p + sin(|v|)v/|v|
        norm = np.linalg.norm(tangent_vector)
        if norm < 1e-10:
            return point

        new_embedded = math.cos(norm) * embedded + math.sin(norm) * tangent_vector / norm

        # Find nearest face domain
        face = max(
            range(self.num_faces),
            key=lambda f: np.dot(new_embedded, self.face_normals[f]),
        )

        # Generate a nonce in that face domain
        perturbation = (face * 7919) & 0xFFFFFFFF
        return (point + perturbation) & 0xFFFFFFFF

    def distance(self, point1: int, point2: int) -> float:
        """
        Compute geodesic distance between two points.

        For M_32, we use the angular distance on the sphere.
        """
        emb1 = self.embed(point1)
        emb2 = self.embed(point2)

        # Angular distance: arccos(dot product)
        dot = np.clip(np.dot(emb1, emb2), -1.0, 1.0)
        return math.acos(dot)

    def geodesic(self, point1: int, point2: int, t: float) -> np.ndarray:
        """
        Compute point along geodesic between two points.

        For M_32, we use spherical interpolation (slerp).
        """
        emb1 = self.embed(point1)
        emb2 = self.embed(point2)

        dot = np.clip(np.dot(emb1, emb2), -1.0, 1.0)
        theta = math.acos(dot)

        if theta < 1e-10:
            return emb1

        sin_theta = math.sin(theta)
        w1 = math.sin((1 - t) * theta) / sin_theta
        w2 = math.sin(t * theta) / sin_theta

        return w1 * emb1 + w2 * emb2

    def curvature(self, point: int) -> float:
        """
        Compute scalar curvature at a point.

        For M_32 (sphere), curvature is constant = 1/R^2.
        Using unit sphere, curvature = 1.
        """
        return 1.0

    def get_neighbors(self, point: int, k: int = 5) -> list[int]:
        """
        Get k nearest neighbors on the manifold.

        For M_32, we return points in adjacent face domains.
        """
        point_arr = np.array([
            float(point & 0xFF),
            float((point >> 8) & 0xFF),
            float((point >> 16) & 0xFF),
        ])
        face = voronoi_cached(tuple(point_arr))
        adjacent_faces = [i for i, adj in enumerate(ADJ[face]) if adj]

        neighbors = []
        for adj_face in adjacent_faces[:k]:
            perturbation = (adj_face * 7919) & 0xFFFFFFFF
            neighbors.append((point + perturbation) & 0xFFFFFFFF)

        # Fill with random points if not enough adjacent faces
        while len(neighbors) < k:
            neighbors.append(np.random.randint(0, 2**32))

        return neighbors

    def get_domain_partition(self) -> list[tuple[int, tuple[int, int]]]:
        """
        Get partition of search space into face domains.

        Returns list of (face_id, (start, end)) tuples.
        """
        partition = []
        chunk_size = 2**32 // self.num_faces

        for face_id in range(self.num_faces):
            start = face_id * chunk_size
            end = (face_id + 1) * chunk_size - 1 if face_id < self.num_faces - 1 else 2**32 - 1
            partition.append((face_id, (start, end)))

        return partition

    def get_domain_for_point(self, point: int) -> int:
        """Get face domain for a given point."""
        point_arr = np.array([
            float(point & 0xFF),
            float((point >> 8) & 0xFF),
            float((point >> 16) & 0xFF),
        ])
        return voronoi_cached(tuple(point_arr))


class GrassmannianManifold(Manifold):
    """
    Grassmannian manifold Gr(p, n) - space of p-dimensional subspaces in R^n.

    General-purpose manifold for subspace optimization problems.
    """

    def __init__(self, p: int, n: int, config: ManifoldConfig | None = None) -> None:
        """
        Initialize Grassmannian manifold.

        Args:
            p: Subspace dimension
            n: Ambient dimension
            config: Manifold configuration
        """
        if config is None:
            config = ManifoldConfig(
                dimension=p * (n - p),
                embedding_dim=p * n,
                curvature_type="positive",
                metric_type="riemannian",
                cache_enabled=True,
                metadata={"name": f"Gr({p},{n})", "p": p, "n": n},
            )

        self.p = p
        self.n = n
        super().__init__(config)

    def embed(self, point: int) -> np.ndarray:
        """Embed integer point to subspace basis matrix."""
        if self._cache is not None and point in self._cache:
            return self._cache[point]

        # Generate random orthonormal basis seeded by point
        np.random.seed(point)
        A = np.random.randn(self.n, self.p)
        Q, _ = np.linalg.qr(A)

        embedded = Q.flatten()

        if self._cache is not None:
            if len(self._cache) >= self.config.cache_size:
                self._cache.clear()
            self._cache[point] = embedded

        return embedded

    def project_to_tangent(self, point: int, vector: np.ndarray) -> np.ndarray:
        """Project to tangent space of Grassmannian."""
        Y = self.embed(point).reshape(self.n, self.p)
        V = vector.reshape(self.n, self.p)

        # Tangent space projection: (I - YY^T)V
        tangent = (np.eye(self.n) - Y @ Y.T) @ V

        return tangent.flatten()

    def retract(self, point: int, tangent_vector: np.ndarray) -> int:
        """Retract using QR-based retraction."""
        Y = self.embed(point).reshape(self.n, self.p)
        V = tangent_vector.reshape(self.n, self.p)

        # QR retraction: qf(Y + V)
        Y_new, _ = np.linalg.qr(Y + V)

        # Convert back to integer (simplified)
        return int(np.abs(np.sum(Y_new)) * 1e6) % (2**32)

    def distance(self, point1: int, point2: int) -> float:
        """Compute principal angles distance."""
        Y1 = self.embed(point1).reshape(self.n, self.p)
        Y2 = self.embed(point2).reshape(self.n, self.p)

        # Compute principal angles via SVD
        U, s, _ = np.linalg.svd(Y1.T @ Y2)

        # Distance based on principal angles
        return np.linalg.norm(np.arccos(np.clip(s, -1, 1)))

    def geodesic(self, point1: int, point2: int, t: float) -> np.ndarray:
        """Compute geodesic using SVD-based interpolation."""
        Y1 = self.embed(point1).reshape(self.n, self.p)
        Y2 = self.embed(point2).reshape(self.n, self.p)

        U, s, Vt = np.linalg.svd(Y1.T @ Y2)

        # Interpolate principal angles
        s_t = np.diag(np.sin(t * np.arccos(s)) / np.sin(np.arccos(s)))

        Y_t = (
            Y1 @ Vt.T @ s_t @ Vt
            + (np.eye(self.n) - Y1 @ Y1.T) @ Y2 @ Vt.T @ np.diag(np.cos(t * np.arccos(s))) @ Vt
        )

        return Y_t.flatten()

    def curvature(self, point: int) -> float:
        """Grassmannian has positive curvature."""
        return 0.5

    def get_neighbors(self, point: int, k: int = 5) -> list[int]:
        """Get random neighbors (no structure for general Grassmannian)."""
        return [(point + np.random.randint(-1000, 1000)) % (2**32) for _ in range(k)]


class StiefelManifold(Manifold):
    """
    Stiefel manifold St(p, n) - space of orthonormal p-frames in R^n.

    General-purpose manifold for orthonormal matrix optimization.
    """

    def __init__(self, p: int, n: int, config: ManifoldConfig | None = None) -> None:
        """
        Initialize Stiefel manifold.

        Args:
            p: Frame dimension
            n: Ambient dimension
            config: Manifold configuration
        """
        if config is None:
            config = ManifoldConfig(
                dimension=p * n - p * (p + 1) // 2,
                embedding_dim=p * n,
                curvature_type="positive",
                metric_type="riemannian",
                cache_enabled=True,
                metadata={"name": f"St({p},{n})", "p": p, "n": n},
            )

        self.p = p
        self.n = n
        super().__init__(config)

    def embed(self, point: int) -> np.ndarray:
        """Embed integer point to orthonormal frame."""
        if self._cache is not None and point in self._cache:
            return self._cache[point]

        # Generate random orthonormal matrix seeded by point
        np.random.seed(point)
        A = np.random.randn(self.n, self.p)
        Q, _ = np.linalg.qr(A)

        embedded = Q.flatten()

        if self._cache is not None:
            if len(self._cache) >= self.config.cache_size:
                self._cache.clear()
            self._cache[point] = embedded

        return embedded

    def project_to_tangent(self, point: int, vector: np.ndarray) -> np.ndarray:
        """Project to tangent space of Stiefel."""
        Y = self.embed(point).reshape(self.n, self.p)
        V = vector.reshape(self.n, self.p)

        # Skew-symmetric projection
        skew = Y.T @ V - V.T @ Y
        tangent = V - Y @ skew

        return tangent.flatten()

    def retract(self, point: int, tangent_vector: np.ndarray) -> int:
        """Retract using Cayley transform."""
        Y = self.embed(point).reshape(self.n, self.p)
        V = tangent_vector.reshape(self.n, self.p)

        # Cayley transform retraction
        A = V.T @ Y - Y.T @ V
        I_mat = np.eye(self.p)
        Y_new = Y @ (I_mat - 0.5 * A) @ np.linalg.inv(I_mat + 0.5 * A)

        return int(np.abs(np.sum(Y_new)) * 1e6) % (2**32)

    def distance(self, point1: int, point2: int) -> float:
        """Compute Frobenius norm distance."""
        Y1 = self.embed(point1).reshape(self.n, self.p)
        Y2 = self.embed(point2).reshape(self.n, self.p)

        return np.linalg.norm(Y1 - Y2, "fro")

    def geodesic(self, point1: int, point2: int, t: float) -> np.ndarray:
        """Linear interpolation (simplified)."""
        Y1 = self.embed(point1).reshape(self.n, self.p)
        Y2 = self.embed(point2).reshape(self.n, self.p)

        Y_t = (1 - t) * Y1 + t * Y2
        Q, _ = np.linalg.qr(Y_t)

        return Q.flatten()

    def curvature(self, point: int) -> float:
        """Stiefel has positive curvature."""
        return 0.3

    def get_neighbors(self, point: int, k: int = 5) -> list[int]:
        """Get random neighbors."""
        return [(point + np.random.randint(-1000, 1000)) % (2**32) for _ in range(k)]
