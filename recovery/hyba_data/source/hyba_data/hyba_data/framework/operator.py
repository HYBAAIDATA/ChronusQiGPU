"""
Abstract Operator Interface for Quantum-Geometric Optimization.

This module defines the abstract base class for operators, which represent
quantum-inspired operations that transform probability distributions or
generate new candidate points. Operators provide:
- Proposal generation
- Distribution transformation
- State evolution
- Interference effects
- Tunneling/barrier crossing

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
class OperatorConfig:
    """Configuration for operator initialization."""

    operator_type: str = "mcmc"
    """Type of operator: 'mcmc', 'quantum_walk', 'riemannian_flow', 'tensor_network', 'variational'."""

    temperature: float = 1.0
    """Temperature for Metropolis-Hastings acceptance."""

    step_size: float = 1.0
    """Step size for proposals."""

    learning_rate: float = 0.01
    """Learning rate for gradient-based operators."""

    momentum: float = 0.0
    """Momentum coefficient."""

    cache_enabled: bool = True
    """Enable caching."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional operator-specific metadata."""


class Operator(ABC):
    """
    Abstract base class for operators in quantum-geometric optimization.

    An operator represents quantum-inspired operations that transform
    probability distributions or generate new candidate points.
    """

    def __init__(self, config: OperatorConfig) -> None:
        self.config = config
        self._cache: dict[int, Any] = {} if config.cache_enabled else None

    @abstractmethod
    def propose(self, current: int, distribution: np.ndarray, context: dict[str, Any]) -> int:
        """
        Generate a proposal from the current point.

        Args:
            current: Current search point
            distribution: Current probability distribution
            context: Additional context (gradient, adjacency, etc.)

        Returns:
            Proposed new point
        """

    @abstractmethod
    def accept_probability(self, current_value: float, proposed_value: float,
                           temperature: float | None = None) -> float:
        """
        Compute acceptance probability for a proposal.

        Args:
            current_value: Current objective value
            proposed_value: Proposed objective value
            temperature: Optional temperature override

        Returns:
            Acceptance probability in [0, 1]
        """

    @abstractmethod
    def transform_distribution(self, distribution: np.ndarray, context: dict[str, Any]) -> np.ndarray:
        """
        Transform the probability distribution.

        Args:
            distribution: Current probability distribution
            context: Additional context

        Returns:
            Transformed probability distribution
        """

    def clear_cache(self) -> None:
        """Clear the operation cache."""
        if self._cache is not None:
            self._cache.clear()

    def get_info(self) -> dict[str, Any]:
        """Get information about the operator."""
        return {
            "operator_type": self.config.operator_type,
            "temperature": self.config.temperature,
            "step_size": self.config.step_size,
            "learning_rate": self.config.learning_rate,
            "momentum": self.config.momentum,
            "cache_enabled": self.config.cache_enabled,
            "metadata": self.config.metadata,
        }
