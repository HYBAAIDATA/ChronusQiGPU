import math
import unittest

from turing import (
    CNOT,
    HADAMARD,
    IDENTITY_2,
    PAULI_X,
    PAULI_Y,
    PAULI_Z,
    PHASE_S,
    PHASE_T,
    LinearOperator,
    ProjectiveMeasurement,
    QuantumState,
    born_probabilities,
    computational_basis_measurement,
    tensor_operators,
    tensor_states,
)


class QuantumMathAxiomsTests(unittest.TestCase):
    def test_state_is_normalized_and_inner_product_is_conjugate_linear_first(self):
        with self.assertRaises(ValueError):
            QuantumState((1, 1))
        state = QuantumState.normalized((1j, 1))
        self.assertAlmostEqual(state.norm_squared, 1.0)
        self.assertAlmostEqual(state.inner_product(state).real, 1.0)
        self.assertAlmostEqual(state.inner_product(state).imag, 0.0)
        basis_one = QuantumState.basis(2, 1)
        complex_state = QuantumState((1 / math.sqrt(2), 1j / math.sqrt(2)))
        self.assertAlmostEqual(basis_one.inner_product(complex_state).imag, 1 / math.sqrt(2))
        self.assertAlmostEqual(complex_state.inner_product(basis_one).imag, -1 / math.sqrt(2))

    def test_standard_gates_are_unitary(self):
        for gate in (IDENTITY_2, PAULI_X, PAULI_Y, PAULI_Z,
                     HADAMARD, PHASE_S, PHASE_T, CNOT):
            self.assertTrue(gate.is_unitary(), repr(gate))
        self.assertTrue(PAULI_Z.is_hermitian())

    def test_hadamard_and_born_rule(self):
        zero = QuantumState.basis(2, 0)
        plus = HADAMARD.apply(zero)
        self.assertTrue(math.isclose(born_probabilities(plus)[0], 0.5))
        self.assertTrue(math.isclose(born_probabilities(plus)[1], 0.5))
        self.assertTrue(math.isclose(sum(born_probabilities(plus)), 1.0))

    def test_observable_expectation(self):
        zero = QuantumState.basis(2, 0)
        one = QuantumState.basis(2, 1)
        self.assertAlmostEqual(PAULI_Z.expectation_value(zero).real, 1.0)
        self.assertAlmostEqual(PAULI_Z.expectation_value(one).real, -1.0)

    def test_tensor_product_and_bell_state_probabilities(self):
        zero = QuantumState.basis(2, 0)
        pair = tensor_states(zero, zero)
        h_on_first = tensor_operators(HADAMARD, IDENTITY_2)
        bell = CNOT.apply(h_on_first.apply(pair))
        probabilities = born_probabilities(bell)
        self.assertTrue(math.isclose(probabilities[0], 0.5))
        self.assertTrue(math.isclose(probabilities[1], 0.0, abs_tol=1e-12))
        self.assertTrue(math.isclose(probabilities[2], 0.0, abs_tol=1e-12))
        self.assertTrue(math.isclose(probabilities[3], 0.5))

    def test_projective_measurement_and_collapse(self):
        plus = HADAMARD.apply(QuantumState.basis(2, 0))
        measurement = computational_basis_measurement(2)
        self.assertEqual(len(measurement.projectors), 2)
        probabilities = measurement.probabilities(plus)
        self.assertTrue(math.isclose(probabilities[0], 0.5))
        collapsed = measurement.collapse(plus, 0)
        self.assertTrue(math.isclose(born_probabilities(collapsed)[0], 1.0))
        self.assertTrue(math.isclose(born_probabilities(collapsed)[1], 0.0, abs_tol=1e-12))

    def test_invalid_measurement_and_dimensions_fail_clearly(self):
        incomplete = (LinearOperator.from_rows(((1, 0), (0, 0))),)
        with self.assertRaises(ValueError):
            ProjectiveMeasurement(incomplete)
        with self.assertRaises(ValueError):
            HADAMARD.apply(QuantumState.basis(3, 0))
        with self.assertRaises(ValueError):
            computational_basis_measurement(0)


if __name__ == "__main__":
    unittest.main()
