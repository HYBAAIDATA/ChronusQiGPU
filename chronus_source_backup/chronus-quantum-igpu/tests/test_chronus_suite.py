import unittest
import os, sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from chronus.core import ChronusVerificationOrchestrator
from chronus.ns_dec import NavierStokesDECFluidRouter

class TestChronusMasterSuite(unittest.TestCase):
    def test_full_verification_suite(self):
        res = ChronusVerificationOrchestrator.run_complete_verification_suite()
        self.assertEqual(res["qualification_status"], "PRODUCTION_QUALIFIED")

    def test_navier_stokes_dec(self):
        routed, dw_zero, helicity, stalls = NavierStokesDECFluidRouter.route_packet_dec_flow(b"test_payload")
        self.assertTrue(dw_zero)
        self.assertEqual(stalls, 0)

if __name__ == "__main__":
    unittest.main()
