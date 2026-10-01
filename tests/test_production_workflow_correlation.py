"""Controlled proof that one TOE frame survives plan, lease, and execution."""

from __future__ import annotations

import dataclasses
import time
import uuid

from manifold_pool_coordinator import StratumJob
from chronus.mla1517.mining.agentic_controller import AgenticMiningController
from chronus.mla1517.mining.causal import CausalCoordinate, CausalLedger
from chronus.mla1517.mining.execution_router import ExecutionRouter, sha256d_scan
from chronus.mla1517.mining.search_plan import PoolOutcome, SearchPlan, WorkIdentity
from chronus.mla1517.mining.toe_adapter import TOEMiningAdapter
from chronus.mla1517.mining.toe_decision import build_toe_decision_frame
from toe.bridge import TOEBridge


class _CpuHasher:
    backend = "cpu_reference"
    device = "python-hashlib"
    vendor = "python"
    grind_batch = 64
    launches = 0
    kernel_ms = 0.0


def _cpu_range(header, target, start, count):
    return sha256d_scan(header, target, range(start, start + count))


def _frame():
    job = StratumJob("job-trace", ("job-trace", "prev", "c1", "c2"), 1.0)
    context = TOEMiningAdapter(TOEBridge()).analyse(
        job=job,
        state=bytes(range(64)),
        node_id=7,
        sequence=19,
    )
    return build_toe_decision_frame(context)


def test_toe_frame_plan_lease_execution_correlation_is_immutable():
    frame = _frame()
    identity = WorkIdentity("session-trace", 1, "job-trace", "fingerprint-trace", 1, True, 1.0)
    agentic = AgenticMiningController(queue_depth=1, initial_lookahead=1)
    agentic.bind_work(identity)
    plan_id = f"plan:{uuid.uuid4()}"
    reserved = agentic.reserve_lease(plan_id, 64, lambda: "00000000")
    plan = SearchPlan(
        job_fingerprint=identity.job_fingerprint,
        pool_session_id=identity.pool_session_id,
        generation=identity.generation,
        base_step=reserved.start,
        window=64,
        extranonce2=reserved.extranonce2,
        lane_order=tuple(range(32)),
        preferred_face=0,
        dispatch_breadth=64,
        executor_route="cpu_reference",
        policy_id="controlled_trace",
        evidence_refs=dict(frame.evidence_refs()),
        created_at=time.monotonic(),
        plan_id=plan_id,
        toe_frame_id=frame.frame_digest,
    )
    assert agentic.submit_plan(plan)
    consumed = agentic.consume_plan()
    lease = agentic.begin_execution(consumed)
    record, candidate = ExecutionRouter(_CpuHasher(), _cpu_range).execute_plan(
        consumed,
        b"\x00" * 80,
        b"\xff" * 32,
        identity=identity,
        lease=reserved.contract(),
    )
    assert candidate is not None
    assert consumed.toe_frame_id == frame.frame_digest
    assert lease.lease_id == consumed.plan_id
    assert record.plan_id == consumed.plan_id
    assert record.toe_frame_id == frame.frame_digest
    assert record.executed_nonce_order == record.requested_nonce_order


def test_unknown_outcome_never_inherits_a_previous_learning_update():
    frame = _frame()
    identity = WorkIdentity("session", 1, "job", "fingerprint", 1, False, 1.0)
    agentic = AgenticMiningController(queue_depth=1, initial_lookahead=1)
    agentic.bind_work(identity)
    plan_id = "plan-learning"
    reserved = agentic.reserve_lease(plan_id, 32, lambda: "00000000")
    plan = SearchPlan(
        identity.job_fingerprint,
        identity.pool_session_id,
        identity.generation,
        reserved.start,
        32,
        reserved.extranonce2,
        tuple(range(32)),
        0,
        32,
        "cpu_reference",
        "policy",
        dict(frame.evidence_refs()),
        time.monotonic(),
        plan_id=plan_id,
        toe_frame_id=frame.frame_digest,
    )
    base = dict(
        plan_id=plan.plan_id,
        job_fingerprint=plan.job_fingerprint,
        policy_id=plan.policy_id,
        planned_window=32,
        actual_window=32,
        device_used="cpu_reference",
        hash_count=32,
        elapsed_seconds=0.01,
        kernel_ms=0.0,
        temperature_c=None,
        locally_valid_shares=1,
        pool_accepted=1,
        pool_rejected=0,
        pool_stale=0,
        recovery_event=False,
        lane_order=plan.lane_order,
        preferred_face=0,
        pool_outcome=PoolOutcome.ACCEPTED,
        toe_frame_id=frame.frame_digest,
    )
    from chronus.mla1517.mining.search_plan import ExecutionRecord

    accepted = ExecutionRecord(**base)
    agentic.record_outcome(accepted)
    assert agentic.telemetry.learning_update_applied
    unknown = dataclasses.replace(
        accepted,
        pool_outcome=PoolOutcome.OUTCOME_UNKNOWN,
        pool_accepted=0,
    )
    agentic.record_outcome(unknown)
    assert not agentic.telemetry.learning_update_applied


def test_causal_trace_resolves_toe_and_learning_axes():
    ledger = CausalLedger()
    coordinate = CausalCoordinate(
        pool_session_id="session",
        generation=2,
        job_fingerprint="fp",
        toe_frame_id="toe",
        plan_id="plan",
        lease_id="lease",
        execution_id="execution",
        learning_record_id="learning",
    )
    ledger.record("learning_observed", coordinate, applied=True)
    traced = ledger.trace(learning_record_id="learning")
    assert traced and traced[-1].coordinate.toe_frame_id == "toe"
    assert traced[-1].coordinate.execution_id == "execution"


def test_new_stratum_identity_clears_stale_toe_evidence():
    from types import SimpleNamespace

    from chronus.mla1517.mining.coordinator import IntelligentPoolCoordinator

    identity = WorkIdentity("session-new", 2, "job-new", "fp-new", 2, True, 2.0)
    wake = SimpleNamespace(set=lambda: None)
    events = []
    coordinator = IntelligentPoolCoordinator.__new__(IntelligentPoolCoordinator)
    coordinator._resolve_work_identity = lambda: (identity, None)
    coordinator.agentic = SimpleNamespace(bind_work=lambda _identity: True)
    coordinator.last_toe_context = object()
    coordinator.last_toe_frame = object()
    coordinator.last_toe_signal = object()
    coordinator._bound_session = None
    coordinator.world = SimpleNamespace(observe_bind=lambda *a, **k: None)
    coordinator.loss = SimpleNamespace(observe_bind=lambda *a, **k: None)
    coordinator.causal = SimpleNamespace(record=lambda *a, **k: events.append((a, k)))
    coordinator._precompute_wake = wake

    assert coordinator._refresh_work_identity() is identity
    assert coordinator.last_toe_context is None
    assert coordinator.last_toe_frame is None
    assert coordinator.last_toe_signal is None
    assert events and events[0][0][0] == "identity_bound"
