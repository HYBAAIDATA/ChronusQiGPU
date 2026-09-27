import unittest
from mla1517.quantum import ExactStateVector, H


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


if __name__ == "__main__":
    unittest.main()
