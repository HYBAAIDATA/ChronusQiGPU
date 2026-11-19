"""Charge-aware (Z2) DMRG: exact sector energies, leak/budget/policy refusals.

Local CPU numerical tests against independent dense diagonalisation and the
exact Jordan-Wigner solution; not evidence of physical GPU execution.
"""
from __future__ import annotations

import math
import os

import numpy as np
import pytest

from chronus.tensor.dmrg import DMRG
from chronus.tensor.hamiltonian import TFIM_terms, build_hamiltonian_mpo
from chronus.tensor.network import build_network
from chronus.tensor.types import UntrustedApproximation, UntrustedResult

pytestmark = pytest.mark.real

_Z = np.diag([1.0, -1.0])
_X = np.array([[0.0, 1.0], [1.0, 0.0]])


def _kron_sites(n, ops):
    out = np.ones((1, 1))
    for i in range(n):
        out = np.kron(out, ops.get(i, np.eye(2)))
    return out


def _dense_sector_ground(n, j, h, parity):
    """Lowest eigenvalue of the dense TFIM restricted to P = prod X = (-1)**parity."""
    matrix = sum(-h * _kron_sites(n, {i: _X}) for i in range(n))
    matrix = matrix + sum(-j * _kron_sites(n, {i: _Z, i + 1: _Z}) for i in range(n - 1))
    p = _kron_sites(n, {i: _X for i in range(n)})
    vals, vecs = np.linalg.eigh(matrix)
    sector = [v for v, vec in zip(vals, vecs.T) if np.isclose(vec @ p @ vec, (-1) ** parity, atol=1e-6)]
    return float(min(sector))


def _jw_open_chain(n):
    """Exact critical (J = h = 1) open-chain ground energy (Pfeuty 1970)."""
    return -sum(2.0 * math.sin((2 * k - 1) * math.pi / (4 * n + 2)) for k in range(1, n + 1))


def _run(n, *, chi=16, sweeps=4, parity=0, j=1.0, h=1.0, **kw):
    network, ledger = build_network(n, topology="MPS", chi_max=chi, group="Z2")
    mpo = build_hamiltonian_mpo(TFIM_terms(j, h, n), n, group="none", chi_mpo_max=4)
    energy = DMRG(network, ledger, mpo, chi_max=chi, sweeps=sweeps, tol=1e-10, target_parity=parity, **kw)
    return energy, network, ledger


@pytest.mark.parametrize("n", [2, 4, 6, 7])
@pytest.mark.parametrize("parity", [0, 1])
def test_z2_sector_energy_matches_dense_sector_diagonalisation(n, parity):
    energy, network, ledger = _run(n, parity=parity)
    assert energy == pytest.approx(_dense_sector_ground(n, 1.0, 1.0, parity), abs=1e-8)
    # The committed state lives in the requested sector of P = prod X.
    psi = network.to_statevector()
    p = _kron_sites(n, {i: _X for i in range(n)})
    assert np.vdot(psi, p @ psi).real == pytest.approx((-1) ** parity, abs=1e-8)
    assert any("Z2ChargeAware" in str(c.tree) for c in ledger.certificates)


def test_z2_off_critical_couplings_match_dense():
    energy, _, _ = _run(5, j=0.7, h=1.4)
    assert energy == pytest.approx(_dense_sector_ground(5, 0.7, 1.4, 0), abs=1e-8)


def test_z2_n16_matches_exact_jordan_wigner_energy():
    energy, _, ledger = _run(16, chi=16, sweeps=3)
    assert energy == pytest.approx(_jw_open_chain(16), abs=1e-9)
    # chi=16 forces ~1e-16 discarded weight per step; the additive 2*sqrt(w)
    # ledger bound stays conservative (measured ~1.3e-6).
    assert 0 < ledger.global_bound < 1e-5


def test_claim_budget_exhaustion_fails_fast_without_mutation():
    network, ledger = build_network(12, topology="MPS", chi_max=2, group="Z2")
    mpo = build_hamiltonian_mpo(TFIM_terms(1.0, 1.0, 12), 12, group="none", chi_mpo_max=4)
    before = [network.node_for(i).tensor.to_dense().copy() for i in range(12)]
    with pytest.raises(UntrustedApproximation, match="claim budget"):
        DMRG(network, ledger, mpo, chi_max=2, sweeps=2, claim_bound=1e-6)
    assert not ledger.truncations
    for i, previous in enumerate(before):
        np.testing.assert_array_equal(network.node_for(i).tensor.to_dense(), previous)


def test_local_dimension_policy_refuses_instead_of_running_unbounded():
    previous = os.environ.get("CHRONUS_MAX_DMRG_LOCAL_DIM")
    os.environ["CHRONUS_MAX_DMRG_LOCAL_DIM"] = "4"
    try:
        with pytest.raises(UntrustedResult):
            _run(8, chi=8, sweeps=1)
    finally:
        if previous is None:
            os.environ.pop("CHRONUS_MAX_DMRG_LOCAL_DIM", None)
        else:
            os.environ["CHRONUS_MAX_DMRG_LOCAL_DIM"] = previous


def test_invalid_target_parity_is_refused():
    with pytest.raises(ValueError):
        _run(4, parity=2)


def test_symmetry_breaking_mpo_is_refused_as_untrusted_result():
    from chronus.tensor.dmrg import Z2SymmetryViolation
    from chronus.tensor.hamiltonian import HamiltonianTerm

    n = 4
    terms = TFIM_terms(1.0, 1.0, n) + [HamiltonianTerm(sites=[0], operators=["Z"], coefficient=-0.3)]
    network, ledger = build_network(n, topology="MPS", chi_max=8, group="Z2")
    mpo = build_hamiltonian_mpo(terms, n, group="none", chi_mpo_max=4)
    with pytest.raises(Z2SymmetryViolation) as refused:
        DMRG(network, ledger, mpo, chi_max=8, sweeps=1)
    assert isinstance(refused.value, UntrustedResult)
    assert not ledger.truncations


def test_claim_budget_counts_bounds_already_in_the_ledger():
    from chronus.tensor.types import TruncationRecord

    network, ledger = build_network(6, topology="MPS", chi_max=8, group="Z2")
    ledger.append(TruncationRecord(step=ledger.next_step(), bond=(0, 1), method="svd", discarded_weight=1e-12,
                                   kept_chi=1, error_bound=2e-6, theorem_ref="Eckart-Young-Mirsky"))
    mpo = build_hamiltonian_mpo(TFIM_terms(1.0, 1.0, 6), 6, group="none", chi_mpo_max=4)
    with pytest.raises(UntrustedApproximation, match="already exhausts"):
        DMRG(network, ledger, mpo, chi_max=8, sweeps=1, claim_bound=1e-6)


def test_e3_refuses_any_size_other_than_its_1000_node_claim():
    from chronus.tensor.experiments import E3_honest_1000_node_claim

    for n in (1, 2, 100):
        with pytest.raises(ValueError, match="1,000-node claim"):
            E3_honest_1000_node_claim(n_nodes=n)
