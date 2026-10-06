"""Chronus runtime lifecycle: admission quotas, deadlines, recovery, device loss.

Admission fields that exist in the ABI must be enforced, not just declared:
``Quota.max_bytes``, ``Workload.deadline_ms``, and the documented
``RECOVERING`` transition. Timeout is recorded as a real outcome — never
rewritten to success — and recovery re-probes devices so a lost device drops
out of selection.
"""
from __future__ import annotations

import time

import pytest

from chronus.virtual_igpu.abi import (
    AdapterAttestation,
    AdapterKind,
    CapabilityManifest,
    ExecutionPolicy,
    Workload,
    WorkloadKind,
    RuntimeState,
    digest_json,
)
from chronus.virtual_igpu.adapters import Adapter, AdapterUnavailable, CPUEmulatorAdapter
from chronus.virtual_igpu.attestation import extend_chain
from chronus.virtual_igpu.runtime import Quota, RuntimeDaemon, RuntimeInvariantError


class _SlowAdapter(CPUEmulatorAdapter):
    """CPU adapter whose execute sleeps longer than any test deadline."""

    id = "slow-cpu"
    delay_s = 5.0

    def execute(self, workload: Workload):
        time.sleep(self.delay_s)
        return super().execute(workload)


class _FlakyProbeAdapter(Adapter):
    """Adapter whose probe can be flipped to simulate device loss."""

    id = "flaky-device"
    kind = AdapterKind.OPENCL
    priority = 50

    def __init__(self):
        self.available = True
        self.probes = 0

    def probe(self) -> AdapterAttestation:
        self.probes += 1
        record = {
            "adapter_id": self.id,
            "kind": self.kind.value,
            "available": self.available,
            "detail": {"probes": self.probes},
            "abi_version": "virtual_igpu_v1",
        }
        chain = extend_chain((), record)
        return AdapterAttestation(
            adapter_id=self.id,
            kind=self.kind.value,
            available=self.available,
            fingerprint=digest_json(record),
            chain_digest=chain[-1],
            detail=record["detail"],
        )

    def capabilities(self) -> CapabilityManifest:
        return CapabilityManifest(
            adapter_id=self.id,
            kind=self.kind.value,
            operations=(WorkloadKind.PROBE.value,),
            available=self.available,
            device_ids=(self.id,),
        )

    def execute(self, workload: Workload):
        started = time.time_ns()
        return self._result(workload, {"ok": True}, started)


def _daemon(adapters, tmp_path, name="rt"):
    return RuntimeDaemon(adapters=adapters, store_dir=str(tmp_path / name))


def _workload(**kw) -> Workload:
    return Workload(
        id=kw.pop("id", "w-lifecycle"),
        kind=WorkloadKind.PROBE,
        tenant=kw.pop("tenant", "t"),
        input=kw.pop("input", {}),
        execution_policy=kw.pop("execution_policy", ExecutionPolicy.PREFERRED_ACCELERATOR.value),
        **kw,
    )


def test_byte_quota_enforced(tmp_path):
    daemon = _daemon([CPUEmulatorAdapter()], tmp_path, "bq")
    daemon.quotas["t"] = Quota(max_workloads=100, max_bytes=10)
    with pytest.raises(RuntimeInvariantError, match="byte quota"):
        daemon.submit(_workload(input={"payload_utf8": "this payload is longer than ten bytes"}))


def test_byte_quota_counts_cumulatively(tmp_path):
    daemon = _daemon([CPUEmulatorAdapter()], tmp_path, "bq2")
    q = Quota(max_workloads=100, max_bytes=60)
    daemon.quotas["t"] = q
    daemon.submit(_workload(id="w1", input={"x": "small"}))
    assert q.submitted_bytes > 0
    with pytest.raises(RuntimeInvariantError, match="byte quota"):
        daemon.submit(_workload(id="w2", input={"x": "y" * 200}))


def test_workload_count_quota_still_enforced(tmp_path):
    daemon = _daemon([CPUEmulatorAdapter()], tmp_path, "cq")
    daemon.quotas["t"] = Quota(max_workloads=0)
    with pytest.raises(RuntimeInvariantError, match="quota"):
        daemon.submit(_workload())


def test_nonpositive_deadline_rejected(tmp_path):
    daemon = _daemon([CPUEmulatorAdapter()], tmp_path, "dl0")
    # Rejected at the ABI boundary (typed), before the daemon is reached.
    with pytest.raises(ValueError, match="deadline_ms"):
        _workload(deadline_ms=0)
    assert daemon.in_flight == {}


def test_deadline_records_timeout_not_success(tmp_path):
    daemon = _daemon([_SlowAdapter()], tmp_path, "dl")
    result = daemon.submit(_workload(deadline_ms=50))
    assert result.status == "timeout"
    assert "deadline" in (result.error or "")
    receipt = result.receipt or {}
    assert receipt.get("verification", {}).get("status") == "timeout"
    # A timed-out attempt must still produce evidence, not a fabricated success.
    assert result.evidence_digest


def test_deadline_passes_when_execution_fast_enough(tmp_path):
    daemon = _daemon([CPUEmulatorAdapter()], tmp_path, "dlok")
    result = daemon.submit(_workload(deadline_ms=10_000))
    assert result.status == "ok"


def test_recover_from_failed_returns_ready(tmp_path):
    adapter = _FlakyProbeAdapter()
    adapter.available = False
    daemon = _daemon([adapter], tmp_path, "rec")
    daemon.state = RuntimeState.FAILED
    adapter.available = True
    assert daemon.recover() == RuntimeState.READY
    result = daemon.submit(_workload())
    assert result.status == "ok"


def test_recovery_budget_is_bounded(tmp_path):
    adapter = _FlakyProbeAdapter()
    adapter.available = False
    daemon = _daemon([adapter], tmp_path, "recb")
    daemon.state = RuntimeState.FAILED
    daemon._max_recoveries = 2
    for _ in range(2):
        with pytest.raises(RuntimeInvariantError):
            daemon.recover()
        daemon.state = RuntimeState.FAILED
    with pytest.raises(RuntimeInvariantError, match="budget"):
        daemon.recover()
    assert daemon.state == RuntimeState.FAILED


def test_recover_when_no_adapter_available_fails_closed(tmp_path):
    adapter = _FlakyProbeAdapter()
    daemon = _daemon([adapter], tmp_path, "recf")
    daemon.state = RuntimeState.FAILED
    adapter.available = False
    with pytest.raises(RuntimeInvariantError, match="no adapter"):
        daemon.recover()
    assert daemon.state == RuntimeState.FAILED


def test_device_loss_reprobe_excludes_dead_adapter(tmp_path):
    """Device loss: a re-probe marks the vanished adapter unavailable and
    subsequent selection fails closed instead of dispatching to a ghost."""
    adapter = _FlakyProbeAdapter()
    cpu = CPUEmulatorAdapter()
    daemon = _daemon([adapter, cpu], tmp_path, "ghost")
    result = daemon.submit(_workload())
    assert result.actual_adapter_id == adapter.id
    adapter.available = False
    daemon.recover()  # READY re-probe refresh
    assert adapter.probes >= 2
    forced = _workload(
        id="w-forced",
        execution_policy=ExecutionPolicy.REQUIRED_ADAPTER.value,
        required_adapter_id=adapter.id,
    )
    with pytest.raises(AdapterUnavailable):
        daemon.submit(forced)
    # Preferred policy now routes to the surviving CPU adapter.
    result2 = daemon.submit(_workload(id="w-after"))
    assert result2.actual_adapter_id == cpu.id


def test_cancel_marks_result_cancelled_not_ok(tmp_path):
    """A workload cancelled in flight completes with status=cancelled — the
    device call may not be retractable, but the receipt never claims success."""
    import threading

    daemon = _daemon([_SlowAdapter()], tmp_path, "cx")
    w = _workload()
    box: dict = {}

    def _run():
        box["result"] = daemon.submit(w)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    deadline = time.time() + 5.0
    while w.id not in daemon._pending and time.time() < deadline:
        time.sleep(0.01)
    assert daemon.cancel(w.id) is True
    t.join(timeout=15.0)
    result = box["result"]
    assert result.status == "cancelled"
    assert (result.receipt or {}).get("verification", {}).get("status") == "cancelled"


def test_cancel_unknown_workload_returns_false(tmp_path):
    daemon = _daemon([CPUEmulatorAdapter()], tmp_path, "cx2")
    assert daemon.cancel("never-submitted") is False


def test_submit_from_failed_state_requires_recovery(tmp_path):
    adapter = _FlakyProbeAdapter()
    daemon = _daemon([adapter], tmp_path, "fstate")
    daemon.state = RuntimeState.FAILED
    with pytest.raises(RuntimeInvariantError, match="not ready"):
        daemon.submit(_workload())
