# tensor_compression.py -- Matrix Product State (tensor-train) representation
# for large qubit counts.
#
# Added per explicit user instruction: "fold in my 1000 qubit tensor ... we
# have our memory compression system that you can use." This replaces the
# pasted pseudocode's infeasible claims of dense state vectors (Cambridge_GQN's
# "Output: size 2**qubit_count" for qubit_count=100; Caltech's
# "braid_matrix = IDENTITY(2**len(self.anyons))" for 1000 anyons) with the
# real mathematical technique that actually makes large qubit counts
# tractable: a bond-dimension-truncated Matrix Product State (MPS / tensor
# train). This is standard tensor-network quantum-simulation math, the same
# family of technique referenced in this workspace's own real
# HYBAANALYTICS76/HYBA_Pythia_Prod tensor_network.py / tensor_train.py
# (MatrixProductState / TensorTrainState, bond_dim=64) -- hardware-agnostic:
# it is pure linear algebra, not tied to any physical qubit substrate.
#
# Honesty note: a prior real audit of this workspace's own TensorTrainState
# (see the "VQC Deep Ansatz 384-Parameter Extension" page) found it was NOT
# actually achieving compression (is_compressed: false, 0.44x -- larger than
# dense). audit_compression() below always actually computes and reports the
# real ratio for the current n_qubits/bond_dim, rather than assuming
# compression is achieved.

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np


@dataclass
class CompressionAudit:
    n_qubits: int
    bond_dim: int
    dense_amplitude_count: float
    mps_parameter_count: int
    compression_ratio: float
    is_compressed: bool


class MatrixProductState:
    # Real MPS for `n_qubits` qubits with a bounded bond dimension
    # `bond_dim`. Memory scales as O(n_qubits * bond_dim^2), not
    # O(2^n_qubits) -- this is what actually makes a "1000 qubit" state
    # tractable to build and manipulate, unlike a dense state vector.

    def __init__(self, n_qubits: int, bond_dim: int = 16):
        self.n = n_qubits
        self.chi = bond_dim
        self.d = 2  # physical (qubit) dimension
        # Initialize as the |000...0> product state: every tensor starts at
        # bond dimension 1 -- a genuinely exact MPS representation of a
        # product state. Entanglement (and bond dimension, up to the chi
        # cap) grows only as two-qubit gates are actually applied.
        self.tensors: List[np.ndarray] = []
        for _ in range(n_qubits):
            t = np.zeros((1, self.d, 1), dtype=complex)
            t[0, 0, 0] = 1.0
            self.tensors.append(t)
        self.bond_singular_values: Dict[int, np.ndarray] = {}

    def apply_single_qubit_gate(self, site: int, gate: np.ndarray) -> None:
        t = self.tensors[site]
        self.tensors[site] = np.einsum("ab,lbr->lar", gate, t)

    def apply_two_qubit_gate(self, site: int, gate: np.ndarray) -> float:
        # Standard MPS two-site update: merge sites (site, site+1) -> apply
        # the real 4x4 gate -> SVD -> truncate to bond_dim. Returns the real
        # truncation error (sum of squared discarded singular values,
        # normalized) so truncation is never silently hidden.
        left = self.tensors[site]        # (chi_l, d, chi_m)
        right = self.tensors[site + 1]   # (chi_m, d, chi_r)
        chi_l, d, chi_m = left.shape
        _, d2, chi_r = right.shape
        theta = np.einsum("lar,rbs->labs", left, right)          # (chi_l, d, d, chi_r)
        two_site = theta.reshape(chi_l, d * d2, chi_r)
        gated = np.einsum("pq,lqr->lpr", gate, two_site)          # apply the 4x4 gate
        gated4 = gated.reshape(chi_l, d, d2, chi_r)
        mat = gated4.reshape(chi_l * d, d2 * chi_r)
        u, s, vh = np.linalg.svd(mat, full_matrices=False)
        keep = min(self.chi, len(s))
        total_weight = float(np.sum(s ** 2)) or 1.0
        truncation_error = float(np.sum(s[keep:] ** 2)) / total_weight if keep < len(s) else 0.0
        u, s, vh = u[:, :keep], s[:keep], vh[:keep, :]
        norm = np.linalg.norm(s)
        if norm > 0:
            s = s / norm  # renormalize the kept Schmidt coefficients
        self.bond_singular_values[site + 1] = s.copy()
        new_left = u.reshape(chi_l, d, keep)
        new_right = (np.diag(s) @ vh).reshape(keep, d2, chi_r)
        self.tensors[site] = new_left
        self.tensors[site + 1] = new_right
        return truncation_error

    def entanglement_entropy(self, bond: int) -> float:
        # Real von Neumann entropy from the Schmidt coefficients captured at
        # the last SVD split across this bond. Valid immediately following
        # that bond's own two-qubit-gate split; this is not a globally
        # maintained canonical form across every bond simultaneously.
        if bond not in self.bond_singular_values:
            return 0.0
        s = self.bond_singular_values[bond]
        p = s ** 2
        p = p[p > 1e-14]
        return float(-np.sum(p * np.log2(p)))

    def expectation_local_z(self, site: int) -> float:
        t = self.tensors[site]
        z = np.array([[1, 0], [0, -1]], dtype=complex)
        tz = np.einsum("ab,lbr->lar", z, t)
        num = np.einsum("lar,lar->", t.conj(), tz).real
        den = np.einsum("lar,lar->", t.conj(), t).real
        return float(num / den) if den != 0 else 0.0

    def to_dense(self) -> np.ndarray:
        # Verification helper for small systems only -- a real 1000-qubit
        # dense vector (2**1000 amplitudes) is not representable in memory
        # by anyone; that is precisely why the MPS representation above
        # exists.
        if self.n > 20:
            raise ValueError(
                f"to_dense() is only for correctness verification on small systems (n<=20); "
                f"n={self.n} would require 2**{self.n} amplitudes."
            )
        vec = self.tensors[0].reshape(self.tensors[0].shape[1], self.tensors[0].shape[2])  # (d, chi)
        for t in self.tensors[1:]:
            vec = np.einsum("pc,cdr->pdr", vec, t)
            vec = vec.reshape(vec.shape[0] * vec.shape[1], vec.shape[2])
        return vec.reshape(-1)

    def audit_compression(self) -> CompressionAudit:
        mps_param_count = sum(t.size for t in self.tensors)
        dense_amplitude_count = float(2 ** self.n)
        ratio = dense_amplitude_count / mps_param_count if mps_param_count > 0 else 0.0
        return CompressionAudit(
            n_qubits=self.n, bond_dim=self.chi,
            dense_amplitude_count=dense_amplitude_count,
            mps_parameter_count=mps_param_count,
            compression_ratio=ratio, is_compressed=ratio > 1.0,
        )


def _self_test() -> None:
    # Real correctness check: H on qubit 0, then CNOT(0,1) on a 2-qubit MPS
    # should produce the exact Bell state, with entanglement entropy 1.0.
    h = (1 / np.sqrt(2)) * np.array([[1, 1], [1, -1]], dtype=complex)
    cnot = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], dtype=complex)
    mps = MatrixProductState(n_qubits=2, bond_dim=4)
    mps.apply_single_qubit_gate(0, h)
    mps.apply_two_qubit_gate(0, cnot)
    dense = mps.to_dense()
    expected = np.array([1, 0, 0, 1], dtype=complex) / np.sqrt(2)
    assert np.allclose(dense, expected, atol=1e-10), f"MPS Bell-state mismatch: {dense} vs {expected}"
    entropy = mps.entanglement_entropy(1)
    assert abs(entropy - 1.0) < 1e-8, f"expected entanglement entropy 1.0, got {entropy}"
    print("tensor_compression._self_test: PASS (real Bell state + entropy=1.0 verified)")


if __name__ == "__main__":
    _self_test()
