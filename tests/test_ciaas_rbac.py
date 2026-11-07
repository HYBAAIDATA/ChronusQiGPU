"""Unit and integration tests for CIaaS Multi-Tenant Fabric, AL HARAS RBAC, and Hermiten Settlement."""

import os
import sys
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from chronus.service.app import create_app
from chronus.service.auth_middleware import Role, jwt_validator


class TestCIaaSRBAC(unittest.TestCase):
    """Test AL HARAS RBAC matrix, token issuing, and multi-tenant endpoints."""

    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_rbac_matrix_endpoint(self):
        """Verify AL HARAS 4-tier privileges matrix structure."""
        response = self.client.get("/v1/auth/rbac/matrix")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("role_tiers", data)
        role_tiers = data["role_tiers"]

        # Ensure all 4 canonical roles exist
        self.assertIn("system_admin", role_tiers)
        self.assertIn("tenant_admin", role_tiers)
        self.assertIn("developer", role_tiers)
        self.assertIn("external_auditor", role_tiers)

        # Check detail fidelity
        self.assertEqual(role_tiers["system_admin"]["title"], "System Admin")
        self.assertEqual(role_tiers["tenant_admin"]["persona"], "Enterprise FinOps / IT Lead")
        self.assertIn("ptr_sdk_", role_tiers["developer"]["scope"])
        self.assertIn("zk-STARK", role_tiers["external_auditor"]["audit"])

    def test_token_issuance_and_validation(self):
        """Mint a token with role tenant_admin and validate it through jwt_validator."""
        payload = {
            "tenant_id": "tenant-enterprise-99",
            "user_id": "user-finops-lead",
            "role": "tenant_admin",
            "expires_in_seconds": 3600,
        }
        response = self.client.post("/v1/auth/token", json=payload)
        self.assertEqual(response.status_code, 200)
        token_data = response.json()
        self.assertIn("access_token", token_data)
        token = token_data["access_token"]

        # Validate with JWT validator
        identity = jwt_validator.validate_token(token)
        self.assertEqual(identity.tenant_id, "tenant-enterprise-99")
        self.assertEqual(identity.user_id, "user-finops-lead")
        self.assertTrue(identity.has_role(Role.TENANT_ADMIN))
        self.assertTrue(identity.has_role(Role.OPERATOR))  # Alias check

    def test_tenant_onboarding_and_retrieval(self):
        """Onboard a new enterprise tenant and retrieve profile with CCE limits."""
        tenant_id = "tenant-unit-test-corp"
        onboard_payload = {
            "tenant_id": tenant_id,
            "organization_name": "Unit Test Global Corp",
            "admin_email": "admin@unittestcorp.com",
            "regional_pod": "beta",
            "cce": {
                "data_at_rest_gb": 4096,
                "data_in_motion_gb": 8192,
                "data_processed_gb": 32768,
                "compute_intensity_ccu": 1024,
                "concurrency_limit": 64,
            },
            "sovereign_profile_enabled": True,
        }
        res = self.client.post("/v1/tenants/onboard", json=onboard_payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["tenant_id"], tenant_id)
        self.assertTrue(data["api_key_prefix"].startswith("ptr_sdk_"))
        self.assertEqual(data["cce"]["compute_intensity_ccu"], 1024)

        # Retrieve profile
        get_res = self.client.get(f"/v1/tenants/{tenant_id}")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["organization_name"], "Unit Test Global Corp")

    def test_cce_quota_update(self):
        """Update CCE 5-dimension allocations."""
        tenant_id = "tenant-default"
        new_cce = {
            "data_at_rest_gb": 5000,
            "data_in_motion_gb": 10000,
            "data_processed_gb": 50000,
            "compute_intensity_ccu": 2048,
            "concurrency_limit": 128,
        }
        res = self.client.post(f"/v1/tenants/{tenant_id}/cce", json=new_cce)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["cce"]["compute_intensity_ccu"], 2048)

    def test_four_part_pricing_breakdown(self):
        """Verify four-part pricing: P_total = P_platform + P_reserved + P_consumption + P_assurance."""
        res = self.client.get("/v1/tenants/tenant-default/pricing?consumed_ccu=200")
        self.assertEqual(res.status_code, 200)
        pricing = res.json()
        self.assertIn("platform_fee_usd", pricing)
        self.assertIn("reserved_capacity_usd", pricing)
        self.assertIn("metered_consumption_usd", pricing)
        self.assertIn("proof_assurance_usd", pricing)
        self.assertIn("total_price_usd", pricing)

        p_plat = float(pricing["platform_fee_usd"])
        p_res = float(pricing["reserved_capacity_usd"])
        p_cons = float(pricing["metered_consumption_usd"])
        p_assur = float(pricing["proof_assurance_usd"])
        p_tot = float(pricing["total_price_usd"])

        # P_total must equal the sum of the four parts
        self.assertAlmostEqual(p_tot, p_plat + p_res + p_cons + p_assur, places=2)

    def test_hermiten_25_percent_settlement(self):
        """Verify Hermiten 25% value share settlement: F_Chronus = 0.25 * max(0, S_net)."""
        payload = {
            "counterfactual_cost": 100000,
            "actual_cost": 20000,
            "incremental_cost": 0,
        }
        res = self.client.post("/v1/tenants/tenant-default/settlement", json=payload)
        self.assertEqual(res.status_code, 200)
        settlement = res.json()

        # Net avoided cost = 100000 - 20000 = 80000
        self.assertEqual(float(settlement["net_avoided_cost_usd"]), 80000.0)
        # Chronus 25% value share = 20000
        self.assertEqual(float(settlement["chronus_value_share_usd"]), 20000.0)
        # Client retained 75% = 60000
        self.assertEqual(float(settlement["client_retained_usd"]), 60000.0)
        self.assertEqual(settlement["settlement_status"], "RECONCILED")
        self.assertTrue(settlement["proof_certificate"].startswith("cert_hermiten_"))

    def test_fabric_pods_fleet(self):
        """Inspect regional fleet pods alpha..delta, DEC fluid routing, and DSW instanton healer."""
        res = self.client.get("/v1/fabric/pods")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["virtual_crossbar"]["bandwidth"], "130 Tb/s")
        self.assertEqual(data["virtual_crossbar"]["packet_stalls"], 0)
        self.assertEqual(data["instanton_healer"]["repair_latency_cycles"], 1)

        pods = {p["pod"]: p for p in data["pods"]}
        self.assertIn("alpha", pods)
        self.assertIn("beta", pods)
        self.assertIn("gamma", pods)
        self.assertIn("delta", pods)

    def test_sovereign_governance_profile(self):
        """Inspect Sovereign Profile, NCSC 14 principles, and Sheaf Cohomology."""
        res = self.client.get("/v1/governance/sovereign")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["compliance"]["principles_passed"], 14)
        self.assertEqual(data["cellular_sheaf_cohomology"]["cohomology_class"], "H^1(X; F) = 0")
        self.assertEqual(data["cellular_sheaf_cohomology"]["prompt_injection_vortices"], 0)


if __name__ == "__main__":
    unittest.main()

