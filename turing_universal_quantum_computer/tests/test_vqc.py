"""End-to-end smoke tests for the Turing Virtual Quantum Computer package."""
import unittest

import turing_universal_quantum_computer as tqc


class VQCPackageTests(unittest.TestCase):
    def test_self_verification(self):
        self.assertTrue(tqc.run_self_verification())

    def test_virtual_dimensions(self):
        self.assertEqual(tqc.VIRTUAL_QUANTUM_QUBITS, 11)
        self.assertEqual(tqc.VIRTUAL_QUANTUM_DIMENSION, 2048)

    def test_exact_register_grover_amplification(self):
        reg = tqc.QuantumRegister(11)
        reg.uniform_superposition()
        target = 777
        reg.apply_grover_oracle({target})
        reg.diffusion()
        reg.assert_normalized()
        dist = reg.distribution()
        argmax = max(dist, key=lambda k: dist[k])
        self.assertEqual(argmax, target)
        # One Grover iteration at N=2048 boosts the marked state to
        # sin^2(3*asin(1/sqrt(2048))) ~= 0.00439 -- a 9x amplification
        # over the uniform 1/2048 baseline.
        self.assertGreater(float(dist[target]), 2.0 / 2048)

    def test_quantum_tensor_exact_roundtrip(self):
        qt = tqc.QuantumTensor()
        qt.h(0).cnot(0, 1)
        dist = qt.born_distribution()
        self.assertEqual(len(dist), 2)  # Bell state: only |0..0> and |1..1>
        with self.assertRaises(TypeError):
            tqc.QuantumTensor.from_numpy([1.0, 0.0])

    def test_strict_quantum_certificate(self):
        cert = tqc.certify_work_window(bytes(range(76)), nonce_start=0, nonce_count=256)
        self.assertTrue(tqc.verify_certificate(cert))
        self.assertFalse(cert["consensus_authority"])
        self.assertFalse(cert["theorem_proven"])

    def test_hendrix_schedule_is_complete_permutation(self):
        schedule = tqc.HendrixStructuredSearch(workers=1, scale_index=76).plan(4096)
        self.assertTrue(schedule.verify())
        nonces = [schedule.nonce_at(p) for p in range(schedule.nonce_count)]
        self.assertEqual(sorted(nonces), list(range(4096)))

    def test_vqc_execution_certifies_window(self):
        adapter = tqc.LucasScaledAethelExecutionAdapter(scale_index=76)
        header = bytes(range(76)) + (0).to_bytes(4, "little")
        result = adapter.execute(header, target=(1 << 256) - 1, base_nonce=0, count=256)
        self.assertEqual(result.hashes, 256)
        self.assertTrue(result.metadata["fold_roundtrip_lossless"])
        self.assertTrue(result.metadata["cassini_holds"])
        self.assertTrue(result.metadata["toe"]["provenance_verified"])


if __name__ == "__main__":
    unittest.main()
