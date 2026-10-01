"""
MPS-backed quantum state memory.

Wraps the existing Chronos MatrixProductState (academic/tensor_compression.py)
as a first-class memory device: store, load, apply gates, audit compression.

This is the real "1000-qubit memory" of Chronos GPU — pure tensor-network
linear algebra, no hardware claims.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from ..academic.tensor_compression import MatrixProductState


@dataclass
class MemoryAudit:
    n_qubits: int
    bond_dim: int
    dense_amplitude_count: float
    mps_parameter_count: int
    compression_ratio: float
    is_compressed: bool
    entanglement_entropy_mid: float
    max_truncation_error: float


class MPSStore:
    """
    Quantum state memory using a bond-dimension-truncated MPS.

    Capacity: n_qubits logical qubits.
    Memory cost: O(n_qubits * bond_dim²) complex parameters.
    """

    def __init__(self, n_qubits: int, bond_dim: int = 64, name: str = "MPSStore"):
        if n_qubits < 1:
            raise ValueError("n_qubits must be ≥ 1")
        self.n = n_qubits
        self.chi = bond_dim
        self.name = name
        self._mps = MatrixProductState(n_qubits=n_qubits, bond_dim=bond_dim)
        self._truncation_errors: List[float] = []
        self._gate_count = 0

    def reset_product_zero(self) -> None:
        """Return to |0…0⟩ product state."""
        self._mps = MatrixProductState(n_qubits=self.n, bond_dim=self.chi)
        self._truncation_errors.clear()
        self._gate_count = 0

    def apply_single(self, site: int, gate: np.ndarray) -> None:
        self._mps.apply_single_qubit_gate(site, gate)
        self._gate_count += 1

    def apply_two(self, site: int, gate: np.ndarray) -> float:
        err = self._mps.apply_two_qubit_gate(site, gate)
        self._truncation_errors.append(err)
        self._gate_count += 1
        return err

    def load_ghz(self) -> float:
        """Build a GHZ state via H + CNOT chain. Returns max truncation error."""
        self.reset_product_zero()
        h = (1 / np.sqrt(2)) * np.array([[1, 1], [1, -1]], dtype=complex)
        cnot = np.array(
            [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]],
            dtype=complex,
        )
        self.apply_single(0, h)
        max_err = 0.0
        for i in range(self.n - 1):
            err = self.apply_two(i, cnot)
            max_err = max(max_err, err)
        return max_err

    def entanglement_entropy(self, bond: Optional[int] = None) -> float:
        if bond is None:
            bond = self.n // 2
        return self._mps.entanglement_entropy(bond)

    def expectation_z(self, site: int) -> float:
        return self._mps.expectation_local_z(site)

    def audit(self) -> MemoryAudit:
        raw = self._mps.audit_compression()
        mid = self.entanglement_entropy(self.n // 2)
        max_err = max(self._truncation_errors) if self._truncation_errors else 0.0
        return MemoryAudit(
            n_qubits=raw.n_qubits,
            bond_dim=raw.bond_dim,
            dense_amplitude_count=raw.dense_amplitude_count,
            mps_parameter_count=raw.mps_parameter_count,
            compression_ratio=raw.compression_ratio,
            is_compressed=raw.is_compressed,
            entanglement_entropy_mid=mid,
            max_truncation_error=max_err,
        )

    def to_dense_small(self) -> np.ndarray:
        """Only for n ≤ 12 verification."""
        if self.n > 12:
            raise MemoryError("to_dense_small refused for n>12")
        return self._mps.to_dense()

    @property
    def gate_count(self) -> int:
        return self._gate_count


def _self_test() -> str:
    # Small Bell state
    store = MPSStore(n_qubits=2, bond_dim=8)
    store.load_ghz()
    dense = store.to_dense_small()
    expected = np.array([1, 0, 0, 1], dtype=complex) / np.sqrt(2)
    phase = 1.0
    if abs(dense[0]) > 1e-12:
        phase = np.exp(-1j * np.angle(dense[0] / expected[0]))
    assert np.allclose(dense * phase, expected, atol=1e-10)
    assert abs(store.entanglement_entropy(1) - 1.0) < 1e-10

    # Compression audit on 20 qubits
    big = MPSStore(n_qubits=20, bond_dim=16)
    big.load_ghz()
    audit = big.audit()
    assert audit.is_compressed
    assert audit.compression_ratio > 100
    assert audit.max_truncation_error == 0.0  # GHZ rank-2 < chi=16
    return "memory.mps_store._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
