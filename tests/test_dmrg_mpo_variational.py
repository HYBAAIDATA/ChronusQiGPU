"""Regression tests for actual MPO-variational DMRG and conservative ledger bounds.

Local CPU numerical matrix tests; not evidence of physical GPU execution.
"""
import numpy as np
import pytest

from chronus.tensor.dmrg import DMRG
from chronus.tensor.hamiltonian import TFIM_terms, build_hamiltonian_mpo
from chronus.tensor.network import build_network
from chronus.tensor.types import ErrorLedger, TruncationRecord


def _dense_tfim_ground(n, j, h):
    z = np.diag([1., -1.])
    x = np.array([[0., 1.], [1., 0.]])
    identity = np.eye(2)
    matrix = np.zeros((2**n, 2**n), dtype=np.float64)
    def term(sites):
        out = np.ones((1, 1))
        for i in range(n):
            out = np.kron(out, sites.get(i, identity))
        return out
    for i in range(n):
        matrix -= h * term({i:x})
    for i in range(n-1):
        matrix -= j * term({i:z, i+1:z})
    return float(np.linalg.eigvalsh(matrix)[0])


@pytest.mark.parametrize("n,j,h", [(2, 1.0, 1.0), (3, 1.0, 1.0),
                                    (4, 0.7, 1.4), (5, 1.0, 1.0)])
def test_actual_mpo_ground_state_matches_independent_dense_oracle(n, j, h):
    network, ledger = build_network(n, topology="MPS", chi_max=8, group="none")
    mpo = build_hamiltonian_mpo(TFIM_terms(j, h, n), n, chi_mpo_max=4)
    observed = DMRG(network, ledger, mpo, chi_max=8, sweeps=3, tol=1e-9)
    expected = _dense_tfim_ground(n, j, h)
    assert np.isclose(observed, expected, atol=2e-8)
    assert any("ActualTwoSiteMPO" in str(c.tree) for c in ledger.certificates)
    wavefunction = network.to_statevector()
    assert np.isclose(np.linalg.norm(wavefunction), 1.0, atol=1e-9)


def test_undocumented_mpo_cannot_be_silently_replaced_by_tfim():
    network, ledger = build_network(2, topology="MPS", chi_max=4)
    mpo1 = build_hamiltonian_mpo(TFIM_terms(0.5, 1.0, 2), 2, chi_mpo_max=4)
    mpo2 = build_hamiltonian_mpo(TFIM_terms(1.5, 1.0, 2), 2, chi_mpo_max=4)
    e1 = DMRG(network, ledger, mpo1, chi_max=4, sweeps=2)
    network2, ledger2 = build_network(2, topology="MPS", chi_max=4)
    e2 = DMRG(network2, ledger2, mpo2, chi_max=4, sweeps=2)
    assert e1 != pytest.approx(e2)


@pytest.mark.parametrize("invalid_sweeps,invalid_tol", [(0, 1e-8), (2, 0.0), (2, float("nan"))])
def test_dmrg_invalid_solver_configuration_refused_atomically(invalid_sweeps, invalid_tol):
    network, ledger = build_network(3, chi_max=4)
    mpo = build_hamiltonian_mpo(TFIM_terms(1, 1, 3), 3, chi_mpo_max=4)
    old = [network.node_for(i).tensor.to_dense().copy() for i in range(3)]
    with pytest.raises(ValueError):
        DMRG(network, ledger, mpo, chi_max=4, sweeps=invalid_sweeps, tol=invalid_tol)
    assert not ledger.truncations
    for i, previous in enumerate(old):
        np.testing.assert_array_equal(network.node_for(i).tensor.to_dense(), previous)


def test_error_ledger_adds_step_bounds_instead_of_root_sum_weights():
    ledger = ErrorLedger()
    for i in range(2):
        ledger.append(TruncationRecord(step=i+1, bond=(i,i+1),
                       method="svd", discarded_weight=0.01, kept_chi=1,
                       error_bound=0.2, theorem_ref="Eckart-Young-Mirsky"))
    assert ledger.global_bound == pytest.approx(0.4)
