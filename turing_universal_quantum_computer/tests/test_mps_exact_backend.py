"""The exact MPS backend: Clifford+T at any width when entanglement stays bounded."""

import unittest

from turing_universal_quantum_computer.backends import (
    MPSExactBackend,
    Program,
    execute,
    schmidt_bound,
    select_backend,
)
from turing_universal_quantum_computer.backends.base import ExecutionClass, TruthClass


def _ghz_t(n: int) -> Program:
    program = Program(n).then("h", 0)
    for i in range(n - 1):
        program = program.then("cx", i, i + 1)
    return program.then("t", 0).then("s", n - 1)


class MPSExactBackendTests(unittest.TestCase):
    def test_wide_clifford_t_program_is_admitted_and_exact(self):
        program = _ghz_t(400)
        backend, admission = select_backend(program)
        self.assertIsNotNone(backend)
        self.assertEqual(backend.name, "mps_exact")
        self.assertTrue(admission.admitted)
        result = execute(
            program,
            shots=64,
            seed=5,
            readout=[0, 200, 399],
            marginal_of=[0, 399],
            entropy_of=list(range(200)),
            measure_qubit=17,
        )
        self.assertEqual(result.truth_class, TruthClass.EXACT)
        self.assertEqual(result.execution_class, ExecutionClass.BOUNDED_EXACT)
        payload = result.payload
        self.assertEqual(payload["max_bond"], 2)
        self.assertEqual(payload["norm_squared"], "1")
        self.assertEqual(payload["marginal"]["probabilities"], {"00": "1/2", "11": "1/2"})
        self.assertLessEqual(set(payload["counts"]), {"000", "111"})
        self.assertEqual(sum(payload["counts"].values()), 64)
        self.assertEqual(payload["entanglement_entropy_bits"], 1)
        self.assertEqual(payload["measurement"]["p0"], "1/2")
        self.assertEqual(len(payload["state_root"]), 64)

    def test_clifford_programs_keep_the_stabilizer_path(self):
        program = Program(400).then("h", 0).then("cx", 0, 399)
        backend, _ = select_backend(program)
        self.assertEqual(backend.name, "stabilizer")

    def test_unbounded_entanglement_is_refused_before_execution(self):
        program = Program(40)
        for _ in range(8):
            for q in range(40):
                program = program.then("h", q).then("t", q)
            for q in range(39):
                program = program.then("cx", q, q + 1)
        backend, admission = select_backend(program)
        self.assertIsNone(backend)
        self.assertIn("exceeds chi_max", admission.reason)

    def test_static_bound_is_sound_against_executed_bonds(self):
        program = Program(10).then("h", 0)
        for q in range(9):
            program = program.then("cx", q, q + 1).then("t", q)
        program = program.then("cx", 0, 9).then("h", 5).then("cz", 2, 7)
        bound = schmidt_bound(program)
        state = MPSExactBackend().build(program)
        bonds = state.bonds()[1:-1]
        self.assertTrue(all((1 << b) >= chi for b, chi in zip(bound, bonds)))

    def test_marginals_equal_the_dense_exact_state(self):
        from kellogg.cyclotomic import Q8
        from kellogg.exact_tensor import GATES, ExactStateVector

        n = 6
        program = (
            Program(n).then("h", 0).then("t", 0).then("cx", 0, 3).then("h", 2)
            .then("cz", 2, 5).then("h", 1).then("t", 1).then("h", 1)
        )
        dense = ExactStateVector.basis(n, 0)
        for op in program.operations:
            if op.gate == "cx":
                dense = dense.apply_cnot(*op.qubits)
            elif op.gate == "cz":
                dense = dense.apply_cz(*op.qubits)
            else:
                dense = dense.apply_single(op.qubits[0], GATES[op.gate.upper()])
        readout = (0, 1, 3)
        expected = {}
        for index, amp in enumerate(dense.amplitudes):
            key = "".join(str((index >> q) & 1) for q in readout)
            weight = Q8.from_f4(amp).norm2()
            expected[key] = expected.get(key, Q8()) + weight
        backend = MPSExactBackend()
        got = backend.build(program).marginal(list(readout))
        self.assertEqual(got, {k: v for k, v in sorted(expected.items()) if not v.is_zero()})

    def test_gates_outside_clifford_t_are_refused_not_approximated(self):
        backend = MPSExactBackend()
        self.assertTrue(backend.admit(Program(3).then("h", 0).then("t", 1)).admitted)
        refusal = backend.admit(Program(3).then("rx", 0))
        self.assertFalse(refusal.admitted)
        self.assertIn("outside Clifford+T", refusal.reason)


if __name__ == "__main__":
    unittest.main()
