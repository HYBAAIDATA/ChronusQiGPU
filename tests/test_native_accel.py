"""Differential tests: C++ accelerators must match the pure-Python reference."""

import hashlib
import os
import struct

import numpy as np
import pytest

try:
    from chronus.lucas import fold
except ImportError:
    from chronos.lucas import fold

native = pytest.importorskip("chronos._native")


@pytest.mark.parametrize("n", [0, 1, 2, 3, 255, 4096])
def test_fold_matches_reference(n):
    raw = os.urandom(n)
    f = fold._py_t_phi_fold(raw)
    assert native.t_phi_fold(raw) == f
    assert native.t_phi_unfold(f, n) == fold._py_t_phi_unfold(f, n) == raw
    w = list(os.urandom(n))
    assert native.folded_modular_dot(f, n, w) == fold._py_folded_modular_dot(f, n, w)


@pytest.mark.parametrize("n", [15, 16, 17, 31, 32, 33, 127])
def test_vector_fold_matches_reference_at_block_boundaries(n):
    raw = bytes(i % 256 for i in range(n))
    expected = fold._py_t_phi_fold(raw)

    assert native.t_phi_fold(raw) == expected
    assert native.t_phi_unfold(expected, n) == raw
    assert native.fold_backend() in ("avx2", "scalar")
    assert isinstance(native.hw_avx2_available(), bool)


def test_native_fold_covers_every_byte_pair():
    raw = bytes(
        value
        for first in range(256)
        for second in range(256)
        for value in (first, second)
    )
    expected = fold._py_t_phi_fold(raw)

    assert native.t_phi_fold(raw) == expected


def test_dot_short_and_negative_weights():
    raw = os.urandom(64)
    f = fold._py_t_phi_fold(raw)
    for w in ([], [5], [-7] * 10, [300] * 64):
        assert native.folded_modular_dot(f, 64, w) == fold._py_folded_modular_dot(f, 64, w)


def test_grind_matches_hashlib():
    prefix = os.urandom(76)
    nonces = np.arange(2000, dtype=np.uint32)

    def val(n):
        h = hashlib.sha256(hashlib.sha256(prefix + struct.pack("<I", int(n))).digest()).digest()
        return int.from_bytes(h, "big"), h

    target = sorted(val(n)[0] for n in nonces)[3]
    expected = next(i for i, n in enumerate(nonces) if val(n)[0] <= target)
    idx, digest, evals = native.grind_sha256d(prefix, nonces, target.to_bytes(32, "big"))
    assert (idx, evals) == (expected, expected + 1)
    assert digest == val(nonces[idx])[1]
    assert native.grind_sha256d(prefix, nonces, (0).to_bytes(32, "big"))[0] == -1


def test_grind_empty_and_duplicate_nonce_contract():
    prefix = bytes(76)
    target = bytes([0xFF]) * 32
    empty = native.grind_sha256d(prefix, np.array([], dtype=np.uint32), target)
    duplicate = native.grind_sha256d(
        prefix, np.array([9, 9], dtype=np.uint32), target
    )

    assert empty == (-1, None, 0)
    assert duplicate[0] == 0
    assert duplicate[2] == 1


def test_grind_activates_and_matches_64_worker_path():
    prefix = bytes(range(76))
    nonces = np.arange(64 * (1 << 15), dtype=np.uint32)
    target = bytes([0xFF]) * 32
    expected_digest = hashlib.sha256(
        hashlib.sha256(prefix + struct.pack("<I", 0)).digest()
    ).digest()

    parallel = native.grind_sha256d(
        prefix, nonces, target, threads=64, use_hw=False
    )
    serial = native.grind_sha256d(
        prefix, nonces, target, threads=1, use_hw=False
    )

    assert parallel == serial == (0, expected_digest, 1)


@pytest.mark.parametrize(
    "nonces",
    [
        np.array([1.5], dtype=np.float64),
        np.array([1], dtype=np.int64),
        np.array([[1]], dtype=np.uint32),
        np.arange(8, dtype=np.uint32)[::2],
    ],
)
def test_native_grind_rejects_implicit_dtype_or_layout_coercion(nonces):
    with pytest.raises((TypeError, ValueError)):
        native.grind_sha256d(bytes(76), nonces, bytes([0xFF]) * 32)


def test_native_grind_rejects_negative_thread_count():
    with pytest.raises(ValueError, match="threads must be non-negative"):
        native.grind_sha256d(
            bytes(76),
            np.array([], dtype=np.uint32),
            bytes([0xFF]) * 32,
            threads=-1,
        )


def _val(prefix, n):
    h = hashlib.sha256(hashlib.sha256(prefix + struct.pack("<I", int(n))).digest()).digest()
    return int.from_bytes(h, "big"), h


@pytest.mark.parametrize("use_hw", [True, False])
@pytest.mark.parametrize("threads", [1, 2, 4, 7, 64])
def test_grind_backends_and_threads_agree(use_hw, threads):
    prefix = os.urandom(76)
    nonces = np.random.default_rng(1).integers(0, 2**32, 300_000, dtype=np.uint32)
    vals = [_val(prefix, n)[0] for n in nonces[:20_000]]
    target = sorted(vals)[2]
    expected = next(i for i, v in enumerate(vals) if v <= target)
    idx, digest, evals = native.grind_sha256d(
        prefix, nonces, target.to_bytes(32, "big"), threads=threads, use_hw=use_hw
    )
    assert (idx, evals) == (expected, expected + 1)
    assert digest == _val(prefix, nonces[idx])[1]
    assert native.grind_sha256d(prefix, nonces, bytes(32), threads=threads, use_hw=use_hw)[0] == -1


def test_dot_u8_fast_path_matches_reference():
    raw = os.urandom(1001)
    f = fold._py_t_phi_fold(raw)
    w = list(os.urandom(1001))
    assert fold.folded_modular_dot(f, 1001, w) == fold._py_folded_modular_dot(f, 1001, w)
    assert fold.folded_modular_dot(f, 1001, bytes(w)) == fold._py_folded_modular_dot(f, 1001, w)
    arr = np.array(w, dtype=np.int64)
    assert fold.folded_modular_dot(f, 1001, arr) == fold._py_folded_modular_dot(f, 1001, w)
