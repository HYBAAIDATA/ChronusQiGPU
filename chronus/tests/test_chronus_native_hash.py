"""Chronus native SHA-256d (CUDA / Metal) — fail-closed, no silent fallback."""
from __future__ import annotations

import hashlib

import numpy as np
import pytest

from chronus.native_hash import (
    NativeHashUnavailable,
    probe_cuda,
    probe_metal,
    reference_sha256d_batch,
    sha256d_batch,
    sha256d_batch_cuda,
    sha256d_batch_metal,
)
from mining.bitcoin_hasher import BitcoinHasher


def _cpu_digest(header: bytes, nonce: int) -> bytes:
    blob = bytearray(header)
    blob[76:80] = int(nonce).to_bytes(4, "little")
    return hashlib.sha256(hashlib.sha256(blob).digest()).digest()


@pytest.mark.unit
def test_reference_sha256d_matches_hashlib():
    header = bytes(range(80))
    nonces = [0, 1, 0x12345678, 0xFFFFFFFF]
    ref = reference_sha256d_batch(header, nonces)
    for i, n in enumerate(nonces):
        assert bytes(ref[i]) == _cpu_digest(header, n)


@pytest.mark.unit
def test_cuda_probe_returns_opencl_required_false():
    p = probe_cuda()
    assert p.backend_id == "chronus-cuda"
    assert p.opencl_required is False
    assert isinstance(p.available, bool)


@pytest.mark.unit
def test_metal_probe_returns_opencl_required_false():
    p = probe_metal()
    assert p.backend_id == "chronus-metal"
    assert p.opencl_required is False
    assert isinstance(p.available, bool)


@pytest.mark.unit
def test_unknown_native_backend_fails_closed():
    with pytest.raises(NativeHashUnavailable):
        sha256d_batch("opencl", bytes(range(80)), [0])


@pytest.mark.unit
def test_explicit_cuda_hasher_fails_closed_or_self_checks():
    """If CUDA is absent → fail closed. If present → hashlib-equal digests."""
    p = probe_cuda()
    if not p.available:
        with pytest.raises((NativeHashUnavailable, RuntimeError, Exception)):
            BitcoinHasher(backend="cuda")
        return
    h = BitcoinHasher(backend="cuda")
    assert h.backend == "cuda"
    assert h.opencl_required is False
    assert h.native_backend_id == "chronus-cuda"
    header = bytes(range(80))
    nonces = [0, 1, 7]
    got = h.hash_batch(header, nonces)
    exp = [_cpu_digest(header, n) for n in nonces]
    assert got == exp


@pytest.mark.unit
def test_explicit_metal_hasher_fails_closed():
    """Metal must not silently become OpenCL/CPU."""
    with pytest.raises((NativeHashUnavailable, RuntimeError, Exception)):
        # Either probe unavailable or kernel not bound — both fail closed
        BitcoinHasher(backend="metal")


@pytest.mark.unit
def test_no_silent_fallback_cuda_stays_cuda_or_raises():
    try:
        h = BitcoinHasher(backend="cuda")
    except Exception:
        return
    assert h.backend == "cuda"
    assert "opencl" not in h.backend
    assert h.backend != "cpu"
    assert h.opencl_required is False


@pytest.mark.unit
def test_cpu_hasher_still_works():
    h = BitcoinHasher(backend="cpu")
    assert h.backend == "cpu"
    header = bytes(range(80))
    assert h.hash_batch(header, [0])[0] == _cpu_digest(header, 0)


@pytest.mark.unit
def test_cuda_batch_api_conformance_when_available():
    p = probe_cuda()
    if not p.available:
        pytest.skip(f"CUDA unavailable: {p.reason}")
    header = bytes(range(80))
    nonces = np.asarray([0, 1, 2, 3], dtype=np.uint32)
    res = sha256d_batch_cuda(header, nonces)
    assert res.backend_id == "chronus-cuda"
    assert res.opencl_required is False
    assert res.hardware_rooted is False
    ref = reference_sha256d_batch(header, nonces)
    assert np.array_equal(res.digests, ref)


@pytest.mark.unit
def test_metal_batch_never_labels_cpu_as_metal():
    """Even if MLX is present, unbound kernel must not return CPU digests as Metal."""
    try:
        sha256d_batch_metal(bytes(range(80)), [0, 1])
        pytest.fail("Metal batch should fail closed until kernel is production-bound")
    except NativeHashUnavailable as exc:
        msg = str(exc).lower()
        assert "metal" in msg or "unavailable" in msg or "not yet" in msg
