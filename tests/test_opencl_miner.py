"""OpenCL iGPU miner adapter tests.

The kernel algorithm is validated on CPU via an exact Python twin (same
midstate decomposition the .cl kernel implements), and the adapter's
availability gating mirrors the other hardware backends. GPU execution
itself requires CHRONUS_ENABLE_OPENCL_MINER=1 on an OpenCL host.
"""

import hashlib
import random

import pytest

from chronus.backends.lattice import HardwareUnavailableError
from chronus.execution.asic_sha256 import _H0, sha256_block
from chronus.execution.opencl_sha256d import (
    OpenCLSha256dMinerBackend,
    _KERNEL_PATH,
)


def _kernel_twin(header: bytes, nonce: int) -> bytes:
    """CPU twin of sha256d_search.cl: identical midstate decomposition."""
    midstate = sha256_block(_H0, header[:64])
    # Outer block 2: header bytes 64..79 + padding + 640-bit length
    block2 = header[64:76] + nonce.to_bytes(4, "little")
    block2 = block2 + b"\x80" + b"\x00" * (64 - len(block2) - 8 - 1) + (640).to_bytes(8, "big")
    digest1_words = sha256_block(midstate, block2)
    digest1 = b"".join(w.to_bytes(4, "big") for w in digest1_words)
    # Inner block: 32-byte digest + padding + 256-bit length
    inner = digest1 + b"\x80" + b"\x00" * (64 - 32 - 8 - 1) + (256).to_bytes(8, "big")
    digest2_words = sha256_block(_H0, inner)
    return b"".join(w.to_bytes(4, "big") for w in digest2_words)


# ---------------------------------------------------------------------------
# Kernel algorithm correctness (CPU twin vs hashlib)
# ---------------------------------------------------------------------------


def test_kernel_twin_matches_hashlib_random_headers():
    rng = random.Random(20261108)
    for _ in range(25):
        header = rng.randbytes(80)
        nonce = rng.randrange(1 << 32)
        expected = hashlib.sha256(hashlib.sha256(header[:76] + nonce.to_bytes(4, "little")).digest()).digest()
        assert _kernel_twin(header, nonce) == expected


def test_kernel_twin_matches_genesis_block():
    from tests.test_stratum_pool import (
        GENESIS_BLOCK_HASH,
        GENESIS_JOB,
        GENESIS_NONCE,
        GENESIS_SESSION,
    )
    from chronus.execution.stratum import build_header

    header = build_header(GENESIS_JOB, b"", GENESIS_SESSION, 0)
    assert _kernel_twin(header, GENESIS_NONCE)[::-1].hex() == GENESIS_BLOCK_HASH


def test_build_kernel_args_matches_twin_preprocessing():
    header = bytes(range(80))
    midstate, tail, target_words = OpenCLSha256dMinerBackend.build_kernel_args(
        header, target=0x00FFFF << 208, base_nonce=7
    )
    assert midstate == sha256_block(_H0, header[:64])
    assert tail == [
        int.from_bytes(header[64:68], "big"),
        int.from_bytes(header[68:72], "big"),
        int.from_bytes(header[72:76], "big"),
    ]
    target = 0x00FFFF << 208
    assert target_words == [(target >> (32 * i)) & 0xFFFFFFFF for i in range(8)]


def test_build_kernel_args_validation():
    backend = OpenCLSha256dMinerBackend()
    with pytest.raises(ValueError):
        backend.build_kernel_args(b"short", 1, 0)
    with pytest.raises(ValueError):
        backend.build_kernel_args(bytes(80), 1 << 256, 0)
    with pytest.raises(ValueError):
        backend.build_kernel_args(bytes(80), 1, 1 << 32)


# ---------------------------------------------------------------------------
# Availability gating (no GPU in CI)
# ---------------------------------------------------------------------------


def test_adapter_unavailable_without_env_flag(monkeypatch):
    monkeypatch.delenv("CHRONUS_ENABLE_OPENCL_MINER", raising=False)
    backend = OpenCLSha256dMinerBackend()
    assert backend.is_available() is False
    assert backend.supports("SHA256D_NONCE_SEARCH") is False
    with pytest.raises(HardwareUnavailableError):
        backend.search(bytes(80), 0, 16, (1 << 256) - 1)
    with pytest.raises(HardwareUnavailableError):
        backend.execute(bytes(80), "SHA256D_NONCE_SEARCH")


def test_adapter_unavailable_without_pyopencl(monkeypatch):
    monkeypatch.setenv("CHRONUS_ENABLE_OPENCL_MINER", "1")
    import builtins

    real_import = builtins.__import__

    def _blocked(name, *args, **kwargs):
        if name == "pyopencl":
            raise ImportError("pyopencl not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked)
    backend = OpenCLSha256dMinerBackend()
    assert backend.is_available() is False


def test_queue_status_shape(monkeypatch):
    monkeypatch.delenv("CHRONUS_ENABLE_OPENCL_MINER", raising=False)
    status = OpenCLSha256dMinerBackend().get_queue_status()
    assert status["available"] is False
    assert status["device"] is None
    assert status["kernel"] == "sha256d_search.cl"


def test_dispatcher_registers_igpu_miner_backend(monkeypatch):
    monkeypatch.delenv("CHRONUS_ENABLE_OPENCL_MINER", raising=False)
    from chronus.execution.hardware_dispatcher import HardwareAcceleratorDispatcher

    dispatcher = HardwareAcceleratorDispatcher()
    discovered = dispatcher.discover_backends()
    assert "opencl-igpu-sha256d-miner" in discovered
    entry = discovered["opencl-igpu-sha256d-miner"]
    assert entry["available"] is False
    assert entry["runtime_classification"] == "PHYSICAL_HARDWARE_EXECUTION"
    assert entry["supported_workloads"] == ["SHA256D_NONCE_SEARCH"]


# ---------------------------------------------------------------------------
# Kernel source purity gate
# ---------------------------------------------------------------------------


def test_kernel_source_is_integer_only_and_complete():
    source = _KERNEL_PATH.read_text()
    assert "__kernel void sha256d_search" in source
    # CI purity gate: zero floating point in mining kernels
    for token in ("float", "double", "half"):
        assert token not in source.replace("floats", ""), f"floating point token {token!r} in kernel"
    # All 64 FIPS 180-4 round constants present
    assert source.count("0x") > 64
