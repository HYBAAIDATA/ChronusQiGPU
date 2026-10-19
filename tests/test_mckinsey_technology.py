"""Unit and integration test suite for McKinsey Technology Transformation Substrate."""

from __future__ import annotations

import pytest
from governance.mckinsey_technology import (
    AdoptionScalingCoordinator,
    BuildOrBuyRecommendation,
    BuildOrBuyVerdict,
    DataAITransformer,
    DataProductManifest,
    DigitalResilienceScore,
    DomainMaturityScore,
    EnterpriseArchitectureEngine,
    InfrastructureCloudOptimizer,
    McKinseyTechnologyTransformer,
    PilotEvaluation,
    PilotVerdict,
    TechDebtReport,
    TechResiliencyCybersecurityGovernor,
    TechTalentSourcingManager,
    TransformationAssessment,
    TransformationDomain,
    TransformationPillar,
)
from governance.agent_governance import (
    AgentGovernanceManifest,
    AgentInventoryRegistry,
    AuditLedger,
    DecisionRightsTier,
    MCPGateway,
    RollbackEngine,
    SovereigntyMode,
)


def test_transformation_pillars_and_domains():
    assert TransformationPillar.REIMAGINE_ROLE.value == "REIMAGINE_THE_ROLE_OF_TECHNOLOGY"
    assert TransformationPillar.REINVENT_DELIVERY.value == "REINVENT_TECHNOLOGY_DELIVERY"
    assert TransformationPillar.REWIRE_FOUNDATION.value == "REWIRE_THE_FOUNDATION"

    assert len(TransformationDomain) == 6
    assert TransformationDomain.INFRASTRUCTURE_CLOUD.value == "INFRASTRUCTURE_AND_CLOUD"
    assert TransformationDomain.DATA_AND_AI.value == "DATA_AND_AI"


def test_infrastructure_cloud_optimizer():
    optimizer = InfrastructureCloudOptimizer()

    eval_result = optimizer.evaluate_multi_cloud_optimization(
        cloud_providers=["AWS", "GCP", "Private_Cloud"],
        workload_portability_score=90.0,
        elastic_scaling_tested=True,
        monthly_spend_usd=100000.0,
        waste_reduction_opportunity_pct=25.0,
    )

    assert eval_result["has_multi_cloud_resilience"] is True
    assert eval_result["elastic_scaling_ready"] is True
    assert eval_result["efficiency_score"] >= 80.0
    assert eval_result["status"] == "OPTIMIZED"
    assert eval_result["estimated_annual_savings_usd"] == 300000.0


def test_enterprise_architecture_engine_tech_debt():
    engine = EnterpriseArchitectureEngine()

    debt = engine.audit_tech_debt(
        total_loc=150000,
        circular_dependencies=2,
        deprecated_routes=4,
        untested_critical_modules=1,
    )

    assert debt.circular_dependencies_count == 2
    assert debt.deprecated_api_count == 4
    assert debt.overall_debt_index > 0.0
    assert debt.estimated_remediation_weeks > 0.0
    assert len(debt.critical_refactoring_targets) == 3


def test_tech_resiliency_cybersecurity_governor():
    gov = TechResiliencyCybersecurityGovernor()

    # Highly resilient profile
    res_high = gov.measure_digital_resilience(
        rto_minutes=30.0,
        rpo_minutes=5.0,
        critical_assets_isolated_pct=95.0,
        chaos_tested=True,
        immutable_audit_active=True,
    )
    assert res_high.status == "HIGHLY_RESILIENT"
    assert res_high.resilience_score_pct >= 85.0

    # Deficit profile
    res_deficit = gov.measure_digital_resilience(
        rto_minutes=300.0,
        rpo_minutes=120.0,
        critical_assets_isolated_pct=20.0,
        chaos_tested=False,
        immutable_audit_active=False,
    )
    assert res_deficit.status in ("CRITICAL_DEFICIT", "ELEVATED_RISK")
    assert res_deficit.resilience_score_pct < 50.0


def test_build_or_buy_decision_framework():
    gov = TechResiliencyCybersecurityGovernor()

    # Core differentiator or sovereign mandated -> BUILD
    rec_build = gov.evaluate_build_or_buy(
        capability_name="Chronus Quantum Execution Plane",
        is_core_differentiator=True,
        estimated_internal_build_cost_usd=500000.0,
        commercial_vendor_annual_license_usd=100000.0,
        sovereignty_control_mandated=True,
    )
    assert rec_build.verdict == BuildOrBuyVerdict.BUILD_IN_HOUSE
    assert rec_build.sovereignty_risk == "ZERO"

    # Commodity capability -> BUY
    rec_buy = gov.evaluate_build_or_buy(
        capability_name="Standard Employee Expense Tracker",
        is_core_differentiator=False,
        estimated_internal_build_cost_usd=800000.0,
        commercial_vendor_annual_license_usd=30000.0,
        sovereignty_control_mandated=False,
    )
    assert rec_buy.verdict == BuildOrBuyVerdict.BUY_COMMERCIAL

    # Collaborative capability -> STRATEGIC PARTNERSHIP
    rec_partner = gov.evaluate_build_or_buy(
        capability_name="Cross-Border Regulatory Compliance Adapter",
        is_core_differentiator=False,
        estimated_internal_build_cost_usd=250000.0,
        commercial_vendor_annual_license_usd=80000.0,
        sovereignty_control_mandated=False,
    )
    assert rec_partner.verdict == BuildOrBuyVerdict.STRATEGIC_PARTNERSHIP


def test_adoption_scaling_pilot_governance():
    coord = AdoptionScalingCoordinator()

    # Successful 8-week pilot meeting criteria
    pilot_scale = coord.evaluate_pilot(
        pilot_id="pilot-01",
        name="Procurement Automated Invoice Triage",
        business_case="Accelerate invoice processing by 70%",
        duration_weeks=8,
        target_roi_multiplier=2.0,
        achieved_roi_multiplier=2.5,
        user_adoption_pct=85.0,
        safety_breaches_count=0,
    )
    assert pilot_scale.verdict == PilotVerdict.SCALE_TO_PRODUCTION

    # Pilot exceeding duration bounds (> 12 weeks)
    pilot_unbounded = coord.evaluate_pilot(
        pilot_id="pilot-02",
        name="Experimental Lab Bot",
        business_case="Exploratory reasoning",
        duration_weeks=16,
        target_roi_multiplier=1.5,
        achieved_roi_multiplier=1.6,
        user_adoption_pct=75.0,
        safety_breaches_count=0,
    )
    assert pilot_unbounded.verdict == PilotVerdict.ITERATE_HYPOTHESIS
    assert "violates 6-12 week" in pilot_unbounded.rationale

    # Pilot with safety breach -> DECOMMISSION
    pilot_breach = coord.evaluate_pilot(
        pilot_id="pilot-03",
        name="Rogue Customer Assistant",
        business_case="Automated ticketing",
        duration_weeks=6,
        target_roi_multiplier=2.0,
        achieved_roi_multiplier=2.1,
        user_adoption_pct=80.0,
        safety_breaches_count=1,
    )
    assert pilot_breach.verdict == PilotVerdict.DECOMMISSION


def test_tech_talent_sourcing_manager():
    mgr = TechTalentSourcingManager()

    readiness = mgr.evaluate_workforce_readiness(
        total_technical_headcount=500,
        ai_native_trained_pct=85.0,
        human_in_the_loop_governor_count=6,
        strategic_partner_count=4,
    )
    assert readiness["talent_readiness_score_pct"] >= 80.0
    assert readiness["status"] == "FUTURE_READY"


def test_data_ai_transformer():
    ledger = AuditLedger()
    data_ai = DataAITransformer(ledger)

    product = data_ai.register_data_product(
        product_id="dp-financial-telemetry",
        name="Real-Time Ledger Telemetry",
        domain="Financial_Operations",
        owner="finance-data-lead@enterprise.corp",
        freshness_slo_seconds=60.0,
        is_digital_twin_enabled=True,
        governance_classification="STRICT_SOVEREIGN",
    )

    assert product.is_digital_twin_enabled is True
    assert data_ai.get_data_product("dp-financial-telemetry") == product
    assert len(data_ai.list_data_products()) == 1

    # Verify audit trail
    records = ledger.get_records()
    assert len(records) == 1
    assert records[0].action_type == "REGISTER_DATA_PRODUCT"


def test_full_enterprise_transformation_assessment():
    registry = AgentInventoryRegistry()
    manifest = AgentGovernanceManifest(
        agent_id="enterprise-coordinator-01",
        name="Enterprise Coordinator",
        version="1.0.0",
        accountable_owner="chief-architect@enterprise.corp",
        decision_rights=DecisionRightsTier.BOUNDED_AUTONOMY,
        allowed_tools={"query_logs", "run_sandbox_scan"},
        allowed_data_compartments={"telemetry_logs", "public_assets"},
    )
    registry.register_agent(manifest, authorized_by="CTO")
    ledger = AuditLedger()
    gateway = MCPGateway(registry, ledger)
    rollback_engine = RollbackEngine(ledger)

    transformer = McKinseyTechnologyTransformer(
        registry=registry,
        gateway=gateway,
        ledger=ledger,
        rollback_engine=rollback_engine,
    )

    sample_pilot = AdoptionScalingCoordinator.evaluate_pilot(
        pilot_id="pilot-01",
        name="Cloud FinOps Autopilot",
        business_case="Reduce idle instances",
        duration_weeks=8,
        target_roi_multiplier=2.0,
        achieved_roi_multiplier=3.2,
        user_adoption_pct=90.0,
        safety_breaches_count=0,
    )

    assessment = transformer.run_full_enterprise_assessment(
        organization_name="Global Enterprise Inc.",
        cloud_providers=["AWS", "GCP"],
        workload_portability=85.0,
        monthly_cloud_spend_usd=250000.0,
        cloud_waste_pct=10.0,
        total_loc=250000,
        circular_dependencies=0,
        deprecated_routes=1,
        untested_critical_modules=0,
        rto_minutes=45.0,
        rpo_minutes=10.0,
        critical_assets_isolated_pct=90.0,
        chaos_tested=True,
        total_headcount=1200,
        ai_trained_pct=82.0,
        hitl_supervisors=10,
        strategic_partners=5,
        pilots=[sample_pilot],
    )

    assert assessment.organization_name == "Global Enterprise Inc."
    assert assessment.overall_maturity_score_pct >= 80.0
    assert len(assessment.pillar_scores) == 3
    assert len(assessment.domain_scores) == 6
    assert len(assessment.strategic_roadmap) == 3
    assert assessment.digital_resilience.status == "HIGHLY_RESILIENT"

    # Verify that the assessment itself was audited to the tamper-evident chain
    records = ledger.get_records()
    assert any(r.action_type == "ENTERPRISE_TRANSFORMATION_ASSESSMENT" for r in records)
