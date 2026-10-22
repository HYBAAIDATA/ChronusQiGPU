"""
Extensible Manifold Constructors with Golden-Ratio Structures (v9.0).

This module provides extensible constructors for creating manifolds with
various geometric structures, including:
- Golden-ratio based manifolds
- Fibonacci lattice structures
- Icosahedral and dodecahedral symmetries
- Lie group embeddings
- Custom user-defined structures

Features:
- Pluggable architecture for custom manifolds
- Golden-ratio parameterized structures
- Fibonacci-based discretizations
- Symmetry-aware construction
- Metric tensor customization
- Extensible for research applications

Author: Phi-Grover Development Team
Version: 9.0.0
Date: 2026-04-18
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

import numpy as np

from .manifold import Manifold, ManifoldConfig

logger = logging.getLogger(__name__)


class ManifoldType(Enum):
    """Types of manifolds supported by constructors."""
    M32 = "m32"
    GOLDEN_RATIO_SPHERE = "golden_ratio_sphere"
    FIBONACCI_LATTICE = "fibonacci_lattice"
    ICOSAHEDRAL = "icosahedral"
    DODECAHEDRAL = "dodecahedral"
    LIE_GROUP = "lie_group"
    CUSTOM = "custom"


@dataclass
class GoldenRatioConfig:
    """Configuration for golden-ratio based manifolds."""
    phi: float = (1 + math.sqrt(5)) / 2
    num_layers: int = 32
    scaling_factor: float = 1.0
    rotation_angle: float = math.pi / 5
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FibonacciConfig:
    """Configuration for Fibonacci-based manifolds."""
    sequence: list[int] = field(default_factory=lambda: [1, 2, 3, 5, 8, 13, 21, 34, 55, 89])
    num_points: int = 100
    spiral_turns: float = 10.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LieGroupConfig:
    """Configuration for Lie group manifolds."""
    group_type: str = "SO(3)"
    dimension: int = 3
    embedding_dim: int = 9
    parameters: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def create_manifold_constructor() -> ManifoldConstructor:
    """Factory function to create a ManifoldConstructor."""
    return ManifoldConstructor()


class ManifoldConstructor:
    """Base class for manifold constructors with pluggable architecture."""

    def __init__(self):
        self._constructors: dict[ManifoldType, Callable] = {}
        self._register_default_constructors()

    def _register_default_constructors(self):
        self._constructors[ManifoldType.M32] = self._construct_m32
        self._constructors[ManifoldType.GOLDEN_RATIO_SPHERE] = self._construct_golden_ratio_sphere
        self._constructors[ManifoldType.FIBONACCI_LATTICE] = self._construct_fibonacci_lattice
        self._constructors[ManifoldType.ICOSAHEDRAL] = self._construct_icosahedral
        self._constructors[ManifoldType.DODECAHEDRAL] = self._construct_dodecahedral
        self._constructors[ManifoldType.LIE_GROUP] = self._construct_lie_group

    def register_constructor(self, manifold_type: ManifoldType, constructor_func: Callable) -> None:
        self._constructors[manifold_type] = constructor_func
        logger.info(f"Registered constructor for {manifold_type.value}")

    def construct(self, manifold_type: ManifoldType, config: ManifoldConfig | None = None, **kwargs) -> Manifold:
        if manifold_type not in self._constructors:
            raise ValueError(f"Unknown manifold type: {manifold_type}")
        return self._constructors[manifold_type](config, **kwargs)

    def _construct_m32(self, config=None, **kwargs):
        from .manifolds import M32Manifold
        return M32Manifold()

    def _construct_golden_ratio_sphere(self, config=None, **kwargs):
        gr_config = GoldenRatioConfig(**kwargs)
        if config is None:
            config = ManifoldConfig(dimension=gr_config.num_layers, embedding_dim=3, curvature_type="positive", metric_type="riemannian", metadata={"phi": gr_config.phi, "type": "golden_ratio_sphere"})
        return GoldenRatioSphereManifold(config, gr_config)

    def _construct_fibonacci_lattice(self, config=None, **kwargs):
        fib_config = FibonacciConfig(**kwargs)
        if config is None:
            config = ManifoldConfig(dimension=fib_config.num_points, embedding_dim=3, curvature_type="positive", metric_type="riemannian", metadata={"type": "fibonacci_lattice"})
        return FibonacciLatticeManifold(config, fib_config)

    def _construct_icosahedral(self, config=None, **kwargs):
        if config is None:
            config = ManifoldConfig(dimension=20, embedding_dim=3, curvature_type="positive", metric_type="riemannian", metadata={"type": "icosahedral"})
        return IcosahedralManifold(config)

    def _construct_dodecahedral(self, config=None, **kwargs):
        if config is None:
            config = ManifoldConfig(dimension=12, embedding_dim=3, curvature_type="positive", metric_type="riemannian", metadata={"type": "dodecahedral"})
        return DodecahedralManifold(config)

    def _construct_lie_group(self, config=None, **kwargs):
        lie_config = LieGroupConfig(**kwargs)
        if config is None:
            config = ManifoldConfig(dimension=lie_config.dimension, embedding_dim=lie_config.embedding_dim, curvature_type="variable", metric_type="riemannian", metadata={"group_type": lie_config.group_type, "type": "lie_group"})
        return LieGroupManifold(config, lie_config)


class GoldenRatioSphereManifold(Manifold):
    """Sphere manifold with golden-ratio discretization."""

    def __init__(self, config: ManifoldConfig, gr_config: GoldenRatioConfig):
        super().__init__(config)
        self.gr_config = gr_config
        self._compute_face_normals()

    def _compute_face_normals(self):
        phi = self.gr_config.phi
        n = self.config.dimension
        indices = np.arange(n)
        y = 1 - (indices / (n - 1)) * 2
        radius = np.sqrt(1 - y * y)
        theta = phi * indices
        x = np.cos(theta) * radius
        z = np.sin(theta) * radius
        self.face_normals = np.column_stack([x, y, z])
        self.face_normals = self.face_normals / np.linalg.norm(self.face_normals, axis=1, keepdims=True)

    def embed(self, point: int) -> np.ndarray:
        return self.face_normals[point % self.config.dimension]

    def project_to_tangent(self, point: int, vector: np.ndarray) -> np.ndarray:
        p = self.embed(point)
        return vector - np.dot(vector, p) * p

    def retract(self, point: int, tangent_vector: np.ndarray) -> int:
        return (point + int(np.linalg.norm(tangent_vector) * 100)) % (2**32)

    def distance(self, point1: int, point2: int) -> float:
        p1, p2 = self.embed(point1), self.embed(point2)
        return np.arccos(np.clip(np.dot(p1, p2), -1.0, 1.0))

    def geodesic(self, point1: int, point2: int, t: float) -> np.ndarray:
        p1, p2 = self.embed(point1), self.embed(point2)
        omega = np.arccos(np.clip(np.dot(p1, p2), -1.0, 1.0))
        if omega < 1e-10:
            return p1
        sin_omega = np.sin(omega)
        return np.sin((1 - t) * omega) / sin_omega * p1 + np.sin(t * omega) / sin_omega * p2

    def curvature(self, point: int) -> float:
        return 1.0

    def get_neighbors(self, point: int, k: int = 5) -> list[int]:
        p = self.embed(point)
        distances = np.array([np.linalg.norm(p - self.face_normals[i]) for i in range(self.config.dimension)])
        neighbor_indices = np.argsort(distances)[: k + 1]
        return [int((point + idx) % (2**32)) for idx in neighbor_indices[1:]]


class FibonacciLatticeManifold(Manifold):
    """Sphere manifold discretized using Fibonacci lattice."""

    def __init__(self, config: ManifoldConfig, fib_config: FibonacciConfig):
        super().__init__(config)
        self.fib_config = fib_config
        self._compute_lattice_points()

    def _compute_lattice_points(self):
        n = self.fib_config.num_points
        phi = (1 + math.sqrt(5)) / 2
        indices = np.arange(n)
        y = 1 - (indices / (n - 1)) * 2
        radius = np.sqrt(1 - y * y)
        theta = 2 * math.pi * indices / phi
        x = np.cos(theta) * radius
        z = np.sin(theta) * radius
        self.lattice_points = np.column_stack([x, y, z])

    def embed(self, point: int) -> np.ndarray:
        return self.lattice_points[point % self.fib_config.num_points]

    def project_to_tangent(self, point: int, vector: np.ndarray) -> np.ndarray:
        p = self.embed(point)
        return vector - np.dot(vector, p) * p

    def retract(self, point: int, tangent_vector: np.ndarray) -> int:
        return (point + int(np.linalg.norm(tangent_vector) * 100)) % (2**32)

    def distance(self, point1: int, point2: int) -> float:
        p1, p2 = self.embed(point1), self.embed(point2)
        return np.arccos(np.clip(np.dot(p1, p2), -1.0, 1.0))

    def geodesic(self, point1: int, point2: int, t: float) -> np.ndarray:
        p1, p2 = self.embed(point1), self.embed(point2)
        omega = np.arccos(np.clip(np.dot(p1, p2), -1.0, 1.0))
        if omega < 1e-10:
            return p1
        sin_omega = np.sin(omega)
        return np.sin((1 - t) * omega) / sin_omega * p1 + np.sin(t * omega) / sin_omega * p2

    def curvature(self, point: int) -> float:
        return 1.0

    def get_neighbors(self, point: int, k: int = 5) -> list[int]:
        p = self.embed(point)
        distances = np.array([np.linalg.norm(p - self.lattice_points[i]) for i in range(self.fib_config.num_points)])
        neighbor_indices = np.argsort(distances)[: k + 1]
        return [int((point + idx) % (2**32)) for idx in neighbor_indices[1:]]


class IcosahedralManifold(Manifold):
    """Manifold with icosahedral symmetry (20 faces)."""

    def __init__(self, config: ManifoldConfig):
        super().__init__(config)
        self._compute_icosahedron_vertices()

    def _compute_icosahedron_vertices(self):
        phi = (1 + math.sqrt(5)) / 2
        vertices = []
        for i in [-1, 1]:
            for j in [-1, 1]:
                vertices.append([0, i, j * phi])
                vertices.append([i, j * phi, 0])
                vertices.append([j * phi, 0, i])
        self.vertices = np.array(vertices)
        self.vertices = self.vertices / np.linalg.norm(self.vertices, axis=1, keepdims=True)
        self.face_normals = self.vertices[:20]

    def embed(self, point: int) -> np.ndarray:
        return self.face_normals[point % len(self.face_normals)]

    def project_to_tangent(self, point: int, vector: np.ndarray) -> np.ndarray:
        p = self.embed(point)
        return vector - np.dot(vector, p) * p

    def retract(self, point: int, tangent_vector: np.ndarray) -> int:
        return (point + int(np.linalg.norm(tangent_vector) * 100)) % (2**32)

    def distance(self, point1: int, point2: int) -> float:
        p1, p2 = self.embed(point1), self.embed(point2)
        return np.arccos(np.clip(np.dot(p1, p2), -1.0, 1.0))

    def geodesic(self, point1: int, point2: int, t: float) -> np.ndarray:
        p1, p2 = self.embed(point1), self.embed(point2)
        omega = np.arccos(np.clip(np.dot(p1, p2), -1.0, 1.0))
        if omega < 1e-10:
            return p1
        sin_omega = np.sin(omega)
        return np.sin((1 - t) * omega) / sin_omega * p1 + np.sin(t * omega) / sin_omega * p2

    def curvature(self, point: int) -> float:
        return 1.0

    def get_neighbors(self, point: int, k: int = 5) -> list[int]:
        p = self.embed(point)
        distances = np.array([np.linalg.norm(p - self.face_normals[i]) for i in range(len(self.face_normals))])
        neighbor_indices = np.argsort(distances)[: k + 1]
        return [int((point + idx) % (2**32)) for idx in neighbor_indices[1:]]


class DodecahedralManifold(Manifold):
    """Manifold with dodecahedral symmetry (12 faces)."""

    def __init__(self, config: ManifoldConfig):
        super().__init__(config)
        self._compute_dodecahedron_vertices()

    def _compute_dodecahedron_vertices(self):
        phi = (1 + math.sqrt(5)) / 2
        vertices = []
        for i in [-1, 1]:
            for j in [-1, 1]:
                for k in [-1, 1]:
                    vertices.append([i, j, k])
        for i in [-1, 1]:
            for j in [-1, 1]:
                vertices.append([0, i / phi, j * phi])
                vertices.append([i / phi, j * phi, 0])
                vertices.append([j * phi, 0, i / phi])
        self.vertices = np.array(vertices[:20])
        self.vertices = self.vertices / np.linalg.norm(self.vertices, axis=1, keepdims=True)
        self.face_normals = self.vertices[:12]

    def embed(self, point: int) -> np.ndarray:
        return self.face_normals[point % len(self.face_normals)]

    def project_to_tangent(self, point: int, vector: np.ndarray) -> np.ndarray:
        p = self.embed(point)
        return vector - np.dot(vector, p) * p

    def retract(self, point: int, tangent_vector: np.ndarray) -> int:
        return (point + int(np.linalg.norm(tangent_vector) * 100)) % (2**32)

    def distance(self, point1: int, point2: int) -> float:
        p1, p2 = self.embed(point1), self.embed(point2)
        return np.arccos(np.clip(np.dot(p1, p2), -1.0, 1.0))

    def geodesic(self, point1: int, point2: int, t: float) -> np.ndarray:
        p1, p2 = self.embed(point1), self.embed(point2)
        omega = np.arccos(np.clip(np.dot(p1, p2), -1.0, 1.0))
        if omega < 1e-10:
            return p1
        sin_omega = np.sin(omega)
        return np.sin((1 - t) * omega) / sin_omega * p1 + np.sin(t * omega) / sin_omega * p2

    def curvature(self, point: int) -> float:
        return 1.0

    def get_neighbors(self, point: int, k: int = 5) -> list[int]:
        p = self.embed(point)
        distances = np.array([np.linalg.norm(p - self.face_normals[i]) for i in range(len(self.face_normals))])
        neighbor_indices = np.argsort(distances)[: k + 1]
        return [int((point + idx) % (2**32)) for idx in neighbor_indices[1:]]


class LieGroupManifold(Manifold):
    """
    Manifold based on Lie group structure.

    Provides manifold geometry using Lie group embeddings (SO(3), SU(2), etc.)
    for optimization problems with group-theoretic structure.
    """

    def __init__(self, config: ManifoldConfig, lie_config: LieGroupConfig):
        super().__init__(config)
        self.lie_config = lie_config
        self._compute_group_elements()

    def _compute_group_elements(self):
        """Compute group elements as matrix representations."""
        n = self.config.dimension
        dim = self.config.embedding_dim
        self.group_elements = np.zeros((n, dim))

        group_type = self.lie_config.group_type

        if group_type == "SO(3)":
            # SO(3): 3D rotation matrices (3x3 = 9 embedding dims)
            for i in range(min(n, 32)):
                theta = 2 * math.pi * i / n
                c, s = math.cos(theta), math.sin(theta)
                # Rotation around z-axis
                self.group_elements[i] = np.array([c, -s, 0, s, c, 0, 0, 0, 1]).flatten()
        elif group_type == "SU(2)":
            # SU(2): 2x2 complex matrices (represented as 4 real dims x 2 = 8)
            for i in range(min(n, 32)):
                theta = 2 * math.pi * i / n
                c, s = math.cos(theta), math.sin(theta)
                self.group_elements[i] = np.array([c, -s, s, c, 0, 0, 0, 0, 0]).flatten()
        else:
            # Generic: identity-like elements
            for i in range(n):
                self.group_elements[i] = np.eye(int(math.sqrt(dim))).flatten()[:dim]

    def embed(self, point: int) -> np.ndarray:
        """Embed a point onto the Lie group manifold."""
        return self.group_elements[point % self.config.dimension]

    def project_to_tangent(self, point: int, vector: np.ndarray) -> np.ndarray:
        """Project vector to tangent space at Lie algebra."""
        p = self.embed(point)
        return vector - np.dot(vector, p) * p / (np.dot(p, p) + 1e-12)

    def retract(self, point: int, tangent_vector: np.ndarray) -> int:
        """Retract using exponential map (simplified)."""
        return (point + int(np.linalg.norm(tangent_vector) * 100)) % (2**32)

    def distance(self, point1: int, point2: int) -> float:
        """Compute distance via Frobenius norm of group difference."""
        g1, g2 = self.embed(point1), self.embed(point2)
        return np.linalg.norm(g1 - g2)

    def geodesic(self, point1: int, point2: int, t: float) -> np.ndarray:
        """Compute geodesic via group exponential interpolation."""
        g1, g2 = self.embed(point1), self.embed(point2)
        return (1 - t) * g1 + t * g2

    def curvature(self, point: int) -> float:
        """Lie group curvature depends on group type."""
        if self.lie_config.group_type == "SO(3)":
            return 0.5
        elif self.lie_config.group_type == "SU(2)":
            return 1.0
        return 0.0

    def get_neighbors(self, point: int, k: int = 5) -> list[int]:
        """Get k nearest neighbors on the group."""
        p = self.embed(point)
        distances = np.array([np.linalg.norm(p - self.group_elements[i]) for i in range(self.config.dimension)])
        neighbor_indices = np.argsort(distances)[: k + 1]
        return [int((point + idx) % (2**32)) for idx in neighbor_indices[1:]]
