"""Tests for McKinsey Framework: Three Actions CEOs Can Take to Get Value from Cloud Computing.

Validates the executive leadership interventions from Chhavi Arora, Tanguy Catlin,
Will Forrest, James Kaplan, and Lars Vinter (McKinsey Digital, July 21, 2020):
1. Establish a sustainable funding model (with the CFO)
2. Develop a new business-technology operating model (with the CIO/CTO and business leads)
3. Put in place HR, compensation, and location strategies (with the CHRO)
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from governance.agent_governance import AuditLedger
from governance.ceo_cloud_value import (
    BusinessUnitAccountabilityScorecard,
    CareerTrackType,
    CEOCloudActionType,
    CEOCloudValueOrchestrator,
    CloudOperatingModelEngine,
    CloudOperatingModelTier,
    CloudTalentStrategyEngine,
    CSuiteStakeholderRole,
    DoubleBubbleForecast,
    DualCareerTrackAppointment,
    FinOpsUnitEconomics,
    FundingModelType,
    LocationAndSourcingPolicy,
    PlatformAsAProductSpec,
    SpecializedCloudRoleProfile,
    SustainableFundingEngine,
    ValueDrivenFundingRequest,
)


@pytest.fixture
def temp_ledger():
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_path = Path(tmpdir) / "test_ceo_cloud_ledger.jsonl"
        yield AuditLedger(persistence_path=str(ledger_path))


class TestCEOCloudValueFramework:
    """Test suite covering the 3 CEO interventions and C-suite collective action."""

    def test_ceo_actions_and_csuite_roles(self):
        """Validates that all three CEO interventions and C-suite roles are defined."""
        actions = list(CEOCloudActionType)
        assert len(actions) == 3
        assert CEOCloudActionType.ACTION_1_SUSTAINABLE_FUNDING_MODEL in actions
        assert CEOCloudActionType.ACTION_2_BUSINESS_TECH_OPERATING_MODEL in actions
        assert CEOCloudActionType.ACTION_3_TALENT_COMPENSATION_LOCATION in actions

        roles = list(CSuiteStakeholderRole)
        assert len(roles) == 7
        assert CSuiteStakeholderRole.CEO in roles
        assert CSuiteStakeholderRole.CFO in roles
        assert CSuiteStakeholderRole.CIO in roles
        assert CSuiteStakeholderRole.CTO in roles
        assert CSuiteStakeholderRole.CHRO in roles
        assert CSuiteStakeholderRole.CISO in roles
        assert CSuiteStakeholderRole.BUSINESS_UNIT_LEAD in roles

    def test_action_1_double_bubble_trajectory_and_finops(self, temp_ledger):
        """Action 1: Sustainable funding model, double-bubble trajectory, and FinOps governance."""
        engine = SustainableFundingEngine(ledger=temp_ledger)

        # 1. Double Bubble Trajectory Modeling
        # Year 2 of 4: Legacy running ($50M) + Migration ($15M) + Cloud Run ($20M) - Decom savings ($5M) = $80M
        peak_forecast = engine.model_double_bubble_trajectory(
            legacy_annual_baseline=50_000_000.0,
            migration_duration_years=4,
            year_index=2,
            cloud_migration_investment=15_000_000.0,
            cloud_run_cost=20_000_000.0,
            decommissioned_savings=5_000_000.0,
        )
        assert peak_forecast.net_annual_expenditure == 80_000_000.0
        assert peak_forecast.double_bubble_premium_annual == 30_000_000.0
        assert peak_forecast.is_bubble_peaked is True
        assert peak_forecast.crossover_year_achieved is False

        # Year 4 of 4 (Crossover achieved): Legacy running ($10M) + Mig ($2M) + Cloud Run ($30M) - Decom savings ($45M) = $17M
        crossover_forecast = engine.model_double_bubble_trajectory(
            legacy_annual_baseline=50_000_000.0,
            migration_duration_years=4,
            year_index=4,
            cloud_migration_investment=2_000_000.0,
            cloud_run_cost=30_000_000.0,
            decommissioned_savings=45_000_000.0,
        )
        assert crossover_forecast.crossover_year_achieved is True
        assert crossover_forecast.net_annual_expenditure < 50_000_000.0

        # 2. FinOps Unit Economics & Bill Shock Detection
        healthy_finops = engine.evaluate_finops_governance(
            monthly_spend=1_200_000.0,
            monthly_active_users=600_000,
            monthly_transactions=3_000_000,
            tagging_pct=98.0,
            rightsizing_pct=92.0,
            savings_plan_pct=85.0,
            anomaly_spike_pct=4.0,
        )
        assert healthy_finops.cost_per_active_user_usd == 2.0
        assert healthy_finops.cost_per_business_transaction_usd == 0.40
        assert healthy_finops.bill_shock_anomaly_detected is False

        shock_finops = engine.evaluate_finops_governance(
            monthly_spend=2_500_000.0,
            monthly_active_users=600_000,
            monthly_transactions=3_000_000,
            tagging_pct=55.0,  # poor tagging
            rightsizing_pct=40.0,  # huge idle waste
            savings_plan_pct=20.0,
            anomaly_spike_pct=35.0,  # sudden 35% unbudgeted spike
        )
        assert shock_finops.bill_shock_anomaly_detected is True
        assert shock_finops.unallocated_waste_spend_usd > 500_000.0

        # 3. Value-Driven Funding Allocation
        req_approved = engine.allocate_value_driven_funding(
            domain="Retail Banking Digital Platform",
            initiative_name="Instant Account Opening API",
            requested_budget=2_000_000.0,
            projected_value=8_000_000.0,  # 4x ROI
            time_to_first_value_months=4.5,
        )
        assert req_approved.approval_status == "APPROVED"
        assert req_approved.projected_roi_multiple == 4.0

        req_rejected = engine.allocate_value_driven_funding(
            domain="Legacy Reporting",
            initiative_name="Lift-and-shift raw logs",
            requested_budget=1_500_000.0,
            projected_value=800_000.0,  # 0.53x ROI
            time_to_first_value_months=18.0,
        )
        assert req_rejected.approval_status == "REJECTED"

        # Verify audit ledger logging
        records = temp_ledger.get_records()
        assert len(records) >= 2
        assert any(r.action_type == "ALLOCATE_VALUE_DRIVEN_FUNDING" for r in records)

    def test_action_2_operating_model_and_bu_accountability(self, temp_ledger):
        """Action 2: Platform-as-a-product and Business-Unit accountability."""
        engine = CloudOperatingModelEngine(ledger=temp_ledger)

        # 1. Platform-as-a-Product Registration
        product = engine.register_platform_product(
            product_id="plt-secure-landing-zone",
            name="Enterprise Automated Cloud Landing Zone",
            description="Self-service ephemeral development environments with automated policy-as-code",
            target_users=["Product Developers", "Data Engineers"],
            self_service_api_available=True,
            provisioning_sla_seconds=90.0,
            built_in_security_guardrails=["OPA_COMPLIANCE", "ENCRYPT_AT_REST", "ZERO_TRUST_INGRESS"],
            active_consumers=145,
        )
        assert product.self_service_api_available is True
        assert product.provisioning_sla_seconds == 90.0
        assert len(product.built_in_security_guardrails) == 3

        # 2. Operating Model Tier Classification
        tier_elite = engine.determine_operating_model_tier(
            self_service_api_pct=92.0,
            automated_guardrails_pct=95.0,
            cross_functional_teams_pct=88.0,
            feature_release_cycle_days=2.0,
        )
        assert tier_elite == CloudOperatingModelTier.BIZDEVSECOPS_AUTONOMOUS_VALUE_STREAM

        tier_platform = engine.determine_operating_model_tier(
            self_service_api_pct=65.0,
            automated_guardrails_pct=75.0,
            cross_functional_teams_pct=50.0,
            feature_release_cycle_days=14.0,
        )
        assert tier_platform == CloudOperatingModelTier.PLATFORM_AS_A_PRODUCT

        tier_legacy = engine.determine_operating_model_tier(
            self_service_api_pct=10.0,
            automated_guardrails_pct=20.0,
            cross_functional_teams_pct=15.0,
            feature_release_cycle_days=90.0,
        )
        assert tier_legacy == CloudOperatingModelTier.CENTRAL_IT_TICKET_BASED

        # 3. Business Unit Accountability
        # BU that embraces cloud and redesigns customer journeys
        high_perf_bu = engine.evaluate_business_unit_accountability(
            bu_name="Global Commercial Payments",
            lead_name="Elena Rostova",
            cloud_adoption_pct=82.0,
            redesigned_processes_pct=70.0,
            lead_time_days=3.0,
            commercial_velocity_increase_pct=45.0,
            it_blaming_excuses_count=0,
        )
        assert high_perf_bu.is_accountability_met is True
        assert high_perf_bu.performance_verdict == "HIGH_PERFORMANCE_VALUE_CREATOR"

        # BU that drags feet and blames IT
        laggard_bu = engine.evaluate_business_unit_accountability(
            bu_name="Mortgage Origination",
            lead_name="Marcus Brody",
            cloud_adoption_pct=35.0,
            redesigned_processes_pct=15.0,
            lead_time_days=45.0,
            commercial_velocity_increase_pct=5.0,
            it_blaming_excuses_count=4,  # Deflecting blame to IT!
        )
        assert laggard_bu.is_accountability_met is False
        assert laggard_bu.performance_verdict == "DEFLECTING_TO_LEGACY_EXCUSES"

    def test_action_3_talent_compensation_and_location_strategy(self, temp_ledger):
        """Action 3: Overhauling HR salary caps, technical dual-track, and modern location policy."""
        engine = CloudTalentStrategyEngine(ledger=temp_ledger)

        # 1. Uncoupling Specialized Engineering Roles from Legacy IT Bands
        role = engine.uncouple_compensation_from_legacy_bands(
            role_id="role-cloud-arch-01",
            title="Principal Cloud Architect",
            legacy_salary_cap=145_000.0,
            market_competitive_salary=285_000.0,
        )
        assert role.uncoupled_from_legacy_bands is True
        assert role.salary_premium_unlocked_pct == 96.6

        # 2. Dual Career Track Technical Fellow Appointment
        fellow = engine.appoint_dual_career_track_fellow(
            employee_id="emp-fellow-09",
            name="Dr. Julian Vance",
            specialization_domain="High-Throughput Distributed Cloud Fabric",
            total_compensation=350_000.0,
            peer_level="Senior Vice President",
            equity_eligible=True,
        )
        assert fellow.career_track == CareerTrackType.DISTINGUISHED_ENGINEER_TECHNICAL_FELLOW
        assert fellow.management_duties_required is False
        assert fellow.peer_executive_equivalent_level == "Senior Vice President"

        # 3. Modernize Location & Sourcing Strategy
        policy = engine.modernize_location_strategy(
            innovation_hubs=["Seattle", "San Francisco", "Austin", "London", "Zurich"],
            distributed_remote_pct=100.0,
            average_time_to_hire_days=24.0,
            acceptance_rate_pct=88.5,
        )
        assert policy.legacy_low_cost_location_mandate_removed is True
        assert len(policy.innovation_hub_cities) == 5
        assert policy.talent_acceptance_rate_pct == 88.5

    def test_master_orchestrator_collective_action_alignment_and_audit(self, temp_ledger):
        """Master Orchestrator conducts full C-suite alignment check and cloud value audit."""
        orchestrator = CEOCloudValueOrchestrator(ledger=temp_ledger)

        # 1. C-Suite Collective Action Check: Full Alignment
        aligned_commitments = {
            CSuiteStakeholderRole.CEO: True,
            CSuiteStakeholderRole.CFO: True,
            CSuiteStakeholderRole.CIO: True,
            CSuiteStakeholderRole.CTO: True,
            CSuiteStakeholderRole.CHRO: True,
            CSuiteStakeholderRole.CISO: True,
            CSuiteStakeholderRole.BUSINESS_UNIT_LEAD: True,
        }
        alignment_result = orchestrator.verify_csuite_collective_action_alignment(aligned_commitments)
        assert alignment_result["collective_action_aligned"] is True
        assert alignment_result["air_cover_status"] == "FULL_AIR_COVER_ACTIVE"
        assert len(alignment_result["dissenting_or_unaligned_roles"]) == 0

        # Dissenting stakeholder check
        dissenting_commitments = dict(aligned_commitments)
        dissenting_commitments[CSuiteStakeholderRole.CFO] = False  # CFO balks at double bubble
        dissent_result = orchestrator.verify_csuite_collective_action_alignment(dissenting_commitments)
        assert dissent_result["collective_action_aligned"] is False
        assert dissent_result["air_cover_status"] == "COLLECTIVE_ACTION_FRICTION"
        assert CSuiteStakeholderRole.CFO.value in dissent_result["dissenting_or_unaligned_roles"]

        # 2. Comprehensive CEO Cloud Value Audit
        bu_scorecards = [
            BusinessUnitAccountabilityScorecard(
                business_unit_name="Digital Retail Wealth",
                business_unit_lead_name="Sarah Jenkins",
                cloud_adoption_pct=85.0,
                processes_digitally_redesigned_pct=75.0,
                deployment_lead_time_days=2.5,
                commercial_velocity_increase_pct=50.0,
                it_blaming_excuses_logged_count=0,
                is_accountability_met=True,
                performance_verdict="HIGH_PERFORMANCE_VALUE_CREATOR",
            )
        ]

        audit_report = orchestrator.execute_ceo_cloud_value_audit(
            csuite_commitments=aligned_commitments,
            legacy_annual_baseline=60_000_000.0,
            migration_duration_years=4,
            current_year_index=2,
            cloud_migration_investment=12_000_000.0,
            cloud_run_cost=18_000_000.0,
            decommissioned_savings=8_000_000.0,
            monthly_spend=1_500_000.0,
            monthly_active_users=800_000,
            monthly_transactions=4_000_000,
            tagging_compliance_pct=97.5,
            rightsizing_efficiency_pct=91.0,
            savings_plan_coverage_pct=82.0,
            self_service_api_pct=88.0,
            automated_guardrails_pct=92.0,
            cross_functional_teams_pct=85.0,
            feature_release_cycle_days=2.5,
            bu_scorecards=bu_scorecards,
            specialized_roles_uncoupled_count=5,
            dual_track_fellows_count=2,
            innovation_hubs=["Seattle", "Bay Area", "Austin"],
            distributed_remote_pct=90.0,
            time_to_hire_days=21.0,
            talent_acceptance_rate_pct=89.0,
        )

        overall = audit_report["overall_ceo_cloud_readiness"]
        assert overall["all_interventions_healthy"] is True
        assert "The CEO has successfully orchestrated the C-suite collective-action problem" in overall["executive_mandate_summary"]
        assert audit_report["action_2_operating_model"]["operating_model_tier"] == "BIZDEVSECOPS_AUTONOMOUS_VALUE_STREAM"

        # Verify cryptographic audit record
        records = temp_ledger.get_records()
        audit_events = [r for r in records if r.action_type == "EXECUTE_CEO_CLOUD_VALUE_AUDIT"]
        assert len(audit_events) == 1
        assert audit_events[0].status == "AUDIT_COMPLETED"
        assert "All actions healthy=True" in audit_events[0].rationale_summary
