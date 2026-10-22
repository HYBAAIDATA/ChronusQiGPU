"""Sparse unitary operations - efficient quantum simulation at scale.

Memory-efficient sparse matrix representations for quantum operators.
Uses pure numpy (no scipy dependency) for CSR-format sparse matrices.

Doctrine: Memory is the bottleneck. Sparse ops trade time for space.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from hyba_data.quantum_substrate import _validate_state


# Simple CSR sparse matrix in pure numpy
class CSRMatrix:
    """Compressed Sparse Row matrix - pure numpy implementation."""

    def __init__(self, data, indices, indptr, shape):
        self.data = np.asarray(data, dtype=np.complex128)
        self.indices = np.asarray(indices, dtype=np.int32)
        self.indptr = np.asarray(indptr, dtype=np.int32)
        self.shape = tuple(shape)

    def toarray(self) -> np.ndarray:
        """Convert to dense matrix."""
        M = np.zeros(self.shape, dtype=np.complex128)
        for i in range(self.shape[0]):
            for jj in range(self.indptr[i], self.indptr[i + 1]):
                j = self.indices[jj]
                M[i, j] = self.data[jj]
        return M

    def matvec(self, x: np.ndarray) -> np.ndarray:
        """Sparse matrix-vector multiply: y = A @ x."""
        y = np.zeros(self.shape[0], dtype=np.complex128)
        for i in range(self.shape[0]):
            val = 0j
            for jj in range(self.indptr[i], self.indptr[i + 1]):
                j = self.indices[jj]
                val += self.data[jj] * x[j]
            y[i] = val
        return y

    def __matmul__(self, other):
        if isinstance(other, np.ndarray) and other.ndim == 1:
            return self.matvec(other)
        raise TypeError("only matvec supported")


def sparse_single_qubit_gate(
    gate: np.ndarray, n_qubits: int, target: int
) -> CSRMatrix:
    """Build sparse single-qubit gate embedded in n-qubit system.

    Uses CSR format. Non-zero entries only where target qubit changes.
    Time: O(2^n). Space: O(2^n) sparse storage.
    """
    if gate.shape != (2, 2):
        raise ValueError(f"gate must be 2x2, got {gate.shape}")
    if target < 0 or target >= n_qubits:
        raise ValueError(f"target {target} out of range [0, {n_qubits-1}]")
    if n_qubits > 20:
        raise ValueError(f"n_qubits {n_qubits} > 20: sparse apply still O(2^n)")

    dim = 2**n_qubits
    target_bit = n_qubits - 1 - target

    indptr = [0]
    indices = []
    data_vals = []

    for row in range(dim):
        bit_val = (row >> target_bit) & 1
        # Two non-zeros per row: contribution from |0> and |1>
        for new_bit in [0, 1]:
            col = (row & ~(1 << target_bit)) | (new_bit << target_bit)
            val = gate[new_bit, bit_val]
            if abs(val) > 1e-15:
                indices.append(col)
                data_vals.append(complex(val))
        indptr.append(len(indices))

    return CSRMatrix(data_vals, indices, indptr, (dim, dim))


def sparse_cnot(n_qubits: int, control: int, target: int) -> CSRMatrix:
    """Build CNOT as a sparse permutation matrix."""
    if control < 0 or control >= n_qubits:
        raise ValueError(f"control {control} out of range")
    if target < 0 or target >= n_qubits:
        raise ValueError(f"target {target} out of range")
    if control == target:
        raise ValueError("control and target must differ")

    dim = 2**n_qubits
    c_bit = n_qubits - 1 - control
    t_bit = n_qubits - 1 - target

    indptr = []
    indices = []
    data_vals = []

    for row in range(dim):
        if (row >> c_bit) & 1:
            col = row ^ (1 << t_bit)
        else:
            col = row
        indices.append(col)
        data_vals.append(1.0 + 0j)
        indptr.append(row)
    indptr.append(dim)

    return CSRMatrix(data_vals, indices, indptr, (dim, dim))


@dataclass
class SparseGate:
    name: str
    matrix: CSRMatrix
    n_qubits: int

    def apply(self, psi: np.ndarray) -> np.ndarray:
        return self.matrix.matvec(psi)


class SparseQuantumCircuit:
    """Quantum circuit using sparse matrix operations."""

    def __init__(self, n_qubits: int, seed: int = 0):
        if n_qubits < 1 or n_qubits > 20:
            raise ValueError(f"n_qubits must be 1-20, got {n_qubits}")
        self.n_qubits = n_qubits
        self.dim = 2**n_qubits
        self.gates: List[SparseGate] = []
        self.seed = seed

    def add_gate(self, name: str, gate: CSRMatrix) -> None:
        self.gates.append(SparseGate(name, gate, self.n_qubits))

    def rx(self, theta: float, target: int) -> None:
        c, s = math.cos(theta / 2), math.sin(theta / 2)
        gate = np.array([[c, -1j * s], [-1j * s, c]], dtype=np.complex128)
        self.add_gate(f"RX({theta:.3f})_{target}", sparse_single_qubit_gate(gate, self.n_qubits, target))

    def ry(self, theta: float, target: int) -> None:
        c, s = math.cos(theta / 2), math.sin(theta / 2)
        gate = np.array([[c, -s], [s, c]], dtype=np.complex128)
        self.add_gate(f"RY({theta:.3f})_{target}", sparse_single_qubit_gate(gate, self.n_qubits, target))

    def rz(self, theta: float, target: int) -> None:
        gate = np.array(
            [[np.exp(-1j * theta / 2), 0], [0, np.exp(1j * theta / 2)]],
            dtype=np.complex128,
        )
        self.add_gate(f"RZ({theta:.3f})_{target}", sparse_single_qubit_gate(gate, self.n_qubits, target))

    def cnot(self, control: int, target: int) -> None:
        self.add_gate(f"CNOT_{control}_{target}", sparse_cnot(self.n_qubits, control, target))

    def run(self, initial_state: Optional[np.ndarray] = None) -> np.ndarray:
        if initial_state is None:
            psi = np.zeros(self.dim, dtype=np.complex128)
            psi[0] = 1.0
        else:
            psi = _validate_state(initial_state)
            if psi.size != self.dim:
                raise ValueError(f"state dim {psi.size} != circuit dim {self.dim}")
        for gate in self.gates:
            psi = gate.apply(psi)
        return psi

    def count_operations(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for g in self.gates:
            op_type = g.name.split("(")[0].split("_")[0]
            counts[op_type] = counts.get(op_type, 0) + 1
        return counts

    def depth(self) -> int:
        return len(self.gates)


def fuse_consecutive_single_qubit_gates(circuit: SparseQuantumCircuit, qubit: int) -> int:
    """Fuse consecutive single-qubit gates on the same qubit into one."""
    fused = 0
    i = 0
    while i < len(circuit.gates) - 1:
        g1 = circuit.gates[i]
        g2 = circuit.gates[i + 1]
        q1 = _extract_qubit_from_name(g1.name)
        q2 = _extract_qubit_from_name(g2.name)
        if q1 is not None and q1 == q2 and "CNOT" not in g1.name and "CNOT" not in g2.name:
            # Fuse: U2 @ U1
            fused_matrix = g2.matrix.toarray() @ g1.matrix.toarray()
            fused_sparse = _dense_to_csr(fused_matrix)
            circuit.gates[i] = SparseGate(f"FUSED_{q1}", fused_sparse, circuit.n_qubits)
            circuit.gates.pop(i + 1)
            fused += 1
        else:
            i += 1
    return fused


def _dense_to_csr(M: np.ndarray) -> CSRMatrix:
    """Convert dense matrix to CSR format."""
    M = np.asarray(M, dtype=np.complex128)
    indptr = [0]
    indices = []
    data_vals = []
    for row in range(M.shape[0]):
        for col in range(M.shape[1]):
            val = M[row, col]
            if abs(val) > 1e-15:
                indices.append(col)
                data_vals.append(complex(val))
        indptr.append(len(indices))
    return CSRMatrix(data_vals, indices, indptr, (M.shape[0], M.shape[1]))


def _extract_qubit_from_name(name: str) -> Optional[int]:
    """Extract qubit index from gate name."""
    parts = name.split("_")
    if len(parts) >= 2:
        try:
            return int(parts[-1])
        except ValueError:
            return None
    return None


def run_sparse_benchmark() -> Dict[str, Any]:
    """Benchmark sparse circuit execution."""
    import time
    results = []
    for nq in [4, 6, 8, 10]:
        circuit = SparseQuantumCircuit(n_qubits=nq, seed=42)
        h_gate = np.array([[1, 1], [1, -1]], dtype=np.complex128) / math.sqrt(2)
        for q in range(nq):
            circuit.add_gate(f"H_{q}", sparse_single_qubit_gate(h_gate, nq, q))
        for q in range(nq):
            circuit.cnot(q, (q + 1) % nq)
        t0 = time.perf_counter()
        psi = circuit.run()
        elapsed = (time.perf_counter() - t0) * 1000
        nrm = float(np.linalg.norm(psi))
        results.append({
            "n_qubits": nq, "dim": circuit.dim, "gate_count": circuit.depth(),
            "elapsed_ms": elapsed, "norm_preserved": abs(nrm - 1.0) < 1e-9,
        })
    return {
        "benchmark": "sparse_quantum_circuit",
        "results": results,
        "sparse_advantage": "Pure numpy CSR: O(2^n) per gate matvec. No scipy needed.",
        "doctrine": {"memory_is_bottleneck": True, "implement_test_elevate": True},
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_sparse_benchmark(), indent=2, default=str))
