"""Unit tests for the unrolled SHA-256 engine and hardware backend adapters.

Covers asic_sha256 (FIPS 180-4 vectors), CUDA/OpenCL adapters (unavailable
and env-enabled paths), and the SystemVerilog Zeckendorf simulator.
"""

import hashlib
import json

import pytest

from chronus.backends.lattice import HardwareUnavailableError
from chronus.execution.asic_sha256 import (
    sha256_block,
    sha256_unrolled,
    sha256d_unrolled,
    _H0,
)
from chronus.execution.cuda_backend import CUDABackendAdapter
from chronus.execution.opencl_backend import OpenCLAcceleratorBackend
from chronus.execution.systemverilog_backend import (
    SystemVerilogHardwareSimulatorBackend,
)


# ---------------------------------------------------------------------------
# asic_sha256 — FIPS 180-4 exactness
# ---------------------------------------------------------------------------


def test_sha256_empty_message_vector():
    assert sha256_unrolled(b"").hex() == hashlib.sha256(b"").hexdigest()
    assert sha256_unrolled(b"").hex() == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_sha256_abc_vector():
    assert sha256_unrolled(b"abc").hex() == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_sha256_two_block_vector():
    msg = b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"
    assert sha256_unrolled(msg).hex() == (
        "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"
    )


def test_sha256_matches_hashlib_across_block_boundaries():
    for length in (0, 1, 55, 56, 57, 63, 64, 65, 119, 120, 128, 1000):
        data = bytes(range(256))[:length] * (length // 256 + 1)
        data = data[:length]
        assert sha256_unrolled(data) == hashlib.sha256(data).digest()


def test_sha256d_matches_hashlib_double():
    data = b"Bitcoin style double hash"
    expected = hashlib.sha256(hashlib.sha256(data).digest()).digest()
    assert sha256d_unrolled(data) == expected


def test_sha256_rejects_non_bytes():
    with pytest.raises(TypeError):
        sha256_unrolled("abc")


def test_sha256_block_validates_shapes():
    with pytest.raises(ValueError):
        sha256_block(_H0, b"\x00" * 63)
    with pytest.raises(ValueError):
        sha256_block(_H0[:7], b"\x00" * 64)


def test_sha256_k_table_derives_from_prime_cube_roots():
    """K constants must be the fractional parts of cube roots of primes."""

    def _primes(n):
        out, candidate = [], 2
        while len(out) < n:
            if all(candidate % p for p in out if p * p <= candidate):
                out.append(candidate)
            candidate += 1
        return out

    from chronus.execution.asic_sha256 import _K

    for prime, k in zip(_primes(64), _K):
        # Exact: K = floor(frac(cbrt(p)) * 2^32). Compute integer cube root c,
        # then binary-search the largest m with (c*2^32 + m)^3 <= p*2^96.
        c = round(prime ** (1 / 3))
        while c * c * c > prime:
            c -= 1
        while (c + 1) ** 3 <= prime:
            c += 1
        target = prime << 96
        base = c << 32
        lo, hi = 0, 1 << 32
        while lo + 1 < hi:
            mid = (lo + hi) // 2
            if (base + mid) ** 3 <= target:
                lo = mid
            else:
                hi = mid
        assert lo == k


# ---------------------------------------------------------------------------
# CUDA backend adapter
# ---------------------------------------------------------------------------


def test_cuda_unavailable_raises(monkeypatch):
    monkeypatch.delenv("CHRONUS_ENABLE_CUDA", raising=False)
    backend = CUDABackendAdapter()
    assert backend.is_available() is False
    assert backend.supports("PV_LATTICE_FOLD") is False
    with pytest.raises(HardwareUnavailableError):
        backend.execute(b"payload", "PV_LATTICE_FOLD")


def test_cuda_enabled_path(monkeypatch):
    monkeypatch.setenv("CHRONUS_ENABLE_CUDA", "1")
    backend = CUDABackendAdapter()
    assert backend.is_available() is True
    assert backend.supports("PV_LATTICE_FOLD") is True
    assert backend.supports("UNKNOWN_WORKLOAD") is False


def test_cuda_payload_memory_limit(monkeypatch):
    monkeypatch.setenv("CHRONUS_ENABLE_CUDA", "1")
    backend = CUDABackendAdapter(max_device_memory_bytes=8)
    with pytest.raises(ValueError, match="memory limit"):
        backend.execute(b"012345678", "PV_LATTICE_FOLD")


def test_cuda_queue_status_accounting(monkeypatch):
    monkeypatch.setenv("CHRONUS_ENABLE_CUDA", "1")
    backend = CUDABackendAdapter()
    status = backend.get_queue_status()
    assert status["active_queue_depth"] == 0
    assert status["available_bytes"] == backend.max_device_memory_bytes


# ---------------------------------------------------------------------------
# OpenCL backend adapter
# ---------------------------------------------------------------------------


def test_opencl_unavailable_raises(monkeypatch):
    monkeypatch.delenv("CHRONUS_ENABLE_OPENCL_PV", raising=False)
    backend = OpenCLAcceleratorBackend()
    assert backend.is_available() is False
    with pytest.raises(HardwareUnavailableError):
        backend.execute(b"{}", "PV_LATTICE_FOLD")


def test_opencl_supports_only_when_available(monkeypatch):
    monkeypatch.setenv("CHRONUS_ENABLE_OPENCL_PV", "1")
    backend = OpenCLAcceleratorBackend()
    assert backend.supports("PV_LATTICE_FOLD") is True
    assert backend.supports("SHA256D_NONCE_SEARCH") is False


def test_opencl_payload_memory_limit(monkeypatch):
    monkeypatch.setenv("CHRONUS_ENABLE_OPENCL_PV", "1")
    backend = OpenCLAcceleratorBackend(max_device_memory_bytes=4)
    with pytest.raises(ValueError, match="memory limit"):
        backend.execute(b"12345", "PV_LATTICE_FOLD")


def test_opencl_queue_status_shape(monkeypatch):
    monkeypatch.delenv("CHRONUS_ENABLE_OPENCL_PV", raising=False)
    status = OpenCLAcceleratorBackend().get_queue_status()
    assert status["queue_depth"] == 0
    assert status["available"] is False


# ---------------------------------------------------------------------------
# SystemVerilog Zeckendorf simulator
# ---------------------------------------------------------------------------


def test_sv_simulator_rejects_over_32_lanes():
    sim = SystemVerilogHardwareSimulatorBackend()
    with pytest.raises(ValueError, match="32 lanes"):
        sim.simulate_32lane_reduction([1] * 33)


def test_sv_simulator_zero_lanes_all_canonical():
    sim = SystemVerilogHardwareSimulatorBackend()
    result = sim.simulate_32lane_reduction([])
    assert result["lane_count"] == 32
    assert result["all_canonical"] is True
    assert result["folded_outputs"] == [0] * 32


def test_sv_simulator_fold_is_idempotent():
    sim = SystemVerilogHardwareSimulatorBackend()
    lanes = [1, 2, 3, 5, 8, 13, 21, 100, 999]
    first = sim.simulate_32lane_reduction(lanes)["folded_outputs"]
    second = sim.simulate_32lane_reduction(first[:9])["folded_outputs"]
    assert first[: len(second)] == second or first == sim.simulate_32lane_reduction(
        first
    )["folded_outputs"]


def test_sv_execute_rejects_unsupported_workload():
    sim = SystemVerilogHardwareSimulatorBackend()
    with pytest.raises(ValueError, match="does not support"):
        sim.execute(b"{}", "GROVER_SEARCH")


def test_sv_execute_rejects_non_json():
    sim = SystemVerilogHardwareSimulatorBackend()
    with pytest.raises(ValueError, match="valid JSON"):
        sim.execute(b"\xff\xfe not json", "ZECKENDORF_ALU_SIM")


def test_sv_execute_alu_sim_roundtrip():
    sim = SystemVerilogHardwareSimulatorBackend()
    payload = json.dumps({"lanes": [0, 1, 1, 2, 3]}).encode()
    result = sim.execute(payload, "ZECKENDORF_ALU_SIM")
    assert result["backend"] == "systemverilog-rtl-simulator"
    assert result["runtime_classification"] == "SOFTWARE_EXECUTION"
    assert result["result"]["lane_count"] == 32


def test_sv_execute_norm_sim():
    sim = SystemVerilogHardwareSimulatorBackend()
    payload = json.dumps({"a": 5, "b": 3}).encode()
    result = sim.execute(payload, "ZECKENDORF_NORM_SIM")
    a, b = result["folded_pair"]
    assert result["norm"] == a * a + a * b - b * b
