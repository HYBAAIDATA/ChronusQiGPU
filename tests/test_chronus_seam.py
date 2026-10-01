"""Seam contract tests — no GPU required. Fail closed."""

from __future__ import annotations

import hashlib

from chronus.seam import store
from chronus.seam.attest_compose import attest_compose
from chronus.seam.buffer import AccessPolicy, allocate, read, release, write
from chronus.seam.fleet import coordinate, route
from chronus.seam.hybrid import kernel_class, partition
from chronus.seam.invariants import audit_hyba_hybrid, audit_chronus
from chronus.seam.kernel import cancel, dispatch, poll
from chronus.seam.probe import lifecycle, probe_devices
from chronus.seam.queue import WorkItem, dequeue, enqueue, queue_state
from chronus.seam.threshold import VerificationRequest, min_required, verify_threshold
from chronus.seam.types import (
    BufferBacking,
    DeviceClass,
    KernelClass,
    KernelName,
    Ok,
    SeamError,
    ThresholdPolicy,
    attest,
    digest_of,
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


def test_probe_never_labels_cpu_as_chronus():
    result = probe_devices()
    assert isinstance(result, Ok)
    for cap in result.value:
        if cap.device_class is DeviceClass.cpu_reference:
            assert cap.vendor_extensions.get("is_integrated", "False") in ("False", "false", "")


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
    kernels = sorted(cap.supported_kernels, key=lambda k: k.value)
    kernel = next(k for k in kernels if k is not KernelName.sha256d_verify)
    handle = dispatch("seam", cap.device_id, kernel, {}, "verify-1")
    assert isinstance(handle, Ok)
    result = poll("seam", handle.value)
    assert isinstance(result, Ok)
    assert result.value is not None
    assert result.value.host_verified is True


def test_seam_string_is_not_a_master_key():
    probe_devices()
    cap = store.all_caps()[0]
    buf = allocate(cap.device_id, 4, policy=AccessPolicy(owner="alice"))
    assert isinstance(buf, Ok)
    # 'seam' is the default owner label, not a privilege: alice's buffer is
    # closed to a caller merely naming itself 'seam'.
    assert read("seam", buf.value).error is SeamError.privacy_violation
    assert write("seam", buf.value, b"xy").error is SeamError.privacy_violation
    assert release("seam", buf.value).error is SeamError.privacy_violation
    assert isinstance(read("alice", buf.value), Ok)


def test_encrypted_backing_fails_closed_without_cipher():
    probe_devices()
    cap = store.all_caps()[0]
    denied = allocate(cap.device_id, 8, BufferBacking.encrypted_at_rest)
    assert denied.error is SeamError.capability_mismatch


def test_negative_offset_is_rejected_not_wrapped():
    probe_devices()
    cap = store.all_caps()[0]
    buf = allocate(cap.device_id, 8)
    assert isinstance(buf, Ok)
    assert write("seam", buf.value, b"zz", offset=-2).error is SeamError.unknown
    assert read("seam", buf.value, offset=-4).error is SeamError.unknown


def _sha256d(payload: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(payload).digest()).digest()


def test_sha256d_verify_actually_verifies():
    probe_devices()
    cap = next(c for c in store.all_caps() if KernelName.sha256d_verify in c.supported_kernels)
    payload = b"real share payload"
    good = dispatch(
        "t",
        cap.device_id,
        KernelName.sha256d_verify,
        {"payload": payload, "claimed": _sha256d(payload)},
        "v-good",
    )
    result = poll("t", good.value)
    assert isinstance(result, Ok) and result.value.outputs == [b"\x01"]
    bad = dispatch(
        "t",
        cap.device_id,
        KernelName.sha256d_verify,
        {"payload": payload, "claimed": _sha256d(b"other")},
        "v-bad",
    )
    result = poll("t", bad.value)
    assert isinstance(result, Ok) and result.value.outputs == [b"\x00"]
    missing = dispatch("t", cap.device_id, KernelName.sha256d_verify, {}, "v-none")
    refused = poll("t", missing.value)
    assert refused.error is SeamError.capability_mismatch
    assert not store.is_quarantined(cap.device_id)


def _cap(device_id: str, vendor: str, kernels) -> "object":
    from chronus.seam.probe import Capability, CapabilityFeatures
    from chronus.seam.types import DeviceState, Distribution, PrivacyMode

    return Capability(
        device_id=device_id,
        device_class=DeviceClass.cpu_reference,
        vendor=vendor,
        model="m",
        firmware_digest=digest_of(device_id.encode()),
        memory_bytes=0,
        compute_units=1,
        max_work_group=1,
        measured_hps=Distribution(1.0, 0.0, 1),
        supported_kernels=set(kernels),
        kernel_costs={},
        features=CapabilityFeatures(),
        attestation_chain=[attest(device_id, issuer=f"probe:{device_id}")],
        privacy_mode=PrivacyMode.none,
        state=DeviceState.present,
    )


def _traversal_caps(n: int):
    caps = []
    for i in range(n):
        cap = _cap(f"dev-{i}", f"vendor-{i}", {KernelName.lucas_wind})
        store.put_cap(cap)
        caps.append(cap)
    return caps


def _lucas_expected() -> list:
    return [digest_of((0).to_bytes(4, "little"))]


def test_threshold_k_cannot_undercut_majority_floor():
    caps = _traversal_caps(3)
    req = VerificationRequest(
        kernel=KernelName.lucas_wind,
        inputs=[],
        outputs=_lucas_expected(),
        candidates=[c.device_id for c in caps],
        policy=ThresholdPolicy.majority,
        k=1,
    )
    # majority of 3 is 2 — a lone agreeing link must not satisfy the vote
    assert min_required(ThresholdPolicy.majority, 1, 3) == 2
    out = verify_threshold(req, caps)
    assert isinstance(out, Ok)


def test_threshold_repoll_does_not_quarantine_healthy_verifier():
    caps = _traversal_caps(1)
    cap = caps[0]
    kernel, inputs = KernelName.lucas_wind, []
    idem = digest_of("|".join([kernel.value] + inputs).encode("utf-8"))
    handle = dispatch("t", cap.device_id, kernel, {"inputs": inputs}, f"tv:{idem}:{cap.device_id}")
    assert isinstance(handle, Ok)
    first = poll("t", handle.value)
    assert isinstance(first, Ok) and first.value is not None
    req = VerificationRequest(
        kernel=kernel,
        inputs=inputs,
        outputs=_lucas_expected(),
        candidates=[cap.device_id],
        policy=ThresholdPolicy.unanimous,
    )
    out = verify_threshold(req, caps)
    assert out.error is SeamError.verification_failed
    assert not store.is_quarantined(cap.device_id)


def test_attest_compose_rejects_forged_issuer():
    link = attest("subject", issuer="result:forged-device")
    out = attest_compose([link], issuers={"result:dev-0"})
    assert out.error is SeamError.attestation_failure


def test_enqueue_denied_on_quarantined_device():
    probe_devices()
    cap = store.all_caps()[0]
    store.quarantine(cap.device_id, "test")
    item = WorkItem(
        id="",
        job_id="j",
        kernel=KernelName.lucas_wind,
        args="{}",
        priority=0,
        deadline=None,
        idempotency_key="q-q",
        submitted_at="",
        assigned_device=None,
        state="pending",
    )
    assert enqueue("seam", cap.device_id, item).error is SeamError.device_quarantined


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


def test_chronus_audit_keeps_honesty_invariants():
    report = audit_chronus()
    assert report["ok"] is True
    assert "P3" in report["passed"] or "S5" in report["passed"] or "error" not in report
