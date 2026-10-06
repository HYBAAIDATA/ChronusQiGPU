import unittest

import turing_universal_quantum_computer as tqc


class QuantumAsicIntegrationTests(unittest.TestCase):
    def test_lazy_product_exports(self):
        self.assertIsNotNone(tqc.QuantumAsicStack)
        self.assertIsNotNone(tqc.SurfaceCode)
        self.assertIsNotNone(tqc.ScalingModel)
        self.assertIsNotNone(tqc.ProductionEvidence)

    def test_virtual_computer_exposes_separate_engineering_model(self):
        system = tqc.TenThousandQubitSystem(n_qubits=32)
        model = system.fault_tolerant_asic()
        report = model.report(physical_qubits=32)
        self.assertEqual(report["truth_class"], "deterministic_engineering_model")
        self.assertFalse(report["physical_qpu_present"])
        status = system.status()
        self.assertEqual(
            status["fault_tolerant_asic"]["schema"],
            "turing.quantum_asic/v1",
        )
        self.assertFalse(status["fault_tolerant_asic"]["physical_qpu_present"])


if __name__ == "__main__":
    unittest.main()
