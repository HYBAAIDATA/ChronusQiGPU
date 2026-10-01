"""Shared fixtures for the agentic mining tests (not collected by pytest)."""

from __future__ import annotations

import time
import uuid

from chronus.mla1517.mining.agentic_controller import AgenticMiningController
from chronus.mla1517.mining.search_plan import ExecutionRecord, PoolOutcome, SearchPlan, WorkIdentity

LANE_ORDER = tuple(range(32))


def identity(
    generation: int = 1,
    *,
    fingerprint: str = "fp-a",
    session: str = "session-1",
    job_id: str = "job-a",
    clean_jobs: bool = False,
    target_generation: int = 1,
) -> WorkIdentity:
    return WorkIdentity(
        pool_session_id=session,
        generation=generation,
        job_id=job_id,
        job_fingerprint=fingerprint,
        target_generation=target_generation,
        clean_jobs=clean_jobs,
        received_at=1.0,
    )


class Extranonce2:
    """Monotonic allocator mirroring StratumProofAdapter.next_extranonce2."""

    def __init__(self, width: int = 8) -> None:
        self.width = width
        self.issued: list[str] = []

    def __call__(self) -> str:
        value = f"{len(self.issued):0{self.width}x}" if self.width else ""
        self.issued.append(value)
        return value


def make_plan(
    controller: AgenticMiningController,
    work: WorkIdentity,
    *,
    window: int = 320,
    policy: str = "flat_exhaustive",
    allocator: Extranonce2 | None = None,
    **overrides,
) -> SearchPlan:
    plan_id = str(uuid.uuid4())
    lease = controller.reserve_lease(plan_id, window, allocator or Extranonce2())
    fields = dict(
        job_fingerprint=work.job_fingerprint,
        pool_session_id=work.pool_session_id,
        generation=work.generation,
        base_step=lease.start,
        window=window,
        extranonce2=lease.extranonce2,
        lane_order=LANE_ORDER,
        preferred_face=0,
        dispatch_breadth=window,
        executor_route="cpu_reference",
        policy_id=policy,
        evidence_refs={},
        created_at=time.monotonic(),
        plan_id=plan_id,
    )
    fields.update(overrides)
    return SearchPlan(**fields)


def make_record(plan: SearchPlan, outcome: PoolOutcome = PoolOutcome.NO_CANDIDATE):
    candidate = outcome is not PoolOutcome.NO_CANDIDATE
    return ExecutionRecord(
        plan_id=plan.plan_id,
        job_fingerprint=plan.job_fingerprint,
        policy_id=plan.policy_id,
        planned_window=plan.window,
        actual_window=plan.window,
        device_used="cpu_reference",
        hash_count=plan.window,
        elapsed_seconds=0.01,
        kernel_ms=10.0,
        temperature_c=None,
        locally_valid_shares=int(candidate),
        pool_accepted=int(outcome is PoolOutcome.ACCEPTED),
        pool_rejected=int(outcome is PoolOutcome.REJECTED),
        pool_stale=0,
        recovery_event=False,
        lane_order=plan.lane_order,
        preferred_face=plan.preferred_face,
        pool_outcome=outcome,
        generation=plan.generation,
    )
