"""
Abstract Oracle Interface for Quantum-Geometric Optimization.

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
class OracleConfig:
    """Configuration for oracle initialization."""

    optimization_type: str = "minimization"
    objective_count: int = 1
    has_gradient: bool = False
    has_constraints: bool = False
    threshold: float | None = None
    cache_enabled: bool = True
    cache_size: int = 100000
    metadata: dict[str, Any] = field(default_factory=dict)


class Oracle(ABC):
    """Abstract base class for oracles in quantum-geometric optimization."""

    def __init__(self, config: OracleConfig) -> None:
        self.config = config
        self._cache: dict[int, float] = {} if config.cache_enabled else None
        self._evaluation_count = 0

    @abstractmethod
    def evaluate(self, point: int) -> float:
        """Evaluate the oracle at a given point."""

    @abstractmethod
    def evaluate_batch(self, points: list[int]) -> list[float]:
        """Evaluate the oracle at multiple points."""

    def gradient(self, point: int) -> np.ndarray | None:
        """Compute gradient at a point (if differentiable)."""
        if not self.config.has_gradient:
            return None
        return None

    def hessian(self, point: int) -> np.ndarray | None:
        """Compute Hessian matrix at a point (if twice differentiable)."""
        if not self.config.has_gradient:
            return None
        return None

    def check_threshold(self, point: int) -> bool:
        """Check if point meets acceptance threshold."""
        if self.config.threshold is None:
            return True
        value = self.evaluate(point)
        if self.config.optimization_type == "minimization":
            return value <= self.config.threshold
        else:
            return value >= self.config.threshold

    def validate_constraints(self, point: int) -> tuple[bool, list[str]]:
        """Validate constraints for a point."""
        if not self.config.has_constraints:
            return True, []
        return True, []

    def multi_objective_evaluate(self, point: int) -> list[float]:
        """Evaluate multiple objectives at a point."""
        if self.config.objective_count == 1:
            return [self.evaluate(point)]
        return []

    def pareto_dominates(self, point1: int, point2: int) -> bool:
        """Check if point1 Pareto-dominates point2 (for multi-objective)."""
        obj1 = self.multi_objective_evaluate(point1)
        obj2 = self.multi_objective_evaluate(point2)
        if self.config.optimization_type == "minimization":
            return all(o1 <= o2 for o1, o2 in zip(obj1, obj2)) and any(
                o1 < o2 for o1, o2 in zip(obj1, obj2)
            )
        else:
            return all(o1 >= o2 for o1, o2 in zip(obj1, obj2)) and any(
                o1 > o2 for o1, o2 in zip(obj1, obj2)
            )

    def clear_cache(self) -> None:
        """Clear the evaluation cache."""
        if self._cache is not None:
            self._cache.clear()

    def get_evaluation_count(self) -> int:
        """Get total number of evaluations performed."""
        return self._evaluation_count

    def reset_evaluation_count(self) -> None:
        """Reset the evaluation counter."""
        self._evaluation_count = 0

    def get_info(self) -> dict[str, Any]:
        """Get information about the oracle."""
        return {
            "optimization_type": self.config.optimization_type,
            "objective_count": self.config.objective_count,
            "has_gradient": self.config.has_gradient,
            "has_constraints": self.config.has_constraints,
            "threshold": self.config.threshold,
            "cache_enabled": self.config.cache_enabled,
            "cache_size": len(self._cache) if self._cache else 0,
            "evaluation_count": self._evaluation_count,
            "metadata": self.config.metadata,
        }
