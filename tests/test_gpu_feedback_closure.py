from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from aethel.gpu import ChronusContext
from aethel.manifold import PrimeStorageManifold
from chronus.mla1517.state import LogicalState
from chronus.opencl_host import (
    OpenClPunchHost,
    PunchUnsupported,
    PUNCH_MANIFOLD_COMPUTE,
    PUNCH_ZECKENDORF_ENCODE,
)
from chronus.seam import fleet
from chronus.seam.fleet import DeviceAssignment
from chronus.seam.hybrid import Window
from chronus.seam.probe import _default_kernels
from chronus.seam.types import (
    DeviceClass,
    Distribution,
    Err,
    KernelName,
    SeamError,
)

ROOT = Path(__file__).resolve().parents[1]


def test_punch_rejects_opcode_channel_mismatch_before_dispatch():
    with pytest.raises(PunchUnsupported):
        OpenClPunchHost._require_channel(PUNCH_MANIFOLD_COMPUTE, "ulong")
    with pytest.raises(PunchUnsupported):
        OpenClPunchHost._require_channel(PUNCH_ZECKENDORF_ENCODE, "float")


def test_capabilities_advertise_midstate_and_merkle_kernels():
    kernels = _default_kernels(DeviceClass.gpu_integrated)
    assert KernelName.sha256d_midstate in kernels
    assert KernelName.sha256d_merkle in kernels


def test_fleet_forwards_original_job_args(monkeypatch):
    seen = {}

    def fake_dispatch(caller, device_id, kernel, args, idempotency_key):
        seen.update(args)
        return Err(SeamError.unknown, "stop after capture")

    monkeypatch.setattr(fleet, "dispatch", fake_dispatch)
    assignment = DeviceAssignment(
        device_id="gpu-0",
        kernel=KernelName.sha256d_scan,
        window=Window(5, 9, KernelName.sha256d_scan),
        priority=0,
        deadline=None,
        cost_estimate=Distribution(1.0),
        fallback=False,
        args={"header": "abc", "target": 17},
        job_id="job-1",
        idempotency_key="job-1:scan:5",
    )
    fleet.execute("test", [assignment], [])
    assert seen["header"] == "abc"
    assert seen["target"] == 17
    assert seen["window"]["start"] == 5


def test_mla1517_digest_keeps_v1_domain():
    state = LogicalState(1, 2, 3, 5, 5, -1, 1, b"payload")
    h = hashlib.sha256()
    h.update(b"mla1517.state.v1")
    for value in (1, 2, 3, 5, 5):
        h.update(value.to_bytes(8, "little", signed=False))
    h.update((-1).to_bytes(8, "little", signed=True))
    h.update((1).to_bytes(8, "little", signed=False))
    h.update(b"payload")
    assert state.digest() == h.hexdigest()


class _FallbackHost:
    use_opencl = True
    backend = "opencl:test"
    last_dispatch_backend = "none"

    def run_punch_batch(self, opcode, n=None, in_float=None, in_ulong=None):
        self.last_dispatch_backend = "cpu_fallback"
        return {"float": np.zeros(11, dtype=np.float32)}


def test_strict_context_rejects_runtime_cpu_fallback():
    context = ChronusContext(punch_host=_FallbackHost(), allow_cpu_fallback=False)
    with pytest.raises(RuntimeError, match="CPU fallback is disabled"):
        context.project_and_collapse_pv(np.ones(11, dtype=np.float32))


def test_manifold_preserves_stricter_context_policy_and_reasons():
    context = ChronusContext(punch_host=_FallbackHost(), allow_cpu_fallback=False)
    manifold = PrimeStorageManifold(context, allow_cpu_fallback=True)
    assert manifold.allow_cpu_fallback is False
    with pytest.raises(RuntimeError, match="CPU fallback is disabled"):
        manifold._record_stage("decode", "cpu_fallback", "device verification failed")
    assert manifold.execution_evidence()["fallback_reasons"]["decode"] == "device verification failed"


def test_packaging_contract_includes_runtime_packages_and_specs():
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"Intelligence"' in project and '"mining"' in project
    assert '"spec/*.json"' in project
    packager = (ROOT / "chronus/mla1517_platform/scripts/package_release.py").read_text(encoding="utf-8")
    assert 'Path("python/chronus/mla1517")' in packager
