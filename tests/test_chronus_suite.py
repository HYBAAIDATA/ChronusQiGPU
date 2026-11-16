import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from chronus.core import ChronusVerificationOrchestrator
from chronus.config import (
    ENABLE_POST_QUANTUM_SIGNATURES,
    ENABLE_ZK_STARK_VERIFICATION,
    INVARIANT_CONTRACT_RANGE,
    ML_DSA_SUPPORT,
    PRODUCTION_MODE,
    total_invariant_range,
)


class TestChronusMasterSuite(unittest.TestCase):
    def test_full_verification_suite_fails_closed_without_external_evidence(self):
        res = ChronusVerificationOrchestrator.run_complete_verification_suite()
        # A local diagnostic is never independent release qualification.
        self.assertEqual(res["qualification_status"], "NOT_QUALIFIED")
        self.assertEqual(res["execution_mode"], "LOCAL_DIAGNOSTIC_ONLY")
        self.assertLessEqual(
            res["release_gates_passed"], res["total_release_gates_evaluated"]
        )
        self.assertEqual(res["total_release_gates_evaluated"], 5)
        self.assertEqual(len(res["gates"]), 5)
        self.assertTrue(any(not gate["passed"] for gate in res["gates"]))
        self.assertIsNone(res["total_invariants_evaluated"])
        self.assertIsNone(res["invariants_passed"])
        self.assertIn("UNAVAILABLE", res["invariant_summary"])
        self.assertTrue(res["blockers"])

    def test_production_config_capabilities(self):
        self.assertTrue(PRODUCTION_MODE)
        self.assertTrue(ENABLE_POST_QUANTUM_SIGNATURES)
        self.assertTrue(ENABLE_ZK_STARK_VERIFICATION)
        self.assertTrue(ML_DSA_SUPPORT)
        self.assertEqual(len(INVARIANT_CONTRACT_RANGE), 94)
        self.assertEqual(len(total_invariant_range()), 94)


if __name__ == "__main__":
    unittest.main()
