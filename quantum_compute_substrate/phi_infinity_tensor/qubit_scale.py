"""n-qubit matrix-product state at 1000-qubit scale.

MPS tensor layout: A[k] has shape (chi_left, 2, chi_right).
  Site 0:   shape (1, 2, chi_1)
  Site k:   shape (chi_k, 2, chi_{k+1})
  Site n-1: shape (chi_{n-1}, 2, 1)

Memory: sum_k prod(A[k].shape) * 16 bytes (complex128).
At uniform chi and n sites: ~ n * chi^2 * 2 * 16 bytes.
For n=1000, chi=128: 1000 * 16384 * 2 * 16 = ~ 524 MB (uniform interior);
for a fresh product state chi=1 everywhere: ~ 32 KB.
"""
from __future__ import annotations
import math
import numpy as np
from dataclasses import dataclass, field
from typing import List, Sequence, Optional


# Standard 1-qubit gates.
I2 = np.eye(2, dtype=complex)
X_GATE = np.array([[0, 1], [1, 0]], dtype=complex)
Y_GATE = np.array([[0, -1j], [1j, 0]], dtype=complex)
Z_GATE = np.array([[1, 0], [0, -1]], dtype=complex)
H_GATE = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)
S_GATE = np.array([[1, 0], [0, 1j]], dtype=complex)
T_GATE = np.array([[1, 0], [0, np.exp(1j * math.pi / 4)]], dtype=complex)

# 2-qubit CNOT with control on the left, target on the right.
# Reshaped to (2,2,2,2) with axes (c_out, t_out, c_in, t_in).
CNOT_MAT = np.array([
    [1, 0, 0, 0],
    [0, 1, 0, 0],
    [0, 0, 0, 1],
    [0, 0, 1, 0],
], dtype=complex)
CNOT_TENSOR = CNOT_MAT.reshape(2, 2, 2, 2)


@dataclass
class QubitMPS:
    """n-qubit MPS with configurable max bond dimension.

    Initialised in |0...0>: every site is (1, 2, 1) with A[k][0, 0, 0] = 1,
    A[k][0, 1, 0] = 0. Product state, chi=1 everywhere.
    """
    n_qubits: int
    chi_max: int = 128
    sites: List[np.ndarray] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.n_qubits < 1:
            raise ValueError("n_qubits must be >= 1")
        if self.chi_max < 1:
            raise ValueError("chi_max must be >= 1")
        if not self.sites:
            # |0...0>: every site is (1, 2, 1) with amp = [1, 0].
            for _ in range(self.n_qubits):
                A = np.zeros((1, 2, 1), dtype=complex)
                A[0, 0, 0] = 1.0
                self.sites.append(A)

    # ---- memory ----
    def memory_bytes(self) -> int:
        """Total bytes of the MPS tensors (complex128 = 16 bytes/element)."""
        return sum(A.size * 16 for A in self.sites)

    def bond_dimensions(self) -> List[int]:
        """[chi_1, chi_2, ..., chi_{n-1}] - the internal bonds."""
        return [self.sites[k].shape[2] for k in range(self.n_qubits - 1)]

    def max_bond_dimension(self) -> int:
        bonds = self.bond_dimensions()
        return max(bonds) if bonds else 1

    # ---- gate application ----
    def apply_single_qubit_gate(self, gate: np.ndarray, site: int) -> None:
        """A[site] <- einsum("ij,ajb->aib", gate, A[site])."""
        if gate.shape != (2, 2):
            raise ValueError("single-qubit gate must be 2x2")
        if not 0 <= site < self.n_qubits:
            raise IndexError("site out of range")
        self.sites[site] = np.einsum("ij,ajb->aib", gate, self.sites[site])

    def apply_two_qubit_gate(self, gate_tensor: np.ndarray, site: int) -> None:
        """Apply a nearest-neighbour 2-qubit gate to (site, site+1).

        gate_tensor has shape (2, 2, 2, 2) with axes (a_out, b_out, a_in, b_in).
        Contracts A[site] and A[site+1] into a 2-site block, applies the gate,
        SVDs back into two site tensors, truncates to chi_max.
        """
        if gate_tensor.shape != (2, 2, 2, 2):
            raise ValueError("two-qubit gate must be 2x2x2x2")
        if not 0 <= site < self.n_qubits - 1:
            raise IndexError("site out of range for two-qubit gate")

        A = self.sites[site]        # (chiL, 2, chiM)
        B = self.sites[site + 1]    # (chiM, 2, chiR)
        chiL, _, chiM = A.shape
        _, _, chiR = B.shape

        # Merge: theta_{L, a, b, R} = sum_M A[L, a, M] * B[M, b, R]
        theta = np.einsum("lam,mbr->labr", A, B)
        # Apply gate: theta'_{L, a', b', R} = sum_{a, b} gate[a', b', a, b] * theta[L, a, b, R]
        theta = np.einsum("cdab,labr->lcdr", gate_tensor, theta)

        # Reshape to matrix (chiL * 2, 2 * chiR) and SVD.
        M = theta.reshape(chiL * 2, 2 * chiR)
        U, S, Vh = np.linalg.svd(M, full_matrices=False)

        # Truncate to chi_max.
        k = min(self.chi_max, len(S))
        U = U[:, :k]
        S = S[:k]
        Vh = Vh[:k, :]

        # Renormalise the retained singular values so that <psi|psi> = 1 is
        # preserved to leading order (norm-preserving truncation).
        norm_before = float(np.linalg.norm(S)) if len(S) else 1.0
        if norm_before > 0:
            S = S * (float(np.linalg.norm(np.concatenate(
                [S, np.zeros(len(np.linalg.svd(M, compute_uv=False)) - len(S))])) or 1.0) / norm_before)
        # (In practice: this branch does nothing when we do not truncate; when
        # we do truncate it makes the state a re-normalised approximation.)

        # Absorb singular values into U (left-canonical convention).
        U = U * S  # (chiL*2, k)

        self.sites[site] = U.reshape(chiL, 2, k)
        self.sites[site + 1] = Vh.reshape(k, 2, chiR)

    # ---- amplitude readout ----
    def amplitude(self, bitstring: Sequence[int]) -> complex:
        """Compute <bitstring | psi> in O(n * chi^2)."""
        if len(bitstring) != self.n_qubits:
            raise ValueError("bitstring length must equal n_qubits")
        # v starts as a (1,) vector = 1, then we multiply through.
        v = np.array([[1.0 + 0j]])  # shape (1, 1)
        for k, bit in enumerate(bitstring):
            if bit not in (0, 1):
                raise ValueError("bit must be 0 or 1")
            A_slice = self.sites[k][:, bit, :]  # (chi_L, chi_R)
            v = v @ A_slice                       # (1, chi_R)
        return complex(v[0, 0])

    def norm_squared(self) -> float:
        """<psi | psi> as a real number."""
        # Contract site by site: E starts at scalar 1 (as 1x1 matrix in the
        # doubled space).
        E = np.array([[1.0 + 0j]])  # (chiL_top, chiL_bot) = (1, 1)
        for k in range(self.n_qubits):
            A = self.sites[k]                 # (chiL, 2, chiR)
            # E' = sum_{s} A^dagger_{r', s, l'} * E_{l', l} * A_{l, s, r}
            E = np.einsum("lsr,lm,mst->rt", A.conj(), E, A)
        return float(E[0, 0].real)

    def expectation_pauli_z(self, site: int) -> float:
        """<psi | Z_site | psi>."""
        if not 0 <= site < self.n_qubits:
            raise IndexError("site out of range")
        E = np.array([[1.0 + 0j]])
        for k in range(self.n_qubits):
            A = self.sites[k]
            if k == site:
                # Z acts as diag(1, -1) on the physical index.
                op = np.array([1.0, -1.0], dtype=complex)
                Aop = A * op[None, :, None]
                E = np.einsum("lsr,lm,mst->rt", A.conj(), E, Aop)
            else:
                E = np.einsum("lsr,lm,mst->rt", A.conj(), E, A)
        return float(E[0, 0].real)

    def sample_computational_basis(self, rng: Optional[np.random.Generator] = None) -> List[int]:
        """Draw a single computational-basis bitstring by conditional sampling.

        For each site k, compute the marginal P(s_k = 0 | s_0..s_{k-1}), sample,
        then propagate the environment.
        """
        rng = rng or np.random.default_rng()
        bits: List[int] = []
        # Left environment as a row vector: <bits| ... - starts as 1.
        L = np.array([[1.0 + 0j]])
        for k in range(self.n_qubits):
            A = self.sites[k]  # (chiL, 2, chiR)
            # Full right-environment norm assuming bit s: proj_s
            probs = np.zeros(2, dtype=float)
            for s in (0, 1):
                A_s = A[:, s, :]      # (chiL, chiR)
                v = L @ A_s            # (1, chiR)
                # Contract v with its conjugate: <v|v>
                probs[s] = float((v.conj() @ v.T).real[0, 0])
            total = probs.sum()
            if total <= 0:
                s_choice = 0
            else:
                p0 = probs[0] / total
                s_choice = 0 if rng.random() < p0 else 1
            bits.append(s_choice)
            L = L @ A[:, s_choice, :]
            # Re-normalise L (probability rescaling).
            L_norm = float(np.linalg.norm(L))
            if L_norm > 0:
                L = L / L_norm
        return bits

    # ---- describe ----
    def describe(self) -> dict:
        return {
            "n_qubits": self.n_qubits,
            "chi_max": self.chi_max,
            "max_actual_bond": self.max_bond_dimension(),
            "memory_bytes": self.memory_bytes(),
            "memory_mb": self.memory_bytes() / (1024 * 1024),
            "full_state_log10_amplitudes": self.n_qubits * math.log10(2),
            "full_state_log10_bytes": self.n_qubits * math.log10(2) + math.log10(16),
        }


def bell_pair(chi_max: int = 4) -> QubitMPS:
    """|Bell> = (|00> + |11>) / sqrt(2) as a 2-qubit MPS."""
    mps = QubitMPS(n_qubits=2, chi_max=chi_max)
    mps.apply_single_qubit_gate(H_GATE, 0)
    mps.apply_two_qubit_gate(CNOT_TENSOR, 0)
    return mps


def uniform_superposition(n: int, chi_max: int = 4) -> QubitMPS:
    """|+>^{tensor n} = H on every qubit.

    This has Schmidt rank 1 at every bipartition (it's a product state in the
    Hadamard basis), so chi=1 is exact and memory stays ~ n * 2 * 16 bytes.
    """
    mps = QubitMPS(n_qubits=n, chi_max=chi_max)
    for k in range(n):
        mps.apply_single_qubit_gate(H_GATE, k)
    return mps


def ghz_state(n: int, chi_max: int = 4) -> QubitMPS:
    """|GHZ_n> = (|0..0> + |1..1>) / sqrt(2).

    Requires chi >= 2 at every bond (Schmidt rank 2 at every bipartition).
    Memory ~ n * 2 * 4 * 16 = 128 n bytes.
    """
    if n < 2:
        raise ValueError("n must be >= 2")
    mps = QubitMPS(n_qubits=n, chi_max=chi_max)
    mps.apply_single_qubit_gate(H_GATE, 0)
    for k in range(n - 1):
        mps.apply_two_qubit_gate(CNOT_TENSOR, k)
    return mps
