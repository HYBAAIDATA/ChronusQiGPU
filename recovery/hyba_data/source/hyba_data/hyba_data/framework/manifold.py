"""
Abstract Manifold Interface for Quantum-Geometric Optimization.

This module defines the abstract base class for manifolds, which represent
geometric spaces where optimization occurs. Manifolds provide:
- Embedding functions from search space to geometric space
- Distance/metric functions
- Tangent space operations
- Geodesic computation
- Curvature information

Author: Phi-Grover Development Team
Version: 8.0.0
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np


@dataclass
class ManifoldConfig:
    """Configuration for manifold initialization."""

    dimension: int
    """Dimension of the manifold."""

    embedding_dim: int
    """Dimension of the embedding space."""

    curvature_type: str = "flat"
    """Type of curvature: 'flat', 'positive', 'negative', 'variable'."""

    metric_type: str = "euclidean"
    """Type of metric: 'euclidean', 'riemannian', 'finsler'."""

    cache_enabled: bool = True
    """Enable caching for expensive operations."""

    cache_size: int = 100000
    """Maximum cache size."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional manifold-specific metadata."""


class Manifold(ABC):
    """
    Abstract base class for manifolds in quantum-geometric optimization.

    A manifold represents a geometric space where the optimization occurs.
    It provides methods for embedding search points, computing distances,
    and performing geometric operations.
    """

    def __init__(self, config: ManifoldConfig) -> None:
        self.config = config
        self._cache: dict[int, Any] = {} if config.cache_enabled else None

    @abstractmethod
    def embed(self, point: int) -> np.ndarray:
        """Embed a search point into the manifold."""

    @abstractmethod
    def project_to_tangent(self, point: int, vector: np.ndarray) -> np.ndarray:
        """Project a vector to the tangent space at a point."""

    @abstractmethod
    def retract(self, point: int, tangent_vector: np.ndarray) -> int:
        """Retract from tangent space back to manifold."""

    @abstractmethod
    def distance(self, point1: int, point2: int) -> float:
        """Compute geodesic distance between two points."""

    @abstractmethod
    def geodesic(self, point1: int, point2: int, t: float) -> np.ndarray:
        """Compute point along geodesic between two points."""

    @abstractmethod
    def curvature(self, point: int) -> float:
        """Compute scalar curvature at a point."""

    @abstractmethod
    def get_neighbors(self, point: int, k: int = 5) -> list[int]:
        """Get k nearest neighbors of a point on the manifold."""

    def get_domain_partition(self) -> list[tuple[int, int]]:
        """Get partition of search space into domains."""
        return [(0, (0, 2**32 - 1))]

    def get_domain_for_point(self, point: int) -> int:
        """Get domain ID for a given point."""
        return 0

    def clear_cache(self) -> None:
        """Clear the operation cache."""
        if self._cache is not None:
            self._cache.clear()

    def get_info(self) -> dict[str, Any]:
        """Get information about the manifold."""
        return {
            "dimension": self.config.dimension,
            "embedding_dim": self.config.embedding_dim,
            "curvature_type": self.config.curvature_type,
            "metric_type": self.config.metric_type,
            "cache_enabled": self.config.cache_enabled,
            "cache_size": len(self._cache) if self._cache else 0,
            "metadata": self.config.metadata,
        }
