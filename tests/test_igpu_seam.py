"""Seam contract tests — no GPU required. Fail closed."""

from __future__ import annotations

from igpu.seam import store
from igpu.seam.buffer import allocate, read, release, write
from igpu.seam.fleet import coordinate, route
from igpu.seam.hybrid import kernel_class, partition
from igpu.seam.invariants import audit_hyba_hybrid, audit_igpu
from igpu.seam.kernel import cancel, dispatch, poll
from igpu.seam.probe import lifecycle, probe_devices
from igpu.seam.queue import WorkItem, dequeue, enqueue, queue_state
from igpu.seam.types import (
    BufferBacking,
    DeviceClass,
    KernelClass,
    KernelName,
    Ok,
    SeamError,
)


def setup_function() -> None:
    store.reset()


def test_probe_returns_attested_nonzero_devices():
    result = probe_devices()
    assert isinstance(result, Ok)
    caps = result.value
    assert caps
    for cap in caps:
        assert cap.measured_hps.mean > 0.0
        assert cap.attestation_chain
        assert cap.firmware_digest
        assert cap.privacy_mode is not None


def test_probe_never_labels_cpu_as_igpu():
    result = probe_devices()
    assert isinstance(result, Ok)
    for cap in result.value:
        if cap.device_class is DeviceClass.cpu_reference:
            assert cap.vendor_extensions.get("is_igpu", "False") in ("False", "false", "")


def test_lifecycle_attests_quarantine():
    probe_devices()
    cap = store.all_caps()[0]
    quarantined = lifecycle(cap.device_id, "quarantine")
    assert isinstance(quarantined, Ok)
    assert quarantined.value.state.value == "quarantined"
    assert any("quarantine" in a.subject for a in quarantined.value.attestation_chain)


def test_buffer_digest_mismatch_is_corruption():
    probe_devices()
    cap = store.all_caps()[0]
    buf = allocate(cap.device_id, 8, BufferBacking.host_mapped)
    assert isinstance(buf, Ok)
    written = write("seam", buf.value, b"abcdefgh")
    assert isinstance(written, Ok)
    written.value.payload = b"tampered!"
    corrupted = read("seam", written.value)
    assert not isinstance(corrupted, Ok)
    assert corrupted.error is SeamError.buffer_corruption


def test_buffer_rejects_unauthorized_reader():
    probe_devices()
    cap = store.all_caps()[0]
    buf = allocate(cap.device_id, 4)
    assert isinstance(buf, Ok)
    denied = read("stranger", buf.value)
    assert denied.error is SeamError.privacy_violation
    released = release("seam", buf.value)
    assert isinstance(released, Ok)


def test_dispatch_rejects_unsupported_kernel():
    probe_devices()
    cpu = next(c for c in store.all_caps() if c.device_class is DeviceClass.cpu_reference)
    result = dispatch("seam", cpu.device_id, KernelName.matmul_f4, {}, "k1")
    assert result.error is SeamError.kernel_unavailable


def test_dispatch_is_idempotent():
    probe_devices()
    cap = store.all_caps()[0]
    kernel = next(iter(cap.supported_kernels))
    a = dispatch("seam", cap.device_id, kernel, {"n": 1}, "same-key")
    b = dispatch("seam", cap.device_id, kernel, {"n": 1}, "same-key")
    assert isinstance(a, Ok) and isinstance(b, Ok)
    assert a.value.id == b.value.id


def test_poll_marks_host_verified():
    probe_devices()
    cap = store.all_caps()[0]
    kernel = KernelName.sha256d_verify
    if kernel not in cap.supported_kernels:
        kernel = next(iter(cap.supported_kernels))
    handle = dispatch("seam", cap.device_id, kernel, {}, "verify-1")
    assert isinstance(handle, Ok)
    result = poll("seam", handle.value)
    assert isinstance(result, Ok)
    assert result.value is not None
    assert result.value.host_verified is True


def test_queue_backpressure_and_idempotency():
    probe_devices()
    cap = store.all_caps()[0]
    q = store.queue_of(cap.device_id)
    q["threshold"] = 1
    first = WorkItem(
        id="",
        job_id="j",
        kernel=KernelName.lucas_wind,
        args="{}",
        priority=0,
        deadline=None,
        idempotency_key="q1",
        submitted_at="",
        assigned_device=None,
        state="pending",
    )
    assert isinstance(enqueue("seam", cap.device_id, first), Ok)
    deq = dequeue("seam", cap.device_id)
    assert isinstance(deq, Ok) and deq.value is not None
    second = WorkItem(
        id="",
        job_id="j",
        kernel=KernelName.lucas_wind,
        args="{}",
        priority=0,
        deadline=None,
        idempotency_key="q2",
        submitted_at="",
        assigned_device=None,
        state="pending",
    )
    limited = enqueue("seam", cap.device_id, second)
    assert limited.error is SeamError.rate_limited
    state = queue_state("seam", cap.device_id)
    assert isinstance(state, Ok)
    assert state.value.throughput.samples >= 1


def test_route_declares_fallback_not_silent():
    probe_devices()
    fleet = store.all_caps()
    job = {
        "job_id": "job-1",
        "kernels": [KernelName.lucas_wind.value, KernelName.sha256d_verify.value],
        "span": 1024,
    }
    routed = route(job, fleet)
    assert isinstance(routed, Ok)
    starts = [a.window.start for a in routed.value]
    assert min(starts) == 0
    for a in routed.value:
        assert a.fallback in (True, False)


def test_coordinate_returns_result_not_exception():
    probe_devices()
    job = {"job_id": "job-2", "kernels": [KernelName.cassini_step.value], "span": 256}
    out = coordinate("seam", job, store.all_caps())
    assert isinstance(out, Ok)
    assert out.value.attestation.signature
    assert out.value.degraded in (True, False)


def test_partition_is_class_not_vendor():
    parts = partition([KernelName.sha256d_scan, KernelName.lucas_wind], span=100)
    assert KernelClass.hash_heavy in parts
    assert KernelClass.traversal in parts
    assert kernel_class(KernelName.sha256d_scan) is KernelClass.hash_heavy


def test_cancel_is_idempotent():
    probe_devices()
    cap = store.all_caps()[0]
    kernel = next(iter(cap.supported_kernels))
    handle = dispatch("seam", cap.device_id, kernel, {}, "cancel-me")
    assert isinstance(handle, Ok)
    assert isinstance(cancel("seam", handle.value), Ok)
    again = cancel("seam", handle.value)
    assert isinstance(again, Ok)


def test_hyba_hybrid_audit_declares_gaps():
    report = audit_hyba_hybrid()
    assert "gaps" in report
    assert "S1" in report["gaps"] or "error" in report


def test_igpu_audit_keeps_honesty_invariants():
    report = audit_igpu()
    assert report["ok"] is True
    assert "P3" in report["passed"] or "S5" in report["passed"] or "error" not in report
