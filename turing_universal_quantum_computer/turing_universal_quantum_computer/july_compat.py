"""Bounded compatibility adapters for retained July quantum facades.

The adapters use Turing's existing algorithms and invariant suite. They are
software execution surfaces, not acceleration, hardware, or consensus claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .property_invariants import InvariantReport, InvariantTestSuite
from .quantum_algorithms import ExactQFT, GroverSearch


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
    "HamiltonianReducer": "kellogg.tensor_network.MatrixProductOperator",
    "HamiltonianResult": "kellogg.tensor_network.TensorNetworkAudit",
    "EnhancedShorAlgorithm": (
        "turing_universal_quantum_computer.july_compat.QuantumAccelerationEngine.run_shor"
    ),
    "next_gen_2025": "turing_universal_quantum_computer.capabilities.capability_report",
    "PulviniFunctor": "python_backend.core_modules.geodesic_tensor_engine.ExactFoldState",
    "AuditLedger": "al_haras.audit.HashChainAudit",
    "ComplianceVerifier": "al_haras.claims_yaml.load_claims",
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
    "EnhancedGroverAlgorithm",
    "EnhancedQuantumFourierTransform",
    "HISTORICAL_REDIRECTS",
    "QuantumAccelerationEngine",
    "UnsupportedAlgorithmError",
    "redirect_historical_surface",
    "run_all_verifications",
]
