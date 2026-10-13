"""Executable contract for the canonical Chronus H4/600 mining fabric."""
from __future__ import annotations

import json
import time

import pytest

from chronos_one_igpu.reference_contract import reference_execution
from chronus.mla1517.mining.geodesic_support import (
    chronus_fabric_execution_state_for,
    chronus_fabric_state_for,
)
from chronus.mla1517.mining.h4_600_execution import (
    H4600HybridCoordinator,
    promote_execution_hasher,
)
from hyba.hybrid.coordinator import HybridCoordinator, StratumJob
from hyba.hybrid.super_asic import SuperAsicHasher
from hyba.hybrid.lucas_partition import H4_FACE_COUNT, partition
from hyba.hybrid.nonce_scheduler import (
    DeviceCapability,
    DispatchHandle,
    next_handle_id,
)


@pytest.fixture
def h4_reference_contract(tmp_path, monkeypatch):
    """Operator approval registry for the reference-only h4_600 capability."""
    path = tmp_path / "approved.json"
    record = {
        "schema": "chronos.reference_approvals/1",
        "approvals": {
            "qc-local": {
                "approved": True,
                "approved_by": "local-test-operator",
                "purpose": "H4/600 contract verification, not production evidence",
                "mode": "reference",
                "expires_unix": time.time() + 120,
                "capabilities": ["chronus.h4_600"],
            }
        },
    }
    path.write_text(json.dumps(record))
    monkeypatch.setenv("CHRONOS_REFERENCE_APPROVALS_FILE", str(path))
    return path


class _Scheduler:
    """Deterministic physical-worker fixture; every assigned nonce is executed."""

    def __init__(self, device_id: str, hps: float, device_class: str = "gpu") -> None:
        self._cap = DeviceCapability(
            device_id=device_id,
            device_class=device_class,
            measured_hashes_per_sec=hps,
            supported=True,
        )
        self._done: dict[int, int] = {}
        self._pending: dict[int, DispatchHandle] = {}
        self.prepared: list[str] = []
        self.dispatched = []

    def capability(self) -> DeviceCapability:
        return self._cap

    def prepare(self, job_id: str, header80: bytes) -> None:
        assert len(header80) == 80
        self.prepared.append(job_id)

    def dispatch(self, window):
        self.dispatched.append(window)
        handle = DispatchHandle(
            handle_id=next_handle_id(),
            device_id=self._cap.device_id,
            window=window,
            dispatched_ns=1,
        )
        self._pending[handle.handle_id] = handle
        return handle

    def poll(self, handle):
        pending = self._pending.pop(handle.handle_id, None)
        if pending is not None:
            self._done[handle.handle_id] = handle.window.span
        return None

    def is_done(self, handle) -> bool:
        return handle.handle_id in self._done

    def hashed_count(self, handle) -> int:
        return self._done.get(handle.handle_id, 0)

    def cancel(self, handle, reason="cancelled") -> None:
        pending = self._pending.pop(handle.handle_id, None)
        if pending is not None:
            self._done[handle.handle_id] = 0


def test_h4_partition_is_600_disjoint_11d_logical_vertices(h4_reference_contract):
    fast = _Scheduler("chronus-a", 9.0)
    slow = _Scheduler("chronus-b", 1.0)
    with reference_execution("qc-local"):
        spans, cert = partition(6000, [fast, slow], strategy="h4_600")

    assert cert.verify()
    assert cert.topology == "chronus_h4_600_11d"
    assert cert.as_dict()["logical_vertex_count"] == H4_FACE_COUNT == 600
    assert len(spans) == 600
    assert [span.face for span in spans] == list(range(600))
    assert sum(span.span for span in spans) == 6000
    assert spans[0].base_nonce == 0
    assert spans[-1].base_nonce + spans[-1].span == 6000

    # Measured capacity controls physical allocation; topology does not invent
    # hashrate. 9:1 workers receive an exact 9:1 nonce budget here.
    by_device = {}
    for span in spans:
        by_device[span.device_id] = by_device.get(span.device_id, 0) + span.span
    assert by_device == {"chronus-a": 5400, "chronus-b": 600}


def test_small_lease_folds_only_empty_vertices_without_losing_coverage(h4_reference_contract):
    worker = _Scheduler("chronus-a", 1.0)
    with reference_execution("qc-local"):
        spans, cert = partition(32, [worker], strategy="h4_600")
    assert cert.verify()
    assert len(spans) == 32
    assert all(span.span == 1 for span in spans)
    assert len(cert.folded_faces) == 568
    assert sum(span.span for span in spans) == 32


def test_h4_coordinator_dispatches_all_600_before_polling(h4_reference_contract):
    a = _Scheduler("chronus-a", 1.0)
    b = _Scheduler("chronus-b", 1.0)
    coordinator = H4600HybridCoordinator(a, extra_devices=[b])
    job = StratumJob(
        job_id="h4-e2e",
        header80=bytes(80),
        target=bytes(32),
        nonce_space=600,
    )

    with reference_execution("qc-local"):
        result = coordinator.run_job(job)
    assert result.certificate.verify()
    assert result.certificate.topology == "chronus_h4_600_11d"
    assert len(result.handles) == 600
    assert result.total_nonces_tried == 600
    assert result.share is None
    assert {handle["window"]["face"] for handle in result.handles} == set(range(600))


def test_super_asic_promotion_reuses_bound_devices_and_changes_only_topology():
    worker = _Scheduler("chronus-a", 1.0)
    original = HybridCoordinator(worker)

    class _Hasher:
        backend = "super_asic:gpu"
        _coord = original

    hasher = _Hasher()
    promoted = promote_execution_hasher(hasher)
    assert promoted is hasher
    assert isinstance(hasher._coord, H4600HybridCoordinator)
    assert hasher._coord.gpu is worker
    assert hasher.topology_id == "chronus_h4_600_11d"
    assert hasher.logical_vertices == 600


def test_non_composite_hasher_is_not_falsely_promoted():
    class _Hasher:
        backend = "opencl:gpu"

    hasher = _Hasher()
    assert promote_execution_hasher(hasher) is hasher
    assert not hasattr(hasher, "topology_id")


def _promoted_super_asic(worker: _Scheduler) -> SuperAsicHasher:
    hasher = SuperAsicHasher(HybridCoordinator(worker), [worker])
    return promote_execution_hasher(hasher)


def test_bound_h4_capability_is_not_reported_as_observed_fanout_before_execution():
    worker = _Scheduler("chronus-a", 1.0)
    hasher = _promoted_super_asic(worker)

    state = chronus_fabric_state_for(hasher)

    assert state["state"] == "ACTIVE"
    assert state["capability_bound"] is True
    assert state["physical_fanout_capable"] is True
    assert state["physical_fanout"] is False
    assert state["physical_fanout_observed"] is False
    assert state["execution_evidence"] == "Unavailable"


def test_fragmented_ordered_batch_preserves_membership_without_false_600_fanout_claim(
    h4_reference_contract,
):
    worker = _Scheduler("chronus-a", 1.0)
    hasher = _promoted_super_asic(worker)
    nonces = [1000, 1002, 1004, 1006, 1008, 1010]

    with reference_execution("qc-local"):
        nonce, digest, done = hasher.grind_target_batch(bytes(80), bytes(32), nonces)

    assert nonce is None
    assert digest is None
    assert done == len(nonces)
    assert [window.base_nonce for window in worker.dispatched] == nonces
    evidence = hasher.last_batch_evidence
    assert evidence is not None
    assert evidence["ordered_nonce_count"] == len(nonces)
    assert evidence["contiguous_run_count"] == len(nonces)
    assert evidence["h4_job_count"] == len(nonces)
    assert evidence["h4_active_shards"] == len(nonces)
    assert evidence["h4_full_600_shard_jobs"] == 0
    assert evidence["h4_topology_observed"] is True
    assert evidence["physical_fanout_observed"] is False
    assert evidence["completion_state"] == "COMPLETE"

    state = chronus_fabric_execution_state_for(hasher)
    assert state["physical_fanout"] is False
    assert state["physical_fanout_observed"] is False
    assert state["execution_evidence"]["completed_work_items"] == len(nonces)


class _FailingScheduler(_Scheduler):
    def poll(self, handle):
        raise RuntimeError("test scheduler failure")


class _SkewedCountScheduler(_Scheduler):
    def hashed_count(self, handle) -> int:
        span = int(handle.window.span)
        if handle.window.face == 0:
            return span + 1
        if handle.window.face == 1:
            return max(0, span - 1)
        return super().hashed_count(handle)


def test_ordered_batch_failure_records_terminal_device_error_evidence(h4_reference_contract):
    worker = _FailingScheduler("chronus-a", 1.0)
    hasher = _promoted_super_asic(worker)

    try:
        with reference_execution("qc-local"):
            hasher.grind_target_batch(bytes(80), bytes(32), [1000])
    except RuntimeError as exc:
        assert "test scheduler failure" in str(exc)
    else:
        raise AssertionError("scheduler failure did not propagate")

    evidence = hasher.last_batch_evidence
    assert evidence is not None
    assert evidence["completion_state"] == "DEVICE_ERROR"
    assert evidence["physical_fanout_observed"] is False
    assert "RuntimeError" in evidence["error"]


def test_aggregate_count_cannot_mask_an_incomplete_h4_shard(h4_reference_contract):
    worker = _SkewedCountScheduler("chronus-a", 1.0)
    hasher = _promoted_super_asic(worker)
    nonces = list(range(30_000, 30_600))

    with reference_execution("qc-local"):
        nonce, digest, done = hasher.grind_target_batch(bytes(80), bytes(32), nonces)

    assert nonce is None
    assert digest is None
    assert done == 600
    evidence = hasher.last_batch_evidence
    assert evidence is not None
    assert evidence["h4_full_600_shard_jobs"] == 1
    assert evidence["h4_completed_600_shard_jobs"] == 0
    assert evidence["physical_fanout_observed"] is False
    handles = hasher.last_result.handles
    assert len(handles) == 600
    assert handles[0]["completed_nonces"] != handles[0]["assigned_nonces"]
    assert handles[1]["completed_nonces"] != handles[1]["assigned_nonces"]


def test_contiguous_600_nonce_batch_records_real_full_h4_fanout(h4_reference_contract):
    worker = _Scheduler("chronus-a", 1.0)
    hasher = _promoted_super_asic(worker)
    nonces = list(range(20_000, 20_600))

    with reference_execution("qc-local"):
        nonce, digest, done = hasher.grind_target_batch(bytes(80), bytes(32), nonces)

    assert nonce is None
    assert digest is None
    assert done == 600
    evidence = hasher.last_batch_evidence
    assert evidence is not None
    assert evidence["contiguous_run_count"] == 1
    assert evidence["h4_job_count"] == 1
    assert evidence["h4_active_shards"] == 600
    assert evidence["h4_full_600_shard_jobs"] == 1
    assert evidence["h4_completed_600_shard_jobs"] == 1
    assert evidence["full_600_shard_dispatch_observed"] is True
    assert evidence["physical_fanout_observed"] is True
    assert evidence["completed_work_items"] == 600
    assert len(worker.dispatched) == 600
    assert {window.face for window in worker.dispatched} == set(range(600))

    state = chronus_fabric_execution_state_for(hasher)
    assert state["physical_fanout"] is True
    assert state["physical_fanout_observed"] is True
    assert state["reason"] is None

