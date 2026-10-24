"""Adversarial native fleet lease tests; all decisions survive python -O."""

from dataclasses import replace
import time

import pytest

from chronus.fleet.native_worker import NativeIGPUWorker
from chronus.fleet.scheduler import FleetScheduler
from chronus.fleet.worker_identity import WorkerIdentity, WorkLease
from chronus.igpu.host import HostGPUPlan


def setup_worker():
    w = NativeIGPUWorker(WorkerIdentity(worker_id="w", tenant="t"), HostGPUPlan(4, 2))
    s = FleetScheduler({"w": w})
    lease = s.issue_lease(
        work_id="job", tenant="t", operation="kernel_eval", input_data=[1, 2, 3, 4]
    )
    return w, s, lease


def require(value, reason):
    if not value:
        raise AssertionError(reason)


@pytest.mark.parametrize(
    "changes",
    [
        {"tenant": "other"},
        {"worker_id": "other"},
        {"work_id": "other"},
        {"fencing_token": "old"},
        {"deadline": time.monotonic() - 1},
        {"partition": (0, 3)},
        {"partition": (1, 5)},
    ],
)
def test_invalid_lease_refused_before_kernel(changes):
    worker, _, lease = setup_worker()
    bad = replace(lease, **changes)
    calls = []
    with pytest.raises(ValueError):
        worker.execute("job", lambda x: calls.append(x) or x, [1, 2, 3, 4], lease=bad)
    require(not calls, "invalid lease ran protected kernel")


@pytest.mark.parametrize(
    "changes",
    [
        {"worker_id": "other"},
        {"lease_id": "other"},
        {"work_id": "other"},
        {"generation": 99},
        {"partition": (0, 3)},
        {"backend": "invented"},
        {"output_digest": "0" * 64},
        {"result": [99, 99, 99, 99]},
    ],
)
def test_result_bound_to_lease(changes):
    worker, scheduler, lease = setup_worker()
    result = worker.execute("job", lambda x: x, [1, 2, 3, 4], lease=lease)
    for k, v in changes.items():
        setattr(result, k, v)
    require(
        not scheduler.register_result(
            lease_id=lease.lease_id, worker=worker, result=result
        ),
        "forged result accepted",
    )


def test_result_from_unregistered_worker_object_refused():
    worker, scheduler, lease = setup_worker()
    result = worker.execute("job", lambda x: x, [1, 2, 3, 4], lease=lease)
    impostor = NativeIGPUWorker(worker.identity, worker.plan)
    require(
        not scheduler.register_result(
            lease_id=lease.lease_id, worker=impostor, result=result
        ),
        "unregistered worker accepted",
    )


@pytest.mark.parametrize("deadline", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_deadline_refused(deadline):
    with pytest.raises(ValueError):
        WorkLease(
            lease_id="l", work_id="j", tenant="t", partition=(0, 1), deadline=deadline
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("cpu_cores", 0),
        ("memory_mb", -1),
        ("concurrency", 0),
        ("cpu_cores", True),
        ("memory_mb", 1.5),
    ],
)
def test_invalid_resource_budget_refused(field, value):
    with pytest.raises(ValueError):
        WorkLease(
            lease_id="l",
            work_id="j",
            tenant="t",
            partition=(0, 1),
            deadline=time.monotonic() + 10,
            **{field: value}
        )


def test_deadline_boundary_is_expired():
    lease = WorkLease(
        lease_id="l", work_id="j", tenant="t", partition=(0, 1), deadline=123.0
    )
    require(lease.is_expired(123.0), "deadline equality accepted")


@pytest.mark.parametrize("generation", [0, 1, -1, True])
def test_rotation_requires_newer_generation(generation):
    with pytest.raises(ValueError):
        WorkerIdentity(worker_id="w").rotated(generation=generation)


def test_rotation_cannot_reuse_token():
    identity = WorkerIdentity(worker_id="w")
    with pytest.raises(ValueError):
        identity.rotated(fencing_token=identity.current_fencing_token)


def test_completion_requires_active_matching_lease():
    worker, _, lease = setup_worker()
    result = worker.execute("job", lambda x: x, [1, 2, 3, 4], lease=lease)
    worker._active_leases.clear()
    with pytest.raises(ValueError):
        worker.complete_lease(lease.lease_id, result)


def test_valid_registration_is_idempotent():
    worker, scheduler, lease = setup_worker()
    result = worker.execute("job", lambda x: x * 2, [1, 2, 3, 4], lease=lease)
    worker.complete_lease(lease.lease_id, result)
    for _ in range(2):
        require(
            scheduler.register_result(
                lease_id=lease.lease_id, worker=worker, result=result
            ),
            "valid result refused",
        )


def test_termination_cannot_reuse_previously_revoked_token():
    worker, scheduler, _ = setup_worker()
    token = worker.identity.current_fencing_token
    scheduler.terminate_worker("w")
    current = scheduler.workers["w"]
    with pytest.raises(ValueError):
        scheduler.terminate_worker("w", fencing_token=token)
    require(scheduler.workers["w"] is current, "failed rotation mutated worker")


def test_generic_kernel_does_not_claim_hash_evaluations():
    worker, _, lease = setup_worker()
    result = worker.execute("job", lambda x: x, [1, 2, 3, 4], lease=lease)
    require(result.sha256d_evaluations == 0, "arbitrary work counted as SHA256d")


def test_tenant_collision_not_accepted_as_idempotent():
    from chronus.fleet.custody import FleetCustody
    from chronus.fleet.native_worker import ExecutionResult

    ledger = FleetCustody()
    a = ExecutionResult(work_id="same", tenant="a", output_digest="same")
    b = ExecutionResult(work_id="same", tenant="b", output_digest="same")
    require(ledger.verify_and_commit(a, "a"), "first local result refused")
    require(
        not ledger.verify_and_commit(b, "b"),
        "cross-tenant collision accepted as duplicate",
    )
