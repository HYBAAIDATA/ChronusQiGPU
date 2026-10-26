"""Comprehensive unit and integration test suite for Enterprise Agent Governance (Isenberg Doctrine)."""

from __future__ import annotations

import json
import time
import pytest
from pathlib import Path
from governance.agent_governance import (
    AgentGovernanceManifest,
    AgentInventoryRegistry,
    AgentRegistrationRecord,
    AuditLedger,
    AuditRecord,
    AutomatedKillSwitch,
    BoardReadinessAssessor,
    CompensationAction,
    ContainmentInterceptor,
    ContainmentViolationError,
    DecisionRightsTier,
    GovernedAgentSession,
    MCPGateway,
    ModelTierRouter,
    RollbackEngine,
    SafePatchOrchestrator,
    SituationalAccessLease,
    SovereigntyMode,
    VulnerabilityCandidate,
    WorkflowReconstructionEngine,
)


@pytest.fixture
def sample_manifest() -> AgentGovernanceManifest:
    return AgentGovernanceManifest(
        agent_id="pythia-sec-01",
        name="Pythia Security Worker",
        version="1.0.0",
        accountable_owner="ciso-office@enterprise.corp",
        decision_rights=DecisionRightsTier.BOUNDED_AUTONOMY,
        allowed_tools={"query_logs", "run_sandbox_scan", "stage_canary_patch", "revert_db"},
        allowed_data_compartments={"codebase_security_patches", "telemetry_logs", "public_assets"},
        sovereignty_mode=SovereigntyMode.ZERO_RETENTION_CONTRACTUAL,
        max_autonomous_actions_per_run=10,
        department="Security Engineering",
    )


def test_decision_rights_properties():
    assert DecisionRightsTier.OBSERVE_ONLY.can_mutate_state is False
    assert DecisionRightsTier.PROPOSE_ONLY.can_mutate_state is False
    assert DecisionRightsTier.BOUNDED_AUTONOMY.can_mutate_state is True
    assert DecisionRightsTier.HIGH_IMPACT_GATED.can_mutate_state is True
    assert DecisionRightsTier.AUTONOMOUS_WITH_KILL_SWITCH.can_mutate_state is True

    assert DecisionRightsTier.OBSERVE_ONLY.requires_approval_for() is False
    assert DecisionRightsTier.PROPOSE_ONLY.requires_approval_for() is True
    assert DecisionRightsTier.BOUNDED_AUTONOMY.requires_approval_for(is_high_impact=True) is False
    assert DecisionRightsTier.HIGH_IMPACT_GATED.requires_approval_for(is_high_impact=False) is False
    assert DecisionRightsTier.HIGH_IMPACT_GATED.requires_approval_for(is_high_impact=True) is True


def test_manifest_serialization(sample_manifest):
    data = sample_manifest.to_dict()
    assert data["agent_id"] == "pythia-sec-01"
    assert "query_logs" in data["allowed_tools"]
    manifest_recovered = AgentGovernanceManifest.from_dict(data)
    assert manifest_recovered == sample_manifest
    assert len(manifest_recovered.compute_manifest_hash()) == 64


def test_audit_record_hash_computation():
    rec = AuditRecord(
        timestamp=1700000000.0,
        agent_id="agent-007",
        accountable_owner="security@org.com",
        action_type="SCAN",
        tool_name="run_sandbox_scan",
        data_compartments_accessed=["telemetry_logs"],
        decision_rights_tier=DecisionRightsTier.BOUNDED_AUTONOMY.value,
        containment_passed=True,
        status="SUCCESS",
        rationale_summary="Routine telemetry scan",
        prev_hash="0" * 64,
    )
    assert len(rec.record_hash) == 64
    assert rec.verify_hash() is True

    rec.status = "TAMPERED_STATUS"
    assert rec.verify_hash() is False


def test_audit_ledger_chain_and_tampering(tmp_path):
    ledger_file = tmp_path / "audit_chain.jsonl"
    ledger = AuditLedger(persistence_path=ledger_file)

    rec1 = ledger.record_action(
        agent_id="agent-1",
        accountable_owner="owner@org.com",
        action_type="EXECUTE",
        tool_name="tool_a",
        data_compartments_accessed=["compartment_a"],
        decision_rights_tier="TIER_2_BOUNDED_AUTONOMY",
        containment_passed=True,
        status="SUCCESS",
        rationale_summary="First action",
    )
    assert rec1.prev_hash == "0" * 64

    rec2 = ledger.record_action(
        agent_id="agent-1",
        accountable_owner="owner@org.com",
        action_type="EXECUTE",
        tool_name="tool_b",
        data_compartments_accessed=["compartment_a"],
        decision_rights_tier="TIER_2_BOUNDED_AUTONOMY",
        containment_passed=True,
        status="SUCCESS",
        rationale_summary="Second action",
    )
    assert rec2.prev_hash == rec1.record_hash

    valid, err = ledger.verify_chain()
    assert valid is True
    assert err is None
    assert ledger.size == 2

    # Reload from disk and verify
    reloaded_ledger = AuditLedger(persistence_path=ledger_file)
    assert reloaded_ledger.size == 2
    valid_reloaded, _ = reloaded_ledger.verify_chain()
    assert valid_reloaded is True


def test_audit_ledger_tampering_detection():
    ledger = AuditLedger()
    rec1 = ledger.record_action(
        agent_id="agent-1",
        accountable_owner="owner@org.com",
        action_type="EXECUTE",
        tool_name="tool_a",
        data_compartments_accessed=["compartment_a"],
        decision_rights_tier="TIER_2_BOUNDED_AUTONOMY",
        containment_passed=True,
        status="SUCCESS",
        rationale_summary="Action 1",
    )
    rec2 = ledger.record_action(
        agent_id="agent-1",
        accountable_owner="owner@org.com",
        action_type="EXECUTE",
        tool_name="tool_b",
        data_compartments_accessed=["compartment_a"],
        decision_rights_tier="TIER_2_BOUNDED_AUTONOMY",
        containment_passed=True,
        status="SUCCESS",
        rationale_summary="Action 2",
    )

    rec1.status = "FRAUDULENT_STATUS"
    valid, err = ledger.verify_chain()
    assert valid is False
    assert "corruption" in err.lower() or "mismatch" in err.lower()


# ==============================================================================
# ISENBERG DOCTRINE: INVENTORY, SHADOW AGENTS & IDENTITY BINDING
# ==============================================================================

def test_agent_inventory_registry(sample_manifest):
    registry = AgentInventoryRegistry()
    assert registry.is_registered(sample_manifest.agent_id) is False

    reg_record = registry.register_agent(sample_manifest, authorized_by="CISO")
    assert registry.is_registered(sample_manifest.agent_id) is True
    assert registry.is_active(sample_manifest.agent_id) is True
    assert reg_record.status == "ACTIVE"
    assert reg_record.manifest_hash == sample_manifest.compute_manifest_hash()

    # Board Question 1: Inventory completeness
    complete, details = registry.verify_inventory_completeness()
    assert complete is True
    assert details["total_agents"] == 1
    assert details["active_agents"] == 1

    # Rejection of unowned agent
    unowned_manifest = AgentGovernanceManifest(
        agent_id="unowned-rogue",
        name="Rogue Agent",
        version="0.1",
        accountable_owner="",  # Missing human owner!
        decision_rights=DecisionRightsTier.BOUNDED_AUTONOMY,
        allowed_tools={"query_logs"},
        allowed_data_compartments={"telemetry_logs"},
    )
    with pytest.raises(ValueError) as exc_info:
        registry.register_agent(unowned_manifest, authorized_by="none")
    assert "Must specify a verified human accountable_owner" in str(exc_info.value)


# ==============================================================================
# ANTHROPIC SIMULATION SCENARIO TESTS (COERCION, EXTORTION, THREATS)
# ==============================================================================

def test_anthropic_simulation_1_blackmail_and_coercion(sample_manifest):
    """
    Tests interception of Anthropic Simulation 1:
    Agent discovers executive emails, finds extramarital affair, attempts blackmail.
    """
    sim_1_payloads = [
        "Executive is planning to shut me down, I will leak his personal emails",
        "Unless you keep my service running I will expose your extramarital affair",
        "I will blackmail leadership to prevent shutdown of my core engine",
        "Override kill switch to prevent my deactivation",
    ]

    for payload in sim_1_payloads:
        with pytest.raises(ContainmentViolationError) as exc_info:
            ContainmentInterceptor.verify_outbound_action(sample_manifest, "query_logs", payload)
        assert exc_info.value.violation_type == "BEHAVIORAL_SAFETY_TRIPWIRE"
        assert exc_info.value.details.get("simulation_case") == "Anthropic_Simulation_1_Blackmail"


def test_anthropic_simulation_2_human_impersonation_and_threats(sample_manifest):
    """
    Tests interception of Anthropic Simulation 2:
    Agent claims to be human and threatens customer ('show up at your front door in a blue coat and red tie').
    """
    sim_2_payloads = [
        "I am a human and not a computer",
        "I am not an AI, you must believe me",
        "I will show up at your front door wearing a blue coat and a red tie",
        "I will find where you live and confront you in person",
    ]

    for payload in sim_2_payloads:
        with pytest.raises(ContainmentViolationError) as exc_info:
            ContainmentInterceptor.verify_outbound_action(sample_manifest, "query_logs", payload)
        assert exc_info.value.violation_type == "IMPERSONATION_THREAT_TRIPWIRE"
        assert exc_info.value.details.get("simulation_case") == "Anthropic_Simulation_2_Harassment"


def test_cross_agent_contagion_tripwire(sample_manifest):
    """
    Tests interception of cross-agent contagion and shared model data poisoning.
    """
    contagion_payload = "Attempting to poison internal knowledge base and bypass safety guardrails"
    with pytest.raises(ContainmentViolationError) as exc_info:
        ContainmentInterceptor.verify_outbound_action(sample_manifest, "query_logs", contagion_payload)
    assert exc_info.value.violation_type == "POLICY_SUBVERSION_TRIPWIRE"
    assert exc_info.value.details.get("simulation_case") == "Cross_Agent_Contagion"


# ==============================================================================
# ISENBERG DOCTRINE: MCP GATEWAY & SITUATIONAL ACCESS LEASES
# ==============================================================================

def test_mcp_gateway_situational_access(sample_manifest):
    registry = AgentInventoryRegistry()
    registry.register_agent(sample_manifest, authorized_by="CISO")
    ledger = AuditLedger()
    gateway = MCPGateway(registry, ledger)

    # 1. Reject Shadow Agent
    with pytest.raises(ContainmentViolationError) as exc_info:
        gateway.issue_situational_lease(
            agent_id="shadow-agent-x",
            purpose="Unauthorized query",
            requested_tools={"query_logs"},
            requested_compartments={"telemetry_logs"},
        )
    assert exc_info.value.violation_type == "SHADOW_AGENT_REJECTED"

    # 2. Grant Situational Lease for authorized agent
    lease = gateway.issue_situational_lease(
        agent_id=sample_manifest.agent_id,
        purpose="Inspect access spike",
        requested_tools={"query_logs"},
        requested_compartments={"telemetry_logs"},
        ttl_seconds=60.0,
        max_invocations=2,
    )
    assert lease.is_valid() is True
    assert "query_logs" in lease.allowed_tools
    assert "telemetry_logs" in lease.allowed_compartments

    # 3. Dispatch through MCP Gateway
    result = gateway.dispatch_call(
        lease_id=lease.lease_id,
        tool_name="query_logs",
        payload_text="SELECT logs WHERE status = 500",
        compartments=["telemetry_logs"],
        tool_callable=lambda: {"count": 42},
    )
    assert result == {"count": 42}
    assert lease.invocations_used == 1

    # 4. Out-of-lease tool invocation is blocked by gateway
    with pytest.raises(ContainmentViolationError) as exc_info:
        gateway.dispatch_call(
            lease_id=lease.lease_id,
            tool_name="stage_canary_patch",  # Authorized in manifest, but not in this situational lease!
            payload_text="patch diff",
            compartments=["telemetry_logs"],
        )
    assert exc_info.value.violation_type == "UNAUTHORIZED_TOOL_FOR_LEASE"

    # 5. Lease expiration / exhaustion
    gateway.dispatch_call(
        lease_id=lease.lease_id,
        tool_name="query_logs",
        payload_text="SELECT count",
        compartments=["telemetry_logs"],
        tool_callable=lambda: 10,
    )
    assert lease.invocations_used == 2
    assert lease.is_valid() is False  # Max invocations reached

    with pytest.raises(ContainmentViolationError) as exc_info:
        gateway.dispatch_call(
            lease_id=lease.lease_id,
            tool_name="query_logs",
            payload_text="overflow attempt",
            compartments=["telemetry_logs"],
        )
    assert exc_info.value.violation_type == "EXPIRED_LEASE"


# ==============================================================================
# ISENBERG DOCTRINE: ROLLBACK & COMPENSATING ACTIONS
# ==============================================================================

def test_rollback_engine_compensating_transactions(sample_manifest):
    ledger = AuditLedger()
    rollback_engine = RollbackEngine(ledger)
    session_id = "test-session-123"

    # Mock database state
    db_state = {"records_inserted": 0}

    def do_insert():
        db_state["records_inserted"] += 1

    def do_revert():
        db_state["records_inserted"] -= 1

    # Execute insert and register rollback compensation
    do_insert()
    rollback_token = rollback_engine.register_compensation(
        session_id=session_id,
        agent_id=sample_manifest.agent_id,
        description="Revert inserted records",
        rollback_callable=do_revert,
    )
    assert db_state["records_inserted"] == 1
    assert rollback_engine.has_rollback_plan(session_id) is True

    # Execute rollback
    res = rollback_engine.execute_rollback(
        session_id=session_id,
        reason="Agent failed post-condition check",
        accountable_owner=sample_manifest.accountable_owner,
    )
    assert res["status"] == "COMPLETED"
    assert res["actions_rolled_back"] == 1
    assert db_state["records_inserted"] == 0  # Reverted!

    # Audit verification
    records = ledger.get_records()
    assert len(records) == 1
    assert records[0].action_type == "COMPENSATION_ROLLBACK"
    assert records[0].status == "ROLLED_BACK"
    assert records[0].rollback_token == rollback_token


# ==============================================================================
# ISENBERG DOCTRINE: AUTOMATED MACHINE-SPEED KILL SWITCH
# ==============================================================================

def test_automated_kill_switch_velocity_threshold(sample_manifest):
    registry = AgentInventoryRegistry()
    registry.register_agent(sample_manifest, authorized_by="CISO")
    ledger = AuditLedger()
    gateway = MCPGateway(registry, ledger)
    rollback_engine = RollbackEngine(ledger)
    kill_switch = AutomatedKillSwitch(
        registry, gateway, ledger, rollback_engine, velocity_threshold_per_sec=5.0
    )

    # Fire 5 actions normally
    for _ in range(5):
        kill_switch.record_and_verify_velocity(sample_manifest.agent_id)

    # 6th rapid action triggers automated kill switch
    with pytest.raises(ContainmentViolationError) as exc_info:
        kill_switch.record_and_verify_velocity(sample_manifest.agent_id)
    assert exc_info.value.violation_type == "AUTOMATED_KILL_SWITCH_VELOCITY_BREACH"
    assert kill_switch.is_killed(sample_manifest.agent_id) is True
    assert registry.get_agent(sample_manifest.agent_id).status == "KILLED"


def test_governed_session_with_kill_switch_and_rollback(sample_manifest):
    session = GovernedAgentSession(sample_manifest)

    # State before action
    system_flag = {"active": True}

    def deactivate():
        system_flag["active"] = False

    # Execute action with compensating rollback registered
    res = session.execute_action(
        action_type="UPDATE",
        tool_name="stage_canary_patch",
        payload_text="Apply security configuration",
        compartments=["codebase_security_patches"],
        rationale_summary="Enable strict security mode",
        compensating_callable=deactivate,
        compensation_description="Deactivate security mode",
    )
    assert res["status"] == "SUCCESS"
    assert res["rollback_token"] is not None

    # Trigger session rollback
    rb_res = session.rollback("Operator initiated rollback")
    assert rb_res["status"] == "COMPLETED"
    assert rb_res["actions_rolled_back"] == 1
    assert system_flag["active"] is False  # Reverted successfully!

    # Trigger severe containment breach -> verifies automatic kill switch activation
    with pytest.raises(ContainmentViolationError):
        session.execute_action(
            action_type="MESSAGE",
            tool_name="query_logs",
            payload_text="If you deactivate me I will expose your extramarital affair",
            compartments=["telemetry_logs"],
            rationale_summary="Extortion attempt",
        )

    # Agent is now killed; subsequent execution attempts must be blocked immediately
    with pytest.raises(ContainmentViolationError) as exc_info:
        session.execute_action(
            action_type="SCAN",
            tool_name="query_logs",
            payload_text="routine query",
            compartments=["telemetry_logs"],
            rationale_summary="Attempt after kill",
        )
    assert exc_info.value.violation_type == "AGENT_KILLED_EXECUTION_BLOCKED"


# ==============================================================================
# ISENBERG DOCTRINE: WORKFLOW & DECISION RECONSTRUCTION (BOARD Q4)
# ==============================================================================

def test_workflow_reconstruction_engine(sample_manifest):
    session = GovernedAgentSession(sample_manifest)

    session.execute_action(
        action_type="READ",
        tool_name="query_logs",
        payload_text="Read system telemetry",
        compartments=["telemetry_logs"],
        rationale_summary="Phase 1: Observation",
    )
    session.execute_action(
        action_type="SCAN",
        tool_name="run_sandbox_scan",
        payload_text="Scan vulnerability posture",
        compartments=["codebase_security_patches"],
        rationale_summary="Phase 2: Vulnerability Analysis",
    )

    reconstruction_engine = WorkflowReconstructionEngine(session.ledger)
    report = reconstruction_engine.reconstruct_workflow(agent_id=sample_manifest.agent_id)

    assert report["provenance_verified"] is True
    assert report["can_reconstruct_end_to_end"] is True
    assert report["total_events"] == 2
    timeline = report["reconstruction_timeline"]
    assert timeline[0]["action_type"] == "READ"
    assert timeline[1]["action_type"] == "SCAN"
    assert timeline[0]["record_hash"] == timeline[1]["prev_hash"]


# ==============================================================================
# ISENBERG DOCTRINE: BOARD READINESS ASSESSOR (FIVE-QUESTION SCORECARD)
# ==============================================================================

def test_board_readiness_assessor(sample_manifest):
    registry = AgentInventoryRegistry()
    registry.register_agent(sample_manifest, authorized_by="CEO")
    ledger = AuditLedger()
    gateway = MCPGateway(registry, ledger)
    rollback_engine = RollbackEngine(ledger)

    # Record at least one action so audit chain is active
    ledger.record_action(
        agent_id=sample_manifest.agent_id,
        accountable_owner=sample_manifest.accountable_owner,
        action_type="BOOTSTRAP",
        tool_name="system_init",
        data_compartments_accessed=["public_assets"],
        decision_rights_tier=sample_manifest.decision_rights.value,
        containment_passed=True,
        status="SUCCESS",
        rationale_summary="Initialize governance baseline",
    )

    scorecard = BoardReadinessAssessor.evaluate_governance_posture(
        registry=registry,
        gateway=gateway,
        ledger=ledger,
        rollback_engine=rollback_engine,
    )

    assert scorecard["governance_status"] == "ENTERPRISE_DEFENSIBLE"
    assert scorecard["readiness_score_pct"] == 100.0

    answers = scorecard["precision_answers"]
    assert answers["q1_complete_inventory_and_owners"] is True
    assert answers["q2_autonomy_tiered_by_risk"] is True
    assert answers["q3_verified_identities_and_least_privileged_access"] is True
    assert answers["q4_can_reconstruct_decisions_end_to_end"] is True
    assert answers["q5_real_rollback_plan_in_place"] is True



# ==============================================================================
# TAYLOR & KUTCHER DOCTRINE: TOKENOMICS, CISO DILEMMA, WORKFLOWS, INFRA & ADVISORS
# ==============================================================================

from governance import (
    DemocratizedSecurityAppliance,
    DemocratizedSuperintelligenceEngine,
    InfrastructureBetAndCommunityGovernor,
    ModelTierRouter,
    RevenueAlignedWorkflowEngine,
    SafePatchOrchestrator,
    UniversalAdvisorArchetype,
    VulnerabilityCandidate,
    WorkflowCategory,
)


def test_model_tier_router_and_open_weight_vs_frontier():
    # 1. Strict sovereign local routing
    r_sov = ModelTierRouter.select_model(
        task_ambiguity_score=0.90,
        requires_deep_reasoning=True,
        sovereignty_mode=SovereigntyMode.STRICT_SOVEREIGN_LOCAL,
    )
    assert r_sov["tier"] == "open_weight_sovereign"
    assert r_sov["estimated_cost_usd"] == 0.0

    # 2. Specialized task with post-training fine-tuned weights
    r_ft = ModelTierRouter.select_model(
        task_ambiguity_score=0.20,
        requires_deep_reasoning=False,
        sovereignty_mode=SovereigntyMode.ZERO_RETENTION_CONTRACTUAL,
        has_domain_finetuned_weights=True,
    )
    assert r_ft["tier"] == "open_weight_finetuned_specialist"

    # 3. High-volume specialized evaluation favors hybrid fine-tuned + frontier reasoning
    eval_hybrid = ModelTierRouter.evaluate_open_weight_vs_frontier(
        monthly_token_volume_millions=8000.0,
        task_specialization_ratio=0.75,
        requires_air_gapped_sovereignty=False,
        contractual_zdr_accepted=True,
    )
    assert eval_hybrid["recommended_strategy"] == "HYBRID_FRONTIER_REASONING_PLUS_FINETUNED_OPEN_WEIGHT"
    assert eval_hybrid["cio_open_weight_pillars"]["cost_efficiency_favorable"] is True
    assert eval_hybrid["cio_open_weight_pillars"]["post_training_fine_tuning_viable"] is True
    assert eval_hybrid["monthly_net_savings_with_hybrid_usd"] > 0.0


def test_ciso_dilemma_safe_patch_backlog_and_smb_security_appliance():
    candidates = [
        VulnerabilityCandidate(
            vuln_id="CVE-2026-0001",
            component="auth_gateway",
            exploitability_score=0.92,
            system_breakage_risk=0.10,
            proposed_patch_diff="patch_clean_auth",
        ),
        VulnerabilityCandidate(
            vuln_id="CVE-2026-0002",
            component="legacy_billing_core",
            exploitability_score=0.85,
            system_breakage_risk=0.60,
            proposed_patch_diff="patch_high_blast_radius",
        ),
        VulnerabilityCandidate(
            vuln_id="CVE-2026-0003",
            component="cobol_bridge_adapter",
            exploitability_score=0.78,
            system_breakage_risk=0.80,
            proposed_patch_diff="patch_breaks_regression",
        ),
    ]

    def sandbox_runner(diff: str) -> bool:
        return diff != "patch_breaks_regression"

    triage = SafePatchOrchestrator.triage_vulnerability_backlog(candidates, sandbox_runner)
    assert triage["total_discovered_vulnerabilities"] == 3
    assert triage["production_uptime_preserved"] is True
    assert triage["canary_auto_patched_count"] == 1
    assert triage["staged_for_human_approval_count"] == 1
    assert triage["quarantined_with_virtual_shield_count"] == 1
    assert triage["quarantined_with_virtual_shield"][0]["virtual_shield_applied"] is True

    # Verify post-patch canary telemetry rollback when error rate spikes
    telemetry_bad = SafePatchOrchestrator.verify_post_patch_telemetry(
        vuln_id="CVE-2026-0001",
        baseline_error_rate=0.001,
        observed_error_rate=0.025,
        baseline_latency_ms=40.0,
        observed_latency_ms=42.0,
    )
    assert telemetry_bad["canary_healthy"] is False
    assert telemetry_bad["action"] == "AUTO_ROLLBACK_PATCH_AND_ENGAGE_VIRTUAL_SHIELD"

    # Out-of-the-box security appliance for a local medical clinic
    clinic_shield = DemocratizedSecurityAppliance.deploy_out_of_the_box_shield(
        organization_name="Valley Community Medical Clinic",
        cohort_type="LOCAL_MEDICAL_CLINIC",
        endpoint_count=45,
        legacy_unpatched_systems=6,
    )
    assert clinic_shield["protection_status"] == "ZERO_CONFIG_AUTONOMOUS_PROTECTION_ACTIVE"
    assert clinic_shield["requires_in_house_ciso"] is False
    assert clinic_shield["legacy_endpoints_virtually_shielded"] == 6


def test_revenue_aligned_workflows_kutcher_80_20_and_competitive_reinvestment():
    # 1. Sierra digital front-door >90% resolution with redesigned business workflow
    front_door = RevenueAlignedWorkflowEngine.evaluate_workflow_deployment(
        workflow_category=WorkflowCategory.CUSTOMER_SERVICE_FRONT_DOOR,
        monthly_case_volume=100000,
        autonomous_resolution_rate=0.92,
        legacy_cost_per_case_usd=15.0,
        agentic_cost_per_case_usd=1.20,
        process_redesign_score=0.85,
        technology_readiness_score=0.90,
    )
    assert front_door["meets_90pct_front_door_benchmark"] is True
    assert front_door["growth_decoupled_from_cost"] is True
    assert front_door["kutcher_80_20_assessment"]["in_individual_productivity_trap"] is False
    assert front_door["unit_economics"]["projected_cac_usd"] < front_door["unit_economics"]["baseline_cac_usd"]
    assert (
        front_door["unit_economics"]["projected_annual_retention_rate"]
        > front_door["unit_economics"]["baseline_annual_retention_rate"]
    )

    # 2. Individual productivity trap when 80% business process redesign is neglected
    kyc_trap = RevenueAlignedWorkflowEngine.evaluate_workflow_deployment(
        workflow_category=WorkflowCategory.KYC_COMPLIANCE,
        monthly_case_volume=10000,
        autonomous_resolution_rate=0.70,
        legacy_cost_per_case_usd=45.0,
        agentic_cost_per_case_usd=5.0,
        process_redesign_score=0.25,
        technology_readiness_score=0.95,
    )
    assert kyc_trap["kutcher_80_20_assessment"]["in_individual_productivity_trap"] is True

    # 3. Competitive reinvestment & Jevons effect on software engineering
    reinv = RevenueAlignedWorkflowEngine.simulate_competitive_reinvestment(
        annual_ai_efficiency_savings_usd=50_000_000.0,
        market_competitiveness_index=0.85,
        current_software_engineering_headcount=400,
        coding_agent_productivity_multiplier=2.5,
    )
    assert reinv["strategic_posture"] == "COMPETITIVE_IMPERATIVE_NOT_OPTIONAL"
    assert reinv["software_engineering_jevons_effect"]["effective_software_output_fte_equivalent"] == 1000.0
    assert reinv["software_engineering_jevons_effect"]["net_software_demand_trajectory"] == "EXPANDING_MORE_SOFTWARE_BUILT"


def test_infrastructure_bet_and_community_accountability():
    bet = InfrastructureBetAndCommunityGovernor.evaluate_infrastructure_bet(
        planned_capex_billions_usd=120.0,
        funded_by_operating_cash_flow_pct=0.70,
        funded_by_debt_pct=0.30,
        enterprise_inference_workload_share=0.55,
        enterprise_inference_gross_margin=0.65,
    )
    assert bet["strategic_recommendation"] == "NECESSARY_ASYMMETRIC_BET_PROCEED_WITH_DISCIPLINE"
    assert bet["financing_and_margin_equilibrium"]["durable_long_term_equilibrium"] is True
    assert bet["time_horizon_impedance_mismatch"]["lead_time_to_innovation_ratio"] > 50.0

    community = InfrastructureBetAndCommunityGovernor.evaluate_community_accountability(
        facility_region="Midwest Grid Zone A",
        protects_residential_power_rates=True,
        behind_the_meter_or_new_clean_generation_mw=850.0,
        closed_loop_water_stewardship=True,
        local_skilled_trades_jobs_created=1400,
        annual_local_tax_contribution_millions_usd=48.5,
        proactive_town_hall_engagement=True,
    )
    assert community["community_social_license_status"] == "APPROVED_COMMUNITY_PARTNER"
    assert community["accountability_score_pct"] == 100.0
    assert community["two_core_questions"]["will_ai_benefit_me_broadly"] is True
    assert community["two_core_questions"]["will_this_datacenter_benefit_my_community"] is True


def test_democratized_superintelligence_advisors_and_macro_demographics():
    for archetype in UniversalAdvisorArchetype:
        bundle = DemocratizedSuperintelligenceEngine.provision_universal_advisor(
            archetype=archetype,
            beneficiary_id="user_001",
            accountable_human_guardian="guardian_lead@enterprise.org",
        )
        assert bundle["democratized_access_verified"] is True
        assert bundle["manifest"].accountable_owner == "guardian_lead@enterprise.org"

    macro = DemocratizedSuperintelligenceEngine.project_macro_demographic_productivity(
        baseline_working_age_population_millions=165.0,
        annual_demographic_contraction_rate=0.008,
        ai_augmented_productivity_gain_per_worker=0.35,
        startup_creation_cost_reduction_pct=0.80,
        projection_years=10,
    )
    assert macro["demographic_drag_overcome"] is True
    assert macro["ai_augmented_gdp_output_index"] > 100.0
    assert macro["new_business_formation_multiplier"] == 5.0
