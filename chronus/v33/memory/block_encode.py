"""
PREPARE + SELECT block-encoding from classical tables (QRAM-backed).

Produces a BlockEnc that can feed QSVT / qubitization pipelines.
Hardware-agnostic pure linear algebra.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .table import Table


@dataclass
class Structure:
    """Normalisation and sparsity metadata for block-encoding."""
    alpha: float
    ancilla_bits: int
    sparsity: int
    n_system: int  # system Hilbert-space dimension (power of 2 preferred)


@dataclass
class BlockEnc:
    alpha: float
    ancilla_bits: int
    # Dense unitary only for small systems; for large systems the
    # semantic action is defined by prepare/select callables.
    unitary: Optional[np.ndarray] = None
    n_system: int = 1
    semantic_name: str = "A"


def prepare_select(
    coeffs: np.ndarray,
    unitaries: list,
    system_dim: int,
) -> tuple[np.ndarray, float]:
    """
    Build the dense PREPARE† SELECT PREPARE block-encoding for small systems.

    coeffs: positive coefficients α_j
    unitaries: list of (system_dim × system_dim) unitary matrices U_j
    Returns (U_A, alpha) where U_A is the full (M * system_dim) unitary
    and alpha = sum(coeffs).
    """
    coeffs = np.asarray(coeffs, dtype=float)
    if np.any(coeffs < 0):
        raise ValueError("coefficients must be non-negative (signs go into U_j)")
    alpha = float(np.sum(coeffs))
    if alpha <= 0:
        raise ValueError("sum of coefficients must be positive")
    m = len(coeffs)
    # Pad to next power of two for clean ancilla dimension
    m_pad = 1 << int(np.ceil(np.log2(max(m, 1))))
    prep = np.zeros(m_pad, dtype=complex)
    prep[:m] = np.sqrt(coeffs / alpha)
    # SELECT = Σ_j |j⟩⟨j| ⊗ U_j
    full_dim = m_pad * system_dim
    select = np.zeros((full_dim, full_dim), dtype=complex)
    for j in range(m):
        Uj = np.asarray(unitaries[j], dtype=complex)
        if Uj.shape != (system_dim, system_dim):
            raise ValueError(f"U_{j} shape mismatch")
        for a in range(system_dim):
            for b in range(system_dim):
                select[j * system_dim + a, j * system_dim + b] = Uj[a, b]
    # Identity on padded indices
    for j in range(m, m_pad):
        for a in range(system_dim):
            select[j * system_dim + a, j * system_dim + a] = 1.0
    # Full U_A = (P† ⊗ I) S (P ⊗ I)
    # Build P ⊗ I as a tall matrix acting on |0⟩|ψ⟩
    # For dense construction we form the complete unitary on ancilla+system.
    p_mat = np.zeros((m_pad, m_pad), dtype=complex)
    p_mat[:, 0] = prep  # first column prepares from |0⟩
    # Complete P to a unitary via QR on a random completion (deterministic seed)
    rng = np.random.default_rng(0)
    rest = rng.normal(size=(m_pad, m_pad - 1)) + 1j * rng.normal(size=(m_pad, m_pad - 1))
    full = np.concatenate([prep.reshape(-1, 1), rest], axis=1)
    q_mat, _ = np.linalg.qr(full)
    # Ensure first column is still prep (phase)
    phase = np.vdot(q_mat[:, 0], prep)
    if abs(phase) > 1e-15:
        q_mat[:, 0] *= np.conj(phase) / abs(phase)
    p_unitary = q_mat
    # (P ⊗ I)
    p_kron = np.kron(p_unitary, np.eye(system_dim))
    u_a = p_kron.conj().T @ select @ p_kron
    return u_a, alpha


def block_encode(
    D_idx: Table,
    D_val: Table,
    structure: Structure,
    system_unitaries: Optional[list] = None,
) -> BlockEnc:
    """
    Construct a block-encoding from index/value tables.

    For small systems (n_system ≤ 8 and sparsity ≤ 8) a dense unitary is
    materialised. Otherwise only the metadata BlockEnc is returned; the
    caller uses QRAM + PREPARE/SELECT oracles abstractly.
    """
    s = structure.sparsity
    n = structure.n_system
    alpha = structure.alpha

    if system_unitaries is not None and n <= 8 and s <= 8:
        coeffs = np.array([D_val.lookup_int(j) for j in range(s)], dtype=float)
        # Fallback uniform if zeros
        if np.sum(coeffs) <= 0:
            coeffs = np.ones(s)
        u_a, alpha = prepare_select(coeffs, system_unitaries, n)
        return BlockEnc(
            alpha=alpha,
            ancilla_bits=structure.ancilla_bits,
            unitary=u_a,
            n_system=n,
            semantic_name="PREPARE_SELECT",
        )

    # Abstract oracle form — no dense matrix
    return BlockEnc(
        alpha=alpha,
        ancilla_bits=structure.ancilla_bits,
        unitary=None,
        n_system=n,
        semantic_name="QRAM_ORACLE",
    )


def _self_test() -> str:
    # Two-term LCU: A = 0.6 X + 0.4 Z on one qubit
    X = np.array([[0, 1], [1, 0]], dtype=complex)
    Z = np.array([[1, 0], [0, -1]], dtype=complex)
    u_a, alpha = prepare_select(np.array([0.6, 0.4]), [X, Z], system_dim=2)
    assert abs(alpha - 1.0) < 1e-12
    # Top-left 2×2 block should approximate A/α = 0.6X + 0.4Z
    A = 0.6 * X + 0.4 * Z
    top_left = u_a[:2, :2]
    assert np.allclose(top_left, A, atol=1e-8), f"block mismatch {top_left} vs {A}"
    # Unitarity of full U_A
    assert np.allclose(u_a.conj().T @ u_a, np.eye(u_a.shape[0]), atol=1e-8)
    return "memory.block_encode._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
