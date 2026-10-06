import unittest

import turing_universal_quantum_computer as tqc


class QuantumAsicIntegrationTests(unittest.TestCase):
    def test_lazy_product_exports(self):
        self.assertIsNotNone(tqc.PureQuantumMathASIC)
        self.assertIsNotNone(tqc.MathematicalEvidence)
        self.assertIsNotNone(tqc.QuantumAsicStack)
        self.assertIsNotNone(tqc.SurfaceCode)

    def test_virtual_computer_exposes_first_principles_math_asic(self):
        system = tqc.TenThousandQubitSystem(n_qubits=32)
        model = system.pure_quantum_asic()
        self.assertEqual(model, system.fault_tolerant_asic())
        report = model.report(logical_scale=32)
        self.assertEqual(
            report["truth_class"],
            "pure_quantum_mathematical_abstraction",
        )
        self.assertEqual(report["formal_hilbert_dimension"], "2^32")
        self.assertFalse(report["physical_qpu_present"])
        status = system.status()
        self.assertEqual(
            status["pure_quantum_asic"]["schema"],
            "turing.pure_quantum_math_asic/v1",
        )
        self.assertTrue(status["pure_quantum_asic"]["first_principles"])
        verification = system.verify_pure_quantum_asic()
        self.assertTrue(verification.verified)
        capacity = system.deterministic_10eh_system()
        self.assertTrue(capacity.certificate.steady_state_floor_met)
        self.assertTrue(capacity.certificate.cold_start_floor_met)
        self.assertEqual(
            verification.evidence.missing,
            ("independent_model_review",),
        )


if __name__ == "__main__":
    unittest.main()
