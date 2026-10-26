"""Core fleet qualification - test agreement of single vs distributed execution."""
from __future__ import annotations

from chronus.fleet.custody import FleetCustody
from chronus.fleet.native_worker import NativeIGPUWorker
from chronus.fleet.scheduler import FleetScheduler
from chronus.fleet.worker_identity import WorkerIdentity
from chronus.igpu.host import HostGPUPlan, execute_reference


def test_results_agree():
    """Single-instance and distributed results agree."""
    print("[TEST 1] Results agreement")
    plan = HostGPUPlan(total_items=4, lanes=2, mode="host_gpu_overlay")

    def k(x):
        return x * 2

    items = list(range(4))
    single = execute_reference(items, plan, k)
    print(f"  Single result: {single}")

    # Distribute via worker
    wid = WorkerIdentity(worker_id="w1", generation=1, instance_id="t1", tenant="ta")
    worker = NativeIGPUWorker(wid, plan)
    scheduler = FleetScheduler({"w1": worker}, 30)
    lease = scheduler.issue_lease(
        work_id="agree1",
        tenant="ta",
        operation="double",
        input_data=items,
    )
    assert lease is not None
    r = worker.execute(work_id=lease.work_id, kernel=k, input_data=items, lease=lease)
    worker.complete_lease(lease.lease_id, r)
    c = FleetCustody()
    committed = c.verify_and_commit(r, "ta")
    assert committed is True
    assert r.result == single
    print(f"  Distributed digest: {r.output_digest[:16]}...")
    print(f"  Custody committed: {committed}")
    print("  [PASS] Results agreement demonstrated")
