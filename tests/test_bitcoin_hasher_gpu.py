"""Kernel packaging regressions and forced-device SHA-256d verification."""

import hashlib
import struct

import numpy as np
import pytest

import mining.bitcoin_hasher as hasher_module


def test_kernel_resolution_uses_chronus_package(tmp_path, monkeypatch):
    monkeypatch.setattr(hasher_module, "__file__", str(tmp_path / "mining" / "bitcoin_hasher.py"))
    packaged = tmp_path / "chronus" / "kernels" / "bitcoin_sha256d.cl"
    packaged.parent.mkdir(parents=True)
    packaged.write_text("// packaged kernel", encoding="utf-8")
    assert hasher_module._resolve_kernel_path() == packaged


def test_kernel_resolution_prefers_root_layout(tmp_path, monkeypatch):
    monkeypatch.setattr(hasher_module, "__file__", str(tmp_path / "mining" / "bitcoin_hasher.py"))
    canonical = tmp_path / "kernels" / "bitcoin_sha256d.cl"
    packaged = tmp_path / "chronus" / "kernels" / "bitcoin_sha256d.cl"
    for path in (canonical, packaged):
        path.parent.mkdir(parents=True)
        path.write_text("// kernel", encoding="utf-8")
    assert hasher_module._resolve_kernel_path() == canonical


def test_missing_kernel_reports_checked_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(hasher_module, "__file__", str(tmp_path / "mining" / "bitcoin_hasher.py"))
    with pytest.raises(FileNotFoundError, match="SHA-256d kernel not found") as exc:
        hasher_module._resolve_kernel_path()
    assert str(tmp_path / "kernels" / "bitcoin_sha256d.cl") in str(exc.value)
    assert str(tmp_path / "chronus" / "kernels" / "bitcoin_sha256d.cl") in str(
        exc.value
    )


def test_forced_gpu_hashes_match_hashlib():
    cl = pytest.importorskip("pyopencl")
    try:
        platforms = cl.get_platforms()
    except cl.LogicError as exc:
        if exc.code == -1001:  # CL_PLATFORM_NOT_FOUND_KHR
            pytest.skip("No OpenCL platform installed")
        raise
    devices = [device for platform in platforms for device in platform.get_devices()]
    if not any(device.type & cl.device_type.GPU for device in devices):
        pytest.skip("No OpenCL GPU available")

    # Do not catch initialization/build errors or permit CPU fallback here.
    hasher = hasher_module.BitcoinHasher(backend="gpu")
    assert hasher.backend == "opencl:gpu"
    assert hasher.fallback_reason is None
    launches = hasher.launches
    rng = np.random.default_rng(1517)
    nonces = [0, 1, 0x12345678, 0xFFFFFFFF]
    nonces += rng.integers(0, 2**32, 1024, dtype=np.uint32).tolist()
    for _ in range(3):
        header = rng.integers(0, 256, 80, dtype=np.uint8).tobytes()
        expected = []
        for nonce in nonces:
            blob = header[:76] + struct.pack("<I", nonce)
            expected.append(hashlib.sha256(hashlib.sha256(blob).digest()).digest())
        assert hasher.hash_batch(header, nonces) == expected
    evidence = hasher.telemetry()
    assert evidence["launches"] == launches + 3
    assert evidence["kernel_ms"] > 0
    assert evidence["device"] == hasher.device
