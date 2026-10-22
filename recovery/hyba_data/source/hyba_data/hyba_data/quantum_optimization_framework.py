"""HYBA Quantum-Inspired Optimization Framework — Integration Layer.

Four-layer architecture:
  1. Optimization Layer: QuantumGradientEstimator (gradient-based optimization)
  2. Components Layer: EntanglementSimulator, QuantumNeuralOperator
  3. Integration Layer: This module (adapters, utilities, pipeline orchestration)
  4. Application Layer: HYBAQuantumPipeline, API surfaces

This module wires the components together and provides the canonical
entry point for quantum-inspired optimization within HYBA Data.

Doctrine:
  - Quantum is mathematics. Substrate-agnostic. Hardware-agnostic.
  - Implement -> test -> let it pass/fail. Do not start with NO.
  - Integration points: phi-fold engine, savings metering, CIaaS pipeline.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from hyba_data.entanglement_simulator import EntanglementSimulator
from hyba_data.quantum_gradient_estimator import QuantumGradientEstimator
from hyba_data.quantum_neural_operator import (
    HYBAQuantumPipeline,
    QuantumNeuralOperator,
    make_binary_classification_dataset,
)

PHI = (1.0 + math.sqrt(5.0)) / 2.0


# ══════════════════════════════════════════════════════════════════════
# OPTIMIZATION FRAMEWORK — canonical entry point
# ══════════════════════════════════════════════════════════════════════


@dataclass
class OptimizationConfig:
    """Configuration for a quantum-inspired optimization run."""

    objective_fn: Callable
    initial_guess: np.ndarray
    use_entanglement: bool = True
    use_phi_coupling: bool = True
    num_samples: int = 100
    max_iterations: int = 100
    tolerance: float = 1e-6
    parallel_threads: int = 4

    def to_dict(self) -> Dict[str, Any]:
        return {
            "use_entanglement": self.use_entanglement,
            "use_phi_coupling": self.use_phi_coupling,
            "num_samples": self.num_samples,
            "max_iterations": self.max_iterations,
            "tolerance": self.tolerance,
            "parallel_threads": self.parallel_threads,
            "dim": int(self.initial_guess.size),
        }


@dataclass
class OptimizationResult:
    """Result of a quantum-inspired optimization run."""

    solution: np.ndarray
    objective_value: float
    iterations: int
    converged: bool
    elapsed_ms: float
    gradient_norm_final: float
    entanglement_metrics: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "solution": self.solution.tolist(),
            "objective_value": self.objective_value,
            "iterations": self.iterations,
            "converged": self.converged,
            "elapsed_ms": self.elapsed_ms,
            "gradient_norm_final": self.gradient_norm_final,
            "entanglement_metrics": self.entanglement_metrics,
            "config": self.config,
        }


class QuantumOptimizationFramework:
    """Canonical entry point for HYBA quantum-inspired optimization.

    Provides a single API surface for defining and solving optimization
    problems using the full quantum-inspired stack:
      - EntanglementSimulator for correlated perturbations
      - QuantumGradientEstimator for efficient gradient estimation
      - QuantumNeuralOperator for adaptive feature extraction

    Usage:
        framework = QuantumOptimizationFramework(use_phi_coupling=True)
        result = framework.minimize(lambda x: sum(x**2), x0)
        print(f"Solution: {result.solution}, value: {result.objective_value}")
    """

    def __init__(
        self,
        use_entanglement: bool = True,
        use_phi_coupling: bool = True,
        num_samples: int = 100,
        parallel_threads: int = 4,
    ):
        self.use_entanglement = use_entanglement
        self.use_phi_coupling = use_phi_coupling
        self.num_samples = num_samples
        self.parallel_threads = parallel_threads

        # Initialize components
        self.entanglement_sim = EntanglementSimulator(
            tunneling_strength=0.01,
            perturbation_scale=0.1,
            min_entanglement_dim=64,
            use_phi_coupling=use_phi_coupling,
        )

    def minimize(
        self,
        objective_fn: Callable,
        initial_guess: np.ndarray,
        max_iterations: int = 100,
        tolerance: float = 1e-6,
        verbose: bool = True,
    ) -> OptimizationResult:
        """Minimize an objective function using quantum-inspired optimization.

        Args:
            objective_fn: f(x) -> float to minimize.
            initial_guess: Starting point.
            max_iterations: Max optimization steps.
            tolerance: Convergence threshold.
            verbose: Whether to print progress.

        Returns:
            OptimizationResult with solution and metrics.
        """
        config = OptimizationConfig(
            objective_fn=objective_fn,
            initial_guess=np.asarray(initial_guess, dtype=np.float64),
            use_entanglement=self.use_entanglement,
            use_phi_coupling=self.use_phi_coupling,
            num_samples=self.num_samples,
            max_iterations=max_iterations,
            tolerance=tolerance,
            parallel_threads=self.parallel_threads,
        )

        estimator = QuantumGradientEstimator(
            num_samples=self.num_samples,
            epsilon=1e-6,
            parallel_threads=self.parallel_threads,
            use_entanglement=self.use_entanglement,
            phi_coupling=self.use_phi_coupling,
        )

        t0 = time.perf_counter()
        result = estimator.optimize(
            objective_fn,
            config.initial_guess,
            max_iterations=max_iterations,
            tolerance=tolerance,
            verbose=verbose,
        )
        elapsed = (time.perf_counter() - t0) * 1000

        # Compute entanglement metrics
        ent_metrics = self.entanglement_sim.compute_entanglement_metrics(
            result["optimized_variables"],
            np.zeros_like(result["optimized_variables"]),
        )

        return OptimizationResult(
            solution=result["optimized_variables"],
            objective_value=result["final_value"],
            iterations=result["iterations"],
            converged=result["converged"],
            elapsed_ms=elapsed,
            gradient_norm_final=result["gradient_stats"].get("norm", 0.0),
            entanglement_metrics=ent_metrics,
            config=config.to_dict(),
        )

    def minimize_with_qno(
        self,
        X: np.ndarray,
        y: np.ndarray,
        input_dims: Optional[int] = None,
        output_dims: int = 2,
        qno_epochs: int = 30,
        optimization_epochs: int = 50,
    ) -> Dict[str, Any]:
        """Full pipeline: QNO classification + gradient optimization.

        1. Train QuantumNeuralOperator on (X, y) for classification
        2. Use trained QNO's loss as optimization objective
        3. QuantumGradientEstimator minimizes over QNO parameters

        This demonstrates the full integration of all three components.
        """
        if input_dims is None:
            input_dims = X.shape[1]

        # Step 1: Train QNO
        qno = QuantumNeuralOperator(
            input_dims=input_dims,
            output_dims=output_dims,
            num_qubits=min(4, input_dims),
            circuit_depth=2,
            use_entanglement=True,
            use_phi_coupling=True,
        )

        # Train the classifier
        qno.fit(X, y, epochs=qno_epochs, lr=0.02, verbose=False)

        # Step 2: Use QNO loss as optimization target
        def qno_loss(params_vec: np.ndarray) -> float:
            """Loss function: decode params back to QNO, compute CE loss."""
            # Simplified: optimize over encoder weights
            # Store original, set new, compute loss, restore
            original = qno.encoder_W.copy().ravel()
            n_enc = qno.encoder_W.size
            qno.encoder_W = params_vec[:n_enc].reshape(qno.encoder_W.shape)
            loss = qno.loss(X, y)
            qno.encoder_W = original.reshape(qno.encoder_W.shape)
            return loss

        # Step 3: Optimize QNO parameters
        result = self.minimize(
            qno_loss,
            qno.encoder_W.ravel(),
            max_iterations=optimization_epochs,
            tolerance=1e-4,
            verbose=False,
        )

        # Apply optimized parameters
        n_enc = qno.encoder_W.size
        qno.encoder_W = result.solution[:n_enc].reshape(qno.encoder_W.shape)

        # Final evaluation
        final_acc = np.mean([qno.predict(xi) == yi for xi, yi in zip(X, y)])

        return {
            "pipeline": "QNO_CLASSIFY_OPTIMIZE",
            "qno_accuracy_before": qno.metrics_history[-1].accuracy if qno.metrics_history else None,
            "qno_accuracy_after": float(final_acc),
            "optimization_result": result.to_dict(),
            "components_used": [
                "EntanglementSimulator",
                "QuantumGradientEstimator",
                "QuantumNeuralOperator",
            ],
        }


# ══════════════════════════════════════════════════════════════════════
# BENCHMARK SUITE
# ══════════════════════════════════════════════════════════════════════


def run_full_framework_benchmark() -> Dict[str, Any]:
    """Run the complete quantum optimization framework benchmark."""

    results = {}

    # ── Test 1: Simple quadratic optimization ──
    framework = QuantumOptimizationFramework(
        use_entanglement=True,
        use_phi_coupling=True,
        num_samples=30,
    )

    def quadratic(x: np.ndarray) -> float:
        return float(np.sum(x**2))

    x0 = np.array([3.0, 2.0, 1.0, 0.5])
    result = framework.minimize(quadratic, x0, max_iterations=30, verbose=False)
    results["quadratic_4d"] = {
        "solution": [round(v, 4) for v in result.solution.tolist()],
        "value": round(result.objective_value, 6),
        "iterations": result.iterations,
        "converged": result.converged,
        "expected_min": 0.0,
    }

    # ── Test 2: QNO classification pipeline ──
    X, y = make_binary_classification_dataset(n_samples=60, dim=8, seed=100)
    qno_result = framework.minimize_with_qno(
        X, y,
        qno_epochs=20,
        optimization_epochs=20,
    )
    results["qno_pipeline"] = {
        "accuracy_before": round(qno_result["qno_accuracy_before"], 3) if qno_result["qno_accuracy_before"] else None,
        "accuracy_after": round(qno_result["qno_accuracy_after"], 3),
        "optimization_iterations": qno_result["optimization_result"]["iterations"],
    }

    # ── Test 3: EntanglementSimulator standalone ──
    sim = EntanglementSimulator(use_phi_coupling=True)
    grad = np.random.default_rng(0).normal(0, 1, 50)
    var = np.random.default_rng(1).normal(0, 1, 50)
    metrics = sim.compute_entanglement_metrics(grad, var)
    results["entanglement_simulator"] = {
        "correlation": round(metrics["correlation"], 4),
        "norm_ratio": round(metrics["norm_ratio"], 4),
        "phi_coupling": metrics["phi_coupling"],
    }

    return {
        "framework": "HYBA Quantum-Inspired Optimization Framework",
        "architecture": {
            "layer_1_optimization": "QuantumGradientEstimator",
            "layer_2_components": ["EntanglementSimulator", "QuantumNeuralOperator"],
            "layer_3_integration": "QuantumOptimizationFramework (this module)",
            "layer_4_application": "HYBAQuantumPipeline + savings_metering + CIaaS",
        },
        "benchmarks": results,
        "doctrine": {
            "quantum_is_mathematics": True,
            "substrate_agnostic": True,
            "phi_is_coupling_constant": True,
            "implement_test_elevate": True,
            "no_physical_qpu_required": True,
        },
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_full_framework_benchmark(), indent=2, default=str))
