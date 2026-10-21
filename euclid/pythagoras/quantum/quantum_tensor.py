"""Canonical mathematically implemented qubit tensor.

The authoritative state is mtheory.hilbert.QuantumRegister: an exact sparse
state vector over Q(i,sqrt(2)) and exact cyclotomic extensions. This adapter
fixes the platform virtual computer at 11 qubits by default and provides an
explicit numerical export boundary for PULVINI/TT/MPO execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Sequence

import numpy as np

from mtheory.hilbert import (
    QuantumRegister,
    GroverExact,
    qft,
    reduced_density_matrix,
    von_neumann_entropy_exact,
)
from lucas.pisot import (
    HilbertCoveragePlan,
    VIRTUAL_QUANTUM_DIMENSION,
    VIRTUAL_QUANTUM_QUBITS,
    operation_record,
    plan_hilbert_coverage,
    resolve_scale,
)


@dataclass(frozen=True)
class QuantumTensorAudit:
    n_qubits: int
    dimension: int
    norm_squared: Any
    nonzero_amplitudes: int
    exact_field: str
    scale_index: int
    operations: int
    numerical_export: bool = False


class QuantumTensor:
    """Exact state tensor backed by the canonical virtual-qubit register."""

    def __init__(
        self,
        n_qubits: int = VIRTUAL_QUANTUM_QUBITS,
        *,
        basis: int = 0,
        register: Optional[QuantumRegister] = None,
        require_platform_width: bool = False,
        scale_index: Optional[int] = None,
    ) -> None:
        self.scale_index = scale_index
        self.operation_audit = []
        if register is not None:
            if not isinstance(register, QuantumRegister):
                raise TypeError("register must be mtheory.hilbert.QuantumRegister")
            if n_qubits not in (VIRTUAL_QUANTUM_QUBITS, register.n_qubits):
                raise ValueError("n_qubits conflicts with supplied register")
            self.register = register
        else:
            if n_qubits < 1:
                raise ValueError("n_qubits must be positive")
            if require_platform_width and n_qubits != VIRTUAL_QUANTUM_QUBITS:
                raise ValueError(f"production virtual quantum width is {VIRTUAL_QUANTUM_QUBITS}")
            self.register = QuantumRegister(n_qubits, basis=basis)
        self.assert_invariants()

    @property
    def n_qubits(self) -> int:
        return self.register.n_qubits

    @property
    def dimension(self) -> int:
        return self.register.dim

    @property
    def amplitudes(self) -> Dict[int, Any]:
        return dict(self.register.amplitudes)

    def copy(self) -> "QuantumTensor":
        result = QuantumTensor(register=self.register.copy(), scale_index=self.scale_index)
        result.operation_audit = list(self.operation_audit)
        return result

    def _record(self, domain: str, operation: str, logical_work: int) -> None:
        record = operation_record(domain, operation, logical_work, self.scale_index)
        self.operation_audit.append(record)

    def assert_invariants(self) -> bool:
        if self.dimension != 1 << self.n_qubits:
            raise ValueError("state dimension is not 2**n_qubits")
        self.register.assert_normalized()
        return True

    def coverage(
        self,
        *,
        available_memory_bytes: Optional[int] = None,
        data_bytes: int = 0,
        bytes_per_amplitude: int = 16,
    ) -> HilbertCoveragePlan:
        return plan_hilbert_coverage(
            self.n_qubits,
            available_memory_bytes=available_memory_bytes,
            data_bytes=data_bytes,
            bytes_per_amplitude=bytes_per_amplitude,
        )

    def audit(self, *, numerical_export: bool = False) -> QuantumTensorAudit:
        scale = resolve_scale("qubit_gate", self.scale_index)
        return QuantumTensorAudit(
            self.n_qubits,
            self.dimension,
            self.register.norm_squared(),
            len(self.register.amplitudes),
            "Q(i,sqrt(2)) + exact cyclotomics",
            scale.index,
            len(self.operation_audit),
            numerical_export,
        )

    def scale_manifest(self) -> dict:
        return {
            "default": resolve_scale("qubit_gate", self.scale_index).as_dict(),
            "operations": list(self.operation_audit),
        }

    # Exact gate operations; returning self permits deterministic composition.
    def h(self, qubit: int) -> "QuantumTensor":
        self._record("qubit_gate", "H", 1)
        self.register.apply_h(qubit)
        self.assert_invariants()
        return self

    def x(self, qubit: int) -> "QuantumTensor":
        self._record("qubit_gate", "X", 1)
        self.register.apply_x(qubit)
        self.assert_invariants()
        return self

    def z(self, qubit: int) -> "QuantumTensor":
        self._record("qubit_gate", "Z", 1)
        self.register.apply_z(qubit)
        self.assert_invariants()
        return self

    def s(self, qubit: int) -> "QuantumTensor":
        self._record("qubit_gate", "S", 1)
        self.register.apply_s(qubit)
        self.assert_invariants()
        return self

    def t(self, qubit: int) -> "QuantumTensor":
        self._record("qubit_gate", "T", 1)
        self.register.apply_t(qubit)
        self.assert_invariants()
        return self

    def phase(self, qubit: int, turns: Any) -> "QuantumTensor":
        self._record("qubit_gate", "PHASE", 1)
        self.register.apply_phase(qubit, turns)
        self.assert_invariants()
        return self

    def cnot(self, control: int, target: int) -> "QuantumTensor":
        self._record("qubit_gate", "CNOT", 1)
        self.register.apply_cnot(control, target)
        self.assert_invariants()
        return self

    def hadamard_all(self) -> "QuantumTensor":
        self._record("qubit_gate", "H_ALL", self.n_qubits)
        for qubit in range(self.n_qubits):
            self.register.apply_h(qubit)
        self.assert_invariants()
        return self

    def qft(
        self, qubits: Optional[Sequence[int]] = None, *, inverse: bool = False
    ) -> "QuantumTensor":
        selected = tuple(range(self.n_qubits)) if qubits is None else tuple(qubits)
        self._record("qft", "IQFT" if inverse else "QFT", 1 << len(selected))
        qft(self.register, selected, inverse=inverse)
        self.assert_invariants()
        return self

    def grover(self, marked: int, iterations: Optional[int] = None) -> "QuantumTensor":
        if not 0 <= marked < self.dimension:
            raise ValueError("marked basis index out of range")
        self.register.uniform_superposition()
        count = (
            GroverExact(self.n_qubits, marked).optimal_iterations()
            if iterations is None
            else iterations
        )
        self._record("grover", "GROVER", count)
        if count < 0:
            raise ValueError("iterations must be non-negative")
        for _ in range(count):
            self.register.apply_grover_oracle(marked)
            self.register.diffusion()
        self.assert_invariants()
        return self

    def born_distribution(self, include_zeros: bool = False) -> Dict[int, Any]:
        return self.register.distribution(include_zeros=include_zeros)

    def measure_classically(self, seed: int) -> int:
        return self.register.measure(seed)

    def reduced_density_matrix(self, subsystem: Iterable[int]):
        return reduced_density_matrix(self.register, tuple(subsystem))

    def von_neumann_entropy(self, subsystem: Iterable[int]):
        return von_neumann_entropy_exact(self.register, tuple(subsystem))

    def to_numpy(self, *, dtype: np.dtype = np.complex128) -> np.ndarray:
        """Explicit finite-precision export; canonical state remains exact."""
        output = np.zeros(self.dimension, dtype=dtype)
        for index, amplitude in self.register.amplitudes.items():
            value = (
                amplitude.to_sympy().evalf(30)
                if hasattr(amplitude, "to_sympy")
                else amplitude.evalf(30)
            )
            output[index] = complex(value)
        return output

    def to_pulvini_input(self) -> np.ndarray:
        return self.to_numpy()

    @classmethod
    def from_numpy(
        cls, values: Sequence[complex], *, n_qubits: Optional[int] = None
    ) -> "QuantumTensor":
        raise TypeError("from_numpy is intentionally unsupported; construct exact gates instead")


__all__ = [
    "VIRTUAL_QUANTUM_QUBITS",
    "VIRTUAL_QUANTUM_DIMENSION",
    "HilbertCoveragePlan",
    "plan_hilbert_coverage",
    "QuantumTensorAudit",
    "QuantumTensor",
]
