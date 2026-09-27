"""Exact state-vector algebra tests (consolidated from mla1517 quantum tests)."""
import unittest
from fractions import Fraction

from turing_universal_quantum_computer.exact_state_vector import (
    C0,
    C1,
    ExactStateVector,
    H,
    Qsqrt2,
    X,
)


class ExactQuantumTests(unittest.TestCase):
    def test_hadamard_is_exact_and_normalized(self):
        state = ExactStateVector.basis(1).apply_single(0, H)
        self.assertTrue(state.normalized_exact())
        self.assertEqual(state.amplitudes[0].real.b, state.amplitudes[1].real.b)

    def test_tensor_and_cnot_bell_state(self):
        state = (
            ExactStateVector.basis(1)
            .tensor(ExactStateVector.basis(1))
            .apply_single(0, H)
            .apply_cnot(0, 1)
        )
        self.assertTrue(state.normalized_exact())
        self.assertEqual(state.amplitudes[1], state.amplitudes[2])

    def test_hamiltonian_fails_closed_outside_exact_domain(self):
        with self.assertRaises(NotImplementedError):
            ExactStateVector.basis(1).evolve_hamiltonian("XX", 1)

    def test_resource_bound_fails_closed(self):
        with self.assertRaises(MemoryError):
            ExactStateVector.basis(10, max_amplitudes=8)


class ExactMeasurementTests(unittest.TestCase):
    def test_hadamard_born_weights_are_exact(self):
        state = ExactStateVector.basis(1).apply_single(0, H)
        self.assertEqual(state.probabilities_exact(), (Qsqrt2(Fraction(1, 2)), Qsqrt2(Fraction(1, 2))))
        self.assertEqual(state.probabilities_exact()[0].a, Fraction(1, 2))
        self.assertEqual(state.probabilities_exact()[0].b, 0)
        self.assertEqual(state.expectation_z_exact(), Qsqrt2())

    def test_deterministic_measurement_tie_breaks_lowest_index(self):
        state = ExactStateVector.basis(1).apply_single(0, H)
        self.assertEqual(state.measure_deterministic(), 0)

    def test_collapse_is_exact_basis_projection(self):
        state = ExactStateVector.basis(1).apply_single(0, H)
        collapsed = state.collapse(1)
        self.assertEqual(collapsed.amplitudes[1].real, Qsqrt2(1))
        self.assertTrue(collapsed.normalized_exact())

    def test_zero_weight_cannot_be_selected(self):
        with self.assertRaises(ValueError):
            ExactStateVector.basis(1).collapse(1)

    def test_ordering_never_uses_float(self):
        self.assertEqual(Qsqrt2(0, 1).compare(Qsqrt2(1, 2)), -1)
        self.assertEqual(Qsqrt2(1, 2).compare(Qsqrt2(0, 1)), 1)

    def test_exact_gate_preserves_born_sum(self):
        state = ExactStateVector.basis(1).apply_single(0, X)
        self.assertEqual(sum(state.probabilities_exact(), Qsqrt2()), Qsqrt2(1))

    def test_non_unitary_gate_fails_closed(self):
        bad_gate = ((C1, C1), (C0, C1))
        with self.assertRaises(ValueError):
            ExactStateVector.basis(1).apply_single(0, bad_gate)


if __name__ == "__main__":
    unittest.main()
