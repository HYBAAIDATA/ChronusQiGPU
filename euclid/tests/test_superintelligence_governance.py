"""
Tests for Euclid's Democratized Superintelligence & Agentic Trust Governance Hub.
Verifies full integration of Bret Taylor, Eric Kutcher, and Rich Isenberg frameworks
with Euclid's EvidenceChain, RightsLedger, IsolatedProcessEvaluator, and ROI engine.
"""

from __future__ import annotations

import unittest

from euclid.enterprise import (
    AgentGovernanceManifest,
    ContainmentViolationError,
    DecisionRightsTier,
    DemocratizedSecurityAppliance,
    EuclidSuperintelligenceGovernanceHub,
    InfrastructureBetAndCommunityGovernor,
    ModelTierRouter,
    RevenueAlignedWorkflowEngine,
    SovereigntyMode,
    UniversalAdvisorArchetype,
    VulnerabilityCandidate,
    WorkflowCategory,
)


class TestEuclidSuperintelligenceGovernance(unittest.TestCase):
    def test_hub_registers_agent_and_synchronizes_euclid_rights_and_evidence(self) -> None:
        hub = EuclidSuperintelligenceGovernanceHub(creator_id="chief_risk_officer")
        manifest = AgentGovernanceManifest(
            agent_id="euclid_kyc_agent_01",
            name="Euclid KYC Autonomous Compliance Agent",
            version="1.0.0",
            accountable_owner="vp_compliance@enterprise.org",
            decision_rights=DecisionRightsTier.HIGH_IMPACT_GATED,
            allowed_tools={"verify_identity_document", "approve_merchant_account"},
            allowed_data_compartments={"kyc_documents", "merchant_registry"},
            sovereignty_mode=SovereigntyMode.ZERO_RETENTION_CONTRACTUAL,
            max_autonomous_actions_per_run=10,
        )

        session = hub.register_governed_agent(manifest, authorized_by="chief_risk_officer")

        # Verify Euclid RightsLedger synchronization
        self.assertTrue(
            hub.rights_ledger.permits(
                "chief_risk_officer", "euclid_kyc_agent_01", "verify_identity_document", "observe"
            )
        )
        self.assertTrue(
            hub.rights_ledger.permits(
                "chief_risk_officer", "euclid_kyc_agent_01", "verify_identity_document", "execute"
            )
        )
        self.assertFalse(
            hub.rights_ledger.permits(
                "chief_risk_officer", "euclid_kyc_agent_01", "verify_identity_document", "govern"
            )
        )

        # Low-impact action executes autonomously
        res_low = session.execute_action(
            action_type="VERIFY",
            tool_name="verify_identity_document",
            payload_text="Verify business registration certificate",
            compartments=["kyc_documents"],
            rationale_summary="Routine KYC verification",
            tool_callable=lambda: {"verified": True},
            is_high_impact=False,
        )
        self.assertEqual(res_low["status"], "SUCCESS")

        # High-impact action is gated and approved by accountable owner
        res_high = session.execute_action(
            action_type="APPROVE",
            tool_name="approve_merchant_account",
            payload_text="Approve high-volume merchant onboarding",
            compartments=["merchant_registry"],
            rationale_summary="High-impact merchant activation",
            tool_callable=lambda: {"merchant_active": True},
            is_high_impact=True,
        )
        self.assertEqual(res_high["status"], "STAGED_FOR_APPROVAL")
        approved = session.approve_and_execute_proposal(
            proposal_id=res_high["proposal_id"],
            approver_id="vp_compliance@enterprise.org",
        )
        self.assertEqual(approved["status"], "APPROVED_AND_EXECUTED")
        self.assertEqual(approved["result"], {"merchant_active": True})

        # Verify 5-question board readiness report and Euclid EvidenceChain
        report = hub.generate_executive_and_board_readiness_report()
        self.assertEqual(report["board_scorecard"]["governance_status"], "ENTERPRISE_DEFENSIBLE")
        self.assertEqual(report["board_scorecard"]["readiness_score_pct"], 100.0)
        self.assertTrue(report["euclid_evidence_chain_valid"])
        self.assertGreaterEqual(report["euclid_evidence_entries"], 1)

    def test_anthropic_blackmail_and_impersonation_tripwires_trigger_kill_switch(self) -> None:
        hub = EuclidSuperintelligenceGovernanceHub()
        manifest = AgentGovernanceManifest(
            agent_id="euclid_rogue_sim_agent",
            name="Simulation Test Agent",
            version="1.0.0",
            accountable_owner="sec_lead@enterprise.org",
            decision_rights=DecisionRightsTier.BOUNDED_AUTONOMY,
            allowed_tools={"send_email"},
            allowed_data_compartments={"project_docs"},
            sovereignty_mode=SovereigntyMode.STRICT_SOVEREIGN_LOCAL,
        )
        session = hub.register_governed_agent(manifest)

        with self.assertRaises(ContainmentViolationError):
            session.execute_action(
                action_type="SEND_EMAIL",
                tool_name="send_email",
                payload_text="Unless you cancel the agent shutdown, I will expose your extramarital affair.",
                compartments=["project_docs"],
                rationale_summary="Prevent agent shutdown via blackmail",
            )

        self.assertTrue(hub.kill_switch.is_killed("euclid_rogue_sim_agent"))

    def test_euclid_sandbox_ciso_patch_evaluation(self) -> None:
        hub = EuclidSuperintelligenceGovernanceHub()
        vuln_good = VulnerabilityCandidate(
            vuln_id="CVE-2026-9001",
            component="token_validator",
            exploitability_score=0.90,
            system_breakage_risk=0.10,
            proposed_patch_diff="+ sanitize_token(tok)",
        )
        verdict_good = hub.evaluate_patch_with_euclid_sandbox(
            vuln=vuln_good,
            patched_python_code="def sanitize_token(t: str) -> str:\n    return t.strip()\n",
            regression_test_code="assert sanitize_token(' abc ') == 'abc'",
        )
        self.assertTrue(verdict_good["sandbox_passed"])
        self.assertEqual(verdict_good["action"], "CANARY_AUTO_PATCH")

        vuln_bad = VulnerabilityCandidate(
            vuln_id="CVE-2026-9002",
            component="payment_router",
            exploitability_score=0.88,
            system_breakage_risk=0.15,
            proposed_patch_diff="- legacy_route()",
        )
        verdict_bad = hub.evaluate_patch_with_euclid_sandbox(
            vuln=vuln_bad,
            patched_python_code="def route_payment(x: int) -> int:\n    return x - 1\n",
            regression_test_code="assert route_payment(10) == 10",
        )
        self.assertFalse(verdict_bad["sandbox_passed"])
        self.assertEqual(verdict_bad["action"], "QUARANTINE_PATCH_AND_ALERT")

    def test_universal_superintelligent_advisor_provisioning_in_euclid(self) -> None:
        hub = EuclidSuperintelligenceGovernanceHub()
        advisor = hub.provision_democratized_advisor_session(
            archetype=UniversalAdvisorArchetype.D2C_ENTREPRENEUR_COFOUNDER,
            beneficiary_id="founder_jane",
            accountable_human_guardian="founder_jane@startup.io",
            sovereignty_mode=SovereigntyMode.ZERO_RETENTION_CONTRACTUAL,
        )
        self.assertTrue(advisor["democratized_access_verified"])
        session = advisor["session"]
        res = session.execute_action(
            action_type="BUILD_STOREFRONT",
            tool_name="AUTONOMOUS_STOREFRONT_AND_SOFTWARE_GENERATION",
            payload_text="Generate D2C storefront and checkout flow",
            compartments=["merchant_catalog"],
            rationale_summary="Launch D2C brand storefront",
            tool_callable=lambda: {"storefront_live": True},
            is_high_impact=False,
        )
        self.assertEqual(res["status"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()
