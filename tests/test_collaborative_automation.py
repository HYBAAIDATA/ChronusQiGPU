"""tests/test_collaborative_automation.py — Verification suite for Collaborative Automation.

Covers:
1. Cross-team orchestration (DevOps, SRE, TechOps, Security, Architecture, Release, Stakeholder)
   and deterministic duplicate-effort prevention (CrossTeamTaskDeduplicator).
2. Automation tool selection (AI_ML, RPA, IT_AUTOMATION, IPAAS) and authority boundary
   enforcement (AI_ML must remain advisory_only=True).
3. Bathtub Effect risk guardrails (scope creep, technical challenges, lack of resources,
   loss of momentum) and incremental scaling limits.
4. Human-in-the-loop judgment checkpoints (pause on missing decision, role verification,
   rejection fail-closed, and signed approval completion).
5. All four canonical Collaborative Automation workflows (Cyber/IT DR, Cloud Migration,
   Application Release Management, Technology Implementation) and repository catalogue
   integration (runbooks/catalogue.json).
6. Postcondition failure and governed automatic rollback + Salamander RecoveryPlan bridge
   + tamper-evident hash-chained EvidenceLedger.
7. Single Pane of Glass dashboard, upstream/downstream dependency transparency, CLI,
   and control_api.py endpoint integration.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CANONICAL_PYTHON = _REPO_ROOT / "chronus" / "mla1517_platform" / "python"
for _p in (str(_REPO_ROOT), str(_CANONICAL_PYTHON)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from salamander import (
    AutomationToolCategory,
    BathtubGuard,
    BathtubRiskFactor,
    CollaborativeAutomationEngine,
    CollaborativeRunbook,
    CollaborativeStep,
    CrossTeamTaskDeduplicator,
    EvidenceLedger,
    HumanDecision,
    RunbookStatus,
    StepMode,
    StepStatus,
    TeamRole,
    ToolSelectionCriteria,
    WorkflowUseCase,
    build_canonical_workflow_runbooks,
    load_repository_catalogue_runbooks,
    select_automation_tool,
)
from salamander.control_plane import FailClosed
from tools.collaborative_automation import (
    catalogue_payload,
    full_runbook_catalogue,
    main as cli_main,
)


def _approve_all_human_steps(
    engine: CollaborativeAutomationEngine,
    runbook: CollaborativeRunbook,
    *,
    actor_id: str = "lead-operator-01",
    approved: bool = True,
) -> None:
    for idx, step in enumerate(runbook.ordered_steps(), start=1):
        if step.mode in (StepMode.HUMAN_IN_THE_LOOP, StepMode.COLLABORATIVE_HYBRID):
            role = (
                step.required_approver_roles[0]
                if step.required_approver_roles
                else step.owner_team
            )
            engine.record_human_decision(
                HumanDecision(
                    decision_id=f"test-dec-{runbook.runbook_id}-{idx}",
                    runbook_id=runbook.runbook_id,
                    step_id=step.step_id,
                    actor_id=actor_id,
                    team_role=role,
                    approved=approved,
                    rationale="Verified prerequisites, telemetry, and blast radius.",
                    at_ns=1_700_000_000_000_000_000 + idx,
                )
            )


@pytest.mark.unit
def test_tool_selection_and_ai_advisory_boundary() -> None:
    """AI_ML tool category is strictly advisory; non-advisory AI_ML fails closed."""
    ai_tool = select_automation_tool(
        "Predictive incident classification",
        requires_predictive_analytics=True,
    )
    assert ai_tool.tool_category is AutomationToolCategory.AI_ML
    assert ai_tool.advisory_only is True
    assert ai_tool.composite_score >= 4.0

    rpa_tool = select_automation_tool(
        "Rule-based lease drain",
        repetitive_rule_based=True,
    )
    assert rpa_tool.tool_category is AutomationToolCategory.RPA

    it_tool = select_automation_tool(
        "Provision Chronus fleet partitions",
        infrastructure_or_config=True,
    )
    assert it_tool.tool_category is AutomationToolCategory.IT_AUTOMATION

    ipaas_tool = select_automation_tool(
        "Exchange THESEUS custody receipts across systems",
        cross_system_data_exchange=True,
    )
    assert ipaas_tool.tool_category is AutomationToolCategory.IPAAS

    with pytest.raises(FailClosed, match="advisory_only=True"):
        ToolSelectionCriteria(
            tool_category=AutomationToolCategory.AI_ML,
            objective="Direct autonomous proof override",
            ease_of_use=5,
            scalability=5,
            integration_capability=5,
            verifier_support=5,
            human_collaboration_fit=5,
            advisory_only=False,
        ).validate()


@pytest.mark.unit
def test_cross_team_task_deduplication_prevents_silo_duplication() -> None:
    """Identical tasks across DevOps, SRE, and TechOps are deduplicated with audit provenance."""
    dedup = CrossTeamTaskDeduplicator()
    engine = CollaborativeAutomationEngine(deduplicator=dedup)

    step_devops = CollaborativeStep(
        step_id="s1_devops_verify",
        title="Verify signed container digest",
        owner_team=TeamRole.DEVOPS,
        collaborating_teams=(TeamRole.SRE,),
        tool_category=AutomationToolCategory.IT_AUTOMATION,
        mode=StepMode.AUTOMATED,
        operation="verify_signed_container_provenance",
        target="hyba-release-pipeline",
        parameters={"digest": "sha256:abc123"},
    )
    step_sre_duplicate = CollaborativeStep(
        step_id="s2_sre_duplicate_verify",
        title="SRE duplicate verification of same container digest",
        owner_team=TeamRole.SRE,
        collaborating_teams=(TeamRole.TECH_OPS,),
        tool_category=AutomationToolCategory.IT_AUTOMATION,
        mode=StepMode.AUTOMATED,
        operation="verify_signed_container_provenance",
        target="hyba-release-pipeline",
        depends_on=("s1_devops_verify",),
        parameters={"digest": "sha256:abc123"},
    )

    rb = CollaborativeRunbook(
        runbook_id="dedup_test_runbook",
        title="Cross-team deduplication test",
        use_case=WorkflowUseCase.APPLICATION_RELEASE_MANAGEMENT,
        tenant_id="tenant_a",
        target="hyba-release-pipeline",
        steps=(step_devops, step_sre_duplicate),
    )

    report = engine.execute_runbook(rb)
    assert report.status is RunbookStatus.COMPLETED_VERIFIED
    assert report.step_states["s1_devops_verify"] is StepStatus.VERIFIED
    assert report.step_states["s2_sre_duplicate_verify"] is StepStatus.DEDUPLICATED
    assert report.deduplicated_steps == ("s2_sre_duplicate_verify",)
    assert dedup.deduplicated_count == 1


@pytest.mark.unit
def test_bathtub_effect_guardrails_halt_uncontrolled_automation() -> None:
    """BathtubGuard detects scope creep, resource exhaustion, and momentum loss."""
    workflows = build_canonical_workflow_runbooks()
    dr = workflows["cyber_it_disaster_recovery"]

    # 1. Scope creep: unapproved mid-flight step injection
    engine_scope = CollaborativeAutomationEngine()
    injected = tuple(s.step_id for s in dr.ordered_steps()) + ("unapproved_extra_step",)
    report_scope = engine_scope.execute_runbook(dr, injected_step_ids=injected)
    assert report_scope.status is RunbookStatus.HALTED_BATHTUB_GUARD
    assert BathtubRiskFactor.SCOPE_CREEP in report_scope.bathtub_assessment.active_risks

    # 2. Scope creep: exceeding small incremental phase limit (phase 0 -> max 1 step)
    engine_small = CollaborativeAutomationEngine(
        bathtub_guard=BathtubGuard(scale_phase_index=0)
    )
    report_small = engine_small.execute_runbook(dr)
    assert report_small.status is RunbookStatus.HALTED_BATHTUB_GUARD
    assert BathtubRiskFactor.SCOPE_CREEP in report_small.bathtub_assessment.active_risks

    # 3. Lack of resources: 0 available operators for a human-in-the-loop runbook
    engine_res = CollaborativeAutomationEngine()
    report_res = engine_res.execute_runbook(dr, available_operators=0)
    assert report_res.status is RunbookStatus.HALTED_BATHTUB_GUARD
    assert BathtubRiskFactor.LACK_OF_RESOURCES in report_res.bathtub_assessment.active_risks

    # 4. Loss of momentum: longest_wait_ns exceeds stall_timeout_ns
    engine_stall = CollaborativeAutomationEngine(
        bathtub_guard=BathtubGuard(stall_timeout_ns=1_000)
    )
    report_stall = engine_stall.execute_runbook(dr, longest_wait_ns=5_000)
    assert report_stall.status is RunbookStatus.HALTED_BATHTUB_GUARD
    assert BathtubRiskFactor.LOSS_OF_MOMENTUM in report_stall.bathtub_assessment.active_risks


@pytest.mark.unit
def test_human_in_the_loop_pause_approval_and_rejection() -> None:
    """Runbooks pause at human checkpoints without fabricating approval, and resume on decision."""
    workflows = build_canonical_workflow_runbooks()
    dr = workflows["cyber_it_disaster_recovery"]
    engine = CollaborativeAutomationEngine()

    # Without human decisions: automated steps run, human checkpoint pauses at AWAITING_HUMAN
    paused_report = engine.execute_runbook(dr)
    assert paused_report.status is RunbookStatus.AWAITING_HUMAN
    assert paused_report.step_states["dr_01_detect_and_engage"] is StepStatus.VERIFIED
    assert paused_report.step_states["dr_02_quarantine_lanes"] is StepStatus.VERIFIED
    assert paused_report.step_states["dr_03_human_recovery_checkpoint"] is StepStatus.AWAITING_HUMAN_DECISION
    assert paused_report.step_states["dr_04_reanchor_witness_audit"] is StepStatus.BLOCKED_UPSTREAM

    # Provide human approvals for the checkpoints and re-execute
    _approve_all_human_steps(engine, dr, actor_id="sec-analyst-prime", approved=True)
    completed_report = engine.execute_runbook(dr)
    assert completed_report.status is RunbookStatus.COMPLETED_VERIFIED
    assert all(
        st in (StepStatus.VERIFIED, StepStatus.DEDUPLICATED)
        for st in completed_report.step_states.values()
    )
    assert engine.ledger.verify() is True

    # Rejection by human fails closed
    engine_reject = CollaborativeAutomationEngine()
    _approve_all_human_steps(engine_reject, dr, actor_id="sec-analyst-deny", approved=False)
    rejected_report = engine_reject.execute_runbook(dr)
    assert rejected_report.status is RunbookStatus.FAILED_CLOSED
    assert rejected_report.step_states["dr_03_human_recovery_checkpoint"] is StepStatus.REJECTED_BY_HUMAN


@pytest.mark.unit
def test_all_four_canonical_workflows_and_dependency_transparency() -> None:
    """All 4 canonical Collaborative Automation workflows execute and produce dependency maps."""
    workflows = build_canonical_workflow_runbooks()
    assert set(workflows) == {
        "cyber_it_disaster_recovery",
        "cloud_migration",
        "application_release_management",
        "technology_implementation",
    }

    engine = CollaborativeAutomationEngine()
    for rb_id, runbook in workflows.items():
        _approve_all_human_steps(engine, runbook, actor_id=f"approver-{rb_id}")
        report = engine.execute_runbook(runbook)
        assert report.status is RunbookStatus.COMPLETED_VERIFIED
        assert report.bathtub_assessment.healthy is True
        dep_map = report.dependency_transparency
        assert len(dep_map) == len(runbook.steps)
        assert all(node["upstream_satisfied"] is True for node in dep_map.values())

        # Verify conversion to Salamander RecoveryPlan
        recovery_plan = runbook.to_recovery_plan(
            actor_id=f"approver-{rb_id}",
            deadline_ns=9_999_999_999_999_999_999,
        )
        assert len(recovery_plan.ordered()) == len(runbook.steps)

    dashboard = engine.single_pane_dashboard(workflows.values())
    assert dashboard["summary"]["registered_workflows"] == 4
    assert dashboard["summary"]["completed_verified"] == 4
    assert dashboard["summary"]["awaiting_human_checkpoints"] == 0
    assert dashboard["audit_trail"]["chain_verified"] is True


@pytest.mark.unit
def test_postcondition_failure_triggers_governed_rollback() -> None:
    """Failed postcondition verification executes the declared rollback operation."""
    workflows = build_canonical_workflow_runbooks()
    release_rb = workflows["application_release_management"]
    engine = CollaborativeAutomationEngine()
    _approve_all_human_steps(engine, release_rb)

    report = engine.execute_runbook(
        release_rb,
        context={"fail_operations": {"deploy_canary_slice"}},
    )
    assert report.status is RunbookStatus.ROLLED_BACK
    assert report.step_states["rel_03_deploy_canary"] is StepStatus.ROLLED_BACK
    assert report.rolled_back_steps == ("rel_03_deploy_canary",)
    assert BathtubRiskFactor.TECHNICAL_CHALLENGES in report.bathtub_assessment.active_risks
    assert engine.ledger.verify() is True


@pytest.mark.unit
def test_repository_catalogue_integration_and_cli(capsys: pytest.CaptureFixture[str]) -> None:
    """runbooks/catalogue.json loads into CollaborativeRunbook objects and CLI executes cleanly."""
    repo_runbooks = load_repository_catalogue_runbooks()
    assert "key_rotation" in repo_runbooks
    assert "schema_migration" in repo_runbooks
    assert "witness_loss" in repo_runbooks
    assert len(repo_runbooks) >= 7

    all_rbs = full_runbook_catalogue()
    assert len(all_rbs) >= 11

    # CLI --catalogue
    rc_cat = cli_main(["--catalogue"])
    assert rc_cat == 0
    out_cat = json.loads(capsys.readouterr().out)
    assert out_cat["canonical_workflow_count"] == 4
    assert out_cat["repository_catalogue_count"] >= 7

    # CLI --run cyber_it_disaster_recovery --approve-all-human
    rc_run = cli_main(["--run", "cyber_it_disaster_recovery", "--approve-all-human"])
    assert rc_run == 0
    out_run = json.loads(capsys.readouterr().out)
    assert out_run["status"] == "COMPLETED_VERIFIED"

    # CLI --dashboard
    rc_dash = cli_main(["--dashboard"])
    assert rc_dash == 0
    out_dash = json.loads(capsys.readouterr().out)
    assert out_dash["schema"] == "hyba.collaborative.dashboard.v1"


@pytest.mark.unit
def test_control_api_collaborative_automation_endpoints() -> None:
    """control_api.py exposes collaborative automation status, runbooks, decisions, and execution."""
    import control_api

    status_doc = control_api.collaborative_automation_status_payload()
    assert status_doc["schema"] == "hyba.collaborative.dashboard.v1"
    assert status_doc["summary"]["registered_workflows"] >= 11

    cat_doc = control_api.collaborative_runbooks_payload()
    assert cat_doc["schema"] == "hyba.collaborative.catalogue.v1"
    assert "cyber_it_disaster_recovery" in cat_doc["canonical_workflows"]
    assert "key_rotation" in cat_doc["repository_catalogue_runbooks"]

    # Execute without human approvals -> AWAITING_HUMAN
    code_run1, payload_run1 = control_api._collaborative_runbook_execute(
        {"runbook_id": "technology_implementation"}
    )
    assert int(code_run1) == 200
    assert payload_run1["status"] == "AWAITING_HUMAN"

    # Record human approval via control_api handler
    code_dec, payload_dec = control_api._collaborative_human_decision(
        {
            "runbook_id": "technology_implementation",
            "step_id": "impl_04_stakeholder_handover",
            "actor_id": "stakeholder-01",
            "team_role": "stakeholder",
            "approved": True,
            "rationale": "Single-pane status verified and approved for handover.",
        }
    )
    assert int(code_dec) == 200
    assert payload_dec["ok"] is True

    # Re-execute after human approval -> COMPLETED_VERIFIED
    code_run2, payload_run2 = control_api._collaborative_runbook_execute(
        {"runbook_id": "technology_implementation"}
    )
    assert int(code_run2) == 200
    assert payload_run2["status"] == "COMPLETED_VERIFIED"
