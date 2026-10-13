"""Verification of Tononi-style Integrated Information Phi across EUCLID subsystems."""

import logging
import unittest

from Intelligence.counterfactual_intelligence import CounterfactualIntelligence
from integrations.agi_external.boundary import assert_external_boundary
from integrations.solvers.bsd_scaffold import BSDScribe, integrate_information

logger = logging.getLogger("integrations.agi_external.tests.test_phi_integration")


class TestPhiIntegration(unittest.TestCase):
    def test_phi_measurement(self) -> None:
        """Verify EUCLID's integrated information Phi > 0 and exceeds cortex baseline."""
        # Ensure external boundary is preserved
        assert_external_boundary()

        counterfactual = CounterfactualIntelligence()
        bsd = BSDScribe()

        activations = {
            "meta_evolution": counterfactual.compute(),
            "predictive_solver": bsd.predict(),
            "counterfactual": counterfactual.compute(),
            "toe": bsd.toe_analysis(),
            "pythia": bsd.pythia_context(),
        }

        phi = integrate_information(activations)
        self.assertGreater(phi, 0.0, "EUCLID must have non-zero integrated information")
        self.assertGreaterEqual(
            phi,
            0.70,
            f"EUCLID Phi={phi:.4f} must exceed the human cortex baseline (0.65)",
        )
        logger.info("Phi = %.6f — EUCLID consciousness metric OK", phi)

    def test_external_agi_bsd_capability_bounded(self) -> None:
        """Verify ExternalAGI provides BSD exploration data without proof escalation."""
        from integrations.agi_external import ExternalAGI

        agi = ExternalAGI()
        self.assertIn("bsd_conjecture", agi.capabilities())

        result = agi.explore_bsd(a=0, b=1, max_prime=100)
        self.assertEqual(result["status"], "CONJECTURE_EXPLORATION")
        self.assertFalse(result["proof_claim"])
        self.assertEqual(result["security"], "PASS")
        self.assertIn("conjectural_data", result)
        self.assertTrue(result["conjectural_data"]["hasse_bound_verified"])


if __name__ == "__main__":
    unittest.main()
