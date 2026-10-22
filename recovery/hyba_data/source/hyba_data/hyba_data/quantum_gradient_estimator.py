"""Quantum-inspired gradient estimator for efficient optimization.

Leverages superposition and entanglement principles to estimate gradients
with enhanced efficiency via parallelized finite differences and stochastic
perturbations from the EntanglementSimulator.

Part of the HYBA Quantum-Inspired Optimization Framework (Layer 1: Optimization).

Doctrine: Quantum is mathematics. Implement -> test -> push.
"""

from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, Optional

import numpy as np

from hyba_data.entanglement_simulator import EntanglementSimulator

PHI = (1.0 + math.sqrt(5.0)) / 2.0

logger = logging.getLogger(__name__)


class QuantumGradientEstimator:
    """Quantum-inspired gradient estimator using parallelized sampling.

    Combines finite-difference approximation with quantum-inspired
    perturbations to estimate gradients in high-dimensional spaces.
    Uses the EntanglementSimulator to generate correlated perturbations
    that help escape local optima.

    Attributes:
        num_samples: Number of gradient samples to average per estimation.
        epsilon: Finite difference step size.
        parallel_threads: Number of parallel threads for sampling.
        use_entanglement: Whether to apply entanglement perturbations.
        phi_coupling: Whether to use phi as coupling constant.
    """

    def __init__(
        self,
        num_samples: int = 100,
        epsilon: float = 1e-6,
        parallel_threads: int = 4,
        use_entanglement: bool = True,
        phi_coupling: bool = False,
    ):
        if num_samples <= 0:
            raise ValueError(f"num_samples must be > 0, got {num_samples}")
        if epsilon <= 0:
            raise ValueError(f"epsilon must be > 0, got {epsilon}")
        if parallel_threads <= 0:
            raise ValueError(f"parallel_threads must be > 0, got {parallel_threads}")

        self.num_samples = num_samples
        self.epsilon = epsilon
        self.parallel_threads = parallel_threads
        self.use_entanglement = use_entanglement
        self.phi_coupling = phi_coupling

        self.entanglement_simulator = EntanglementSimulator(
            tunneling_strength=0.01,
            perturbation_scale=0.1,
            min_entanglement_dim=64,
            use_phi_coupling=phi_coupling,
        )

        # History tracking
        self.gradient_history: list = []
        self.loss_history: list = []

    def estimate_gradient(
        self, objective_fn: Callable, variables: np.ndarray
    ) -> np.ndarray:
        """Estimate gradient using quantum-inspired techniques.

        For each variable, compute finite-difference partial derivative
        with quantum-inspired perturbations. Uses parallel execution
        for efficiency on multi-core systems.

        Args:
            objective_fn: Function f(x) -> float to differentiate.
            variables: Current optimization variables.

        Returns:
            Estimated gradient vector.
        """
        num_vars = variables.shape[0]
        gradient = np.zeros(num_vars, dtype=np.float64)

        def _estimate_partial(i: int) -> tuple:
            """Estimate df/dx_i with entanglement perturbation."""
            perturbation = np.zeros(num_vars, dtype=np.float64)
            perturbation[i] = self.epsilon

            if self.use_entanglement:
                entangled_pert = self.entanglement_simulator.simulate_entanglement(
                    perturbation, variables
                )
                entangled_pert = np.clip(entangled_pert[:num_vars], -100.0, 100.0)
                denom = max(abs(float(entangled_pert[i])), 1e-12)
                pert = entangled_pert * (self.epsilon / denom)
            else:
                pert = perturbation

            f_plus = objective_fn(variables + pert)
            f_minus = objective_fn(variables - pert)

            return i, (f_plus - f_minus) / (2 * self.epsilon)

        # Parallelized sampling
        total_samples = num_vars * self.num_samples
        chunk_size = max(1, total_samples // self.parallel_threads)

        with ThreadPoolExecutor(max_workers=self.parallel_threads) as executor:
            futures = []
            for sample_idx in range(self.num_samples):
                for i in range(num_vars):
                    futures.append(executor.submit(_estimate_partial, i))

            for future in as_completed(futures):
                i, partial = future.result()
                gradient[i] += partial / self.num_samples

        # Store history
        self.gradient_history.append({
            "norm": float(np.linalg.norm(gradient)),
            "mean": float(np.mean(np.abs(gradient))),
        })

        return gradient

    def optimize(
        self,
        objective_fn: Callable,
        initial_guess: np.ndarray,
        max_iterations: int = 100,
        tolerance: float = 1e-6,
        learning_rate: Optional[float] = None,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """Perform gradient-based optimization with quantum-inspired techniques.

        Iteratively updates variables by estimating gradient and taking
        steps with an adaptive learning rate schedule.

        Args:
            objective_fn: Function f(x) -> float to minimize.
            initial_guess: Starting point for optimization.
            max_iterations: Maximum optimization steps.
            tolerance: Convergence threshold on gradient norm.
            learning_rate: Fixed LR if provided, else adaptive.
            verbose: Whether to log progress.

        Returns:
            Dict with optimized variables, history, and metrics.
        """
        variables = np.asarray(initial_guess, dtype=np.float64).copy()
        history = []

        for iteration in range(max_iterations):
            # Estimate gradient
            gradient = self.estimate_gradient(objective_fn, variables)
            grad_norm = float(np.linalg.norm(gradient))

            # Check convergence
            if grad_norm < tolerance:
                if verbose:
                    print(f"Converged at iteration {iteration}: |grad| = {grad_norm:.2e} < {tolerance}")
                break

            # Compute step
            if learning_rate is not None:
                lr = learning_rate
            else:
                lr = self._compute_learning_rate(iteration, max_iterations)

            variables -= lr * gradient

            # Track
            f_val = objective_fn(variables)
            self.loss_history.append(float(f_val))
            history.append({
                "iteration": iteration,
                "gradient_norm": grad_norm,
                "learning_rate": lr,
                "objective_value": float(f_val),
            })

            if verbose and (iteration % 20 == 0 or iteration == max_iterations - 1):
                print(
                    f"Iter {iteration:3d}/{max_iterations}: "
                    f"f={f_val:.6f} |grad|={grad_norm:.2e} lr={lr:.4f}"
                )

        return {
            "optimized_variables": variables,
            "final_value": self.loss_history[-1] if self.loss_history else float(objective_fn(variables)),
            "iterations": len(history),
            "converged": grad_norm < tolerance if 'grad_norm' in dir() else False,
            "history": history,
            "gradient_stats": self.gradient_history[-1] if self.gradient_history else {},
        }

    def _compute_learning_rate(
        self, iteration: int, max_iterations: int
    ) -> float:
        """Adaptive learning rate with exponential decay.

        Starts at 0.1, decays with rate 0.1, with phi-modulation
        if coupling is enabled.
        """
        decay_rate = 0.1
        initial_lr = 0.1
        lr = initial_lr * math.exp(-decay_rate * iteration / max_iterations)

        if self.phi_coupling:
            # Phi-modulate the decay: phi-damped oscillations
            lr *= 0.5 + 0.5 * math.cos(iteration * PHI / 10.0)

        return max(lr, 1e-8)

    def reset(self) -> None:
        """Reset history for a fresh optimization run."""
        self.gradient_history.clear()
        self.loss_history.clear()


def benchmark_optimizer() -> Dict[str, Any]:
    """Benchmark the quantum gradient estimator on standard test functions."""
    import time

    results = {}

    # Rosenbrock function (banana valley — hard for gradient descent)
    def rosenbrock(x: np.ndarray) -> float:
        x = np.asarray(x, dtype=np.float64).ravel()
        return float(np.sum(100.0 * (x[1:] - x[:-1] ** 2) ** 2 + (1 - x[:-1]) ** 2))

    # Rastrigin function (many local minima)
    def rastrigin(x: np.ndarray) -> float:
        x = np.asarray(x, dtype=np.float64).ravel()
        A = 10.0
        return float(A * len(x) + np.sum(x**2 - A * np.cos(2 * math.pi * x)))

    for name, fn, dim in [
        ("rosenbrock_2d", rosenbrock, 2),
        ("rastrigin_5d", rastrigin, 5),
    ]:
        estimator = QuantumGradientEstimator(
            num_samples=20,
            epsilon=1e-5,
            use_entanglement=True,
            phi_coupling=True,
        )
        estimator.reset()

        x0 = np.random.default_rng(42).uniform(-2, 2, dim)
        t0 = time.perf_counter()
        result = estimator.optimize(
            fn, x0, max_iterations=50, tolerance=1e-4, verbose=False
        )
        elapsed = (time.perf_counter() - t0) * 1000

        results[name] = {
            "dim": dim,
            "final_value": result["final_value"],
            "iterations": result["iterations"],
            "converged": result["converged"],
            "elapsed_ms": elapsed,
            "gradient_norm_final": result["history"][-1]["gradient_norm"]
            if result["history"]
            else None,
        }

    return {
        "benchmark": "quantum_gradient_optimizer",
        "functions_tested": list(results.keys()),
        "results": results,
        "doctrine": {"quantum_is_mathematics": True, "implement_test_elevate": True},
    }


if __name__ == "__main__":
    import json
    print(json.dumps(benchmark_optimizer(), indent=2, default=str))
