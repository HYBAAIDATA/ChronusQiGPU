"""Fleet qualification test - stale and duplicate result prevention."""

from __future__ import annotations

from datetime import datetime

from chronus.fleet.custody import FleetCustody
from chronus.fleet.native_worker import ExecutionResult, NativeIGPUWorker
from chronus.fleet.scheduler import FleetScheduler
from chronus.fleet.worker_identity import WorkerIdentity
from chronus.igpu.host import HostGPUPlan


def test_no_duplicate_commit():
    """Stale and duplicate results cannot commit twice."""
    print("[TEST 4] Stale/duplicate prevention")
    scheduler = FleetScheduler({}, 30)
    custody = FleetCustody()

    items = list(range(4))

    # Set up worker
    wid = WorkerIdentity(worker_id="w1", generation=1, instance_id="t1", tenant="ta")
    worker = NativeIGPUWorker(
        wid,
        HostGPUPlan(total_items=4, lanes=2, mode="host_gpu_overlay"),
    )
    scheduler.register_worker(worker)
    lease = scheduler.issue_lease(
        work_id="dup1",
        tenant="ta",
        operation="op",
        input_data=items,
    )
    assert lease is not None
    r = worker.execute(lease.work_id, lambda x: x, items, lease=lease)
    worker.complete_lease(lease.lease_id, r)
    assert custody.verify_and_commit(r, "ta") is True

    # 4a: Duplicate with same digest (idempotent re-delivery)
    same_accept = custody.check_duplicate(r.work_id, r.output_digest)
    assert same_accept is True
    print(f"  4a) Same digest idempotent: {same_accept}")

    # 4b: Stale result with different digest
    stale = custody.check_stale(r.work_id, "a" * 64)
    assert stale is True
    print(f"  4b) Stale different digest: {stale}")

    # 4c: Commit stale - should be rejected
    stale_r = ExecutionResult(
        lease_id="",
        work_id="dup1",
        tenant="ta",
        operation="op",
        output_digest="a" * 64,
        partition=(0, 4),
        success=True,
        timestamp=datetime.now(),
    )
    stale_commit = custody.verify_and_commit(stale_r, "ta")
    assert stale_commit is False
    print(f"  4c) Stale commit blocked: {not stale_commit}")

    print("  [PASS] Duplicate/stale prevention demonstrated")
