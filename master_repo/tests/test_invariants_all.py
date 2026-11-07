import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from chronus.core import ChronusVerificationOrchestrator, run_invariant_tests

class TestAllInvariantsSuite(unittest.TestCase):
    def test_run_invariant_tests_function(self):
        res = run_invariant_tests()
        self.assertTrue(res, "run_invariant_tests must return True for all 94 invariants")

    def test_complete_orchestrator_verification(self):
        res = ChronusVerificationOrchestrator.run_complete_verification_suite()
        self.assertEqual(res["qualification_status"], "PRODUCTION_QUALIFIED")
        self.assertEqual(res["total_release_gates_evaluated"], 8)

if __name__ == "__main__":
    unittest.main()
