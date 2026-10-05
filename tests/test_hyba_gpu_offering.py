"""HYBA GPU offering readiness — Chronus product, mining is not."""
from __future__ import annotations

import pytest

from chronus.hyba_offering import (
    HYBA_FLEET_DESIGN_TARGET_HS,
    assert_hyba_gpu_software_ready,
    prepare_hyba_gpu,
)
from chronus.virtual_igpu.abi import ExecutionPolicy, TrustClass, Workload, WorkloadKind
from chronus.virtual_igpu.adapters import CPUEmulatorAdapter
from chronus.virtual_igpu.runtime import RuntimeDaemon
from chronus.paradigm.honesty import _LyingHardwareAdapter, run_honesty_chaos


@pytest.mark.unit
def test_liar_hardware_root_is_downgraded(tmp_path):
    d = RuntimeDaemon(
        adapters=[_LyingHardwareAdapter(), CPUEmulatorAdapter()],
        store_dir=tmp_path / "liar",
    )
    d.attach()
    w = Workload(
        id="liar-check",
        kind=WorkloadKind.STORE,
        tenant="t",
        input={"payload_utf8": "lie"},
        execution_policy=ExecutionPolicy.PREFERRED_ACCELERATOR.value,
        allow_software_fallback=True,
    )
    result = d.submit(w)
    assert result.hardware_rooted is False
    assert result.trust_class != TrustClass.HARDWARE_ROOTED.value


@pytest.mark.unit
def test_honesty_chaos_green(tmp_path):
    report = run_honesty_chaos(store_dir=tmp_path / "hon")
    failed = [c for c in report.cases if not c.passed]
    assert report.ok, f"honesty failures: {failed}"


@pytest.mark.unit
def test_prepare_hyba_gpu_software_ready():
    report = prepare_hyba_gpu()
    assert report.product == "Chronus"
    assert report.consumer == "HYBA"
    assert report.mining_is_product is False
    assert report.design_target_hs == HYBA_FLEET_DESIGN_TARGET_HS
    assert report.design_target_kind == "design_envelope_not_measured"
    assert report.ok, report.as_dict()
    data = assert_hyba_gpu_software_ready(report)
    assert data["ok"] is True
    assert "live_opencl_device_measurement" in data["gaps"]
