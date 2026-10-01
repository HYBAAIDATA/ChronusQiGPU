"""Super-GPU surface regression tests — spec-named entry points.

``tests/test_chronus_fabric.py`` owns the (a)–(h) coverage contract for the
substrate itself; this file pins the spec-named surfaces that sit on top of
it: ``hyba.virtual_gpu.SuperGPU``, ``hyba.math_ir.emit_msl``, the
``benchmark_super_gpu`` alias, the per-device pin on
``OpenCLLadderExecutor``, explicit ``device_index`` dispatch in
``OpenCLDriver``, the dead ``iGPU_Accelerator_JV`` kernel path, and the
``super_gpu`` diagnose section. Everything here must pass GPU-less.
"""

from __future__ import annotations

import inspect
import runpy
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

from hyba.inventory import ClusterInventory, DeviceInfo


def cpu_device() -> DeviceInfo:
    return DeviceInfo(
        name="CPU (hashlib)",
        vendor="test",
        backend="cpu",
        type="cpu",
        compute_units=4,
        global_mem_mb=None,
        capabilities=(("hashlib_sha256d", True),),
    )


def synth_inventory(*devices: DeviceInfo) -> ClusterInventory:
    inv = ClusterInventory()
    inv.devices = list(devices) or [cpu_device()]
    return inv


# ---------------------------------------------------------------------------
# hyba.virtual_gpu.SuperGPU — the spec's composition surface
# ---------------------------------------------------------------------------


def test_super_gpu_is_the_chronus_fabric():
    from chronus.fabric import ChronusFabric
    from hyba.virtual_gpu import SuperGPU

    assert SuperGPU is ChronusFabric


def test_super_gpu_compose_and_route_shape():
    from hyba.virtual_gpu import SuperGPU

    sg = SuperGPU.compose(synth_inventory(cpu_device()))
    assert sg.compute_units >= 1
    decision = sg.route("sha256d_grind", {"work_items": 1024})
    # The spec's tuple fields: (device, capability, backend, lucas_dispatch).
    assert decision.device_name == "CPU (hashlib)"
    assert decision.backend == "cpu"
    assert decision.capability == "hashlib_sha256d"
    assert isinstance(decision.lucas_dispatch, dict)
    assert decision.lucas_dispatch["on_ladder"] is True


# ---------------------------------------------------------------------------
# emit_msl — generated canonical MSL, honest refusal elsewhere
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "spec,entry",
    [
        ("poincare_fold", "hyba_poincare_fold"),
        ("poincare_unfold", "hyba_poincare_unfold"),
        ("geodesic", "hyba_geodesic_distance"),
        ("cnormsq", "hyba_cnormsq"),
        ("lucas_pisot_scale", "mla1517_lucas_pisot_scale"),
    ],
)
def test_emit_msl_generates_supported_ops(spec, entry):
    from hyba.math_ir.emit_msl import emit_msl

    emitted = emit_msl(spec)
    assert emitted.entry == entry
    assert f"kernel void {entry}" in emitted.source
    assert "metal_stdlib" in emitted.source
    assert emitted.verified is False
    assert emitted.origin == "generated"


def test_emit_msl_ladder_entry_is_canonical_name():
    from hyba.math_ir.emit_msl import emit_msl

    emitted = emit_msl("lucas_pisot_scale")
    # byte-compatible entry name with the canonical .cl kernel
    canonical = REPO_ROOT / (
        "chronus/mla1517_platform/kernels/mla1517_lucas_pisot_scale.cl"
    )
    assert f"__kernel void {emitted.entry}" in canonical.read_text(
        encoding="utf-8"
    )


def test_emit_msl_refuses_f64_and_unknown_ops():
    from hyba.math_ir.emit_msl import NoCanonicalKernel, emit_msl
    from hyba.math_ir.specs import KERNEL_SPECS

    assert KERNEL_SPECS["phi_lattice_batch"].precision_bound == "f64"
    with pytest.raises(NoCanonicalKernel, match="f64"):
        emit_msl("phi_lattice_batch")
    for name, spec in KERNEL_SPECS.items():
        if name in (
            "poincare_fold",
            "poincare_unfold",
            "geodesic",
            "cnormsq",
            "lucas_pisot_scale",
        ):
            continue
        if spec.precision_bound == "f64":
            continue  # covered above
        with pytest.raises(NoCanonicalKernel):
            emit_msl(name)


# ---------------------------------------------------------------------------
# Per-device selection — pin contracts on the executors/drivers
# ---------------------------------------------------------------------------


def test_ladder_executor_accepts_device_pin():
    from chronus.mla1517.scaling import OpenCLLadderExecutor

    sig = inspect.signature(OpenCLLadderExecutor.__init__)
    assert "device" in sig.parameters


def test_ladder_executor_pin_resolution():
    from chronus.mla1517.scaling import (
        GPUExecutionUnavailable,
        _resolve_device_pin,
    )

    class _Dev:
        def __init__(self, name):
            self.name = name

    devices = [_Dev("igpu-0"), _Dev("dgpu-1")]
    assert _resolve_device_pin(devices, "DGPU-1") is devices[1]
    assert _resolve_device_pin(devices, devices[0]) is devices[0]
    assert _resolve_device_pin(devices, None) is None
    with pytest.raises(GPUExecutionUnavailable):
        _resolve_device_pin(devices, "no-such-device")


def test_opencl_driver_execute_kernel_exposes_device_index():
    from chronus.mla1517.mining.opencl_driver import OpenCLDriver

    sig = inspect.signature(OpenCLDriver.execute_kernel)
    assert "device_index" in sig.parameters
    assert sig.parameters["device_index"].default is None


def test_hasher_kernel_path_has_no_dead_candidates():
    import inspect as _inspect

    from mining.bitcoin_hasher import _resolve_kernel_path

    src = _inspect.getsource(_resolve_kernel_path)
    assert "iGPU_Accelerator_JV" not in src
    resolved = _resolve_kernel_path()
    assert resolved.is_file()
    assert resolved.name == "bitcoin_sha256d.cl"


def test_hasher_accepts_device_pin():
    from mining.bitcoin_hasher import BitcoinHasher

    sig = inspect.signature(BitcoinHasher.__init__)
    assert "device" in sig.parameters


# ---------------------------------------------------------------------------
# benchmark_super_gpu — spec-named alias of the canonical benchmark
# ---------------------------------------------------------------------------


def test_benchmark_super_gpu_alias_smoke(tmp_path, monkeypatch):
    out = tmp_path / "bench.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "benchmark_super_gpu.py",
            "--n",
            "2",
            "--nonce-space",
            "64",
            "--out",
            str(out),
        ],
    )
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(
            str(REPO_ROOT / "scripts" / "benchmark_super_gpu.py"),
            run_name="__main__",
        )
    assert exc.value.code == 0
    import json

    report = json.loads(out.read_text())
    assert "per_device" in report and "aggregate" in report
    # GPU-less host: no fabricated measured numbers.
    for record in report["per_device"]:
        assert record.get("measured") in (True, False)


# ---------------------------------------------------------------------------
# diagnose — the super_gpu section mirrors chronus_fabric, error-free
# ---------------------------------------------------------------------------


def test_diagnose_super_gpu_section():
    import hyba.diagnose

    report = hyba.diagnose.diagnose()
    assert "super_gpu" in report
    assert report["super_gpu"] is report["chronus_fabric"]
    for section in ("kernel_path", "punch_host", "hasher", "super_gpu"):
        assert "error" not in report[section], report[section]


def test_hyba_telemetry_reexports_canonical_names():
    import hyba.telemetry as t

    for name in (
        "attach_to_host",
        "get_telemetry",
        "reset_telemetry",
        "EUCLID_CHRONUS_TELEMETRY",
        "IGpuTelemetryCollector",
    ):
        assert hasattr(t, name), name
