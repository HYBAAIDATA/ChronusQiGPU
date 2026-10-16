"""
Error correction (Unbuilt) -- Section 9. Builds the ACTUAL stabilizer
operators S_v (Z-type) and S_p (X-type) for the distance-3 planar surface
code already defined in academic/caltech.py, as real dense Pauli
tensor-product matrices, and verifies -- by direct linear algebra, not by
assertion -- that they mutually commute and that the code-space projector
they define is non-trivial and genuinely satisfies S|psi>=|psi> for a real,
numerically obtained code state.
"""
from __future__ import annotations

from typing import List, Tuple

import numpy as np

from ..academic.caltech import Caltech_Surface_Code

I2 = np.eye(2, dtype=complex)
X = np.array([[0, 1], [1, 0]], dtype=complex)
Z = np.array([[1, 0], [0, -1]], dtype=complex)


def pauli_string_operator(qubits: List[int], pauli: np.ndarray, n_qubits: int) -> np.ndarray:
    """Real dense tensor-product operator: `pauli` on each listed qubit, identity elsewhere."""
    ops = [pauli if q in qubits else I2 for q in range(n_qubits)]
    result = ops[0]
    for op in ops[1:]:
        result = np.kron(result, op)
    return result


def build_stabilizer_operators(code: Caltech_Surface_Code) -> Tuple[List[np.ndarray], List[np.ndarray]]:
    n = code.n_qubits
    s_z = [pauli_string_operator(qubits, Z, n) for qubits in code.z_stabilizers]
    s_x = [pauli_string_operator(qubits, X, n) for qubits in code.x_stabilizers]
    return s_z, s_x


def verify_stabilizer_algebra(code: Caltech_Surface_Code, tol: float = 1e-9) -> dict:
    """
    Real, computed checks:
      1. All stabilizers mutually commute.
      2. All stabilizers are Hermitian involutions (S^2 = I).
      3. The code-space projector Prod_s (I+S)/2 is non-trivial (rank > 0).
      4. A real eigenvector of the projector with eigenvalue 1 genuinely
         satisfies S|psi> = |psi> for every stabilizer S.
    """
    s_z, s_x = build_stabilizer_operators(code)
    all_stabs = s_z + s_x
    n_dim = 2 ** code.n_qubits

    commute_ok = True
    for a in range(len(all_stabs)):
        for b in range(a + 1, len(all_stabs)):
            comm = all_stabs[a] @ all_stabs[b] - all_stabs[b] @ all_stabs[a]
            if np.max(np.abs(comm)) > tol:
                commute_ok = False

    hermitian_and_involution_ok = all(
        np.allclose(s, s.conj().T, atol=tol) and np.allclose(s @ s, np.eye(n_dim), atol=tol)
        for s in all_stabs
    )

    projector = np.eye(n_dim, dtype=complex)
    for s in all_stabs:
        projector = projector @ (np.eye(n_dim) + s) / 2
    projector = (projector + projector.conj().T) / 2

    eigvals, eigvecs = np.linalg.eigh(projector)
    code_space_dim = int(np.sum(eigvals > 0.5))

    code_state_check_ok = True
    if code_space_dim > 0:
        psi = eigvecs[:, eigvals > 0.5][:, 0]
        psi = psi / np.linalg.norm(psi)
        for s in all_stabs:
            if not np.allclose(s @ psi, psi, atol=1e-6):
                code_state_check_ok = False
    else:
        code_state_check_ok = False

    return {
        "n_qubits": code.n_qubits,
        "n_stabilizers": len(all_stabs),
        "all_stabilizers_commute": commute_ok,
        "all_stabilizers_hermitian_involutions": hermitian_and_involution_ok,
        "code_space_dimension": code_space_dim,
        "ground_state_condition_verified": code_state_check_ok,
    }


def _self_test() -> str:
    code = Caltech_Surface_Code(distance=3)
    result = verify_stabilizer_algebra(code)
    assert result["all_stabilizers_commute"], "surface-code stabilizers must mutually commute"
    assert result["all_stabilizers_hermitian_involutions"], "stabilizers must be Hermitian involutions"
    assert result["code_space_dimension"] > 0, "code space must be non-trivial"
    assert result["ground_state_condition_verified"], "S|psi>=|psi> must hold for a real code state"
    return "error_correction._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
