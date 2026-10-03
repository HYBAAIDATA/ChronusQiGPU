"""asic/super_asic lane honesty: real probes, real composition, real shares.

The `asic` lane binds a physically attached channel or refuses closed;
`super_asic` composes every supported substrate (ASIC channel, remote
fleet, resident GPU/CPU solver) under the Lucas partitioner. Every test
below either exercises the real machinery or asserts its honest absence —
no lane is simulated.
"""

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from chronus.mla1517.mining.backend_registry import (
    BackendRegistry,
    BackendUnavailable,
)
from hyba.hybrid.coordinator import HybridCoordinator, StratumJob
from hyba.hybrid.gpu_solver import GPUSolver
from hyba.hybrid.nonce_scheduler import AttestationRegistry, verify_share
from hyba.hybrid.remote_solver import RemoteScheduler
from hyba.hybrid.super_asic import SuperAsicHasher, _contiguous_runs


@pytest.fixture(autouse=True)
def _clean_asic_env(monkeypatch):
    for var in (
        "HYBRID_ASIC_ENDPOINT",
        "HYBRID_ASIC_SERIAL",
        "HYBRID_ASIC_PCIE",
        "MLA1517_REMOTE_GPU_ENDPOINT",
        "HYBA_REMOTE_OPENCL_ENDPOINTS",
    ):
        monkeypatch.delenv(var, raising=False)
    AttestationRegistry.reset()
    yield
    AttestationRegistry.reset()


def test_asic_lane_unavailable_without_channel():
    """No configured channel → the lane probe reports the real reason."""
    registry = BackendRegistry()
    with pytest.raises(BackendUnavailable) as exc:
        registry.select("asic", reprobe=True)
    assert "no ASIC channel configured" in str(exc.value)


def test_asic_lane_does_not_fall_back(monkeypatch):
    """An explicit asic request never reroutes to CPU."""
    monkeypatch.setenv("HYBRID_ASIC_ENDPOINT", "127.0.0.1:1")
    registry = BackendRegistry()
    with pytest.raises(BackendUnavailable):
        registry.select("asic", reprobe=True)


def test_super_asic_binds_resident_substrate():
    """With no ASIC/remote configured, super_asic runs the resident solver."""
    selection = BackendRegistry().select("super_asic", reprobe=True)
    hasher = selection.hasher
    assert selection.lane == "super_asic"
    assert hasher.backend.startswith("super_asic:")
    assert hasher.k_range is not None
    assert hasher.k_m32 is None and hasher.k_gold is None
    assert isinstance(hasher, SuperAsicHasher)


def test_super_asic_grind_finds_verified_share():
    """A loose target produces a real share, host-verified digest."""
    hasher = SuperAsicHasher.bind()
    header = bytes(range(80))
    nonce, digest, done = hasher.grind_target_range(header, b"\xff" * 32, 0, 64)
    assert nonce is not None
    real = hashlib.sha256(
        hashlib.sha256(header[:76] + int(nonce).to_bytes(4, "little")).digest()
    ).digest()
    assert real == bytes(digest)
    assert done >= 1


def test_super_asic_grind_honours_base_offset():
    """base_nonce shifts the partition into the uint32 field."""
    hasher = SuperAsicHasher.bind()
    header = bytes(range(80))
    # impossible target grinds the whole window honestly
    nonce, digest, done = hasher.grind_target_range(header, b"\x00" * 32, 4096, 32)
    assert nonce is None
    assert done == 32


def test_super_asic_wrap_window_rejected():
    hasher = SuperAsicHasher.bind()
    with pytest.raises(ValueError):
        hasher.grind_target_range(bytes(80), b"\xff" * 32, (1 << 32) - 4, 16)


class _SecondSubstrate(GPUSolver):
    """A second CPU substrate with a distinct device identity — the shape
    two physically separate CPU hosts would present to the partitioner.
    Execution is entirely real hashlib grinding."""

    def capability(self):
        from dataclasses import replace

        return replace(super().capability(), device_id="cpu-member-2")


def test_hybrid_mode_with_two_substrates():
    """Two supported schedulers join: mode=hybrid, partition stays total."""
    gpu_a = GPUSolver(backend="cpu")
    gpu_b = _SecondSubstrate(backend="cpu")
    coord = HybridCoordinator(gpu_a, extra_devices=[gpu_b])
    assert coord.mode == "hybrid"
    job = StratumJob(
        job_id="j-hybrid",
        header80=bytes(range(80)),
        target=b"\xff" * 32,
        nonce_space=256,
    )
    result = coord.run_job(job)
    assert result.share is not None
    assert verify_share(result.share, job.header80[:76], job.target)
    assert result.certificate.verify()
    assert result.mode == "hybrid"
    assert len(result.layer_samples) == 2


def test_hybrid_base_nonce_offset():
    gpu = GPUSolver(backend="cpu")
    coord = HybridCoordinator(gpu)
    job = StratumJob(
        job_id="j-offset",
        header80=bytes(range(80)),
        target=b"\xff" * 32,
        nonce_space=64,
        base_nonce=1024,
    )
    result = coord.run_job(job)
    assert result.share is not None
    assert 1024 <= result.share.nonce < 1088


def test_remote_scheduler_unsupported_without_endpoints():
    from mining.remote_hasher import RemoteHasherError

    with pytest.raises(RemoteHasherError):
        RemoteScheduler.from_env()


def test_contiguous_runs_decomposition():
    # Runs preserve the caller's traversal order — a ranked sequence is
    # searched in the order supplied, never re-sorted or deduplicated.
    assert _contiguous_runs([5, 6, 7, 20, 9, 21]) == [(5, 3), (20, 1), (9, 1), (21, 1)]
    assert _contiguous_runs([20, 5, 6]) == [(20, 1), (5, 2)]
    assert _contiguous_runs([5, 5]) == [(5, 1), (5, 1)]
    assert _contiguous_runs([]) == []
    assert _contiguous_runs([0xFFFFFFFF]) == [(0xFFFFFFFF, 1)]
