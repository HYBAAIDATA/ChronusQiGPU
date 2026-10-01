"""Exact state-vector algebra tests (consolidated from chronus.mla1517 quantum tests)."""
import unittest
from fractions import Fraction

from turing_universal_quantum_computer.exact_state_vector import (
    C0,
    C1,
    ExactStateVector,
    H,
    Qsqrt2,
    X,
    Y,
    Z,
)
from turing_universal_quantum_computer.exact_tensor import (
    GATE_H,
    GATE_X,
    GATE_Y,
    GATE_Z,
)
from turing_universal_quantum_computer.exact_tensor import (
    ExactStateVector as TensorState,
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


class ExactPauliEvolutionTests(unittest.TestCase):
    """X/Y Hamiltonian evolution via Clifford conjugation, exact in Q(sqrt(2))+iQ(sqrt(2))."""

    def test_x_half_turn_is_the_x_gate(self):
        evolved = ExactStateVector.basis(1).evolve_hamiltonian("X", 2)
        expected = ExactStateVector.basis(1).apply_single(0, X)
        self.assertEqual(evolved.amplitudes, expected.amplitudes)

    def test_y_half_turn_is_the_y_gate(self):
        evolved = ExactStateVector.basis(1).evolve_hamiltonian("Y", 2)
        expected = ExactStateVector.basis(1).apply_single(0, Y)
        self.assertEqual(evolved.amplitudes, expected.amplitudes)

    def test_z_half_turn_is_the_z_gate(self):
        evolved = ExactStateVector.basis(1).evolve_hamiltonian("Z", 2)
        expected = ExactStateVector.basis(1).apply_single(0, Z)
        self.assertEqual(evolved.amplitudes, expected.amplitudes)

    def test_full_x_turn_returns_to_basis(self):
        evolved = ExactStateVector.basis(1).evolve_hamiltonian("X", 4)
        self.assertEqual(evolved.amplitudes, ExactStateVector.basis(1).amplitudes)

    def test_evolution_preserves_exact_normalization(self):
        for axis in ("X", "Y", "Z"):
            for k in (1, 2, 3):
                state = ExactStateVector.basis(1).evolve_hamiltonian(axis, k)
                self.assertTrue(state.normalized_exact())

    def test_multi_qubit_evolution_acts_on_lsb(self):
        state = ExactStateVector.basis(2).evolve_hamiltonian("X", 2)
        # X gate on qubit 0 of |00> gives |01>.
        self.assertEqual(state.amplitudes[1].real, Qsqrt2(1))
        self.assertTrue(state.normalized_exact())

    def test_non_pauli_axis_still_fails_closed(self):
        with self.assertRaises(NotImplementedError):
            ExactStateVector.basis(1).evolve_hamiltonian("XZ", 1)
        with self.assertRaises(NotImplementedError):
            ExactStateVector.basis(1).evolve_hamiltonian("H", 1)
        with self.assertRaises(TypeError):
            ExactStateVector.basis(1).evolve_hamiltonian("X", 1.5)


class ExactTensorPauliEvolutionTests(unittest.TestCase):
    """The F4 (Q(zeta8)) engine: same Clifford conjugation, per-qubit."""

    def test_half_turn_is_the_pauli_gate_on_each_qubit(self):
        state = TensorState.basis(2).apply_single(1, GATE_H)
        gates = {"X": GATE_X, "Y": GATE_Y, "Z": GATE_Z}
        for axis, gate in gates.items():
            for qubit in (0, 1):
                evolved = state.evolve_hamiltonian(axis, 2, qubit)
                expected = state.apply_single(qubit, gate)
                self.assertEqual(evolved.amplitudes, expected.amplitudes)
                full = state.evolve_hamiltonian(axis, 4, qubit)
                self.assertEqual(full.amplitudes, state.amplitudes)

    def test_bad_axis_or_qubit_fails_closed(self):
        state = TensorState.basis(1)
        with self.assertRaises(NotImplementedError):
            state.evolve_hamiltonian("XZ", 1)
        with self.assertRaises(ValueError):
            state.evolve_hamiltonian("X", 1, qubit=1)


if __name__ == "__main__":
    unittest.main()
