import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from chronus.ns_dec import NavierStokesDECFluidRouter

class TestNavierStokesDECSuite(unittest.TestCase):
    def test_dec_packet_routing_zero_stall(self):
        payload = b"NavierStokes_DEC_2Form_Fluid_Payload_100Pct_Saturation"
        routed, dw_zero, helicity, stalls = NavierStokesDECFluidRouter.route_packet_dec_flow(
            payload, bus_saturation=1.0
        )
        self.assertEqual(bytes(routed), payload)
        self.assertTrue(dw_zero)
        self.assertEqual(stalls, 0)

    def test_dec_enstrophy_conservation(self):
        flow_field = [1.2, 0.8, -0.5, 2.1, -1.7, 0.4]
        metrics = NavierStokesDECFluidRouter.compute_dec_2form_enstrophy(flow_field)
        self.assertTrue(metrics["helicity_conserved"])
        self.assertFalse(metrics["triad_singularity"])
        self.assertEqual(metrics["dec_status"], "SYMPLECTIC_DEC_FLOW_STABLE")

    def test_dec_empty_payload(self):
        routed, dw_zero, helicity, stalls = NavierStokesDECFluidRouter.route_packet_dec_flow(b"")
        self.assertEqual(bytes(routed), b"")
        self.assertTrue(dw_zero)
        self.assertEqual(stalls, 0)

if __name__ == "__main__":
    unittest.main()
