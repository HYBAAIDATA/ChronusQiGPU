from fractions import Fraction
import numpy as np
import pytest
from euclid.pythagoras.quantum.quantum_tensor import QuantumTensor, VIRTUAL_QUANTUM_DIMENSION, VIRTUAL_QUANTUM_QUBITS


def test_platform_tensor_is_11_qubits_and_2048_dimensional():
    tensor = QuantumTensor(require_platform_width=True)
    assert (tensor.n_qubits, tensor.dimension) == (VIRTUAL_QUANTUM_QUBITS, VIRTUAL_QUANTUM_DIMENSION)
    assert tensor.assert_invariants()


def test_hadamard_all_is_exactly_normalized():
    tensor = QuantumTensor(require_platform_width=True).hadamard_all()
    distribution = tensor.born_distribution()
    assert len(distribution) == 2048
    assert set(distribution.values()) == {Fraction(1, 2048)}
    assert sum(distribution.values()) == 1


def test_exact_bell_tensor_and_entropy():
    tensor = QuantumTensor(n_qubits=2).h(0).cnot(0, 1)
    assert tensor.born_distribution() == {0: Fraction(1, 2), 3: Fraction(1, 2)}
    assert tensor.von_neumann_entropy([0]) == 1


def test_qft_round_trip_preserves_exact_tensor():
    tensor = QuantumTensor(n_qubits=3).h(0).x(2)
    before = tensor.amplitudes
    tensor.qft().qft(inverse=True)
    assert tensor.amplitudes == before


def test_grover_operates_on_full_virtual_dimension():
    tensor = QuantumTensor(require_platform_width=True).grover(marked=1379, iterations=1)
    distribution = tensor.born_distribution(include_zeros=True)
    assert len(distribution) == 2048
    assert sum(distribution.values()) == 1
    assert distribution[1379] > distribution[0]


def test_numeric_export_is_explicit_and_dimension_preserving():
    exported = QuantumTensor(require_platform_width=True).hadamard_all().to_pulvini_input()
    assert exported.shape == (2048,) and exported.dtype == np.complex128
    assert np.isclose(np.vdot(exported, exported), 1.0)
    with pytest.raises(TypeError, match="from_numpy"):
        QuantumTensor.from_numpy(exported)
