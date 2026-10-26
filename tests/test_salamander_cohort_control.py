from fractions import Fraction
import pytest
from salamander.cohort_control import CohortModel, CohortRecovery, CohortAutonomicLoop
from chronus.fleet.authority_admission import AdmissionController, AuthorityGrant, TenantBudgetQuota
from chronus.fleet.recovery_security import DurableMutationLatch, BlindRetryForbiddenError
from chronus.fleet.workload_contracts import ResourceVector
from chronus.fleet.scheduler import FleetScheduler
from chronus.fleet.native_worker import NativeIGPUWorker
from chronus.fleet.worker_identity import WorkerIdentity
from chronus.igpu.host import HostGPUPlan


def test_lyapunov_invariant_box_and_disturbance_refusal():
    model = CohortModel((Fraction(1, 2), Fraction(1, 3)), (1, 2))
    assert model.invariant_box == (2, 3)
    result = model.certify_transition((10, 9), (6, 5))
    assert result["verified"]
    assert Fraction(*result["lyapunov_after"]) <= Fraction(*result["lyapunov_before"]) / 4
    assert model.certify_transition((2, 3), (2, 3))["lyapunov_after"] == [0, 1]
    with pytest.raises(ValueError, match="disturbance"):
        model.certify_transition((10, 9), (7, 5))
    with pytest.raises(TypeError):
        model.lyapunov((0.5, 1))


@pytest.mark.parametrize("mode", ["manual", "automatic", "io_failure"])
def test_authorized_recovery_rotates_fence_reissues_and_latches_uncertainty(
    tmp_path, monkeypatch, mode
):
    key = b"c" * 32
    controller = AdmissionController(audit_dir=tmp_path / "audit", signing_key=key)
    controller.register_tenant(TenantBudgetQuota(tenant_id="tenant"))
    scheduler = FleetScheduler(
        {
            "w": NativeIGPUWorker(
                WorkerIdentity(worker_id="w", tenant="tenant"), HostGPUPlan(total_items=8, lanes=4)
            )
        }
    )
    journal = DurableMutationLatch(tmp_path / "journal")
    recovery = CohortRecovery(scheduler, controller, journal)
    rv = ResourceVector(
        cpu_time_ms=10,
        peak_memory_bytes=4096,
        custody_bytes=4096,
        custody_io_bps=4096,
        network_bytes=0,
        deadline_epoch_ms=20000,
        exactness_plane="exact",
        tenant_id="tenant",
    )
    grant = AuthorityGrant.issue(
        signing_key=key,
        grant_id="recover",
        tenant_id="tenant",
        workload_id="recover",
        owner_authority="Salamander",
        resource_vector=rv,
        nonce="once",
        issued_at_ms=1000,
        ttl_ms=10000,
    )
    lease = scheduler.issue_lease(
        work_id="work",
        tenant="tenant",
        operation="op",
        input_data=list(range(8)),
        target_worker="w",
    )
    kwargs = dict(
        worker_id="w",
        tenant="tenant",
        new_lanes=2,
        operation_id="recover",
        grant=grant,
        resources=rv,
        capacity=controller.default_capacity_snapshot(now_ms=2000),
        now_ms=2000,
    )
    if mode == "io_failure":
        commit = journal.commit

        def fail_completion(**args):
            if args["operation_id"].endswith(":complete"):
                raise OSError("synthetic completion failure")
            return commit(**args)

        monkeypatch.setattr(journal, "commit", fail_completion)
        with pytest.raises(OSError):
            recovery.recover(**kwargs)
        assert scheduler.workers["w"].identity.current_fencing_token != lease.fencing_token
        restarted = CohortRecovery(
            scheduler, controller, DurableMutationLatch(tmp_path / "journal")
        )
        with pytest.raises(BlindRetryForbiddenError):
            restarted.recover(**kwargs)
        return
    if mode == "automatic":
        observations = iter([(10,), (5,)])

        def authorize(request):
            assert request["new_lanes"] == 3
            return {k: kwargs[k] for k in ("grant", "resources", "capacity", "now_ms")}

        loop = CohortAutonomicLoop(
            recovery,
            CohortModel((Fraction(1, 2),), (1,)),
            lambda worker, tenant: next(observations),
            authorize,
        )
        result = loop.step(worker_id="w", tenant="tenant", operation_id="recover")
        assert result["stability_verified"]
    else:
        result = recovery.recover(**kwargs)
        assert result.postcondition_verified
    replacement = scheduler.issue_lease(
        work_id="work",
        tenant="tenant",
        operation="op",
        input_data=list(range(8)),
        target_worker="w",
    )
    assert replacement.fencing_token != lease.fencing_token
    assert scheduler.workers["w"].plan.lanes == (3 if mode == "automatic" else 2)
    # Replayed authority is refused before a further worker rotation.
    old = scheduler.workers["w"].identity.generation
    assert not recovery.recover(**kwargs).postcondition_verified
    assert scheduler.workers["w"].identity.generation == old
    journal.mark_uncertain(operation_id="external", detail="lost acknowledgement")
    with pytest.raises(BlindRetryForbiddenError):
        recovery.recover(**kwargs)
    with pytest.raises(PermissionError):
        recovery.recover(**{**kwargs, "tenant": "other"})


def test_crash_between_intent_and_rotation_blocks_restart(tmp_path):
    journal = DurableMutationLatch(tmp_path)
    journal.commit(operation_id="interrupted:intent", payload={"worker": "w"})
    recovery = CohortRecovery(None, None, DurableMutationLatch(tmp_path))
    with pytest.raises(BlindRetryForbiddenError, match="unfinished"):
        recovery._check_pending_intents()
