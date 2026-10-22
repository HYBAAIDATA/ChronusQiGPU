"""
Abstract Solver Interface for Quantum-Geometric Optimization.

Author: Phi-Grover Development Team
Version: 8.0.0
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .manifold import Manifold
    from .operator import Operator
    from .oracle import Oracle


@dataclass
class SolverConfig:
    """Configuration for solver initialization."""

    max_iterations: int = 100000
    """Maximum number of iterations."""

    max_time_seconds: float = 300.0
    """Maximum wall-clock time."""

    convergence_threshold: float = 1e-6
    """Convergence threshold."""

    convergence_window: int = 100
    """Window for convergence detection."""

    parallel_workers: int = 1
    """Number of parallel workers."""

    verbose: bool = False
    """Enable verbose output."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional solver-specific metadata."""


@dataclass
class SolverResult:
    """Result of a solver run."""

    best_point: int
    """Best point found."""

    best_value: float
    """Best objective value found."""

    iterations: int
    """Number of iterations performed."""

    elapsed_time: float
    """Wall-clock time elapsed."""

    converged: bool
    """Whether the solver converged."""

    evaluation_count: int
    """Number of oracle evaluations."""

    trajectory: list[tuple[int, float]]
    """Optimization trajectory."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional result metadata."""


class Solver(ABC):
    """Abstract base class for solvers in quantum-geometric optimization."""

    def __init__(
        self,
        manifold: Manifold,
        oracle: Oracle,
        operator: Operator,
        config: SolverConfig | None = None,
    ) -> None:
        self.manifold = manifold
        self.oracle = oracle
        self.operator = operator
        self.config = config if config is not None else SolverConfig()
        self._start_time: datetime | None = None
        self._trajectory: list[tuple[int, float]] = []

    @abstractmethod
    def solve(
        self,
        initial_point: int | None = None,
        initial_distribution: np.ndarray | None = None,
    ) -> SolverResult:
        """Execute the optimization."""

    def _check_timeout(self) -> bool:
        """Check if time limit exceeded."""
        if self._start_time is None:
            return False
        elapsed = (datetime.now() - self._start_time).total_seconds()
        return elapsed >= self.config.max_time_seconds

    def _check_convergence(self) -> bool:
        """Check if convergence criterion is met."""
        if len(self._trajectory) < self.config.convergence_window:
            return False
        recent = [v for _, v in self._trajectory[-self.config.convergence_window:]]
        if len(recent) < 2:
            return False
        value_range = max(recent) - min(recent)
        return value_range < self.config.convergence_threshold

    def _record_trajectory(self, point: int, value: float) -> None:
        """Record a point in the optimization trajectory."""
        self._trajectory.append((point, value))

    def get_info(self) -> dict[str, Any]:
        """Get information about the solver."""
        return {
            "max_iterations": self.config.max_iterations,
            "max_time_seconds": self.config.max_time_seconds,
            "convergence_threshold": self.config.convergence_threshold,
            "parallel_workers": self.config.parallel_workers,
            "verbose": self.config.verbose,
            "metadata": self.config.metadata,
        }
