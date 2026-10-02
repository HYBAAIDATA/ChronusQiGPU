import sys
from types import SimpleNamespace

import pytest

from chronus.tensor_compute import (
    ChronusTensorRuntime,
    _DeviceSelector,
    _device_score,
    _matches,
    _plan_1d,
    _plan_matmul,
    _pick_gpu,
    _selector_from_env,
)


@pytest.fixture(autouse=True)
def _clean_selector_env(monkeypatch):
    for name in (
        "CHRONUS_OPENCL_PLATFORM",
        "CHRONUS_OPENCL_DEVICE",
        "HYBA_DEVICE_VENDOR",
        "HYBA_DEVICE_ALIAS",
        "HYBA_REQUIRE_HYBA",
    ):
        monkeypatch.delenv(name, raising=False)


def _device(name, vendor, unified, units=24, memory=4 << 30):
    return SimpleNamespace(
        name=name,
        vendor=vendor,
        host_unified_memory=unified,
        max_compute_units=units,
        global_mem_size=memory,
        max_clock_frequency=1100,
    )


def _gpu(name, vendor, unified, units=24, memory=4 << 30, wg=256, local=64 << 10):
    device = _device(name, vendor, unified, units=units, memory=memory)
    device.type = 1
    device.max_work_group_size = wg
    device.local_mem_size = local
    return device


def _fake_cl(devices):
    platform = SimpleNamespace(name="TestCL", get_devices=lambda: devices)
    return SimpleNamespace(
        device_type=SimpleNamespace(GPU=1, ACCELERATOR=2),
        get_platforms=lambda: [platform],
    )


class _FakeProgram:
    def __init__(self, kernels):
        self._kernels = kernels

    def build(self):
        return self

    def __getattr__(self, name):
        try:
            return self._kernels[name]
        except KeyError:
            raise AttributeError(name)


def _install_runtime_cl(monkeypatch, device, kernel_info=None, query_error=False):
    platform = SimpleNamespace(name="TestCL", get_devices=lambda: [device])

    def _kernel(_name):
        if query_error:

            def _raise(param, dev):
                raise RuntimeError("driver rejected query")

            return SimpleNamespace(get_work_group_info=_raise)
        limits = (kernel_info or {}).get(_name, {})
        return SimpleNamespace(get_work_group_info=lambda param, dev: limits.get(param, 0))

    kernels = {
        name: _kernel(name)
        for name in (
            "tensor_add_f32",
            "tensor_hadamard_f32",
            "tensor_scale_f32",
            "tensor_matmul_tiled_f32",
            "tensor_kron_1d_f32",
            "tensor_kron_2d_f32",
        )
    }
    fake_cl = SimpleNamespace(
        device_type=SimpleNamespace(GPU=1, ACCELERATOR=2),
        command_queue_properties=SimpleNamespace(PROFILING_ENABLE=1),
        kernel_work_group_info=SimpleNamespace(WORK_GROUP_SIZE=1, LOCAL_MEM_SIZE=2),
        get_platforms=lambda: [platform],
        Context=lambda devices: SimpleNamespace(devices=devices),
        CommandQueue=lambda context, properties=0: SimpleNamespace(),
        Program=lambda context, source: _FakeProgram(kernels),
    )
    monkeypatch.setitem(sys.modules, "pyopencl", fake_cl)


def test_explicit_intel_igpu_identity_matches():
    platform = SimpleNamespace(name="Intel OpenCL")
    device = _device("Intel(R) UHD Graphics 620", "Intel", True)
    selector = _DeviceSelector(vendor="intel", aliases=("intel",))
    assert _matches(platform, device, selector)
    assert not _matches(platform, device, _DeviceSelector(device="nvidia"))


def test_intel_integrated_gpu_is_preferred_by_default():
    platform = SimpleNamespace(name="OpenCL")
    intel = _device("Intel UHD Graphics 630", "Intel", True, units=24)
    discrete = _device("Discrete GPU", "Other", False, units=30)
    assert _device_score(platform, intel) > _device_score(platform, discrete)


def test_intel_discrete_graphics_is_not_scored_as_integrated():
    platform = SimpleNamespace(name="OpenCL")
    # Intel Arc-class discrete part: carries a "Graphics" product name but
    # reports no unified host memory, so it is not an iGPU and must not
    # outrank a genuinely shared-memory device.
    arc = _device("Intel(R) Arc(TM) A770 Graphics", "Intel", False, units=512)
    integrated = _device("Other Unified GPU", "Other", True, units=4)
    assert _device_score(platform, integrated) > _device_score(platform, arc)
    uhd = _device("Intel(R) UHD Graphics 620", "Intel", True, units=24)
    assert _device_score(platform, uhd) > _device_score(platform, arc)


def test_1d_launch_is_padded_and_bounded():
    assert _plan_1d(1000, 256) == ((1024,), (256,))
    assert _plan_1d(17, 64) == ((32,), (16,))


def test_matmul_launch_uses_igpu_local_memory_tile():
    assert _plan_matmul(31, 17, 256, 32 << 10) == ((32, 32), (16, 16))
    assert _plan_matmul(7, 9, 64, 512) == ((16, 8), (8, 8))


def test_requested_device_absence_fails_closed(monkeypatch):
    device = _device("Intel UHD Graphics 620", "Intel", True)
    device.type = 1
    platform = SimpleNamespace(name="Intel OpenCL", get_devices=lambda: [device])
    fake_cl = SimpleNamespace(
        device_type=SimpleNamespace(GPU=1, ACCELERATOR=2),
        get_platforms=lambda: [platform],
    )
    monkeypatch.setitem(sys.modules, "pyopencl", fake_cl)
    monkeypatch.setenv("CHRONUS_OPENCL_DEVICE", "UHD Graphics 630")
    cl, selected, reason = _pick_gpu()
    assert cl is None and selected is None
    assert "requested OpenCL GPU identity not found" in reason


def test_alias_is_not_explicit_without_require_hyba(monkeypatch):
    monkeypatch.setenv("HYBA_DEVICE_ALIAS", "definitely-absent-alias")
    monkeypatch.setenv("HYBA_REQUIRE_HYBA", "0")
    selector = _selector_from_env()
    assert selector.explicit is False
    device = _gpu("Other Vendor GPU", "Other", False)
    monkeypatch.setitem(sys.modules, "pyopencl", _fake_cl([device]))
    cl, selected, reason = _pick_gpu()
    assert cl is not None and selected is not None and reason == ""
    assert selected[1] is device


def test_alias_prefers_matching_device_when_not_required(monkeypatch):
    monkeypatch.setenv("HYBA_DEVICE_ALIAS", "mla1517")
    weak = _gpu("Custom MLA1517 iGPU", "Intel", True, units=8)
    strong = _gpu("Big Discrete", "Other", False, units=128)
    monkeypatch.setitem(sys.modules, "pyopencl", _fake_cl([strong, weak]))
    cl, selected, reason = _pick_gpu()
    assert selected is not None and selected[1] is weak


def test_alias_mismatch_fails_closed_when_require_hyba(monkeypatch):
    monkeypatch.setenv("HYBA_DEVICE_ALIAS", "hyba")
    monkeypatch.setenv("HYBA_REQUIRE_HYBA", "1")
    monkeypatch.setitem(sys.modules, "pyopencl", _fake_cl([_gpu("Other GPU", "Other", False)]))
    cl, selected, reason = _pick_gpu()
    assert cl is None and selected is None
    assert "requested OpenCL GPU identity not found" in reason


def test_require_hyba_uses_default_alias_set(monkeypatch):
    monkeypatch.setenv("HYBA_REQUIRE_HYBA", "true")
    hyba = _gpu("hyba-mla1517", "Intel", True)
    other = _gpu("Other GPU", "Other", False, units=128)
    monkeypatch.setitem(sys.modules, "pyopencl", _fake_cl([other, hyba]))
    cl, selected, reason = _pick_gpu()
    assert selected is not None and selected[1] is hyba


def test_require_hyba_without_alias_device_fails_closed(monkeypatch):
    monkeypatch.setenv("HYBA_REQUIRE_HYBA", "1")
    monkeypatch.setitem(sys.modules, "pyopencl", _fake_cl([_gpu("Other GPU", "Other", False)]))
    cl, selected, reason = _pick_gpu()
    assert cl is None and selected is None
    assert "requested OpenCL GPU identity not found" in reason


def test_launch_limits_respect_compiled_kernel_bounds(monkeypatch):
    device = _gpu("Intel UHD Graphics 620", "Intel", True, wg=256, local=64 << 10)
    _install_runtime_cl(monkeypatch, device, {"tensor_matmul_tiled_f32": {1: 64, 2: 1024}})
    runtime = ChronusTensorRuntime()
    group_limit, local_budget = runtime._launch_limits("tensor_matmul_tiled_f32")
    assert (group_limit, local_budget) == (64, (64 << 10) - 1024)
    assert _plan_matmul(31, 17, group_limit, local_budget) == ((24, 32), (8, 8))


def test_launch_limits_fall_back_to_device_limits_when_query_fails(monkeypatch):
    device = _gpu("Intel UHD Graphics 620", "Intel", True, wg=256, local=64 << 10)
    _install_runtime_cl(monkeypatch, device, query_error=True)
    runtime = ChronusTensorRuntime()
    assert runtime._launch_limits("tensor_matmul_tiled_f32") == (256, 64 << 10)
