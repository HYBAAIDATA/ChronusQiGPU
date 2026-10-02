import sys
from types import SimpleNamespace

from chronus.tensor_compute import (
    _DeviceSelector,
    _device_score,
    _matches,
    _plan_1d,
    _plan_matmul,
    _pick_gpu,
)


def _device(name, vendor, unified, units=24, memory=4 << 30):
    return SimpleNamespace(
        name=name,
        vendor=vendor,
        host_unified_memory=unified,
        max_compute_units=units,
        global_mem_size=memory,
        max_clock_frequency=1100,
    )


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


def test_1d_launch_is_padded_and_bounded():
    assert _plan_1d(1000, 256) == ((1024,), (256,))
    assert _plan_1d(17, 64) == ((32,), (16,))


def test_matmul_launch_uses_igpu_local_memory_tile():
    assert _plan_matmul(31, 17, 256, 32 << 10) == ((32, 32), (16, 16))
    assert _plan_matmul(7, 9, 64, 512) == ((16, 8), (8, 8))


def test_requested_device_absence_fails_closed(monkeypatch):
    device = _device("Intel UHD Graphics 620", "Intel", True)
    device.type = 1
    platform = SimpleNamespace(
        name="Intel OpenCL", get_devices=lambda: [device]
    )
    fake_cl = SimpleNamespace(
        device_type=SimpleNamespace(GPU=1, ACCELERATOR=2),
        get_platforms=lambda: [platform],
    )
    monkeypatch.setitem(sys.modules, "pyopencl", fake_cl)
    monkeypatch.setenv("CHRONUS_OPENCL_DEVICE", "UHD Graphics 630")
    cl, selected, reason = _pick_gpu()
    assert cl is None and selected is None
    assert "requested OpenCL GPU identity not found" in reason