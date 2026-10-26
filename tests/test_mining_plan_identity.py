"""Configured order remains authoritative alongside planner advice and receipts."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from chronus.mla1517.mining.coordinator import IntelligentPoolCoordinator
from chronus.mla1517.mining.execution_router import (
    NONCE_ORDER_HENDRIX,
    NONCE_ORDER_M32,
    NONCE_ORDER_POINCARE_11D,
)
from chronus.mla1517.mining.search_plan import PlanSource, WorkIdentity


@pytest.fixture
def planning_context():
    identity = WorkIdentity("session-7", 7, "job-7", "a" * 64, 11, False, 1.0)
    lease = SimpleNamespace(start=96, count=96, extranonce2="00000007", lease_id="lease-7")
    coordinator = IntelligentPoolCoordinator.__new__(IntelligentPoolCoordinator)
    coordinator._nonce_order = NONCE_ORDER_HENDRIX
    coordinator._dispatch_breadth = 8
    coordinator._next_window = Mock(return_value=lease.count)
    coordinator._toe_advice_reason = Mock(return_value="fixture_advice")
    coordinator.production_integration = SimpleNamespace(
        plan_evidence=Mock(return_value={"status": "SOFTWARE_VERIFIED", "receipt": "fixture"})
    )
    coordinator.solver = SimpleNamespace(get_lane_start_offset=Mock(return_value=7))
    coordinator.last_toe_frame = SimpleNamespace(
        frame_digest="toe-frame-7",
        evidence_refs=Mock(return_value={"toe_frame_digest": "toe-frame-7"}),
    )
    coordinator.last_toe_signal = SimpleNamespace(face_bias=7)
    coordinator.last_mining_decision = SimpleNamespace(lead="fixture_policy")
    coordinator.tuning = SimpleNamespace(last_decision=SimpleNamespace(action="hold"))
    coordinator.client = SimpleNamespace(
        proof_adapter=SimpleNamespace(next_extranonce2=Mock(return_value=lease.extranonce2))
    )
    coordinator.agentic = SimpleNamespace(
        reserve_lease=Mock(return_value=lease), release_lease=Mock(), lookahead=3
    )
    return coordinator, identity, lease


@pytest.mark.parametrize("builder", ["_baseline_plan", "_build_plan"])
@pytest.mark.parametrize(
    "nonce_order", [NONCE_ORDER_HENDRIX, NONCE_ORDER_M32, NONCE_ORDER_POINCARE_11D]
)
@pytest.mark.parametrize("route", ["cpu_reference", "opencl_m32"])
def test_order_preserves_nonzero_lease_and_supporting_evidence(
    planning_context, builder, nonce_order, route
):
    coordinator, identity, lease = planning_context
    lanes = tuple(range(7, 32)) + tuple(range(7))
    advice = {"path_used": "solve", "complete_lane_coverage": True}
    coordinator._nonce_order = nonce_order
    coordinator._execution_route = Mock(return_value=route)
    coordinator._lane_order_for = Mock(return_value=(lanes, "pulvini_solve", advice))

    if builder == "_baseline_plan":
        plan = coordinator._baseline_plan(identity, lease, lease.count, "queue_empty")
        assert plan.source is PlanSource.BASELINE_FALLBACK
        assert plan.plan_id == lease.lease_id
        assert plan.policy_id == "baseline_fallback"
        assert plan.plan_fallback_reason == "queue_empty"
        coordinator.agentic.reserve_lease.assert_not_called()
    else:
        plan = coordinator._build_plan(identity)
        assert plan is not None
        assert plan.source is PlanSource.AGENTIC_PRECOMPUTED
        assert plan.policy_id == "fixture_policy"
        assert plan.plan_fallback_reason is None
        assert plan.evidence_refs["lookahead"] == 3
        assert plan.evidence_refs["tuning_action"] == "hold"
        assert plan.evidence_refs["toe_face_bias"] == 7
        assert plan.evidence_refs["window_basis"] == (
            "device_launch_lucas" if route == "opencl_m32" else "cpu_lucas_rung"
        )
        coordinator.agentic.reserve_lease.assert_called_once_with(
            plan.plan_id, lease.count, coordinator.client.proof_adapter.next_extranonce2
        )

    assert plan.nonce_order == nonce_order
    assert plan.executor_route == route
    assert plan.is_valid_for(identity)
    assert (plan.base_step, plan.window, plan.extranonce2) == (
        lease.start,
        lease.count,
        lease.extranonce2,
    )
    assert plan.lane_order == lanes
    assert plan.preferred_face == 7
    assert plan.dispatch_breadth == 8
    assert plan.toe_frame_id == "toe-frame-7"
    assert plan.evidence_refs["toe_frame_digest"] == "toe-frame-7"
    assert plan.evidence_refs["solve_first"] == advice
    assert plan.evidence_refs["lane_order_source"] == "pulvini_solve"
    assert plan.evidence_refs["toe_advice_reason"] == "fixture_advice"
    assert plan.evidence_refs["chronus107"] == {"status": "SOFTWARE_VERIFIED", "receipt": "fixture"}
    coordinator._lane_order_for.assert_called_once_with(lease.start, identity)
    coordinator.production_integration.plan_evidence.assert_called_once_with(96, 96)
    coordinator.agentic.release_lease.assert_not_called()


@pytest.mark.parametrize("builder", ["_baseline_plan", "_build_plan"])
def test_each_plan_captures_current_configuration_without_rewriting_previous_plan(
    planning_context, builder
):
    coordinator, identity, lease = planning_context
    coordinator._execution_route = Mock(return_value="cpu_reference")
    coordinator._lane_order_for = Mock(
        return_value=(tuple(range(32)), "solver", {"status": "UNAVAILABLE"})
    )

    def build():
        if builder == "_baseline_plan":
            return coordinator._baseline_plan(identity, lease, lease.count, "queue_empty")
        return coordinator._build_plan(identity)

    first = build()
    coordinator._nonce_order = NONCE_ORDER_POINCARE_11D
    second = build()

    assert first is not None and second is not None
    assert first.nonce_order == NONCE_ORDER_HENDRIX
    assert second.nonce_order == NONCE_ORDER_POINCARE_11D
    assert first.evidence_refs["solve_first"] == second.evidence_refs["solve_first"]
