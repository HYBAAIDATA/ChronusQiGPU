"""Integration & concurrency tests for Chronus CIaaS Instant Provisioning & Enduring Capacity Engine."""

import base64
import hashlib
import hmac
import json
import os
import sys
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from chronus.security.kms import al_haras_kms_custody
from chronus.service.app import create_app
from chronus.service.auth_middleware import Role, create_jwt_token, jwt_validator
from chronus.service.instant_provisioning import instant_provisioning_engine
from chronus.storage.theseus import tenant_storage_registry


class TestInstantProvisioningEngine(unittest.TestCase):
    """End-to-end verification of the 4-Stage Zero-Friction Provisioning & ECA Engine."""

    def setUp(self) -> None:
        self.app = create_app()
        self.client = TestClient(self.app)
        self.sys_admin_token = create_jwt_token(
            tenant_id="chronus-root",
            user_id="sre-lead@chronus.io",
            role=Role.SYSTEM_ADMIN,
        )
        self._created_tenants: list[str] = []

    def tearDown(self) -> None:
        for tid in self._created_tenants:
            instant_provisioning_engine.remove_tenant_completely(tid)

    def test_exact_spec_instant_onboarding_and_self_service_scaling(self) -> None:
        """Verify exact REST API contract for T0 instant onboarding and zero-addendum scaling."""
        tenant_id = "tenant_apex_9921a"
        self._created_tenants.append(tenant_id)

        onboard_body = {
            "contract_id": "ctr_apex_2026_9941",
            "company_name": "Apex Global Financial",
            "tenant_id": tenant_id,
            "admin_email": "security@apexglobal.com",
            "enduring_addendum_accepted": True,
            "cce_allocations": {
                "initial_warps": 32,
                "max_authorized_warps": 1024,
                "data_at_rest_gb": 10000,
                "data_in_motion_gb": 5000,
                "kms_provider": "AWS_KMS",
                "kms_key_arn": "arn:aws:kms:us-east-1:123456789012:key/apex-prod-key",
            },
        }

        res = self.client.post(
            "/v1/tenants/onboard/instant",
            json=onboard_body,
            headers={"Authorization": f"Bearer {self.sys_admin_token}"},
        )
        self.assertEqual(res.status_code, 201, res.text)
        data = res.json()

        # Verify exact specification fields
        self.assertEqual(data["status"], "TENANT_PROVISIONED_INSTANTLY")
        self.assertEqual(data["tenant_id"], "tenant_apex_9921a")
        self.assertTrue(data["assigned_cce_id"].startswith("cce_apex_"))
        # Keys are in process memory today, so the computed status must say so.
        self.assertEqual(data["al_haras_kms_status"], "LOCAL_KEY_NOT_CUSTOMER_HELD")
        self.assertTrue(data["tenant_admin_token"].startswith("eyJ"))
        self.assertIn("tenant_apex_9921a/workloads", data["console_access_url"])
        self.assertEqual(data["zero_copy_prefix"], "ptr_sdk_apex_")
        self.assertEqual(data["ovid_namespace"], "o1_tenant_apex_9921a")
        self.assertLess(data["execution_time_ms"], 30000.0)

        # Stage 2: Verify Postgres REPEATABLE READ isolation & THESEUS journal continuity
        self.assertEqual(data["postgres_isolation"]["pool_size"], 10)
        self.assertEqual(
            data["postgres_isolation"]["isolation_level"], "REPEATABLE READ"
        )
        self.assertTrue(tenant_storage_registry.verify_journal_continuity(tenant_id))

        # Stage 3: Verify AL HARAS KMS PKCS#11 custody attestation & JWT claims
        self.assertTrue(al_haras_kms_custody.verify_binding(tenant_id))
        admin_token = data["tenant_admin_token"]
        identity = jwt_validator.validate_token(admin_token)
        self.assertEqual(identity.tenant_id, tenant_id)
        self.assertTrue(identity.has_role(Role.TENANT_ADMIN))

        # Verify T0 immediate workload execution using issued SDK API key
        sdk_api_key = data["credential_handoff"]["sdk_api_key"]
        self.assertTrue(sdk_api_key.startswith("ptr_sdk_apex_"))
        wkld_payload = base64.b64encode(
            json.dumps({"index": 24}).encode("utf-8")
        ).decode("ascii")
        wkld_res = self.client.post(
            "/v1/workloads",
            json={
                "tenant_id": tenant_id,
                "workload_type": "LUCAS_PV_SCALING",
                "representation_mode": "EXACT_Q5_RATIONAL",
                "payload_bytes": f"base64:{wkld_payload}",
                "priority": "HIGH",
            },
            headers={"Authorization": f"Bearer {sdk_api_key}"},
        )
        self.assertEqual(wkld_res.status_code, 202, wkld_res.text)
        self.assertEqual(wkld_res.json()["status"], "COMPLETED")

        # Stage 4: Dynamic Self-Service Capacity Expansion (No Addendum Required)
        expand_body = {
            "requested_warp_capacity": 256,
            "expand_storage_gb": 50000,
            "reason": "Q4_QUANT_MODEL_BURST_RUN",
        }
        patch_res = self.client.patch(
            f"/v1/tenants/{tenant_id}/capacity",
            json=expand_body,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(patch_res.status_code, 200, patch_res.text)
        patch_data = patch_res.json()

        self.assertEqual(patch_data["status"], "CAPACITY_EXPANDED_INSTANTLY")
        self.assertEqual(patch_data["tenant_id"], tenant_id)
        self.assertEqual(patch_data["previous_warps"], 32)
        self.assertEqual(patch_data["new_active_warps"], 256)
        self.assertTrue(patch_data["enduring_addendum_valid"])
        self.assertFalse(patch_data["additional_approval_required"])
        self.assertEqual(patch_data["new_storage_gb"], 50000)

        # Verify automated Hermiten 25% Value-Share settlement & THESEUS journal append
        settlement = patch_data["hermiten_settlement"]
        s_net = float(settlement["net_avoided_cost_usd"])
        f_chronus = float(settlement["chronus_value_share_usd"])
        self.assertGreater(s_net, 0.0)
        self.assertAlmostEqual(f_chronus, s_net * 0.25, places=2)
        self.assertEqual(len(tenant_storage_registry.get_journal(tenant_id)), 2)
        self.assertTrue(tenant_storage_registry.verify_journal_continuity(tenant_id))

        # Verify GET /capacity reflects updated allocations
        cap_status = self.client.get(
            f"/v1/tenants/{tenant_id}/capacity",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(cap_status.status_code, 200)
        self.assertEqual(cap_status.json()["active_warps"], 256)
        self.assertEqual(cap_status.json()["theseus_journal_entries"], 2)

    def test_webhook_hmac_signature_ingress(self) -> None:
        """Verify Stage 1 DocuSign / Ironclad HMAC-SHA256 webhook signature authentication."""
        tenant_id = "tenant_ironclad_771"
        self._created_tenants.append(tenant_id)
        secret = "docusign-enterprise-msa-webhook-secret-2026"
        old_secret = os.environ.get("CHRONUS_WEBHOOK_SECRET")
        os.environ["CHRONUS_WEBHOOK_SECRET"] = secret
        try:
            payload = {
                "contract_id": "ctr_ironclad_2026_771",
                "company_name": "Ironclad Sovereign Capital",
                "tenant_id": tenant_id,
                "admin_email": "ciso@ironcladcap.io",
                "enduring_addendum_accepted": True,
                "webhook_source": "IRONCLAD_CLM",
                "cce_allocations": {
                    "initial_warps": 64,
                    "max_authorized_warps": 4096,
                    "data_at_rest_gb": 20000,
                    "data_in_motion_gb": 10000,
                    "kms_provider": "HASHICORP_VAULT",
                    "kms_key_arn": "transit/keys/ironclad-sovereign-root",
                },
            }
            raw_bytes = json.dumps(payload).encode("utf-8")
            sig_hex = hmac.new(
                secret.encode("utf-8"), raw_bytes, hashlib.sha256
            ).hexdigest()

            # Valid HMAC signature without Bearer token succeeds
            res = self.client.post(
                "/v1/tenants/onboard/instant",
                content=raw_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-Ironclad-Signature": f"sha256={sig_hex}",
                },
            )
            self.assertEqual(res.status_code, 201, res.text)
            self.assertEqual(
                res.json()["al_haras_kms_status"], "LOCAL_KEY_NOT_CUSTOMER_HELD"
            )

            # Tampered signature is rejected with 401
            bad_res = self.client.post(
                "/v1/tenants/onboard/instant",
                content=raw_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-Ironclad-Signature": "sha256=" + ("0" * 64),
                },
            )
            self.assertEqual(bad_res.status_code, 401)
        finally:
            if old_secret is not None:
                os.environ["CHRONUS_WEBHOOK_SECRET"] = old_secret
            else:
                os.environ.pop("CHRONUS_WEBHOOK_SECRET", None)

    def test_rbac_and_tenant_isolation_guards(self) -> None:
        """Verify zero-trust RBAC and cross-tenant isolation on onboarding and scaling."""
        tenant_a = "tenant_iso_alpha_01"
        tenant_b = "tenant_iso_beta_02"
        self._created_tenants.extend([tenant_a, tenant_b])

        # Unauthenticated instant onboarding rejected
        unauth = self.client.post("/v1/tenants/onboard/instant", json={})
        self.assertEqual(unauth.status_code, 401)

        # Developer cannot trigger instant onboarding
        dev_tok = create_jwt_token(
            tenant_id=tenant_a, user_id="dev1", role=Role.DEVELOPER
        )
        forbidden_onboard = self.client.post(
            "/v1/tenants/onboard/instant",
            json={
                "contract_id": "ctr_unauth_01",
                "company_name": "Unauth Org",
                "tenant_id": tenant_a,
                "admin_email": "sec@unauth.io",
                "enduring_addendum_accepted": True,
                "cce_allocations": {
                    "initial_warps": 32,
                    "max_authorized_warps": 256,
                    "data_at_rest_gb": 1000,
                    "data_in_motion_gb": 1000,
                    "kms_provider": "AWS_KMS",
                    "kms_key_arn": "arn:aws:kms:us-east-1:111122223333:key/k1",
                },
            },
            headers={"Authorization": f"Bearer {dev_tok}"},
        )
        self.assertEqual(forbidden_onboard.status_code, 403)

        # Provision tenant_a and tenant_b via system_admin
        for idx, tid in enumerate((tenant_a, tenant_b)):
            r = self.client.post(
                "/v1/tenants/onboard/instant",
                json={
                    "contract_id": f"ctr_iso_{idx}",
                    "company_name": f"Iso Org {idx}",
                    "tenant_id": tid,
                    "admin_email": f"sec{idx}@iso.io",
                    "enduring_addendum_accepted": True,
                    "cce_allocations": {
                        "initial_warps": 32,
                        "max_authorized_warps": 512,
                        "data_at_rest_gb": 2000,
                        "data_in_motion_gb": 1000,
                        "kms_provider": "AZURE_KEY_VAULT",
                        "kms_key_arn": f"https://iso{idx}.vault.azure.net/keys/root",
                    },
                },
                headers={"Authorization": f"Bearer {self.sys_admin_token}"},
            )
            self.assertEqual(r.status_code, 201)

        # Tenant A admin cannot expand Tenant B capacity
        tenant_a_admin = create_jwt_token(
            tenant_id=tenant_a, user_id="admin_a", role=Role.TENANT_ADMIN
        )
        cross_res = self.client.patch(
            f"/v1/tenants/{tenant_b}/capacity",
            json={"requested_warp_capacity": 128, "reason": "CROSS_TENANT_ATTEMPT"},
            headers={"Authorization": f"Bearer {tenant_a_admin}"},
        )
        self.assertEqual(cross_res.status_code, 403)

        # Developer of Tenant A cannot expand Tenant A capacity
        dev_res = self.client.patch(
            f"/v1/tenants/{tenant_a}/capacity",
            json={"requested_warp_capacity": 128, "reason": "DEV_ESCALATION_ATTEMPT"},
            headers={"Authorization": f"Bearer {dev_tok}"},
        )
        self.assertEqual(dev_res.status_code, 403)

    def test_enduring_addendum_ceiling_and_conflict_checks(self) -> None:
        """Verify ECA ceiling enforcement, unaccepted ECA block, and duplicate conflict 409."""
        tenant_no_eca = "tenant_legacy_no_eca"
        self._created_tenants.append(tenant_no_eca)

        res = self.client.post(
            "/v1/tenants/onboard/instant",
            json={
                "contract_id": "ctr_legacy_009",
                "company_name": "Legacy Bank",
                "tenant_id": tenant_no_eca,
                "admin_email": "legal@legacybank.com",
                "enduring_addendum_accepted": False,
                "cce_allocations": {
                    "initial_warps": 32,
                    "max_authorized_warps": 128,
                    "data_at_rest_gb": 4000,
                    "data_in_motion_gb": 2000,
                    "kms_provider": "PKCS11_HSM",
                    "kms_key_arn": "pkcs11:token=legacy-hsm;object=root",
                },
            },
            headers={"Authorization": f"Bearer {self.sys_admin_token}"},
        )
        self.assertEqual(res.status_code, 201)
        admin_tok = res.json()["tenant_admin_token"]

        # Duplicate contract/tenant rejected with 409 Conflict
        dup = self.client.post(
            "/v1/tenants/onboard/instant",
            json={
                "contract_id": "ctr_legacy_009",
                "company_name": "Legacy Bank",
                "tenant_id": tenant_no_eca,
                "admin_email": "legal@legacybank.com",
                "enduring_addendum_accepted": False,
                "cce_allocations": {
                    "initial_warps": 32,
                    "max_authorized_warps": 128,
                    "data_at_rest_gb": 4000,
                    "data_in_motion_gb": 2000,
                    "kms_provider": "PKCS11_HSM",
                    "kms_key_arn": "pkcs11:token=legacy-hsm;object=root",
                },
            },
            headers={"Authorization": f"Bearer {self.sys_admin_token}"},
        )
        self.assertEqual(dup.status_code, 409)

        # Self-service scaling blocked when ECA was not accepted
        blocked = self.client.patch(
            f"/v1/tenants/{tenant_no_eca}/capacity",
            json={"requested_warp_capacity": 64, "reason": "NO_ECA_TEST"},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        self.assertEqual(blocked.status_code, 403)
        self.assertTrue(blocked.json()["detail"]["additional_approval_required"])

        # Seeded tenant exceeding max_authorized_warps is blocked
        default_admin = create_jwt_token(
            tenant_id="tenant-default",
            user_id="admin@chronus.io",
            role=Role.TENANT_ADMIN,
        )
        over_ceiling = self.client.patch(
            "/v1/tenants/tenant-default/capacity",
            json={"requested_warp_capacity": 9999, "reason": "OVER_AUTHORIZED_LIMIT"},
            headers={"Authorization": f"Bearer {default_admin}"},
        )
        self.assertEqual(over_ceiling.status_code, 403)

    def test_500_concurrent_tenant_activations_load_simulation(self) -> None:
        """Verify 500 concurrent tenant activations complete well under the 30-second T0 SLA."""
        res = self.client.post(
            "/v1/tenants/onboard/instant/load-test",
            json={
                "tenant_count": 500,
                "concurrency_workers": 32,
                "cleanup_ephemeral": True,
            },
            headers={"Authorization": f"Bearer {self.sys_admin_token}"},
        )
        self.assertEqual(res.status_code, 200, res.text)
        stats = res.json()
        self.assertEqual(stats["status"], "LOAD_SIMULATION_PASSED")
        self.assertEqual(stats["tenants_requested"], 500)
        self.assertEqual(stats["tenants_activated"], 500)
        self.assertEqual(stats["kms_custody_verified_count"], 500)
        self.assertEqual(stats["theseus_continuity_verified_count"], 500)
        self.assertTrue(stats["under_30_second_sla"])
        self.assertLess(stats["total_wall_time_ms"], 30000.0)


if __name__ == "__main__":
    unittest.main()
