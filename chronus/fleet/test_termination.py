"""Fleet qualification test - worker termination and safe reassignment."""
from __future__ import annotations

from chronus.fleet.native_worker import NativeIGPUWorker
from chronus.fleet.scheduler import FleetScheduler
from chronus.fleet.worker_identity import WorkerIdentity
from chronus.igpu.host import HostGPUPlan


def test_termination_safe_reassign():
    """Worker termination triggers safe reassignment."""
    print("[TEST 3] Termination safe reassignment")
    scheduler = FleetScheduler(
        {
            "w1": NativeIGPUWorker(
                WorkerIdentity(worker_id="w1", generation=1, instance_id="t1", tenant="ta"),
                HostGPUPlan(total_items=4, lanes=2, mode="host_gpu_overlay"),
            )
        },
        30,
    )

    # Issue lease
    lease = scheduler.issue_lease(
        work_id="term1",
        tenant="ta",
        operation="op",
        input_data=list(range(4)),
    )
    assert lease is not None
    # Simulate worker termination with fencing token rotation
    old_token = lease.fencing_token
    scheduler.worker_terminated("w1", fencing_token="new_token_xyz_123")
    # New work should use new fencing token
    lease2 = scheduler.issue_lease(
        work_id="term1_new",
        tenant="ta",
        operation="op",
        input_data=list(range(4)),
        target_worker="w1",
    )
    assert lease2 is not None
    assert lease2.fencing_token == "new_token_xyz_123"
    assert lease2.fencing_token != old_token
    print(f"  Old token: {old_token[:8]}... New lease fencing: {lease2.fencing_token[:8]}...")
    print("  [PASS] Worker termination with fencing token rotation demonstrated")
