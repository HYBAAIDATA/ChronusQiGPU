"""Tests for Technology Operations Guide to Collaborative Automation Framework.

Validates the Cutover Collaborative Automation model:
1. Interconnecting people and technology (System of Execution).
2. Mitigating the Bathtub Effect (complexity spikes and performance dips).
3. Addressing silo chaos across DevOps, SRE, and Tech Ops.
4. The Four Core Use Cases:
   - Cyber & IT Disaster Recovery
   - Cloud Migration
   - Application Release Management
   - Complex Technology Implementation
5. Single-pane-of-glass operational visibility and cryptographic audit trails.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from governance.agent_governance import AuditLedger
from governance.collaborative_automation import (
    ApplicationReleaseOrchestrator,
    AutomatedRunbook,
    AutomationToolCategory,
    AutomationUseCaseType,
    BathtubEffectMetrics,
    BathtubEffectRiskGovernor,
    BathtubRiskLevel,
    CloudMigrationOrchestrator,
    CollaborativeAutomationMasterSystem,
    CollaborativeRunbookExecutionEngine,
    DisasterRecoveryOrchestrator,
    OperationalVisibilityDashboard,
    RunbookTask,
    RunbookTaskType,
    TaskExecutionStatus,
    TechnologyImplementationOrchestrator,
)


@pytest.fixture
def temp_ledger():
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_path = Path(tmpdir) / "test_collab_auto_ledger.jsonl"
        yield AuditLedger(persistence_path=str(ledger_path))


class TestCollaborativeAutomationFramework:
    """Test suite covering the Collaborative Automation System of Execution."""

    def test_enums_and_task_types(self):
        """Validates all four use cases and task definitions."""
        use_cases = list(AutomationUseCaseType)
        assert len(use_cases) == 4
        assert AutomationUseCaseType.CYBER_AND_IT_DISASTER_RECOVERY in use_cases
        assert AutomationUseCaseType.CLOUD_MIGRATION in use_cases
        assert AutomationUseCaseType.APPLICATION_RELEASE_MANAGEMENT in use_cases
        assert AutomationUseCaseType.COMPLEX_TECHNOLOGY_IMPLEMENTATION in use_cases

        task_types = list(RunbookTaskType)
        assert len(task_types) == 4
        assert RunbookTaskType.AUTOMATED_TASK in task_types
        assert RunbookTaskType.HUMAN_IN_THE_LOOP in task_types
        assert RunbookTaskType.DECISION_GATE in task_types
        assert RunbookTaskType.COMMUNICATION_BROADCAST in task_types

        tools = list(AutomationToolCategory)
        assert len(tools) == 5
        assert AutomationToolCategory.AI_MACHINE_LEARNING in tools
        assert AutomationToolCategory.RPA in tools
        assert AutomationToolCategory.IT_AUTOMATION in tools
        assert AutomationToolCategory.IPAAS in tools
        assert AutomationToolCategory.COLLABORATIVE_RUNBOOK in tools

    def test_runbook_creation_and_topological_advance(self, temp_ledger):
        """Tests runbook creation, dependency linkage, and automated execution."""
        engine = CollaborativeRunbookExecutionEngine(ledger=temp_ledger)

        # Register mock automated handler
        engine.register_automated_handler(
            AutomationToolCategory.IT_AUTOMATION.value,
            lambda task: True,
        )

        rb = engine.create_runbook(
            runbook_id="rb_test_01",
            name="Test Automated Flow",
            use_case=AutomationUseCaseType.COMPLEX_TECHNOLOGY_IMPLEMENTATION,
        )

        task1 = RunbookTask(
            task_id="t1",
            name="Run Infrastructure Script",
            task_type=RunbookTaskType.AUTOMATED_TASK,
            tool_category=AutomationToolCategory.IT_AUTOMATION,
            assigned_owner="terraform_runner",
            estimated_duration_seconds=30.0,
        )
        task2 = RunbookTask(
            task_id="t2",
            name="Security Review Sign-Off",
            task_type=RunbookTaskType.HUMAN_IN_THE_LOOP,
            tool_category=AutomationToolCategory.COLLABORATIVE_RUNBOOK,
            assigned_owner="Security Engineer",
            dependencies=["t1"],
            estimated_duration_seconds=60.0,
        )

        engine.add_task(rb.runbook_id, task1)
        engine.add_task(rb.runbook_id, task2)

        assert rb.total_estimated_duration_seconds == 90.0
        assert "t1" in rb.critical_path_task_ids
        assert "t2" in rb.critical_path_task_ids

        # Start the runbook: task1 is automated and should complete immediately,
        # unlocking task2 which awaits human approval.
        engine.start_runbook(rb.runbook_id)

        assert task1.status == TaskExecutionStatus.COMPLETED
        assert task2.status == TaskExecutionStatus.AWAITING_HUMAN_APPROVAL

    def test_human_in_the_loop_approval_and_auditability(self, temp_ledger):
        """Tests recording human judgment and unlocking downstream execution."""
        engine = CollaborativeRunbookExecutionEngine(ledger=temp_ledger)
        engine.register_automated_handler(
            AutomationToolCategory.IT_AUTOMATION.value,
            lambda task: True,
        )

        rb = engine.create_runbook(
            runbook_id="rb_approval_flow",
            name="Human Approval Flow",
            use_case=AutomationUseCaseType.APPLICATION_RELEASE_MANAGEMENT,
        )

        task1 = RunbookTask(
            task_id="gate_1",
            name="Release Manager Go/No-Go Gate",
            task_type=RunbookTaskType.DECISION_GATE,
            tool_category=AutomationToolCategory.COLLABORATIVE_RUNBOOK,
            assigned_owner="Release Manager",
            estimated_duration_seconds=45.0,
        )
        task2 = RunbookTask(
            task_id="auto_deploy",
            name="Promote to Production Fleet",
            task_type=RunbookTaskType.AUTOMATED_TASK,
            tool_category=AutomationToolCategory.IT_AUTOMATION,
            assigned_owner="cicd_deployer",
            dependencies=["gate_1"],
            estimated_duration_seconds=120.0,
        )

        engine.add_task(rb.runbook_id, task1)
        engine.add_task(rb.runbook_id, task2)

        engine.start_runbook(rb.runbook_id)
        assert task1.status == TaskExecutionStatus.AWAITING_HUMAN_APPROVAL
        assert task2.status == TaskExecutionStatus.PENDING

        # Submit human approval
        decision_success = engine.submit_human_decision(
            runbook_id="rb_approval_flow",
            task_id="gate_1",
            approved=True,
            actor_name="Sarah Connor (Release VP)",
            judgment_notes="All automated test gates passed and error budget is 99.99%.",
        )
        assert decision_success is True
        assert task1.status == TaskExecutionStatus.COMPLETED
        assert task1.approval_actor == "Sarah Connor (Release VP)"
        # Task 2 was automatically unblocked and completed by the automated handler
        assert task2.status == TaskExecutionStatus.COMPLETED
        assert rb.status == "COMPLETED"

        # Check cryptographic audit trail
        records = temp_ledger.get_records()
        approval_records = [r for r in records if r.action_type == "RECORD_HUMAN_JUDGMENT"]
        assert len(approval_records) == 1
        assert approval_records[0].accountable_owner == "Sarah Connor (Release VP)"
        assert approval_records[0].status == "APPROVED"

    def test_operational_visibility_dashboard_single_pane_of_glass(self, temp_ledger):
        """Tests the real-time operational dashboard."""
        engine = CollaborativeRunbookExecutionEngine(ledger=temp_ledger)
        rb = engine.create_runbook(
            runbook_id="rb_dash",
            name="Dashboard Runbook",
            use_case=AutomationUseCaseType.CLOUD_MIGRATION,
        )

        engine.add_task(
            rb.runbook_id,
            RunbookTask(
                task_id="m1",
                name="Step 1 Human Check",
                task_type=RunbookTaskType.HUMAN_IN_THE_LOOP,
                tool_category=AutomationToolCategory.COLLABORATIVE_RUNBOOK,
                assigned_owner="Operator 1",
            ),
        )
        engine.start_runbook(rb.runbook_id)

        dashboard = engine.get_operational_dashboard(rb.runbook_id)
        assert dashboard.runbook_name == "Dashboard Runbook"
        assert dashboard.use_case == "CLOUD_MIGRATION"
        assert dashboard.human_tasks_pending_count == 1
        assert dashboard.overall_progress_pct == 0.0
        assert len(dashboard.live_telemetry_feed) == 1

    def test_bathtub_effect_risk_governor(self):
        """Tests the Bathtub Effect risk governor under stable and high-complexity conditions."""
        # 1. Stable condition (low risk)
        stable = BathtubEffectRiskGovernor.assess_runbook_risk(
            initial_task_count=10,
            current_task_count=11,
            failed_tasks_count=0,
            duration_variance_pct=5.0,
        )
        assert stable.risk_level == BathtubRiskLevel.LOW_STABLE
        assert stable.scope_creep_ratio == 1.1

        # 2. Bathtub complexity spike condition (high scope creep + unexpected failure rate)
        spike = BathtubEffectRiskGovernor.assess_runbook_risk(
            initial_task_count=10,
            current_task_count=18,  # +80% scope creep
            failed_tasks_count=4,   # 22.2% failure rate
            duration_variance_pct=45.0,
        )
        assert spike.risk_level == BathtubRiskLevel.HIGH_BATHTUB_COMPLEXITY_SPIKE
        assert spike.scope_creep_ratio == 1.8
        assert any("HALT SCOPE EXPANSION" in r for r in spike.mitigation_recommendations)
        assert any("INJECT HUMAN CHECKPOINTS" in r for r in spike.mitigation_recommendations)

    def test_use_case_1_disaster_recovery_orchestration(self, temp_ledger):
        """Tests Use Case 1: Cyber and IT Disaster Recovery."""
        engine = CollaborativeRunbookExecutionEngine(ledger=temp_ledger)
        engine.register_automated_handler(
            AutomationToolCategory.IT_AUTOMATION.value,
            lambda task: True,
        )

        dr_orchestrator = DisasterRecoveryOrchestrator(engine)
        rb = dr_orchestrator.build_disaster_recovery_runbook(
            incident_id="INC-RANSOMWARE-8092",
            target_datacenter_or_cloud="us-west-2-cloud-dr",
        )
        assert len(rb.tasks) == 4
        assert "dr_step_1" in rb.tasks  # Automated snapshot
        assert "dr_step_2" in rb.tasks  # Human security analyst
        assert "dr_step_3" in rb.tasks  # Automated DNS failover
        assert "dr_step_4" in rb.tasks  # Executive incident commander

        # Start failover
        engine.start_runbook(rb.runbook_id)
        assert rb.tasks["dr_step_1"].status == TaskExecutionStatus.COMPLETED
        assert rb.tasks["dr_step_2"].status == TaskExecutionStatus.AWAITING_HUMAN_APPROVAL

        # Security analyst reviews and clears the failover
        engine.submit_human_decision(
            rb.runbook_id,
            "dr_step_2",
            approved=True,
            actor_name="Alex Ward (Security Analyst)",
            judgment_notes="Clean snapshot verified; ransomware payload isolated.",
        )

        # dr_step_3 auto-executes, unlocking dr_step_4
        assert rb.tasks["dr_step_3"].status == TaskExecutionStatus.COMPLETED
        assert rb.tasks["dr_step_4"].status == TaskExecutionStatus.AWAITING_HUMAN_APPROVAL

        # Executive incident commander signs off
        engine.submit_human_decision(
            rb.runbook_id,
            "dr_step_4",
            approved=True,
            actor_name="Chief Operating Officer",
            judgment_notes="DR failover complete. Production live in us-west-2.",
        )
        assert rb.status == "COMPLETED"

    def test_use_case_2_cloud_migration_orchestration(self, temp_ledger):
        """Tests Use Case 2: Cloud Migration."""
        engine = CollaborativeRunbookExecutionEngine(ledger=temp_ledger)
        engine.register_automated_handler(AutomationToolCategory.IT_AUTOMATION.value, lambda t: True)
        engine.register_automated_handler(AutomationToolCategory.IPAAS.value, lambda t: True)

        mig_orchestrator = CloudMigrationOrchestrator(engine)
        rb = mig_orchestrator.build_cloud_migration_runbook(
            application_name="Core Ledgers",
            source_environment="On-Prem Datacenter A",
            target_cloud="AWS us-east-1",
        )
        assert len(rb.tasks) == 4
        engine.start_runbook(rb.runbook_id)

        # Provisioning and data sync auto-complete
        assert rb.tasks["mig_step_1"].status == TaskExecutionStatus.COMPLETED
        assert rb.tasks["mig_step_2"].status == TaskExecutionStatus.COMPLETED
        # DBA decision gate waits for approval
        assert rb.tasks["mig_step_3"].status == TaskExecutionStatus.AWAITING_HUMAN_APPROVAL

        engine.submit_human_decision(
            rb.runbook_id,
            "mig_step_3",
            approved=True,
            actor_name="Elena Vance (DBA Lead)",
            judgment_notes="Zero replication lag confirmed.",
        )
        assert rb.tasks["mig_step_4"].status == TaskExecutionStatus.COMPLETED
        assert rb.status == "COMPLETED"

    def test_use_case_3_release_management_orchestration(self, temp_ledger):
        """Tests Use Case 3: Application Release Management."""
        engine = CollaborativeRunbookExecutionEngine(ledger=temp_ledger)
        engine.register_automated_handler(AutomationToolCategory.IT_AUTOMATION.value, lambda t: True)

        rel_orchestrator = ApplicationReleaseOrchestrator(engine)
        rb = rel_orchestrator.build_release_runbook(
            service_name="payment-processor",
            release_version="3.4.1",
        )
        assert len(rb.tasks) == 3
        engine.start_runbook(rb.runbook_id)

        assert rb.tasks["rel_step_1"].status == TaskExecutionStatus.COMPLETED
        assert rb.tasks["rel_step_2"].status == TaskExecutionStatus.AWAITING_HUMAN_APPROVAL

        engine.submit_human_decision(
            rb.runbook_id,
            "rel_step_2",
            approved=True,
            actor_name="DevOps Release Lead",
            judgment_notes="Canary metrics show 0% error rate.",
        )
        assert rb.tasks["rel_step_3"].status == TaskExecutionStatus.COMPLETED
        assert rb.status == "COMPLETED"

    def test_use_case_4_complex_technology_implementation(self, temp_ledger):
        """Tests Use Case 4: Complex Technology Implementation."""
        engine = CollaborativeRunbookExecutionEngine(ledger=temp_ledger)
        engine.register_automated_handler(AutomationToolCategory.IT_AUTOMATION.value, lambda t: True)

        impl_orchestrator = TechnologyImplementationOrchestrator(engine)
        components = ["Kafka Cluster", "Redis Substrate", "Service Mesh Gateway"]
        rb = impl_orchestrator.build_implementation_runbook(
            project_name="Streaming Core",
            system_components=components,
        )
        assert len(rb.tasks) == 4  # 3 component steps + 1 chief architect signoff
        engine.start_runbook(rb.runbook_id)

        # First 3 automated steps chain-complete
        assert rb.tasks["impl_step_1"].status == TaskExecutionStatus.COMPLETED
        assert rb.tasks["impl_step_2"].status == TaskExecutionStatus.COMPLETED
        assert rb.tasks["impl_step_3"].status == TaskExecutionStatus.COMPLETED
        assert rb.tasks["impl_final_signoff"].status == TaskExecutionStatus.AWAITING_HUMAN_APPROVAL

        engine.submit_human_decision(
            rb.runbook_id,
            "impl_final_signoff",
            approved=True,
            actor_name="Chief Architect",
            judgment_notes="All components online and peer-reviewed.",
        )
        assert rb.status == "COMPLETED"

    def test_master_system_collaborative_assessment(self, temp_ledger):
        """Tests master system holistic evaluation and immutable audit logging."""
        system = CollaborativeAutomationMasterSystem(ledger=temp_ledger)

        # Evaluate healthy collaborative automation (symbiotic balance: ~16.7% human judgment)
        report = system.run_collaborative_automation_assessment(
            active_runbooks_count=12,
            human_judgment_interventions_count=20,
            automated_actions_count=100,
            bathtub_scope_creep_ratio=1.1,
            bathtub_failure_rate_pct=3.0,
        )

        assert report["is_symbiotic_collaboration"] is True
        assert report["human_in_the_loop_ratio_pct"] == 16.7
        assert report["bathtub_effect_assessment"]["risk_level"] == "LOW_STABLE"
        assert "healthy symbiotic state" in report["executive_summary"]

        # Verify audit records logged to ledger
        records = temp_ledger.get_records()
        assert len(records) >= 1
        eval_record = next(r for r in records if r.action_type == "COLLABORATIVE_AUTOMATION_ASSESSMENT")
        assert eval_record.status == "ASSESSMENT_COMPLETED"
        assert "Human involvement ratio=16.7%" in eval_record.rationale_summary
