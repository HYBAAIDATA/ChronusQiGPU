"""Tests for McKinsey DevOps for IT Infrastructure Agility Framework.

Validates the six fundamental shifts and quantified benchmark targets from
Thomas Delaet & Ling Lau (McKinsey Digital):
- 25% to 30% increase in capacity creation
- 50% to 75% reduction in time to market (lead time)
- > 50% reduction in failure rates (change failure rate)
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from governance.agent_governance import AuditLedger
from governance.devops_infrastructure_agility import (
    CustomerJourneyMap,
    CultureChangeMetrics,
    DeveloperPersona,
    DevOpsBalancedScorecard,
    DevOpsBalancedScorecardEngine,
    DevOpsCultureGovernor,
    DevOpsInfrastructureAgilityOrchestrator,
    FundamentalShiftType,
    IaCDeploymentResult,
    InfraTalentBootcampManager,
    InfrastructureAsCodeSpec,
    InfrastructureComponentType,
    InfrastructureDesignThinkingEngine,
    InfrastructureOperatingModel,
    InfrastructureServiceTemplate,
    JourneyStep,
    NextGenInfrastructurePracticesEngine,
    TalentUpskillingProfile,
    UnifiedInfrastructureTeamEngine,
)


@pytest.fixture
def temp_ledger():
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_path = Path(tmpdir) / "test_devops_ledger.jsonl"
        yield AuditLedger(persistence_path=str(ledger_path))


class TestDevOpsInfrastructureAgility:
    """Test suite covering all six fundamental shifts and McKinsey benchmarks."""

    def test_fundamental_shift_enum_and_types(self):
        """Ensure all 6 fundamental shifts from Delaet & Lau are defined."""
        shifts = list(FundamentalShiftType)
        assert len(shifts) == 6
        assert FundamentalShiftType.WORK_AS_ONE_TEAM in shifts
        assert FundamentalShiftType.APPLY_DESIGN_THINKING in shifts
        assert FundamentalShiftType.SHIFT_TO_NEXTGEN_PRACTICES in shifts
        assert FundamentalShiftType.INVEST_IN_SOFTWARE_TALENT in shifts
        assert FundamentalShiftType.OVERINVEST_IN_CULTURE in shifts
        assert FundamentalShiftType.LINK_INCENTIVES_TO_GOALS in shifts

    def test_shift_1_work_as_one_team_self_service_api(self, temp_ledger):
        """Shift 1: Cross-functional units deliver full-stack infrastructure as self-service APIs."""
        engine = UnifiedInfrastructureTeamEngine(ledger=temp_ledger)

        # Baseline: legacy siloed plan-build-run
        assert engine.current_operating_model == InfrastructureOperatingModel.LEGACY_SILOED_PLAN_BUILD_RUN

        # Register unified full-stack template (eliminating compute/storage/network hand-offs)
        template = InfrastructureServiceTemplate(
            template_id="tpl-standard-microservice-env",
            name="Standard Secure Microservice Substrate",
            component_types=[
                InfrastructureComponentType.COMPUTE,
                InfrastructureComponentType.STORAGE,
                InfrastructureComponentType.NETWORK,
                InfrastructureComponentType.SECURITY_GATEWAY,
            ],
            version="1.0.0",
            owner_team="Platform Engineering Cross-Functional Unit Alpha",
            declarative_spec={
                "cluster": "k8s-prod-us-east",
                "storage_tier": "nvme-encrypted",
                "vpc_id": "vpc-secure-mesh",
                "ingress_tls": True,
            },
            sla_availability_target=99.99,
            compliance_checks=["PCI-DSS", "SOC2-Type-II"],
        )

        engine.register_service_template(template, registering_team="Platform Unit Alpha")

        retrieved = engine.get_template("tpl-standard-microservice-env")
        assert retrieved is not None
        assert retrieved.name == "Standard Secure Microservice Substrate"
        assert len(retrieved.component_types) == 4

        # Transition operating model to Cross-Functional DevOps API
        engine.transition_operating_model(
            new_model=InfrastructureOperatingModel.CROSS_FUNCTIONAL_DEVOPS_API,
            rationale="Eliminated ticket hand-offs across silos via unified self-service platform API.",
        )
        assert engine.current_operating_model == InfrastructureOperatingModel.CROSS_FUNCTIONAL_DEVOPS_API

        # Verify audit records were logged to cryptographic chain
        records = temp_ledger.get_records()
        assert len(records) >= 2
        assert any(r.action_type == "REGISTER_INFRASTRUCTURE_SERVICE_TEMPLATE" for r in records)
        assert any(r.action_type == "TRANSITION_OPERATING_MODEL" for r in records)

    def test_shift_2_apply_design_thinking_to_infrastructure(self):
        """Shift 2: Customer personas, provisioning journey mapping, friction score, and test-and-learn."""
        engine = InfrastructureDesignThinkingEngine()

        persona = DeveloperPersona(
            persona_id="persona-dev-01",
            role_title="Senior Backend Microservice Developer",
            key_tasks=["Provision staging DB", "Deploy service mesh", "Test API gateway"],
            pain_points=["Waiting 3 weeks for firewall changes", "Storage provisioning tickets"],
            delighters=["Single CLI command infrastructure spin-up", "Automated TLS cert issuance"],
        )

        steps = [
            JourneyStep(
                step_id="step-1",
                step_name="Submit Infrastructure Ticket",
                is_automated=False,
                manual_ticket_required=True,
                duration_minutes=4320.0,  # 72 hours
                friction_score=9.0,
            ),
            JourneyStep(
                step_id="step-2",
                step_name="Security & Network Review",
                is_automated=False,
                manual_ticket_required=True,
                duration_minutes=5760.0,  # 96 hours
                friction_score=8.5,
            ),
            JourneyStep(
                step_id="step-3",
                step_name="Automated API Deployment",
                is_automated=True,
                manual_ticket_required=False,
                duration_minutes=15.0,   # 15 minutes
                friction_score=1.5,
            ),
        ]

        journey = engine.map_provisioning_journey(
            journey_id="journey-staging-env",
            persona=persona,
            steps=steps,
        )

        assert journey.journey_id == "journey-staging-env"
        assert journey.total_duration_hours == 168.25
        assert journey.average_friction_score > 6.0
        assert journey.has_manual_bottleneck is True

        delighters = engine.generate_delighter_catalog()
        assert len(delighters) == 3
        assert any(d["delighter_id"] == "DELIGHT-01" for d in delighters)

    def test_shift_3_next_gen_technical_practices_iac_and_drift(self, temp_ledger):
        """Shift 3: Declarative IaC, automated policy checks, continuous delivery, and drift detection."""
        engine = NextGenInfrastructurePracticesEngine(ledger=temp_ledger)

        valid_spec = InfrastructureAsCodeSpec(
            spec_id="iac-vpc-east-01",
            environment="PROD",
            compute_units=16,
            memory_gb=64,
            storage_type="SSD_NVME",
            network_vpc_id="vpc-prod-mesh-01",
            ingress_allowed_ports=[443, 8443],  # Secure ports (no SSH port 22 in PROD)
            immutable_audit_logging=True,
            tags={"Owner": "PlatformEngineering", "CostCenter": "CC-9012"},
        )

        # Deploy spec through next-gen engine
        result = engine.deploy_infrastructure_as_code(spec=valid_spec)
        assert result.status == "PROVISIONED"
        assert result.compliance_passed is True
        assert result.spec_id == "iac-vpc-east-01"

        # Check drift detection: when live state matches, drift is False
        identical_live_spec = InfrastructureAsCodeSpec(
            spec_id="iac-vpc-east-01",
            environment="PROD",
            compute_units=16,
            memory_gb=64,
            storage_type="SSD_NVME",
            network_vpc_id="vpc-prod-mesh-01",
            ingress_allowed_ports=[443, 8443],
            immutable_audit_logging=True,
            tags={"Owner": "PlatformEngineering", "CostCenter": "CC-9012"},
        )
        assert engine.check_configuration_drift(result.deployment_id, identical_live_spec) is False

        # Simulate unauthorized out-of-band manual change (drift: open port 8080 added)
        drifted_live_spec = InfrastructureAsCodeSpec(
            spec_id="iac-vpc-east-01",
            environment="PROD",
            compute_units=16,
            memory_gb=64,
            storage_type="SSD_NVME",
            network_vpc_id="vpc-prod-mesh-01",
            ingress_allowed_ports=[443, 8443, 8080],  # Drift!
            immutable_audit_logging=True,
            tags={"Owner": "PlatformEngineering", "CostCenter": "CC-9012"},
        )
        assert engine.check_configuration_drift(result.deployment_id, drifted_live_spec) is True

        # Test policy-as-code rejection on non-compliant PROD spec with open SSH port 22
        non_compliant_spec = InfrastructureAsCodeSpec(
            spec_id="iac-insecure-prod",
            environment="PROD",
            compute_units=8,
            memory_gb=32,
            storage_type="SSD_NVME",
            network_vpc_id="vpc-prod-mesh-01",
            ingress_allowed_ports=[22, 443],  # Insecure SSH in PROD!
        )
        failed_result = engine.deploy_infrastructure_as_code(spec=non_compliant_spec)
        assert failed_result.status == "COMPLIANCE_FAILED"
        assert failed_result.compliance_passed is False

    def test_shift_4_invest_in_building_software_engineering_talent(self):
        """Shift 4: Transition sysadmins to software engineers via bootcamps and upskilling."""
        manager = InfraTalentBootcampManager()

        engineer = manager.enroll_employee(
            employee_id="emp-101",
            name="Alex Mercer",
            legacy_role="Legacy Unix System Administrator",
            target_role="Site Reliability Engineer",
        )
        assert engineer.employee_id == "emp-101"
        assert engineer.legacy_role == "Legacy Unix System Administrator"
        assert engineer.target_role == "Site Reliability Engineer"

        # Baseline readiness index before bootcamp
        initial_index = manager.get_talent_readiness_index()
        assert initial_index == 12.5  # (15 + 10) / 2

        # Complete immersive hands-on curriculum modules
        for mod in InfraTalentBootcampManager.CORE_BOOTCAMP_CURRICULUM:
            manager.complete_module(
                employee_id="emp-101",
                module_name=mod,
                proficiency_gain=18.0,
            )

        updated_profile = manager._profiles["emp-101"]
        assert len(updated_profile.bootcamp_modules_completed) == 5
        assert updated_profile.git_iac_proficiency_pct >= 90.0
        assert manager.get_talent_readiness_index() >= 90.0

    def test_shift_5_overinvest_in_culture_change(self):
        """Shift 5: Executive role modeling, DevOps coaches, journey teams, blameless culture."""
        governor = DevOpsCultureGovernor()

        # Poor culture scenario
        low_culture = governor.assess_culture(
            exec_modeling_score=30.0,
            devops_coaches=0,
            journey_service_teams=0,
            blameless_postmortems_pct=20.0,
        )
        assert low_culture.adoption_velocity_score < 40.0
        assert low_culture.status == "CULTURAL_HEADWINDS"

        # Transformed high-investment culture
        high_culture = governor.assess_culture(
            exec_modeling_score=95.0,
            devops_coaches=5,
            journey_service_teams=4,
            blameless_postmortems_pct=95.0,
        )
        assert high_culture.adoption_velocity_score >= 80.0
        assert high_culture.status == "HIGH_MOMENTUM"

    def test_shift_6_link_incentives_to_delivery_and_service_goals(self):
        """Shift 6: Balanced scorecard connecting DORA metrics, availability, quality, and eNPS."""
        engine = DevOpsBalancedScorecardEngine()

        scorecard = engine.calculate_scorecard(
            deployments_per_day=14.5,
            lead_time_hours=1.2,
            change_failure_rate_pct=2.5,
            mttr_minutes=15.0,
            baseline_capacity_hours=1000.0,
            actual_capacity_hours=1280.0,  # +28% capacity creation
            baseline_ttm_days=60.0,
            actual_ttm_days=18.0,          # -70% time to market
            baseline_failure_rate=0.22,
            actual_failure_rate=0.08,      # -63.6% failure rate
            availability_sla_pct=99.98,
            employee_enps=68.0,
        )

        assert scorecard.capacity_creation_increase_pct == 28.0
        assert scorecard.time_to_market_reduction_pct == 70.0
        assert scorecard.failure_rate_reduction_pct > 60.0
        assert scorecard.performance_tier == "ELITE_PERFORMER"
        assert scorecard.team_incentive_aligned is True

    def test_master_orchestrator_full_audit_and_mckinsey_benchmarks(self, temp_ledger):
        """Master Orchestrator verifies all 3 McKinsey benchmarks and end-to-end integration."""
        orchestrator = DevOpsInfrastructureAgilityOrchestrator(ledger=temp_ledger)

        # Enroll and train platform engineering staff
        orchestrator.talent_manager.enroll_employee(
            employee_id="emp-prod-01",
            name="Morgan Vance",
            legacy_role="Systems Administrator",
            target_role="Site Reliability Engineer",
        )
        for mod in InfraTalentBootcampManager.CORE_BOOTCAMP_CURRICULUM:
            orchestrator.talent_manager.complete_module(
                employee_id="emp-prod-01",
                module_name=mod,
                proficiency_gain=18.0,
            )

        steps = [
            JourneyStep(
                step_id="step-api-01",
                step_name="Declarative API Infrastructure Request",
                is_automated=True,
                manual_ticket_required=False,
                duration_minutes=2.0,
                friction_score=1.2,
            ),
            JourneyStep(
                step_id="step-policy-02",
                step_name="Automated Policy-as-Code Gate",
                is_automated=True,
                manual_ticket_required=False,
                duration_minutes=1.0,
                friction_score=1.0,
            ),
        ]

        # Run end-to-end audit with metrics reflecting high-performing DevOps transition
        audit_report = orchestrator.run_full_infrastructure_agility_audit(
            operating_model=InfrastructureOperatingModel.AUTONOMOUS_AGILE_PLATFORM,
            developer_steps=steps,
            deployments_per_day=20.0,
            lead_time_hours=0.5,
            change_failure_rate_pct=1.8,
            mttr_minutes=10.0,
            baseline_capacity_hours=1000.0,
            actual_capacity_hours=1290.0,  # 29% capacity increase (in 25-30% target)
            baseline_ttm_days=90.0,
            actual_ttm_days=25.0,          # 72.2% reduction (in 50-75% target)
            baseline_failure_rate=0.20,
            actual_failure_rate=0.07,      # 65% reduction (> 50% target)
            availability_sla_pct=99.99,
            employee_enps=72.0,
            exec_modeling_score=90.0,
            devops_coaches_count=5,
            journey_service_teams=4,
            blameless_postmortems_pct=92.0,
        )

        benchmarks = audit_report["mckinsey_benchmarks"]
        assert benchmarks["all_benchmarks_met"] is True
        assert "29.0%" in benchmarks["achieved_capacity_increase"]
        assert "72.2%" in benchmarks["achieved_ttm_reduction"]
        assert "65.0%" in benchmarks["achieved_failure_rate_reduction"]

        assert "IT Infrastructure has successfully cleared the agile bottleneck" in audit_report["executive_summary"]
        assert audit_report["operating_model"] == "AUTONOMOUS_AGILE_PLATFORM"

        # Verify cryptographic audit trail
        ledger_records = temp_ledger.get_records()
        audit_records = [r for r in ledger_records if r.action_type == "DEVOPS_INFRASTRUCTURE_AGILITY_AUDIT"]
        assert len(audit_records) == 1
        assert audit_records[0].status == "AUDIT_COMPLETED"
        assert "All McKinsey benchmarks met: True" in audit_records[0].rationale_summary
