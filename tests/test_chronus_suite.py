import unittest
import os, sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from chronus.core import ChronusVerificationOrchestrator

class TestChronusMasterSuite(unittest.TestCase):
    def test_full_verification_suite(self):
        res = ChronusVerificationOrchestrator.run_complete_verification_suite()
        self.assertEqual(res["qualification_status"], "PRODUCTION_QUALIFIED")

if __name__ == "__main__":
    unittest.main()
