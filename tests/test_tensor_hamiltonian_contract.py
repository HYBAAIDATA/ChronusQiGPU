"""Independent dense Pauli oracle for small MPOs and fail-closed integrity."""
import numpy as np
import pytest

from chronus.tensor.hamiltonian import HamiltonianTerm, TFIM_terms, build_hamiltonian_mpo
from chronus.tensor.geodesic import TopologicalIntegrityGate
from chronus.tensor.types import UnsupportedHamiltonian


def dense(mpo):
    value = np.ones((1, 1, 1), dtype=complex)
    for node in mpo.nodes.values():
        block = node.tensor.blocks[(0, 0, 0, 0)]
        value = np.einsum("abl,lpqr->apbqr", value, block)
        value = value.reshape(value.shape[0] * 2, value.shape[2] * 2, block.shape[-1])
    return value[:, :, 0]


def oracle(terms, n):
    pauli = {"I": np.eye(2), "X": np.array([[0, 1], [1, 0]]),
             "Y": np.array([[0, -1j], [1j, 0]]), "Z": np.diag([1, -1])}
    result = np.zeros((2**n, 2**n), dtype=complex)
    for term in terms:
        product = np.ones((1, 1))
        operators = dict(zip(term.sites, term.operators))
        for site in range(n):
            product = np.kron(product, pauli[operators.get(site, "I")])
        result += term.coefficient * product
    return result


@pytest.mark.parametrize("terms,n", [
    ([HamiltonianTerm([0], ["Z"], 2)], 1),
    ([HamiltonianTerm([0], ["Y"], 0.7), HamiltonianTerm([1], ["Z"], -2)], 2),
    ([HamiltonianTerm([0, 1], ["Z", "Z"], 0.3), HamiltonianTerm([1, 2], ["Z", "Z"], 1.7),
      HamiltonianTerm([0], ["X"], -2), HamiltonianTerm([2], ["X"], 0.8)], 3),
    (TFIM_terms(0.2, 1.3, 4), 4), ([], 1), ([], 3),
])
def test_mpo_matches_declared_terms(terms, n):
    actual = dense(build_hamiltonian_mpo(terms, n, chi_mpo_max=4))
    np.testing.assert_allclose(actual, oracle(terms, n), atol=1e-14)
    np.testing.assert_allclose(actual, actual.conj().T, atol=1e-14)


@pytest.mark.parametrize("term", [HamiltonianTerm([2], ["X"]), HamiltonianTerm([0], ["Q"]),
    HamiltonianTerm([0, 0], ["X", "Z"]), HamiltonianTerm([0], ["X"], float("nan")),
    HamiltonianTerm([0], ["X"], 1j)])
def test_invalid_hamiltonians_refused(term):
    with pytest.raises(ValueError):
        build_hamiltonian_mpo([term], 2)


def test_no_silent_long_range_approximation():
    with pytest.raises(UnsupportedHamiltonian):
        build_hamiltonian_mpo([HamiltonianTerm([0, 3], ["Z", "Z"])], 4,
                              approximate_long_range=True)


def test_gate_rejects_dtype_mismatch_and_nonfinite():
    gate = TopologicalIntegrityGate()
    assert not gate.verify(np.array([1], dtype=np.float32), np.array([1], dtype=np.float64)).passed
    assert not gate.verify(np.array([np.nan]), np.array([1.0])).passed
    with pytest.raises(ValueError):
        TopologicalIntegrityGate(float("nan"))


def test_integrity_error_cannot_wrap_in_integer_dtype():
    gate = TopologicalIntegrityGate()
    assert not gate.verify(np.array([-(2**63)], dtype=np.int64), np.array([0], dtype=np.int64)).passed
    assert not gate.verify(np.array([True]), np.array([False])).passed
