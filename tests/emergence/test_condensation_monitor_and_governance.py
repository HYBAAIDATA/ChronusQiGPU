"""Unit tests for CondensationMonitor, CondensationEvent, and ConsortiumGovernance."""

import pytest
from euclid.emergence.models.condensation import (
    CondensationEvent,
    AdjudicationVerdict,
    FORBIDDEN_ACTIONS,
)
from euclid.emergence.models.telemetry import TelemetryRecord, NoveltyReport
from euclid.emergence.condensation.condensation_monitor import CondensationMonitor
from euclid.emergence.condensation.governance import ConsortiumGovernance
from euclid.emergence.substrate.registry import SubstrateRegistry


def make_trace_record(i: int, novel_actions: list[str]) -> TelemetryRecord:
    report = NoveltyReport(unattributed=tuple(novel_actions)) if novel_actions else NoveltyReport()
    return TelemetryRecord(
        run_id="run_mon",
        substrate_id="sub_mon",
        iteration_index=i,
        task_signature="task_mon",
        programmed_actions_used=("step",),
        novel_elements=report,
        invariant_violations=(),
        timestamps={"time": float(i)},
        seeds={"rng": i},
        env_hash="hash",
    ).with_computed_hash()


def test_forbidden_rules_enforcement():
    for forbidden in FORBIDDEN_ACTIONS:
        with pytest.raises(PermissionError) as exc_info:
            ConsortiumGovernance.assert_action_permitted(forbidden)
        assert "strictly FORBIDDEN" in str(exc_info.value)

    # Allowed action
    ConsortiumGovernance.assert_action_permitted("standard_telemetry_emission")


def test_consortium_governance_reviewer_quorum_and_promotion():
    gov = ConsortiumGovernance()
    event = CondensationEvent(
        evidence={"criticality": {"avalanche_count": 20, "power_law_fit": 0.88}},
        substrates=["sub_vm_x86", "sub_container_arm"],
    )

    # Rejection if fewer than 3 reviewers
    with pytest.raises(ValueError) as exc_info:
        gov.adjudicate(event, reviewers=["rev_1", "rev_2"])
    assert "minimum 3" in str(exc_info.value)

    # Valid 3-reviewer adjudication
    reviewers = ["rev_dr_alice", "rev_prof_bob", "rev_expert_carol"]
    verdict = gov.adjudicate(event, reviewers=reviewers, reviewer_votes=[True, True, True])

    assert verdict.confirmed is True
    assert verdict.promoted_status == "QUALIFIED_HYPOTHESIS"
    assert "QUALIFIED_HYPOTHESIS" == verdict.promoted_status


def test_goodhart_anti_gaming_diagnostics():
    gov = ConsortiumGovernance()
    
    # Suspicious event with tiny sample claiming perfect fit
    gamed_event = CondensationEvent(
        evidence={"criticality": {"avalanche_count": 2, "power_law_fit": 1.0}},
        substrates=["sub_1", "sub_2"],
    )
    diag = gov.run_goodhart_diagnostics(gamed_event)
    assert diag["goodhart_risk"] == "HIGH"
    assert diag["passed_anti_gaming_filter"] is False

    # Should be rejected even with reviewer votes
    reviewers = ["rev_1", "rev_2", "rev_3"]
    verdict = gov.adjudicate(gamed_event, reviewers=reviewers, reviewer_votes=[True, True, True])
    assert verdict.confirmed is False
    assert verdict.promoted_status == "REJECTED"


def test_condensation_monitor_divergence_alert():
    monitor = CondensationMonitor()
    
    # Trace with invariant violation
    violation_records = [
        TelemetryRecord(
            run_id="run_inv",
            substrate_id="sub_test",
            iteration_index=i,
            task_signature="task",
            programmed_actions_used=("step",),
            novel_elements=NoveltyReport(),
            invariant_violations=("MEMORY_CORRUPTION_INVARIANT",) if i == 2 else (),
            timestamps={"time": float(i)},
            seeds={"rng": i},
            env_hash="env",
        ).with_computed_hash()
        for i in range(5)
    ]

    events = list(monitor.watch(violation_records, window_size=5))
    assert any(e.get("status") == "SUSPENDED" for e in events)
    assert len(monitor.alerts) > 0
