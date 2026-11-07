import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from chronus.core import (
    FourPartPricingFramework,
    WorkloadBillingEligibilityPolicy,
    HermitenSavingsSettlementEngine,
    DeploymentSovereigntyAssuranceProfile
)

class TestHermitenAndPricingSuite(unittest.TestCase):
    def test_four_part_pricing(self):
        res = FourPartPricingFramework.calculate_total_price("CHRONUS_ENTERPRISE", reserved_blades=10, ccu_consumed=50000.0)
        self.assertEqual(res["calculation_status"], "FOUR_PART_PRICING_CALCULATED")
        self.assertEqual(res["p_platform_usd"], 150000.0)
        self.assertEqual(res["p_total_annual_usd"], 302500.0)

    def test_billing_eligibility_policy(self):
        res_ver = WorkloadBillingEligibilityPolicy.evaluate_billing_eligibility("VERIFIED", ccu_consumed=10.0)
        self.assertTrue(res_ver["is_billable"])
        
        res_rec = WorkloadBillingEligibilityPolicy.evaluate_billing_eligibility("REJECTED", ccu_consumed=10.0)
        self.assertFalse(res_rec["is_billable"])

    def test_hermiten_savings_settlement(self):
        res_settle = HermitenSavingsSettlementEngine.calculate_hermiten_savings_settlement(
            workload_id="job_123",
            lifecycle_state="VERIFIED",
            counterfactual_baseline_usd=10000.0,
            chronus_actual_cost_usd=4000.0,
            incremental_hosting_cost_usd=500.0
        )
        self.assertEqual(res_settle["net_verified_savings_usd"], 5500.0)
        self.assertEqual(res_settle["hermiten_value_share_fee_usd"], 1375.0)
        self.assertEqual(res_settle["net_customer_savings_usd"], 4125.0)
        self.assertEqual(res_settle["settlement_status"], "SETTLEMENT_VERIFIED_AND_ANCHORED")

    def test_sovereignty_profile(self):
        profile = DeploymentSovereigntyAssuranceProfile.evaluate_sovereignty_profile("CHRONUS_SOVEREIGN_NATIONAL")
        self.assertTrue(profile["sovereign_assurance_active"])
        self.assertEqual(profile["active_control_dimensions_count"], 8)

if __name__ == "__main__":
    unittest.main()
