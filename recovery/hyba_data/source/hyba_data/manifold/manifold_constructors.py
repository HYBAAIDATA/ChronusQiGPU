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
    """Original M32 dodecahedron-icosahedron compound."""

    GOLDEN_RATIO_SPHERE = "golden_ratio_sphere"
    """Sphere with golden-ratio discretization."""

    FIBONACCI_LATTICE = "fibonacci_lattice"
    """Fibonacci lattice on sphere."""

    ICOSAHEDRAL = "icosahedral"
    """Icosahedral symmetry manifold."""

    DODECAHEDRAL = "dodecahedral"
    """Dodecahedral symmetry manifold."""

    LIE_GROUP = "lie_group"
    """Lie group embedding manifold."""

    CUSTOM = "custom"
    """Custom user-defined manifold."""


@dataclass
class GoldenRatioConfig:
    """Configuration for golden-ratio based manifolds."""

    phi: float = (1 + math.sqrt(5)) / 2
    """Golden ratio value."""

    num_layers: int = 32
    """Number of layers in the structure."""

    scaling_factor: float = 1.0
    """Overall scaling factor."""

    rotation_angle: float = math.pi / 5
    """Rotation angle (default: icosahedral)."""

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FibonacciConfig:
    """Configuration for Fibonacci-based manifolds."""

    sequence: list[int] = field(default_factory=lambda: [1, 2, 3, 5, 8, 13, 21, 34, 55, 89])
    """Fibonacci sequence for discretization."""

    num_points: int = 100
    """Number of points on the sphere."""

    spiral_turns: float = 10.0
    """Number of spiral turns."""

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LieGroupConfig:
    """Configuration for Lie group manifolds."""

    group_type: str = "SO(3)"
    """Lie group type (e.g., SO(3), SU(2))."""

    dimension: int = 3
    """Dimension of the group."""

    embedding_dim: int = 9
    """Embedding dimension (for matrix representation)."""

    parameters: dict[str, float] = field(default_factory=dict)
    """Group-specific parameters."""

    metadata: dict[str, Any] = field(default_factory=dict)


class ManifoldConstructor:
    """
    Base class for manifold constructors.

    Provides extensible interface for creating manifolds with
    various geometric structures.
    """

    def __init__(self):
        """Initialize manifold constructor."""
        self._constructors: dict[ManifoldType, Callable] = {}
        self._register_default_constructors()

    def _register_default_constructors(self):
        """Register default manifold constructors."""
        self._constructors[ManifoldType.M32] = self._construct_m32
        self._constructors[ManifoldType.GOLDEN_RATIO_SPHERE] = self._construct_golden_ratio_sphere
        self._constructors[ManifoldType.FIBONACCI_LATTICE] = self._construct_fibonacci_lattice
        self._constructors[ManifoldType.ICOSAHEDRAL] = self._construct_icosahedral
        self._constructors[ManifoldType.DODECAHEDRAL] = self._construct_dodecahedral
        self._constructors[ManifoldType.LIE_GROUP] = self._construct_lie_group

    def register_constructor(self, manifold_type: ManifoldType, constructor_func: Callable) -> None:
        """
        Register a custom manifold constructor.

        Args:
            manifold_type: Type of manifold
            constructor_func: Function that constructs the manifold
        """
        self._constructors[manifold_type] = constructor_func
        logger.info(f"Registered constructor for {manifold_type.value}")

    def construct(
        self,
        manifold_type: ManifoldType,
        config: ManifoldConfig | None = None,
        **kwargs,
    ) -> Manifold:
        """
        Construct a manifold of the specified type.

        Args:
            manifold_type: Type of manifold to construct
            config: Optional manifold configuration
            **kwargs: Additional type-specific parameters

        Returns:
            Constructed manifold
        """
        if manifold_type not in self._constructors:
            msg = f"Unknown manifold type: {manifold_type}"
            raise ValueError(msg)

        constructor = self._constructors[manifold_type]
        return constructor(config, **kwargs)

    def _construct_m32(self, config: ManifoldConfig | None = None, **kwargs) -> Manifold:
        """Construct M32 manifold."""
        from .manifolds import M32Manifold

        return M32Manifold()

    def _construct_golden_ratio_sphere(
        self, config: ManifoldConfig | None = None, **kwargs
    ) -> Manifold:
        """Construct golden-ratio sphere manifold."""
        gr_config = GoldenRatioConfig(**kwargs)

        if config is None:
            config = ManifoldConfig(
                dimension=gr_config.num_layers,
                embedding_dim=3,
                curvature_type="positive",
                metric_type="riemannian",
                metadata={"phi": gr_config.phi, "type": "golden_ratio_sphere"},
            )

        return GoldenRatioSphereManifold(config, gr_config)

    def _construct_fibonacci_lattice(
        self, config: ManifoldConfig | None = None, **kwargs
    ) -> Manifold:
        """Construct Fibonacci lattice manifold."""
        fib_config = FibonacciConfig(**kwargs)

        if config is None:
            config = ManifoldConfig(
                dimension=fib_config.num_points,
                embedding_dim=3,
                curvature_type="positive",
                metric_type="riemannian",
                metadata={"type": "fibonacci_lattice"},
            )

        return FibonacciLatticeManifold(config, fib_config)

    def _construct_icosahedral(self, config: ManifoldConfig | None = None, **kwargs) -> Manifold:
        """Construct icosahedral symmetry manifold."""
        if config is None:
            config = ManifoldConfig(
                dimension=20,  # 20 faces of icosahedron
                embedding_dim=3,
                curvature_type="positive",
                metric_type="riemannian",
                metadata={"type": "icosahedral"},
            )

        return IcosahedralManifold(config)

    def _construct_dodecahedral(self, config: ManifoldConfig | None = None, **kwargs) -> Manifold:
        """Construct dodecahedral symmetry manifold."""
        if config is None:
            config = ManifoldConfig(
                dimension=12,  # 12 faces of dodecahedron
                embedding_dim=3,
                curvature_type="positive",
                metric_type="riemannian",
                metadata={"type": "dodecahedral"},
            )

        return DodecahedralManifold(config)

    def _construct_lie_group(self, config: ManifoldConfig | None = None, **kwargs) -> Manifold:
        """Construct Lie group manifold."""
        lie_config = LieGroupConfig(**kwargs)

        if config is None:
            config = ManifoldConfig(
                dimension=lie_config.dimension,
                embedding_dim=lie_config.embedding_dim,
                curvature_type="variable",
                metric_type="riemannian",
                metadata={"group_type": lie_config.group_type, "type": "lie_group"},
            )

        return LieGroupManifold(config, lie_config)


class GoldenRatioSphereManifold(Manifold):
    """
    Sphere manifold with golden-ratio discretization.

    Discretizes the sphere using golden-ratio spacing for
    optimal coverage and φ-based geometric relationships.
    """

    def __init__(self, config: ManifoldConfig, gr_config: GoldenRatioConfig):
        """
        Initialize golden-ratio sphere manifold.

        Args:
            config: Manifold configuration
            gr_config: Golden-ratio specific configuration
        """
        super().__init__(config)
        self.gr_config = gr_config
        self._compute_face_normals()

    def _compute_face_normals(self):
        """Compute face normals using golden-ratio discretization."""
        phi = self.gr_config.phi
        n = self.config.dimension

        # Golden-ratio sphere discretization
        indices = np.arange(n)
        y = 1 - (indices / (n - 1)) * 2  # y goes from 1 to -1
        radius = np.sqrt(1 - y * y)
        theta = phi * indices

        x = np.cos(theta) * radius
        z = np.sin(theta) * radius

        self.face_normals = np.column_stack([x, y, z])
        self.face_normals = self.face_normals / np.linalg.norm(
            self.face_normals, axis=1, keepdims=True
        )

    def embed(self, point: int) -> np.ndarray:
        """Embed a point onto the golden-ratio sphere."""
        # Map point to face index
        face_idx = point % self.config.dimension
        return self.face_normals[face_idx]

    def project_to_tangent(self, point: int, vector: np.ndarray) -> np.ndarray:
        """Project vector to tangent space."""
        p = self.embed(point)
        return vector - np.dot(vector, p) * p

    def retract(self, point: int, tangent_vector: np.ndarray) -> int:
        """Retract from tangent space back to manifold."""
        # Simple retraction: move to nearest face
        new_point = point + int(np.linalg.norm(tangent_vector) * 100)
        return new_point % (2**32)

    def distance(self, point1: int, point2: int) -> float:
        """Compute geodesic distance."""
        p1 = self.embed(point1)
        p2 = self.embed(point2)
        dot = np.clip(np.dot(p1, p2), -1.0, 1.0)
        return np.arccos(dot)

    def geodesic(self, point1: int, point2: int, t: float) -> np.ndarray:
        """Compute point along geodesic."""
        p1 = self.embed(point1)
        p2 = self.embed(point2)

        # Slerp (spherical linear interpolation)
        omega = np.arccos(np.clip(np.dot(p1, p2), -1.0, 1.0))

        if omega < 1e-10:
            return p1

        sin_omega = np.sin(omega)
        return np.sin((1 - t) * omega) / sin_omega * p1 + np.sin(t * omega) / sin_omega * p2

    def curvature(self, point: int) -> float:
        """Compute scalar curvature (constant for sphere)."""
        return 1.0

    def get_neighbors(self, point: int, k: int = 5) -> list[int]:
        """Get k nearest neighbors."""
        p = self.embed(point)
        distances = np.array(
            [np.linalg.norm(p - self.face_normals[i]) for i in range(self.config.dimension)]
        )
        neighbor_indices = np.argsort(distances)[: k + 1]  # +1 to exclude self
        return [int((point + idx) % (2**32)) for idx in neighbor_indices[1:]]


class FibonacciLatticeManifold(Manifold):
    """
    Sphere manifold discretized using Fibonacci lattice.

    Provides nearly-uniform point distribution on sphere using
    Fibonacci sequence for optimal coverage.
    """

    def __init__(self, config: ManifoldConfig, fib_config: FibonacciConfig):
        """
        Initialize Fibonacci lattice manifold.

        Args:
            config: Manifold configuration
            fib_config: Fibonacci specific configuration
        """
        super().__init__(config)
        self.fib_config = fib_config
        self._compute_lattice_points()

    def _compute_lattice_points(self):
        """Compute Fibonacci lattice points on sphere."""
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
        """Embed a point onto the Fibonacci lattice."""
        idx = point % self.fib_config.num_points
        return self.lattice_points[idx]

    def project_to_tangent(self, point: int, vector: np.ndarray) -> np.ndarray:
        """Project vector to tangent space."""
        p = self.embed(point)
        return vector - np.dot(vector, p) * p

    def retract(self, point: int, tangent_vector: np.ndarray) -> int:
        """Retract from tangent space back to manifold."""
        new_point = point + int(np.linalg.norm(tangent_vector) * 100)
        return new_point % (2**32)

    def distance(self, point1: int, point2: int) -> float:
        """Compute geodesic distance."""
        p1 = self.embed(point1)
        p2 = self.embed(point2)
        dot = np.clip(np.dot(p1, p2), -1.0, 1.0)
        return np.arccos(dot)

    def geodesic(self, point1: int, point2: int, t: float) -> np.ndarray:
        """Compute point along geodesic."""
        p1 = self.embed(point1)
        p2 = self.embed(point2)

        omega = np.arccos(np.clip(np.dot(p1, p2), -1.0, 1.0))

        if omega < 1e-10:
            return p1

        sin_omega = np.sin(omega)
        return np.sin((1 - t) * omega) / sin_omega * p1 + np.sin(t * omega) / sin_omega * p2

    def curvature(self, point: int) -> float:
        """Compute scalar curvature (constant for sphere)."""
        return 1.0

    def get_neighbors(self, point: int, k: int = 5) -> list[int]:
        """Get k nearest neighbors."""
        p = self.embed(point)
        distances = np.array(
            [np.linalg.norm(p - self.lattice_points[i]) for i in range(self.fib_config.num_points)]
        )
        neighbor_indices = np.argsort(distances)[: k + 1]
        return [int((point + idx) % (2**32)) for idx in neighbor_indices[1:]]


class IcosahedralManifold(Manifold):
    """
    Manifold with icosahedral symmetry.

    Uses the 20 faces of an icosahedron as the domain structure.
    """

    def __init__(self, config: ManifoldConfig):
        """Initialize icosahedral manifold."""
        super().__init__(config)
        self._compute_icosahedron_vertices()

    def _compute_icosahedron_vertices(self):
        """Compute icosahedron vertices (12) and face normals (20)."""
        phi = (1 + math.sqrt(5)) / 2

        # 12 vertices of icosahedron
        vertices = []
        for i in [-1, 1]:
            for j in [-1, 1]:
                vertices.append([0, i, j * phi])
                vertices.append([i, j * phi, 0])
                vertices.append([j * phi, 0, i])

        self.vertices = np.array(vertices)
        self.vertices = self.vertices / np.linalg.norm(self.vertices, axis=1, keepdims=True)

        # Face normals (20 faces)
        self.face_normals = self.vertices[:20]  # Simplified

    def embed(self, point: int) -> np.ndarray:
        """Embed a point onto icosahedral manifold."""
        idx = point % len(self.face_normals)
        return self.face_normals[idx]

    def project_to_tangent(self, point: int, vector: np.ndarray) -> np.ndarray:
        """Project vector to tangent space."""
        p = self.embed(point)
        return vector - np.dot(vector, p) * p

    def retract(self, point: int, tangent_vector: np.ndarray) -> int:
        """Retract from tangent space back to manifold."""
        new_point = point + int(np.linalg.norm(tangent_vector) * 100)
        return new_point % (2**32)

    def distance(self, point1: int, point2: int) -> float:
        """Compute geodesic distance."""
        p1 = self.embed(point1)
        p2 = self.embed(point2)
        dot = np.clip(np.dot(p1, p2), -1.0, 1.0)
        return np.arccos(dot)

    def geodesic(self, point1: int, point2: int, t: float) -> np.ndarray:
        """Compute point along geodesic."""
        p1 = self.embed(point1)
        p2 = self.embed(point2)

        omega = np.arccos(np.clip(np.dot(p1, p2), -1.0, 1.0))

        if omega < 1e-10:
            return p1

        sin_omega = np.sin(omega)
        return np.sin((1 - t) * omega) / sin_omega * p1 + np.sin(t * omega) / sin_omega * p2

    def curvature(self, point: int) -> float:
        """Compute scalar curvature."""
        return 1.0

    def get_neighbors(self, point: int, k: int = 5) -> list[int]:
        """Get k nearest neighbors."""
        p = self.embed(point)
        distances = np.array(
            [np.linalg.norm(p - self.face_normals[i]) for i in range(len(self.face_normals))]
        )
        neighbor_indices = np.argsort(distances)[: k + 1]
        return [int((point + idx) % (2**32)) for idx in neighbor_indices[1:]]


class DodecahedralManifold(Manifold):
    """
    Manifold with dodecahedral symmetry.

    Uses the 12 faces of a dodecahedron as the domain structure.
    """

    def __init__(self, config: ManifoldConfig):
        """Initialize dodecahedral manifold."""
        super().__init__(config)
        self._compute_dodecahedron_vertices()

    def _compute_dodecahedron_vertices(self):
        """Compute dodecahedron vertices (20)."""
        phi = (1 + math.sqrt(5)) / 2

        # 20 vertices of dodecahedron
        vertices = []
        for i in [-1, 1]:
            for j in [-1, 1]:
                for k in [-1, 1]:
                    vertices.append([i, j, k])

        # Additional vertices from golden ratio
        for i in [-1, 1]:
            for j in [-1, 1]:
                vertices.append([0, i / phi, j * phi])
                vertices.append([i / phi, j * phi, 0])
                vertices.append([j * phi, 0, i / phi])

        self.vertices = np.array(vertices[:20])
        self.vertices = self.vertices / np.linalg.norm(self.vertices, axis=1, keepdims=True)

        # Face normals (12 faces)
        self.face_normals = self.vertices[:12]

    def embed(self, point: int) -> np.ndarray:
        """Embed a point onto dodecahedral manifold."""
        idx = point % len(self.face_normals)
        return self.face_normals[idx]

    def project_to_tangent(self, point: int, vector: np.ndarray) -> np.ndarray:
        """Project vector to tangent space."""
        p = self.embed(point)
        return vector - np.dot(vector, p) * p

    def retract(self, point: int, tangent_vector: np.ndarray) -> int:
        """Retract from tangent space back to manifold."""
        new_point = point + int(np.linalg.norm(tangent_vector) * 100)
        return new_point % (2**32)

    def distance(self, point1: int, point2: int) -> float:
        """Compute geodesic distance."""
        p1 = self.embed(point1)
        p2 = self.embed(point2)
        dot = np.clip(np.dot(p1, p2), -1.0, 1.0)
        return np.arccos(dot)

    def geodesic(self, point1: int, point2: int, t: float) -> np.ndarray:
        """Compute point along geodesic."""
        p1 = self.embed(point1)
        p2 = self.embed(point2)

        omega = np.arccos(np.clip(np.dot(p1, p2), -1.0, 1.0))

        if omega < 1e-10:
            return p1

        sin_omega = np.sin(omega)
        return np.sin((1 - t) * omega) / sin_omega * p1 + np.sin(t * omega) / sin_omega * p2

    def curvature(self, point: int) -> float:
        """Compute scalar curvature."""
        return 1.0

    def get_neighbors(self, point: int, k: int = 5) -> list[int]:
        """Get k nearest neighbors."""
        p = self.embed(point)
        distances = np.array(
            [np.linalg.norm(p - self.face_normals[i]) for i in range(len(self.face_normals))]
        )
        neighbor_indices = np.argsort(distances)[: k + 1]
        return [int((point + idx) % (2**32)) for idx in neighbor_indices[1:]]


class LieGroupManifold(Manifold):
    """
    Manifold based on Lie group structure.

    Provides manifold structure for Lie groups like SO(3), SU(2), etc.
    """

    def __init__(self, config: ManifoldConfig, lie_config: LieGroupConfig):
        """
        Initialize Lie group manifold.

        Args:
            config: Manifold configuration
            lie_config: Lie group specific configuration
        """
        super().__init__(config)
        self.lie_config = lie_config

    def embed(self, point: int) -> np.ndarray:
        """Embed a point into Lie group representation."""
        # Simplified: map to rotation matrix (SO(3) case)
        # In practice, would use proper group parameterization

        # Generate rotation matrix from point
        theta = (point % 360) * math.pi / 180
        c, s = math.cos(theta), math.sin(theta)

        # Simple rotation around z-axis
        rotation = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])

        return rotation.flatten()

    def project_to_tangent(self, point: int, vector: np.ndarray) -> np.ndarray:
        """Project to tangent space of Lie group."""
        # Simplified: project to skew-symmetric matrices for SO(3)
        matrix = vector.reshape(3, 3)
        skew = (matrix - matrix.T) / 2
        return skew.flatten()

    def retract(self, point: int, tangent_vector: np.ndarray) -> int:
        """Retract using exponential map."""
        # Simplified: add tangent contribution
        new_point = point + int(np.linalg.norm(tangent_vector) * 100)
        return new_point % (2**32)

    def distance(self, point1: int, point2: int) -> float:
        """Compute geodesic distance on Lie group."""
        # Simplified: use embedding distance
        p1 = self.embed(point1)
        p2 = self.embed(point2)
        return np.linalg.norm(p1 - p2)

    def geodesic(self, point1: int, point2: int, t: float) -> np.ndarray:
        """Compute point along geodesic."""
        p1 = self.embed(point1)
        p2 = self.embed(point2)
        return (1 - t) * p1 + t * p2

    def curvature(self, point: int) -> float:
        """Compute sectional curvature."""
        # Variable curvature for Lie groups
        return 0.5

    def get_neighbors(self, point: int, k: int = 5) -> list[int]:
        """Get k nearest neighbors."""
        # Simple nearest neighbors in embedding space
        neighbors = []

        for offset in range(1, k + 1):
            neighbors.append((point + offset) % (2**32))

        return neighbors


def create_manifold_constructor() -> ManifoldConstructor:
    """Create a manifold constructor with default constructors registered."""
    return ManifoldConstructor()
