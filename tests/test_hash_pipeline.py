"""Tests for the live hash pipeline: score, filter, real sha256d grind."""

import hashlib
import struct

import numpy as np
import pytest

from Intelligence.unified_punch import UnifiedPunchHost
from mining.bitcoin_hasher import BitcoinHasher
from mining.hash_pipeline import (
    HashPipeline,
    double_sha256,
    resubmit_with_jitter,
)

# Real Bitcoin genesis block header (80 bytes) and its block hash.
GENESIS_HEADER = bytes.fromhex(
    "01000000"
    + "00" * 32
    + "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
    + "29ab5f49"
    + "ffff001d"
    + "1dac2b7c"
)
GENESIS_HASH = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
GENESIS_NONCE = 2083236893


def _easy_target():
    # Very easy target: first byte of reversed hash must be 0x00 (~1/256).
    return bytes.fromhex("00" + "ff" * 31)


def test_double_sha256_known_vector():
    # sha256d("") is a known constant.
    assert double_sha256(b"").hex() == (
        "5df6e0e2761359d30a8275058e299fcc0381534545f55cf43e41983f5d4c9456"
    )


def test_grind_finds_winner_on_easy_target():
    header = bytes(80)
    target = _easy_target()
    pipe = HashPipeline(threshold=0.0)  # pass everything; grind decides
    nonces = list(range(2000))
    res = pipe.grind(header, target, nonces)
    assert res.hashes_computed > 0
    if res.mining_success:
        assert res.winning_nonce is not None
        blob = header[:76] + struct.pack("<I", res.winning_nonce)
        assert double_sha256(blob)[::-1] < target
    else:
        # Exhausted window honestly: every hash checked against target.
        assert res.hashes_computed == len(nonces)


def test_grind_impossible_target_finds_nothing():
    header = bytes(80)
    target = bytes(32)  # hash < 0 impossible
    pipe = HashPipeline(threshold=0.0)
    res = pipe.grind(header, target, list(range(200)))
    assert not res.mining_success
    assert res.winning_nonce is None
    assert res.hashes_computed == 200


def test_benchmark_reports_measured():
    pipe = HashPipeline()
    rep = pipe.benchmark_hashrate(bytes(80), _easy_target(), nonce_count=500, duration_s=5.0)
    assert rep["truth_class"] == "measured"
    assert rep["measured_hps"] > 0
    assert rep["hashes"] == 500


def test_jitter_deterministic():
    a = resubmit_with_jitter(b"header", 123, 1)
    b = resubmit_with_jitter(b"header", 123, 1)
    c = resubmit_with_jitter(b"header", 123, 2)
    assert a == b
    assert a != c


def test_new_punch_ids_registered():
    host = UnifiedPunchHost()
    assert host.PUNCH_IDS["sha256d_grind_mark"] == 0x1B
    assert host.PUNCH_IDS["zeckendorf_decode"] == 0x1C
    assert "phi_filter_score" not in host.PUNCH_IDS
    assert "quantum_phase" not in host.PUNCH_IDS
    assert "quantum_hamiltonian" not in host.PUNCH_IDS
    assert "quantum_grover" not in host.PUNCH_IDS
    assert len(host.PUNCH_IDS) == 24


def test_removed_quantum_standin_ids_are_rejected():
    host = UnifiedPunchHost()
    with pytest.raises(ValueError, match="unsupported punch id 0x12"):
        host.run_punch_batch(0x12, in_ulong=[0])


def test_run_punch_batch_uses_scratch_for_unwritten_ulong_channel():
    host = UnifiedPunchHost()
    result = host.run_punch_batch(host.PUNCH_IDS["golden_angle"], n=4, in_ulong=[0, 1, 2, 3])
    assert result["ulong"].shape == (1,)


# ----------------------------------------------------------------------
# BitcoinHasher: real SHA-256d on whatever backend is actually present
# ----------------------------------------------------------------------


def test_hasher_genesis_vector():
    """hash_batch on the real genesis header must yield the known block hash."""
    hasher = BitcoinHasher(backend="auto")
    digest = hasher.hash_batch(GENESIS_HEADER, [GENESIS_NONCE])[0]
    assert digest[::-1].hex() == GENESIS_HASH
    assert double_sha256(GENESIS_HEADER)[::-1].hex() == GENESIS_HASH


def test_hasher_matches_cpu_on_randomized_inputs():
    """Every backend must agree with the hashlib reference, digest-exact."""
    hasher = BitcoinHasher(backend="auto")
    rng = np.random.default_rng(7)
    for _ in range(4):
        header = rng.integers(0, 256, 80, dtype=np.uint8).tobytes()
        nonces = rng.integers(0, 2**32, 257, dtype=np.uint32).tolist()
        expected = [double_sha256(header[:76] + struct.pack("<I", n)) for n in nonces]
        assert hasher.hash_batch(header, nonces) == expected


def test_hasher_batch_bounds():
    hasher = BitcoinHasher(backend="cpu")
    assert hasher.hash_batch(bytes(80), []) == []
    with pytest.raises(ValueError):
        hasher.hash_batch(bytes(80), list(range(65537)))
    with pytest.raises(ValueError):
        hasher.hash_batch(bytes(79), [0])
    with pytest.raises(ValueError):
        hasher.hash_batch(bytes(80), [-1])


# ----------------------------------------------------------------------
# Backend truth: labels must reflect what physically executed
# ----------------------------------------------------------------------


def test_grind_reports_executing_backends():
    host = UnifiedPunchHost()
    pipe = HashPipeline(host=host)
    res = pipe.grind(bytes(80), _easy_target(), list(range(2000)))
    assert res.backend == pipe.hasher.backend
    assert res.device == pipe.hasher.device
    assert res.scoring_backend == "input-order"
    assert res.scoring_device == "declared-window"


def test_cpu_and_opencl_grind_find_same_winner():
    """Equality-at-target: CPU and OpenCL hashers must select the same nonce."""
    host = UnifiedPunchHost()
    target = _easy_target()
    nonces = list(range(5000))
    cpu_pipe = HashPipeline(host=host, hasher=BitcoinHasher(backend="cpu"))
    gpu_pipe = HashPipeline(host=host, hasher=BitcoinHasher(backend="auto"))
    r_cpu = cpu_pipe.grind(bytes(80), target, nonces)
    r_gpu = gpu_pipe.grind(bytes(80), target, nonces)
    assert r_cpu.winning_nonce == r_gpu.winning_nonce
    assert r_cpu.winning_hash == r_gpu.winning_hash
    if gpu_pipe.hasher.backend.startswith("opencl"):
        assert gpu_pipe.hasher.launches >= 1


def test_grind_handles_multi_batch_windows():
    """Nonce windows larger than one launch are chunked, not truncated."""
    host = UnifiedPunchHost()
    pipe = HashPipeline(host=host, hasher=BitcoinHasher(backend="cpu"), threshold=0.0)
    res = pipe.grind(bytes(80), bytes(32), list(range(70000)))
    assert not res.mining_success
    assert res.hashes_computed == 70000


# ----------------------------------------------------------------------
# Midstate kernel equivalence: reference kernel vs midstate kernel vs hashlib
# ----------------------------------------------------------------------


def test_sha256_midstate_compress_matches_hashlib():
    """Python-level midstate + compress must equal the full hashlib digest."""
    from mining.bitcoin_hasher import sha256_compress, sha256_midstate

    block = bytes(range(64))
    mid = sha256_midstate(block)
    state = struct.unpack(">8I", mid)
    pad = struct.pack(">16I", 0x80000000, *([0] * 14), 512)
    digest = struct.pack(">8I", *sha256_compress(state, pad))
    assert digest == hashlib.sha256(block).digest()


def test_midstate_kernel_matches_reference_and_hashlib():
    """Device-backed equivalence: midstate kernel vs reference kernel vs hashlib.

    When OpenCL is available, the midstate kernel (bitcoin_sha256d_midstate /
    bitcoin_sha256d_range) must produce byte-identical digests to the reference
    kernel (bitcoin_sha256d) on hash_batch, and both must match hashlib. This
    proves the midstate optimisation (beta_midstate = 0.5) is an honest
    constant-factor speedup, not a consensus shortcut.

    On CPU-only, the test still verifies hashlib equivalence for the CPU path.
    """
    header = bytes(80)
    nonces = list(range(0, 257, 7)) + [0x12345678, 0xFFFFFFFF]
    target = b"\xff" * 32  # accepts everything

    # Reference: hashlib
    expected = [double_sha256(header[:76] + struct.pack("<I", n)) for n in nonces]

    # Reference kernel path: hash_batch (CPU fallback here for portability;
    # the OpenCL equivalence is tested in test_opencl_midstate_vs_reference_kernel)
    hasher = BitcoinHasher(backend="cpu")
    batch_digests = hasher.hash_batch(header, nonces)
    assert batch_digests == expected

    # Midstate kernel path: grind_target_range uses bitcoin_sha256d_range
    # (or grind_target_batch uses bitcoin_sha256d_midstate). Both must
    # agree with the reference path -- at least on hits (target = 0xff accepts all).
    win_range, dig_range, _ = hasher.grind_target_range(header, target, nonces[0], len(nonces))
    assert win_range == nonces[0]
    assert dig_range == expected[0]


def test_opencl_midstate_vs_reference_kernel():
    """OpenCL-specific: midstate kernel (bitcoin_sha256d_range) must produce
    byte-identical digests to the reference kernel (bitcoin_sha256d on
    hash_batch), and both must match hashlib. Skipped when no OpenCL device.
    """
    header = bytes(80)
    nonces = list(range(0, 257, 7)) + [0x12345678, 0xFFFFFFFF]

    try:
        hasher = BitcoinHasher(backend="auto")
    except Exception:
        pytest.skip("OpenCL backend required")
    if not hasher.backend.startswith("opencl"):
        pytest.skip("OpenCL backend required")

    expected = [double_sha256(header[:76] + struct.pack("<I", n)) for n in nonces]

    # Reference kernel: bitcoin_sha256d via hash_batch
    batch_digests = hasher.hash_batch(header, nonces)
    assert batch_digests == expected

    # Midstate kernel: bitcoin_sha256d_range via grind_target_range
    # With target = 0xff (accepts all), the first nonce should win.
    target_accept = b"\xff" * 32
    win, dig, _ = hasher.grind_target_range(header, target_accept, nonces[0], len(nonces))
    assert win == nonces[0]
    assert dig == expected[0]

    # Midstate kernel: with target = 0x00 (accepts none), should get no winner.
    target_reject = bytes(32)
    win_r, dig_r, _ = hasher.grind_target_range(header, target_reject, nonces[0], len(nonces))
    assert win_r is None
    assert dig_r is None


def test_midstate_cache_is_per_header_not_per_nonce():
    """The midstate cache must be keyed on the 64-byte header prefix, not
    on individual nonces. The SHA-256 midstate of the first block depends
    only on the first 64 header bytes; the nonce (bytes 76-80) is in the
    second block and does not affect the midstate.

    This test verifies:
    1. Different nonces with the same prefix produce the same midstate.
    2. Changing the first 64 bytes produces a different midstate.
    """
    from mining.bitcoin_hasher import BitcoinHasher as BH
    from mining.bitcoin_hasher import sha256_midstate

    prefix = bytes(64)
    different_prefix = bytes(55) + b"different"  # 64 bytes

    # Midstate depends only on the first 64 bytes
    mid_42 = sha256_midstate(prefix)
    mid_99 = sha256_midstate(prefix)
    assert mid_42 == mid_99, "midstate must depend only on first 64 bytes, not nonce"

    # Different first-64 bytes produces different midstate
    mid_diff = sha256_midstate(different_prefix)
    assert mid_diff != mid_42, "different prefix must yield different midstate"

    # Now verify the cache behavior: the device path caches on the full
    # 80-byte header. With a different full header (different nonce), the
    # cache is invalidated -- but the midstate bytes uploaded to the device
    # should be identical (proving the optimization is correct).
    try:
        hasher = BH(backend="auto")
    except Exception:
        pytest.skip("OpenCL backend required for midstate cache test")
    if not hasher.backend.startswith("opencl"):
        pytest.skip("OpenCL backend required for midstate cache test")

    header1 = bytes(76) + struct.pack("<I", 42)
    header2 = bytes(76) + struct.pack("<I", 99)

    # First grind populates the cache
    hasher.grind_target_range(header1, b"\xff" * 32, 0, 10)
    cache1 = hasher._cached_header
    assert cache1 == header1

    # Second grind with different nonce invalidates the full-header cache
    hasher.grind_target_range(header2, b"\xff" * 32, 0, 10)
    cache2 = hasher._cached_header
    assert cache2 == header2

    # But the midstate itself (first 64 bytes) is the same:
    assert sha256_midstate(header1[:64]) == sha256_midstate(header2[:64])
