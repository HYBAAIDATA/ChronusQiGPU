"""
Concrete Oracle Implementations.

This module provides concrete implementations of the Oracle abstract class,
including the phi-resonance oracle used in phi-Grover, as well as general-purpose
oracles for combinatorial and continuous optimization.

Author: Phi-Grover Development Team
Version: 8.0.0
"""

from __future__ import annotations

import os
import sys
from typing import Callable

import numpy as np

from .oracle import Oracle, OracleConfig

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class PhiResonanceOracle(Oracle):
    """
    Phi-resonance oracle for Bitcoin nonce optimization.

    This oracle evaluates the phi-resonance score of nonces, combining
    face alignment, Beatty sequence proximity, and Yang-Mills curvature.
    """

    def __init__(self, config: OracleConfig | None = None) -> None:
        if config is None:
            config = OracleConfig(
                optimization_type="maximization",
                objective_count=1,
                has_gradient=False,
                has_constraints=False,
                threshold=0.5,
                cache_enabled=True,
                cache_size=150000,
                metadata={
                    "name": "PhiResonance",
                    "description": "Golden ratio resonance scoring",
                },
            )
        super().__init__(config)

    def evaluate(self, point: int) -> float:
        """Evaluate phi-resonance score."""
        if self._cache is not None and point in self._cache:
            return self._cache[point]

        from core.m32 import phi_resonance_face, voronoi_cached
        point_arr = np.array([float(point & 0xFF), float((point >> 8) & 0xFF), float((point >> 16) & 0xFF)])
        value = phi_resonance_face(point_arr)
        self._evaluation_count += 1

        if self._cache is not None:
            if len(self._cache) >= self.config.cache_size:
                self._cache.clear()
            self._cache[point] = value

        return value

    def evaluate_batch(self, points: list[int]) -> list[float]:
        """Evaluate phi-resonance for multiple points."""
        return [self.evaluate(p) for p in points]

    def gradient(self, point: int) -> np.ndarray | None:
        """Phi-resonance is not differentiable."""
        return None


class CombinatorialOracle(Oracle):
    """
    General-purpose combinatorial optimization oracle.

    This oracle evaluates cost functions for combinatorial problems
    like TSP, scheduling, graph coloring, etc.
    """

    def __init__(
        self,
        cost_function: Callable[[int], float],
        config: OracleConfig | None = None,
        **kwargs,
    ) -> None:
        if config is None:
            config = OracleConfig(
                optimization_type="minimization",
                objective_count=1,
                has_gradient=False,
                has_constraints=False,
                cache_enabled=True,
                metadata={
                    "name": "Combinatorial",
                    "description": "General combinatorial optimization",
                },
            )
        self.cost_function = cost_function
        self.cost_kwargs = kwargs
        super().__init__(config)

    def evaluate(self, point: int) -> float:
        """Evaluate cost function."""
        if self._cache is not None and point in self._cache:
            return self._cache[point]
        value = self.cost_function(point, **self.cost_kwargs)
        self._evaluation_count += 1
        if self._cache is not None:
            if len(self._cache) >= self.config.cache_size:
                self._cache.clear()
            self._cache[point] = value
        return value

    def evaluate_batch(self, points: list[int]) -> list[float]:
        """Evaluate cost function for multiple points."""
        return [self.evaluate(p) for p in points]


class ContinuousOracle(Oracle):
    """
    General-purpose continuous optimization oracle.

    This oracle evaluates differentiable functions for continuous
    optimization problems, providing gradient information.
    """

    def __init__(
        self,
        objective_function: Callable[[np.ndarray], float],
        gradient_function: Callable[[np.ndarray], np.ndarray] | None = None,
        dimension: int = 10,
        config: OracleConfig | None = None,
    ) -> None:
        if config is None:
            config = OracleConfig(
                optimization_type="minimization",
                objective_count=1,
                has_gradient=gradient_function is not None,
                has_constraints=False,
                cache_enabled=True,
                metadata={
                    "name": "Continuous",
                    "description": "General continuous optimization",
                },
            )
        self.objective_function = objective_function
        self.gradient_function = gradient_function
        self.dimension = dimension
        super().__init__(config)

    def evaluate(self, point: int) -> float:
        """Evaluate objective function (convert int to vector)."""
        if self._cache is not None and point in self._cache:
            return self._cache[point]
        vector = self._int_to_vector(point)
        value = self.objective_function(vector)
        self._evaluation_count += 1
        if self._cache is not None:
            if len(self._cache) >= self.config.cache_size:
                self._cache.clear()
            self._cache[point] = value
        return value

    def evaluate_batch(self, points: list[int]) -> list[float]:
        """Evaluate objective function for multiple points."""
        return [self.evaluate(p) for p in points]

    def gradient(self, point: int) -> np.ndarray | None:
        """Compute gradient at point."""
        if self.gradient_function is None:
            return None
        vector = self._int_to_vector(point)
        return self.gradient_function(vector)

    def _int_to_vector(self, point: int) -> np.ndarray:
        """Convert integer to vector in [0,1]^dimension."""
        vector = np.zeros(self.dimension)
        for i in range(self.dimension):
            bits = (point >> (i * 8)) & 0xFF
            vector[i] = bits / 255.0
        return vector


class RastriginOracle(ContinuousOracle):
    """Rastrigin function - classic multimodal benchmark."""

    def __init__(self, dimension: int = 10, A: float = 10.0) -> None:
        def rastrigin(x: np.ndarray) -> float:
            n = len(x)
            return A * n + np.sum(x**2 - A * np.cos(2 * np.pi * x))

        def rastrigin_grad(x: np.ndarray) -> np.ndarray:
            return 2 * x + 2 * A * np.pi * np.sin(2 * np.pi * x)

        super().__init__(rastrigin, rastrigin_grad, dimension)
        self.config.metadata["name"] = "Rastrigin"
        self.config.metadata["A"] = A


class RosenbrockOracle(ContinuousOracle):
    """Rosenbrock function - classic non-convex benchmark."""

    def __init__(self, dimension: int = 10, a: float = 1.0, b: float = 5.0) -> None:
        def rosenbrock(x: np.ndarray) -> float:
            return np.sum(a * (x[1:] - x[:-1] ** 2) ** 2 + (b - x[:-1]) ** 2)

        def rosenbrock_grad(x: np.ndarray) -> np.ndarray:
            grad = np.zeros_like(x)
            grad[0] = -4 * a * x[0] * (x[1] - x[0] ** 2) - 2 * (b - x[0])
            grad[-1] = 2 * a * (x[-1] - x[-2] ** 2)
            for i in range(1, len(x) - 1):
                grad[i] = (
                    2 * a * (x[i] - x[i - 1] ** 2)
                    - 4 * a * x[i] * (x[i + 1] - x[i] ** 2)
                    - 2 * (b - x[i])
                )
            return grad

        super().__init__(rosenbrock, rosenbrock_grad, dimension)
        self.config.metadata["name"] = "Rosenbrock"
        self.config.metadata["a"] = a
        self.config.metadata["b"] = b


class AckleyOracle(ContinuousOracle):
    """Ackley function - classic multimodal benchmark."""

    def __init__(
        self, dimension: int = 10, a: float = 20.0, b: float = 0.2, c: float = 2 * np.pi
    ) -> None:
        def ackley(x: np.ndarray) -> float:
            n = len(x)
            term1 = -a * np.exp(-b * np.sqrt(np.sum(x**2) / n))
            term2 = -np.exp(np.sum(np.cos(c * x)) / n)
            return term1 + term2 + a + np.exp(1)

        super().__init__(ackley, None, dimension)
        self.config.metadata["name"] = "Ackley"
        self.config.metadata["a"] = a
        self.config.metadata["b"] = b
        self.config.metadata["c"] = c


class SphereOracle(ContinuousOracle):
    """Sphere function - simple convex benchmark."""

    def __init__(self, dimension: int = 10) -> None:
        def sphere(x: np.ndarray) -> float:
            return np.sum(x**2)

        def sphere_grad(x: np.ndarray) -> np.ndarray:
            return 2 * x

        super().__init__(sphere, sphere_grad, dimension)
        self.config.metadata["name"] = "Sphere"
