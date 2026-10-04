"""Bounded compatibility adapters for retained July quantum facades.

The adapters use Turing's existing algorithms and invariant suite. They are
software execution surfaces, not acceleration, hardware, or consensus claims.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Sequence, Tuple

from .property_invariants import InvariantReport, InvariantTestSuite
from .quantum_algorithms import ExactQFT, GroverSearch
from .quantum_tensor import Complex


HISTORICAL_REDIRECTS = {
    "FormalContract": "turing_universal_quantum_computer.certificates.RunWitness",
    "AxiomReport": "turing_universal_quantum_computer.certificates.RunWitness",
    "TheoremReport": "turing_universal_quantum_computer.certificates.RunWitness",
    "ComplexityReport": "turing_universal_quantum_computer.certificates.RunWitness",
    "FullContractReport": "turing_universal_quantum_computer.certificates.RunWitness",
    "QuantumInspiredOptimizer": "turing_universal_quantum_computer.quantum_algorithms.VQE.optimize",
    "RegenerativeContract": (
        "turing_universal_quantum_computer.phi_quantum_machine.PhiQuantumMachine.checkpoint"
    ),
    "PulviniArray": "python_backend.core_modules.geodesic_tensor_engine.ExactFoldState",
    "PulviniMatrix": "python_backend.core_modules.geodesic_tensor_engine.ExactFoldState",
    "PulviniTensor": "python_backend.core_modules.geodesic_tensor_engine.ExactFoldState",
    "PulviniCompressionService": "kellogg.compressed_tensor.QuantumCompressedTensorEngine",
    "CompressionPolicy": "kellogg.compressed_tensor.EngineConfig",
    "ArtifactCodec": "kellogg.tensor_serialization.save_pv/load_pv/validate_pv",
    "EnhancedShorAlgorithm": (
        "turing_universal_quantum_computer.july_compat.QuantumAccelerationEngine.run_shor"
    ),
    "next_gen_2025": "turing_universal_quantum_computer.capabilities.capability_report",
    "PulviniFunctor": "python_backend.core_modules.geodesic_tensor_engine.ExactFoldState",
    "AuditLedger": "al_haras.audit.HashChainAudit",
    "ComplianceVerifier": "al_haras.claims_yaml.load_claims",
    # July 2026 support surfaces retired onto canonical owners.
    "FaultSeverity": "salamander.models.Severity",
    "verify_invariants": "euclid.adapter.EuclidEngineAdapter.verify_property_invariants",
    "euclid": "euclid.adapter.EuclidEngineAdapter",
    "property_invariants": "turing_universal_quantum_computer.property_invariants.InvariantTestSuite",
    "run_ultimate_integration": "turing_universal_quantum_computer.run_all_verifications",
    "run_1000_qubit_vqc_integration": "turing_universal_quantum_computer.run_1000_qubit_verification",
    "close_gaps_test": "chronus.v33.test_harness.ChronosTestHarness",
    "run_benchmarks": "benchmarks.common",
    "memory_integration": "chronus.v33.memory.run_memory_self_tests",
    "test_pulvini_completion": "quantum_compute_substrate.pulvini",
    "test_pulvini_use_cases": "quantum_compute_substrate.pulvini",
    "test_geodesic_tensor_engine": "python_backend.core_modules.geodesic_tensor_engine",
    "test_geodesic_tensor_engine_extensions": "python_backend.core_modules.geodesic_tensor_engine",
    "test_phi_quantum_machine": "turing_universal_quantum_computer.phi_quantum_machine",
    "test_vqc_phi_grover": "turing_universal_quantum_computer.phi_vqc",
}


class UnsupportedAlgorithmError(ValueError):
    """A historical facade requested an algorithm outside the supported domain."""


@dataclass(frozen=True)
class AlgorithmResult:
    algorithm: str
    backend: str
    truth_class: str
    result: Any
    speedup_claim: bool = False
    physical_hardware: bool = False
    consensus_authority: bool = False

    def __post_init__(self) -> None:
        if self.speedup_claim or self.physical_hardware or self.consensus_authority:
            raise ValueError("software adapter results cannot assert speedup, hardware, or authority")
        if self.truth_class != "finite_precision_software_simulation":
            raise ValueError("software adapter results require an explicit simulation truth class")


class QuantumAccelerationEngine:
    """Bounded adapter to existing Turing algorithms; no acceleration is claimed."""

    def __init__(self, *, max_qubits: int = 8) -> None:
        if isinstance(max_qubits, bool) or not isinstance(max_qubits, int) or max_qubits < 1:
            raise ValueError("max_qubits must be a positive integer")
        self.max_qubits = max_qubits

    def _validate_qubits(self, n_qubits: int) -> int:
        if isinstance(n_qubits, bool) or not isinstance(n_qubits, int):
            raise TypeError("n_qubits must be an integer")
        if not 1 <= n_qubits <= self.max_qubits:
            raise UnsupportedAlgorithmError(
                f"n_qubits must be in [1, {self.max_qubits}] for the bounded dense adapter"
            )
        return n_qubits

    def run_grover(
        self,
        n_qubits: int,
        marked_indices: list[int] | tuple[int, ...],
        iterations: int | None = None,
    ) -> AlgorithmResult:
        n_qubits = self._validate_qubits(n_qubits)
        if not isinstance(marked_indices, (list, tuple)) or not marked_indices:
            raise ValueError("marked_indices must be a non-empty list or tuple")
        if any(isinstance(index, bool) or not isinstance(index, int) for index in marked_indices):
            raise TypeError("marked indices must be integers")
        if len(set(marked_indices)) != len(marked_indices):
            raise ValueError("marked indices must be unique")
        if any(index < 0 or index >= 1 << n_qubits for index in marked_indices):
            raise ValueError("marked index is outside the search domain")
        if iterations is not None and (
            isinstance(iterations, bool) or not isinstance(iterations, int) or iterations < 0
        ):
            raise ValueError("iterations must be a non-negative integer")
        value = GroverSearch(n_qubits).run(list(marked_indices), iterations)
        return AlgorithmResult(
            "grover",
            "turing.quantum_algorithms.GroverSearch",
            "finite_precision_software_simulation",
            value,
        )

    def run_qft(self, n_qubits: int, *, inverse: bool = False) -> AlgorithmResult:
        n_qubits = self._validate_qubits(n_qubits)
        if not isinstance(inverse, bool):
            raise TypeError("inverse must be a boolean")
        matrix = ExactQFT.inverse(n_qubits) if inverse else ExactQFT.matrix(n_qubits)
        return AlgorithmResult(
            "qft",
            "turing.quantum_algorithms.ExactQFT",
            "finite_precision_software_simulation",
            matrix,
        )

    def run_shor(self, *_args: Any, **_kwargs: Any) -> AlgorithmResult:
        raise UnsupportedAlgorithmError(
            "Shor factoring has no validated implementation in this backend; "
            "no factoring or quantum-speedup claim is available"
        )

    def run_qaoa(
        self,
        edges: Sequence[Sequence[int]],
        p_layers: int = 1,
        grid_points: int = 12,
    ) -> AlgorithmResult:
        """Bounded exact QAOA for MaxCut on a small graph.

        The historical ``qaoa_optimize`` facade is realised here as a real
        finite-precision simulation: the state vector is evolved exactly for
        ``p_layers`` cost/mixer pairs and the angles are chosen by a
        deterministic layer-by-layer grid search followed by one local
        refinement pass.  Nothing about the result is a hardware or speedup
        claim; ``n_qubits`` is bounded by ``max_qubits``.
        """
        parsed, n_qubits = _validate_maxcut_edges(edges)
        self._validate_qubits(n_qubits)
        if isinstance(p_layers, bool) or not isinstance(p_layers, int) or p_layers < 1:
            raise ValueError("p_layers must be a positive integer")
        if isinstance(grid_points, bool) or not isinstance(grid_points, int) or grid_points < 4:
            raise ValueError("grid_points must be an integer >= 4")

        costs = [
            sum(1 for (u, v) in parsed if ((index >> u) ^ (index >> v)) & 1)
            for index in range(1 << n_qubits)
        ]
        optimal_cost = max(costs)

        def evolve(angles: Sequence[Tuple[float, float]]) -> List[Complex]:
            dim = 1 << n_qubits
            offset = Complex(1.0 / math.sqrt(dim), 0.0)
            amplitudes = [offset] * dim
            for gamma, beta in angles:
                phase = {
                    c: Complex(math.cos(-gamma * c), math.sin(-gamma * c))
                    for c in set(costs)
                }
                amplitudes = [a * phase[c] for a, c in zip(amplitudes, costs)]
                cos_b = math.cos(beta)
                minus_i_sin_b = Complex(0.0, -math.sin(beta))
                for qubit in range(n_qubits):
                    mask = 1 << qubit
                    for base in range(dim):
                        if base & mask:
                            continue
                        partner = base | mask
                        a, b = amplitudes[base], amplitudes[partner]
                        amplitudes[base] = a * cos_b + b * minus_i_sin_b
                        amplitudes[partner] = a * minus_i_sin_b + b * cos_b
            return amplitudes

        def expectation(angles: Sequence[Tuple[float, float]]) -> float:
            amplitudes = evolve(angles)
            return sum(a.abs2() * c for a, c in zip(amplitudes, costs))

        chosen: List[Tuple[float, float]] = []
        history: List[Dict[str, Any]] = []
        for layer in range(p_layers):
            best: Tuple[float, float, float] | None = None
            for g_index in range(grid_points):
                for b_index in range(grid_points):
                    gamma = math.pi * g_index / grid_points
                    beta = math.pi * b_index / grid_points
                    value = expectation(chosen + [(gamma, beta)])
                    if best is None or value > best[0]:
                        best = (value, gamma, beta)
            assert best is not None
            step = math.pi / (2 * grid_points)
            for d_gamma in (-step, 0.0, step):
                for d_beta in (-step, 0.0, step):
                    gamma = best[1] + d_gamma
                    beta = best[2] + d_beta
                    if not (0.0 <= gamma < math.pi and 0.0 <= beta < math.pi):
                        continue
                    value = expectation(chosen + [(gamma, beta)])
                    if value > best[0]:
                        best = (value, gamma, beta)
            chosen.append((best[1], best[2]))
            history.append(
                {
                    "layer": layer,
                    "gamma": best[1],
                    "beta": best[2],
                    "cost_expectation": best[0],
                }
            )

        final_amplitudes = evolve(chosen)
        final_expectation = sum(a.abs2() * c for a, c in zip(final_amplitudes, costs))
        most_likely = max(
            range(1 << n_qubits),
            key=lambda index: (final_amplitudes[index].abs2(), -index),
        )
        result = {
            "problem": "maxcut",
            "n_qubits": n_qubits,
            "edges": [[u, v] for (u, v) in parsed],
            "p_layers": p_layers,
            "grid_points": grid_points,
            "angles": [[gamma, beta] for gamma, beta in chosen],
            "layer_history": history,
            "cost_expectation": final_expectation,
            "optimal_cost": optimal_cost,
            "approximation_ratio": (
                final_expectation / optimal_cost if optimal_cost else 1.0
            ),
            "most_likely_bitstring": format(most_likely, f"0{n_qubits}b"),
            "most_likely_cost": costs[most_likely],
            "most_likely_probability": final_amplitudes[most_likely].abs2(),
        }
        return AlgorithmResult(
            "qaoa_maxcut",
            "turing_universal_quantum_computer.july_compat.qaoa",
            "finite_precision_software_simulation",
            result,
        )


def _validate_maxcut_edges(edges: Sequence[Sequence[int]]) -> Tuple[List[Tuple[int, int]], int]:
    if not isinstance(edges, (list, tuple)) or not edges:
        raise ValueError("edges must be a non-empty list of node pairs")
    parsed: List[Tuple[int, int]] = []
    nodes = set()
    for edge in edges:
        if not isinstance(edge, (list, tuple)) or len(edge) != 2:
            raise ValueError("each edge must be a 2-element node pair")
        u, v = edge
        if any(isinstance(x, bool) or not isinstance(x, int) for x in (u, v)):
            raise TypeError("edge endpoints must be integers")
        if u == v:
            raise ValueError("self-loops are not supported")
        if u < 0 or v < 0:
            raise ValueError("edge endpoints must be non-negative")
        key = (min(u, v), max(u, v))
        if key in parsed:
            raise ValueError("edges must be unique")
        parsed.append(key)
        nodes.update(key)
    n_qubits = (max(nodes) + 1) if nodes else 0
    if sorted(nodes) != list(range(n_qubits)):
        raise ValueError("graph nodes must be labelled 0..n-1 without gaps")
    return parsed, n_qubits


OptimizerStage = Callable[
    [Callable[[Sequence[float]], float], List[float]],
    Tuple[List[float], Dict[str, Any]],
]


def grid_search_stage(low: float, high: float, points: int) -> OptimizerStage:
    """Deterministic full-grid minimisation stage over the parameter vector."""
    if not (isinstance(low, (int, float)) and isinstance(high, (int, float))):
        raise TypeError("grid bounds must be numeric")
    if not low < high:
        raise ValueError("grid requires low < high")
    if isinstance(points, bool) or not isinstance(points, int) or points < 2:
        raise ValueError("grid points must be an integer >= 2")
    step = (high - low) / (points - 1)
    lattice = [low + step * k for k in range(points)]

    def stage(
        objective: Callable[[Sequence[float]], float], theta: List[float]
    ) -> Tuple[List[float], Dict[str, Any]]:
        import itertools

        best_value = objective(theta)
        best_theta = list(theta)
        for combo in itertools.product(lattice, repeat=len(theta)):
            candidate = list(combo)
            value = objective(candidate)
            if value < best_value:
                best_value, best_theta = value, candidate
        return best_theta, {
            "stage": "grid",
            "evaluations": points ** len(theta) + 1,
            "objective_after": best_value,
        }

    return stage


def coordinate_descent_stage(
    learning_rate: float = 0.1,
    iterations: int = 20,
    epsilon: float = 1e-6,
) -> OptimizerStage:
    """Deterministic central-difference coordinate-descent stage."""
    for name, value in (("learning_rate", learning_rate), ("epsilon", epsilon)):
        if not isinstance(value, (int, float)) or not value > 0:
            raise ValueError(f"{name} must be a positive number")
    if isinstance(iterations, bool) or not isinstance(iterations, int) or iterations < 1:
        raise ValueError("iterations must be a positive integer")

    def stage(
        objective: Callable[[Sequence[float]], float], theta: List[float]
    ) -> Tuple[List[float], Dict[str, Any]]:
        current = list(theta)
        for _ in range(iterations):
            for i in range(len(current)):
                plus = current[:i] + [current[i] + epsilon] + current[i + 1 :]
                minus = current[:i] + [current[i] - epsilon] + current[i + 1 :]
                gradient = (objective(plus) - objective(minus)) / (2.0 * epsilon)
                current[i] -= learning_rate * gradient
        return current, {
            "stage": "coordinate_descent",
            "iterations": iterations,
            "objective_after": objective(current),
        }

    return stage


class CompositionStrategy:
    """Ordered composition of optimizer stages over one parameter vector.

    The historical ``CompositionStrategy`` combined optimisation passes; this
    adapter applies each stage's returned parameters to the next stage in
    declared order and records the objective value after every stage.  It is
    a deterministic software combinator — no speedup is claimed.
    """

    def __init__(self, *stages: OptimizerStage) -> None:
        if not stages:
            raise ValueError("CompositionStrategy requires at least one stage")
        for stage in stages:
            if not callable(stage):
                raise TypeError("each stage must be callable")
        self.stages = tuple(stages)

    def run(
        self,
        objective: Callable[[Sequence[float]], float],
        initial_theta: Sequence[float],
    ) -> Dict[str, Any]:
        if not callable(objective):
            raise TypeError("objective must be callable")
        if not isinstance(initial_theta, (list, tuple)) or not initial_theta:
            raise ValueError("initial_theta must be a non-empty sequence")
        if any(isinstance(t, bool) or not isinstance(t, (int, float)) for t in initial_theta):
            raise TypeError("initial_theta entries must be numeric")
        theta = [float(t) for t in initial_theta]
        records: List[Dict[str, Any]] = []
        for index, stage in enumerate(self.stages):
            outcome = stage(objective, theta)
            if not isinstance(outcome, tuple) or len(outcome) != 2:
                raise ValueError("each stage must return (theta, record)")
            theta, info = outcome
            if not isinstance(theta, list) or any(
                isinstance(t, bool) or not isinstance(t, (int, float)) for t in theta
            ):
                raise ValueError("each stage must return a numeric parameter list")
            record = {"stage_index": index, "objective_after": objective(theta)}
            if isinstance(info, dict):
                record.update(info)
            records.append(record)
        return {
            "optimal_theta": theta,
            "objective_value": objective(theta),
            "stage_records": records,
            "strategy": "sequential",
        }


class EnhancedGroverAlgorithm:
    """Compatibility facade over the bounded canonical Grover implementation."""

    def run(
        self,
        n_qubits: int,
        marked_indices: list[int] | tuple[int, ...],
        iterations: int | None = None,
    ) -> AlgorithmResult:
        return QuantumAccelerationEngine().run_grover(n_qubits, marked_indices, iterations)


class EnhancedQuantumFourierTransform:
    """Compatibility facade over Turing's bounded QFT matrix constructor."""

    def transform(self, n_qubits: int, *, inverse: bool = False) -> AlgorithmResult:
        return QuantumAccelerationEngine().run_qft(n_qubits, inverse=inverse)


def redirect_historical_surface(name: str) -> str:
    """Return the canonical replacement for a retired July-only surface."""
    if not isinstance(name, str):
        raise TypeError("historical surface name must be a string")
    try:
        return HISTORICAL_REDIRECTS[name]
    except KeyError as exc:
        raise UnsupportedAlgorithmError(
            f"no retired-surface redirect is registered for {name!r}"
        ) from exc


def run_all_verifications(
    op: Callable[..., Any] | None = None,
    inv_op: Callable[..., Any] | None = None,
) -> InvariantReport:
    """Run the canonical deterministic invariant suite and return its report."""
    report = InvariantTestSuite().run_all(op=op, inv_op=inv_op)
    if report.total_failed:
        raise AssertionError(f"invariant suite failed {report.total_failed} check(s)")
    return report


__all__ = [
    "AlgorithmResult",
    "CompositionStrategy",
    "EnhancedGroverAlgorithm",
    "EnhancedQuantumFourierTransform",
    "HISTORICAL_REDIRECTS",
    "OptimizerStage",
    "QuantumAccelerationEngine",
    "UnsupportedAlgorithmError",
    "coordinate_descent_stage",
    "grid_search_stage",
    "redirect_historical_surface",
    "run_all_verifications",
]
