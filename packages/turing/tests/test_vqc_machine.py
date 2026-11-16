import unittest
import numpy as np

from turing.applications.vqc_machine import (
    ALGORITHM_CATALOG, PhiQuantumCircuit, PhiQuantumMachine1000,
    StabilizerRegister, run_1000_qubit_demonstration,
)
from turing.applications.vqc_fold import ValidationError


class TestPhiQuantumMachine(unittest.TestCase):
    def test_default_width_is_1000(self):
        m = PhiQuantumMachine1000()
        self.assertEqual(m.logical_qubits, 1000)
        self.assertLess(m.register.storage_bytes, 5_000_000)
        self.assertEqual(m.system_report()['dense_statevector_log2_bytes'], 1004)

    def test_zero_state_measurement(self):
        r = PhiQuantumMachine1000(8).execute(PhiQuantumCircuit(8), shots=4)
        self.assertTrue(np.all(r.samples == 0))

    def test_x_state_measurement(self):
        c = PhiQuantumCircuit(16)
        for q in range(16): c.x(q)
        r = PhiQuantumMachine1000(16).execute(c, shots=3)
        self.assertTrue(np.all(r.samples == 1))

    def test_bell_correlations(self):
        c = PhiQuantumCircuit(2).h(0).cx(0, 1)
        r = PhiQuantumMachine1000(2).execute(c, shots=128, seed=3)
        self.assertTrue(np.all(r.samples[:, 0] == r.samples[:, 1]))
        self.assertGreater(len(r.counts), 1)

    def test_1000_qubit_ghz_correlations(self):
        r = PhiQuantumMachine1000().execute(PhiQuantumCircuit.ghz(1000), shots=16, seed=9)
        self.assertEqual(r.gates_executed, 1000)
        self.assertTrue(all((row == 0).all() or (row == 1).all() for row in r.samples))
        self.assertGreater(len(r.counts), 1)

    def test_checkpoint_roundtrip_and_regeneration(self):
        m = PhiQuantumMachine1000(64, fold_depth=8)
        m.apply_circuit(PhiQuantumCircuit.ghz(64))
        cp = m.checkpoint()
        original = m.register.digest()
        m.register.x[0, 0] ^= True
        self.assertNotEqual(m.register.digest(), original)
        m.regenerate()
        self.assertEqual(m.register.digest(), original)
        self.assertLess(cp.reconstruction_error, 1e-12)

    def test_qasm_subset(self):
        qasm = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'
        c = PhiQuantumCircuit.from_qasm(qasm)
        r = PhiQuantumMachine1000(2).execute(c, shots=32)
        self.assertTrue(np.all(r.samples[:, 0] == r.samples[:, 1]))

    def test_non_affine_small_circuit_uses_tableau_sampler(self):
        c = PhiQuantumCircuit(2).h(0).cx(0, 1).h(0)
        r = PhiQuantumMachine1000(2).execute(c, shots=64, seed=4)
        self.assertEqual(r.samples.shape, (64, 2))
        self.assertGreaterEqual(len(r.counts), 3)

    def test_gate_validation(self):
        with self.assertRaises(ValidationError): PhiQuantumCircuit(2).cx(0, 0)
        with self.assertRaises(ValidationError): PhiQuantumCircuit(2).h(2)

    def test_algorithm_catalog_and_plans(self):
        m = PhiQuantumMachine1000()
        self.assertEqual(len(ALGORITHM_CATALOG), 12)
        for name in ALGORITHM_CATALOG:
            self.assertEqual(m.plan_algorithm(name)['logical_qubits'], 1000)
        self.assertEqual(m.plan_algorithm('grover')['search_space_log2'], 1000)
        self.assertEqual(m.plan_algorithm('shor')['max_modulus_bits'], 500)
        self.assertEqual(m.plan_algorithm('qft')['gate_count'], 500500)

    def test_demonstration(self):
        report = run_1000_qubit_demonstration(shots=8)
        self.assertTrue(report['ghz_correlations_verified'])
        self.assertEqual(report['logical_qubits'], 1000)
        self.assertLess(report['checkpoint_reconstruction_error'], 1e-12)


if __name__ == '__main__':
    unittest.main()
