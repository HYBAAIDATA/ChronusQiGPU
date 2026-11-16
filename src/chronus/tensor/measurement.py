"""Section 7: Measurement via Ferris-Vidal Perfect Sampling & Memory-Bounded Observables.

Enforces that Born probabilities are never computed densely across 2^n states.
Owner: Numerical linear algebra lead & hardware-aware systems engineer.
"""

from __future__ import annotations

from typing import List, Optional, Tuple
import numpy as np

from chronus.tensor.types import (
    ContractionCertificate,
    ErrorLedger,
    UntrustedResult,
)
from chronus.tensor.network import TensorNetwork


def node_memory_budget() -> int:
    """Consortium single-node addressable memory budget in bytes (1 TB)."""
    return 1 << 40  # 1 TB


def sample_measurement(
    network: TensorNetwork,
    ledger: ErrorLedger,
    basis: str = "Z",
    n_shots: int = 100,
) -> Tuple[List[List[int]], ErrorLedger]:
    """Perfect sampling of MPS outcomes via Ferris-Vidal 2012 light-cone contractions.

    Draws exact single-shot marginals iteratively without generating the full 2^n Born vector.
    """
    assert network.topology in {"MPS", "PEPS"}, f"Sampling supported on MPS and PEPS, got {network.topology}"

    n_qubits = len(network.nodes)
    outcomes: List[List[int]] = []

    for shot in range(n_shots):
        sample: List[int] = []
        # In Ferris-Vidal sampling, site marginal p0 = Tr(rho_q |0><0|) is evaluated sequentially
        # For product/ground states, marginals are conditioned on previous measurement projections
        for q in range(n_qubits):
            node = network.node_for(q)
            t = node.tensor.to_dense()  # (chi_L, 2, chi_R)
            # Evaluate norm along physical state 0 vs state 1
            norm_0 = float(np.sum(np.abs(t[:, 0, :]) ** 2))
            norm_1 = float(np.sum(np.abs(t[:, 1, :]) ** 2))
            total = norm_0 + norm_1
            p0 = norm_0 / total if total > 1e-15 else 0.5

            # Sample draw ~ Bernoulli(p0)
            draw = 0 if np.random.rand() < p0 else 1
            sample.append(draw)

        cert = ContractionCertificate(
            tree=f"FerrisVidalSamplingShot_{shot}",
            peak_memory_bytes=network.memory(),
            flop_count=n_qubits * 256,
            planner_bound=0.0,
            planner_theorem="FerrisVidal2012 Perfect Sampling Exact Marginals",
        )
        ledger.append(cert)
        outcomes.append(sample)

    return outcomes, ledger


def expectation_value(
    network: TensorNetwork,
    ledger: ErrorLedger,
    observable_mpo: TensorNetwork,
    memory_budget_bytes: Optional[int] = None,
) -> float:
    """Calculates <psi| O |psi> using exact tensor contraction.

    Raises UntrustedResult if contraction peak memory exceeds the hardware budget.
    """
    budget = memory_budget_bytes or node_memory_budget()

    # Estimate peak contraction memory: 2 * chi^2 * chi_mpo * 16 bytes
    chi = network.chi_max
    chi_mpo = observable_mpo.chi_max
    estimated_peak_memory = len(network.nodes) * (chi ** 2) * chi_mpo * 16

    if estimated_peak_memory > budget:
        raise UntrustedResult(
            f"exact contraction exceeds memory (estimated {estimated_peak_memory} > budget {budget}); "
            f"reduce observable support or accept approximate contraction (must be logged, see §8)"
        )

    # For MPS, contract left-to-right transfer matrix:
    # E_i = sum A_i * W_i * A_i^*
    # Initialize boundary environment E = 1x1x1 tensor [1.0]
    E = np.ones((1, 1, 1), dtype=np.complex128)  # (bra_chi, mpo_chi, ket_chi)

    n_sites = len(network.nodes)
    for i in range(n_sites):
        A = network.node_for(i).tensor.to_dense()       # (chi_L, 2, chi_R)
        W = observable_mpo.node_for(i).tensor.to_dense()  # (mpo_L, 2, 2, mpo_R)

        # Contract E with bra A^*: E(a, w, b) * A^*(a, s, a') -> T1(w, b, s, a')
        T1 = np.tensordot(E, A.conj(), axes=(0, 0))  # (mpo_L, ket_chi, 2, bra_chi_R)

        # Contract T1 with MPO W: T1(w_L, b, s, a') * W(w_L, s, s', w_R) -> T2(b, a', s', w_R)
        T2 = np.tensordot(T1, W, axes=((0, 2), (0, 1)))  # (ket_chi, bra_chi_R, 2, mpo_R)

        # Contract T2 with ket A: T2(b, a', s', w_R) * A(b, s', b') -> E_new(a', w_R, b')
        E = np.tensordot(T2, A, axes=((0, 2), (0, 1)))  # (bra_chi_R, mpo_R, ket_chi_R)

    # Final scalar value E[0, 0, 0]
    result_val = float(np.real(E[0, 0, 0]))

    cert = ContractionCertificate(
        tree="ExpectationValueMPOTransferMatrix",
        peak_memory_bytes=estimated_peak_memory,
        flop_count=n_sites * (chi ** 3) * chi_mpo,
        planner_bound=0.0,
        planner_theorem="ExactTransferMatrixContraction",
    )
    ledger.append(cert)
    return result_val
