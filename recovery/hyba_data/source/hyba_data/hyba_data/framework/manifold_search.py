"""
ManifoldSearch - Main Framework Orchestrator.

This module provides the main ManifoldSearch class that orchestrates
manifolds, oracles, operators, and solvers into a cohesive optimization
framework. It provides a high-level interface for running quantum-geometric
optimization on arbitrary problems.

Author: Phi-Grover Development Team
Version: 8.0.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from .manifold import Manifold, ManifoldConfig
    from .operator import Operator, OperatorConfig
    from .oracle import Oracle, OracleConfig
    from .solver import Solver, SolverConfig, SolverResult

logger = logging.getLogger(__name__)


@dataclass
class ManifoldSearchConfig:
    """Configuration for ManifoldSearch framework."""

    manifold_config: ManifoldConfig | None = None
    oracle_config: OracleConfig | None = None
    operator_config: OperatorConfig | None = None
    solver_config: SolverConfig | None = None

    enable_parallel: bool = True
    num_workers: int = 4
    enable_coherence: bool = True
    coherence_interval: int = 100
    enable_adaptive: bool = True
    adaptation_interval: int = 500
    verbose: bool = True
    save_trajectory: bool = True
    checkpoint_enabled: bool = False
    checkpoint_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ManifoldSearch:
    """
    Main orchestrator for quantum-geometric optimization framework.

    ManifoldSearch combines manifolds, oracles, operators, and solvers
    to provide a flexible, pluggable optimization framework that can
    attack a wide range of high-dimensional optimization problems.
    """

    def __init__(
        self,
        manifold: Manifold,
        oracle: Oracle,
        operator: Operator,
        solver: Solver,
        config: ManifoldSearchConfig | None = None,
    ) -> None:
        self.manifold = manifold
        self.oracle = oracle
        self.operator = operator
        self.solver = solver
        self.config = config if config is not None else ManifoldSearchConfig()
        self._results: list[SolverResult] = []
        self._start_time: datetime | None = None
        self._best_result: SolverResult | None = None

        logger.info(
            f"ManifoldSearch initialized with {type(manifold).__name__}, "
            f"{type(oracle).__name__}, {type(operator).__name__}, "
            f"{type(solver).__name__}"
        )

    def optimize(
        self,
        initial_point: int | None = None,
        initial_distribution: np.ndarray | None = None,
        num_runs: int = 1,
    ) -> SolverResult:
        """Execute optimization with configured components."""
        self._start_time = datetime.now()
        self._results = []

        if self.config.verbose:
            print("\n" + "=" * 78)
            print("MANIFOLD SEARCH OPTIMIZATION")
            print("=" * 78)
            self._print_configuration()
            print("=" * 78 + "\n")

        for run_idx in range(num_runs):
            if self.config.verbose:
                print(f"Run {run_idx + 1}/{num_runs}")
                print("-" * 78)

            result = self._run_single_optimization(initial_point, initial_distribution)
            self._results.append(result)

            if self.config.verbose:
                self._print_run_result(result)

            if self._best_result is None or self._is_better(result, self._best_result):
                self._best_result = result

        if self.config.verbose:
            print("\n" + "=" * 78)
            print("OPTIMIZATION COMPLETE")
            print("=" * 78)
            self._print_best_result()
            print("=" * 78 + "\n")

        return self._best_result if self._best_result else self._results[0]

    def _run_single_optimization(
        self, initial_point: int | None, initial_distribution: np.ndarray | None
    ) -> SolverResult:
        """Execute a single optimization run."""
        return self.solver.solve(initial_point, initial_distribution)

    def _is_better(self, result1: SolverResult, result2: SolverResult) -> bool:
        """Determine if result1 is better than result2."""
        if self.oracle.config.optimization_type == "minimization":
            return result1.best_value < result2.best_value
        else:
            return result1.best_value > result2.best_value

    def _print_configuration(self) -> None:
        """Print framework configuration."""
        print(f"Manifold: {type(self.manifold).__name__}")
        print(f"  Dimension: {self.manifold.config.dimension}")
        print(f"  Embedding: {self.manifold.config.embedding_dim}")
        print(f"  Curvature: {self.manifold.config.curvature_type}")
        print()
        print(f"Oracle: {type(self.oracle).__name__}")
        print(f"  Type: {self.oracle.config.optimization_type}")
        print(f"  Objectives: {self.oracle.config.objective_count}")
        print(f"  Has Gradient: {self.oracle.config.has_gradient}")
        print()
        print(f"Operator: {type(self.operator).__name__}")
        print(f"  Type: {self.operator.config.operator_type}")
        print(f"  Temperature: {self.operator.config.temperature}")
        print(f"  Step Size: {self.operator.config.step_size}")
        print()
        print(f"Solver: {type(self.solver).__name__}")
        print(f"  Max Iterations: {self.solver.config.max_iterations}")
        print(f"  Max Time: {self.solver.config.max_time_seconds}s")
        print(f"  Parallel Workers: {self.solver.config.parallel_workers}")
        print()
        print("Framework Settings:")
        print(f"  Parallel: {self.config.enable_parallel}")
        print(f"  Workers: {self.config.num_workers}")
        print(f"  Coherence: {self.config.enable_coherence}")
        print(f"  Adaptive: {self.config.enable_adaptive}")

    def _print_run_result(self, result: SolverResult) -> None:
        """Print result of a single run."""
        print(f"  Best Point: {result.best_point}")
        print(f"  Best Value: {result.best_value:.6f}")
        print(f"  Iterations: {result.iterations}")
        print(f"  Time: {result.elapsed_time:.3f}s")
        print(f"  Evaluations: {result.evaluation_count}")
        print(f"  Converged: {result.converged}")
        print()

    def _print_best_result(self) -> None:
        """Print best result across all runs."""
        if self._best_result is None:
            return
        total_time = (datetime.now() - self._start_time).total_seconds()
        print(f"Best Result Across {len(self._results)} Run(s):")
        print(f"  Best Point: {self._best_result.best_point}")
        print(f"  Best Value: {self._best_result.best_value:.6f}")
        print(f"  Total Time: {total_time:.3f}s")
        print(f"  Total Evaluations: {sum(r.evaluation_count for r in self._results)}")

    def optimize_parallel(
        self, num_workers: int, initial_points: list[int] | None = None
    ) -> SolverResult:
        """Execute optimization in parallel across multiple workers."""
        if not self.config.enable_parallel:
            logger.warning("Parallel execution disabled, falling back to sequential")
            return self.optimize()

        logger.info(f"Starting parallel optimization with {num_workers} workers")

        if initial_points is None:
            initial_points = [np.random.randint(0, 2**32) for _ in range(num_workers)]

        results = []
        for i, init_point in enumerate(initial_points):
            if self.config.verbose:
                print(f"Worker {i+1}/{num_workers}")
            result = self._run_single_optimization(init_point, None)
            results.append(result)
            if self._best_result is None or self._is_better(result, self._best_result):
                self._best_result = result

        return self._best_result if self._best_result else results[0]

    def get_statistics(self) -> dict[str, Any]:
        """Get optimization statistics."""
        if not self._results:
            return {}
        values = [r.best_value for r in self._results]
        times = [r.elapsed_time for r in self._results]
        evals = [r.evaluation_count for r in self._results]
        return {
            "num_runs": len(self._results),
            "best_value": (
                min(values) if self.oracle.config.optimization_type == "minimization" else max(values)
            ),
            "mean_value": np.mean(values),
            "std_value": np.std(values),
            "mean_time": np.mean(times),
            "total_time": sum(times),
            "total_evaluations": sum(evals),
            "convergence_rate": sum(1 for r in self._results if r.converged) / len(self._results),
        }

    def save_results(self, filepath: str) -> None:
        """Save optimization results to file."""
        import json
        data = {
            "best_result": (
                {
                    "best_point": self._best_result.best_point,
                    "best_value": self._best_result.best_value,
                    "iterations": self._best_result.iterations,
                    "elapsed_time": self._best_result.elapsed_time,
                    "converged": self._best_result.converged,
                    "evaluation_count": self._best_result.evaluation_count,
                }
                if self._best_result else None
            ),
            "statistics": self.get_statistics(),
            "configuration": {
                "manifold": self.manifold.get_info(),
                "oracle": self.oracle.get_info(),
                "operator": self.operator.get_info(),
                "solver": self.solver.get_info(),
            },
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Results saved to {filepath}")

    @classmethod
    def from_components(
        cls,
        manifold_class: type,
        oracle_class: type,
        operator_class: type,
        solver_class: type,
        manifold_kwargs: dict[str, Any] | None = None,
        oracle_kwargs: dict[str, Any] | None = None,
        operator_kwargs: dict[str, Any] | None = None,
        solver_kwargs: dict[str, Any] | None = None,
        config: ManifoldSearchConfig | None = None,
    ) -> ManifoldSearch:
        """Create ManifoldSearch from component classes."""
        manifold_kwargs = manifold_kwargs or {}
        oracle_kwargs = oracle_kwargs or {}
        operator_kwargs = operator_kwargs or {}
        solver_kwargs = solver_kwargs or {}

        manifold = manifold_class(**manifold_kwargs)
        oracle = oracle_class(**oracle_kwargs)
        operator = operator_class(**operator_kwargs)
        solver = solver_class(manifold, oracle, operator, **solver_kwargs)

        return cls(manifold, oracle, operator, solver, config)
