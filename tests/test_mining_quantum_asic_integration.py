"""Mining owns the capacity surface: the PureQuantumMathASIC abstraction and the
exact 10 EH/s formal-capacity certificates, built on TURING's exact algebra."""

import unittest

from mining.fault_tolerant_asic import (
    MathematicalEvidence,
    PureQuantumMathASIC,
    QuantumAsicStack,
    SurfaceCode,
)


class MiningQuantumAsicIntegrationTests(unittest.TestCase):
    def test_capacity_surface_exports(self):
        self.assertIsNotNone(PureQuantumMathASIC)
        self.assertIsNotNone(MathematicalEvidence)
        self.assertIsNotNone(QuantumAsicStack)
        self.assertIsNotNone(SurfaceCode)

    def test_first_principles_math_asic_and_capacity_certificates(self):
        model = PureQuantumMathASIC()
        report = model.report(logical_scale=32)
        self.assertEqual(report["truth_class"], "pure_quantum_mathematical_abstraction")
        self.assertEqual(report["formal_hilbert_dimension"], "2^32")
        self.assertFalse(report["physical_qpu_present"])
        verification = model.verify_first_principles()
        self.assertTrue(verification.verified)
        capacity = model.deterministic_hashrate_system()
        self.assertTrue(capacity.certificate.steady_state_floor_met)
        self.assertTrue(capacity.certificate.cold_start_floor_met)
        heterogeneous = model.heterogeneous_hashrate_certificate()
        self.assertTrue(heterogeneous.floor_met)
        self.assertEqual(
            heterogeneous.truth_class,
            "exact_mathematical_capacity_not_executed_work",
        )
        self.assertEqual(verification.evidence.missing, ("independent_model_review",))


if __name__ == "__main__":
    unittest.main()
