"""Section 3 & Section 5: Gate Application & Theorem-Backed Error Bounds.

Prevents silent truncation by logging every truncation event to the ErrorLedger
with an explicit academic theorem reference.
Owner: TN theorist & numerical linear algebra specialist.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Union
import numpy as np

from chronus.tensor.types import (
    BondId,
    ContractionCertificate,
    ErrorLedger,
    Leg,
    LegDirection,
    Node,
    SymmetricTensor,
    TruncationRecord,
    UntrustedApproximation,
)
from chronus.tensor.network import TensorNetwork


@dataclass
class FactorizationResult:
    """Result of factorizing a merged two-site tensor across a bond."""

    left_block: np.ndarray
    right_block: np.ndarray
    discarded_weight: float
    kept_chi: int
    singular_values: np.ndarray
    rand_svd_residual: float = 0.0
    boundary_error: float = 0.0
    ctmrg_environment_error: float = 0.0


def theorem_for(method: str) -> str:
    """Returns the peer-reviewed mathematical citation establishing the error bound."""
    if method == "svd":
        return "Vidal 2003, Fannes-Audenaert inequality"
    if method == "rand_svd":
        return "Halko-Martinsson-Tropp 2011, Thm 10.7 + 10.8"
    if method == "tensor_train":
        return "Oseledets 2011 Tensor-Train Rank Truncation"
    if method == "boundary_mps":
        return "Verstraete-Cirac 2004 Boundary MPS Truncation"
    if method == "ctmrg":
        return "Nishino-Okunishi Corner Transfer Matrix (Non-Hilbert Environmental Bound)"
    if method == "bp":
        raise UntrustedApproximation(
            "belief propagation has no rigorous Hilbert-space error bound; results must be cross-checked at n<=32"
        )
    raise ValueError(f"Unknown truncation method: {method}")


def bound_from_method(method: str, result: FactorizationResult) -> float:
    """Calculates the rigorous mathematical error bound for a truncation result (Section 5)."""
    if method == "svd":
        # Vidal 2003, Fannes-Audenaert inequality: 2 * sqrt(discarded_weight)
        return 2.0 * math.sqrt(max(0.0, result.discarded_weight))
    elif method == "rand_svd":
        # Halko-Martinsson-Tropp 2011, Thm 10.7 + 10.8
        return 2.0 * math.sqrt(max(0.0, result.discarded_weight)) + result.rand_svd_residual
    elif method == "tensor_train":
        # Oseledets 2011
        return float(result.discarded_weight)
    elif method == "boundary_mps":
        # Verstraete-Cirac 2004; boundary MPS truncation dominates
        return float(result.boundary_error + 2.0 * math.sqrt(max(0.0, result.discarded_weight)))
    elif method == "ctmrg":
        # Nishino-Okunishi; NOT a Hilbert-space bound — flagged as such
        return float(result.ctmrg_environment_error)
    elif method == "bp":
        raise UntrustedApproximation(
            "belief propagation has no rigorous Hilbert-space error bound; results must be cross-checked at n<=32"
        )
    raise ValueError(f"Unknown truncation method: {method}")


def get_standard_gate(name: str) -> np.ndarray:
    """Returns standard 1-qubit or 2-qubit unitary gate matrices."""
    name_up = name.upper()
    if name_up == "X":
        return np.array([[0, 1], [1, 0]], dtype=np.complex128)
    if name_up == "Y":
        return np.array([[0, -1j], [1j, 0]], dtype=np.complex128)
    if name_up == "Z":
        return np.array([[1, 0], [0, -1]], dtype=np.complex128)
    if name_up == "H":
        return (1.0 / math.sqrt(2.0)) * np.array([[1, 1], [1, -1]], dtype=np.complex128)
    if name_up == "S":
        return np.array([[1, 0], [0, 1j]], dtype=np.complex128)
    if name_up == "T":
        return np.array([[1, 0], [0, np.exp(1j * np.pi / 4.0)]], dtype=np.complex128)
    if name_up in ("CX", "CNOT"):
        # Controlled-NOT gate: |00><00| + |01><01| + |11><10| + |10><11|
        # Reshaped to (2, 2, 2, 2): (p0_out, p1_out, p0_in, p1_in)
        mat = np.array(
            [
                [1, 0, 0, 0],
                [0, 1, 0, 0],
                [0, 0, 0, 1],
                [0, 0, 1, 0],
            ],
            dtype=np.complex128,
        )
        return mat.reshape(2, 2, 2, 2)
    if name_up == "CZ":
        mat = np.diag([1, 1, 1, -1]).astype(np.complex128)
        return mat.reshape(2, 2, 2, 2)
    if name_up == "SWAP":
        mat = np.array(
            [
                [1, 0, 0, 0],
                [0, 0, 1, 0],
                [0, 1, 0, 0],
                [0, 0, 0, 1],
            ],
            dtype=np.complex128,
        )
        return mat.reshape(2, 2, 2, 2)
    raise ValueError(f"Unsupported standard gate: {name}")


def factorize_two_site(
    two_site_tensor: np.ndarray,
    chi_max: int,
    method: str = "svd",
    tolerance: float = 1e-12,
) -> FactorizationResult:
    """Factorizes a merged two-site tensor T of shape (chi_left, 2, 2, chi_right)

    into left A (chi_left, 2, chi_mid) and right B (chi_mid, 2, chi_right).
    Applies SVD or randomized SVD and records discarded weights.
    """
    chi_left, d0, d1, chi_right = two_site_tensor.shape
    # Reshape into matrix M of shape (chi_left * d0, d1 * chi_right)
    matrix = two_site_tensor.reshape(chi_left * d0, d1 * chi_right)

    if method == "svd":
        U, S, Vh = np.linalg.svd(matrix, full_matrices=False)
        _total_weight = float(np.sum(S ** 2))
        rand_res = 0.0
    elif method == "rand_svd":
        # Randomized SVD (Halko-Martinsson-Tropp 2011)
        k = min(chi_max, min(matrix.shape))
        # Deterministic projection using orthogonalized Gaussian test matrix
        np.random.seed(42)
        Omega = np.random.randn(matrix.shape[1], k + 5).astype(np.complex128)
        Y = matrix @ Omega
        Q, _ = np.linalg.qr(Y)
        B = Q.conj().T @ matrix
        Ub, S, Vh = np.linalg.svd(B, full_matrices=False)
        U = Q @ Ub
        _total_weight = float(np.sum(S ** 2))
        rand_res = float(np.linalg.norm(matrix - Q @ (Q.conj().T @ matrix)))
    else:
        raise NotImplementedError(f"Factorization method '{method}' not implemented in factorize_two_site.")

    # Determine truncation rank
    rank = len(S)
    kept_chi = min(chi_max, rank)

    # Discarded singular values
    discarded_s = S[kept_chi:]
    discarded_weight = float(np.sum(discarded_s ** 2))

    # Truncate
    U_trunc = U[:, :kept_chi]
    S_trunc = S[:kept_chi]
    Vh_trunc = Vh[:kept_chi, :]

    # Fold singular values symmetrically (sqrt(S)) into left and right
    s_sqrt = np.diag(np.sqrt(S_trunc))
    left_mat = U_trunc @ s_sqrt
    right_mat = s_sqrt @ Vh_trunc

    left_block = left_mat.reshape(chi_left, d0, kept_chi)
    right_block = right_mat.reshape(kept_chi, d1, chi_right)

    return FactorizationResult(
        left_block=left_block,
        right_block=right_block,
        discarded_weight=discarded_weight,
        kept_chi=kept_chi,
        singular_values=S,
        rand_svd_residual=rand_res,
    )


def apply_gate(
    network: TensorNetwork,
    ledger: ErrorLedger,
    gate: Union[str, np.ndarray],
    qubits: List[int],
    truncation_method: str = "svd",
) -> None:
    """Applies a gate to the tensor network with mandatory truncation logging (Section 3)."""
    if isinstance(gate, str):
        gate_mat = get_standard_gate(gate)
    else:
        gate_mat = np.asarray(gate, dtype=np.complex128)

    if len(qubits) == 1:
        # 1-qubit gate application: exact, introduces 0 truncation
        q = qubits[0]
        node = network.node_for(q)
        dense_t = node.tensor.to_dense()  # shape (chi_left, 2, chi_right)
        # Contract physical index (axis 1) with gate matrix
        # (chi_left, 2, chi_right) * (2, 2) -> (chi_left, chi_right, 2)
        new_t = np.tensordot(dense_t, gate_mat, axes=(1, 1))  # (chi_left, chi_right, p_out)
        new_t = np.transpose(new_t, (0, 2, 1))  # (chi_left, p_out, chi_right)

        phys_leg = Leg(id=q, dim=2, charge=0, direction=LegDirection.OUT)
        left_leg = node.virt_legs[0]
        right_leg = node.virt_legs[1]

        updated_tensor = SymmetricTensor(
            blocks={(0, 0, 0): new_t},
            legs=[left_leg, phys_leg, right_leg],
            group=network.gauge_group,
        )
        network.replace(Node(id=q, phys_legs=[phys_leg], virt_legs=[left_leg, right_leg], tensor=updated_tensor))

        cert = ContractionCertificate(
            tree=f"1QubitGate({qubits[0]})",
            peak_memory_bytes=network.memory(),
            flop_count=new_t.size * 2,
            planner_bound=0.0,
            planner_theorem="Exact1QubitGate",
        )
        ledger.record(cert)

    elif len(qubits) == 2:
        q0, q1 = qubits
        assert abs(q0 - q1) == 1, "Currently supporting nearest-neighbor 2-qubit gates on 1D MPS."
        if q0 > q1:
            q0, q1 = q1, q0

        node0 = network.node_for(q0)
        node1 = network.node_for(q1)

        t0 = node0.tensor.to_dense()  # (chi_L, 2, chi_mid)
        t1 = node1.tensor.to_dense()  # (chi_mid, 2, chi_R)

        # Merge t0 and t1 across the shared virtual bond chi_mid
        # merged: (chi_L, 2, 2, chi_R)
        two_site = np.tensordot(t0, t1, axes=(2, 0))  # (chi_L, 2, 2, chi_R)

        # Apply 2-qubit gate tensor (shape (2, 2, 2, 2): p0_out, p1_out, p0_in, p1_in)
        # two_site axes: 0=chi_L, 1=p0_in, 2=p1_in, 3=chi_R
        contracted = np.tensordot(two_site, gate_mat, axes=((1, 2), (2, 3)))
        # contracted has axes: (chi_L, chi_R, p0_out, p1_out)
        contracted = np.transpose(contracted, (0, 2, 3, 1))  # (chi_L, p0_out, p1_out, chi_R)

        # Factorize back using truncation_method
        res = factorize_two_site(
            contracted,
            chi_max=network.chi_max,
            method=truncation_method,
        )

        bond_id: BondId = (q0, q1)

        # MANDATORY AUDIT: Silent truncation is strictly forbidden!
        if res.discarded_weight > 0.0:
            bound = bound_from_method(truncation_method, res)
            record = TruncationRecord(
                step=ledger.next_step(),
                bond=bond_id,
                method=truncation_method,
                discarded_weight=res.discarded_weight,
                kept_chi=res.kept_chi,
                error_bound=bound,
                theorem_ref=theorem_for(truncation_method),
            )
            ledger.append(record)

        left_phys = Leg(id=q0, dim=2, charge=0, direction=LegDirection.OUT)
        right_phys = Leg(id=q1, dim=2, charge=0, direction=LegDirection.OUT)
        new_mid_left = Leg(id=10000 + q0, dim=res.kept_chi, charge=0, direction=LegDirection.OUT)
        new_mid_right = Leg(id=10000 + q0, dim=res.kept_chi, charge=0, direction=LegDirection.IN)

        tensor0 = SymmetricTensor(
            blocks={(0, 0, 0): res.left_block},
            legs=[node0.virt_legs[0], left_phys, new_mid_left],
            group=network.gauge_group,
        )
        tensor1 = SymmetricTensor(
            blocks={(0, 0, 0): res.right_block},
            legs=[new_mid_right, right_phys, node1.virt_legs[1]],
            group=network.gauge_group,
        )

        network.replace(Node(id=q0, phys_legs=[left_phys], virt_legs=[node0.virt_legs[0], new_mid_left], tensor=tensor0))
        network.replace(Node(id=q1, phys_legs=[right_phys], virt_legs=[new_mid_right, node1.virt_legs[1]], tensor=tensor1))

        cert = ContractionCertificate(
            tree=f"2QubitGate({q0},{q1})",
            peak_memory_bytes=network.memory(),
            flop_count=two_site.size * 4,
            planner_bound=0.0,
            planner_theorem=f"Factorization({truncation_method})",
        )
        ledger.record(cert)
    else:
        raise ValueError(f"Gates on {len(qubits)} qubits not supported; decompose into 1-qubit and 2-qubit gates.")
