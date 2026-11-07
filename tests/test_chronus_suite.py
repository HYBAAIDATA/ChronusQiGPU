import unittest
import os, sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from chronus.core import ChronusVerificationOrchestrator
from chronus.config import (
    ENABLE_POST_QUANTUM_SIGNATURES,
    ENABLE_ZK_STARK_VERIFICATION,
    INVARIANT_CONTRACT_RANGE,
    ML_DSA_SUPPORT,
    PRODUCTION_MODE,
    sram_total_per_node,
)

class TestChronusMasterSuite(unittest.TestCase):
    def test_package_facade_does_not_claim_unrun_qualification(self):
        res = ChronusVerificationOrchestrator.run_complete_verification_suite()
        self.assertEqual(res["qualification_status"], "NOT_QUALIFIED")
        self.assertEqual(res["total_release_gates_evaluated"], 0)
        self.assertEqual(res["release_gates_passed"], 0)
        self.assertIn("no executable", res["qualification_reason"])

    def test_compatibility_config_does_not_claim_unavailable_capabilities(self):
        self.assertFalse(PRODUCTION_MODE)
        self.assertFalse(ENABLE_POST_QUANTUM_SIGNATURES)
        self.assertFalse(ENABLE_ZK_STARK_VERIFICATION)
        self.assertFalse(ML_DSA_SUPPORT)
        self.assertEqual(INVARIANT_CONTRACT_RANGE, ())
        self.assertIsNone(sram_total_per_node())

if __name__ == "__main__":
    unittest.main()
