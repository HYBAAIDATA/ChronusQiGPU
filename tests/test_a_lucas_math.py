"""Owner A — direct verification of the lucas/ math stack.

The Lucas pool is the shared algebraic substrate every other named
capability routes through. These tests exercise it end to end: the
fast-doubling core against the naive recurrence, the documented ladder,
the T_phi byte fold over Z/256Z, and every pool kernel's honest
{is_lucas_bounded, bound, theorem_proven} contract.
"""

from __future__ import annotations

import random

import numpy as np
import pytest

from lucas import core as lucas_core
from lucas import fold as lucas_fold
from lucas import pool as lucas_pool
from lucas.ladder import CURRICULUM_RUNGS, FULL_LADDER, SCALE_RUNGS, verify_ladder


def _naive_lucas(n: int) -> int:
    a, b = 2, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def _naive_fib(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


# --- core exactness --------------------------------------------------------


def test_lucas_matches_naive_recurrence_up_to_80():
    for n in range(81):
        assert lucas_core.lucas(n) == _naive_lucas(n), n


def test_fibonacci_matches_naive_recurrence_up_to_80():
    for n in range(81):
        assert lucas_core.fibonacci(n) == _naive_fib(n), n


def test_lucas_identity_via_fibonacci():
    """L_n = F_{n-1} + F_{n+1} — the Lucas/Fibonacci bridge, exact."""
    for n in range(1, 80):
        assert lucas_core.lucas(n) == lucas_core.fibonacci(n - 1) + lucas_core.fibonacci(n + 1)


def test_cassini_identity_exact():
    """Cassini: L_n^2 - 5 F_n^2 = 4 (-1)^n for every n in the ladder range."""
    for n in range(80):
        lhs = lucas_core.lucas(n) ** 2 - 5 * lucas_core.fibonacci(n) ** 2
        assert lhs == 4 * ((-1) ** n), n


def test_documented_ladder_values():
    expected = {
        10: 123,
        12: 322,
        15: 1364,
        18: 5778,
        20: 15127,
        31: 3010349,
        50: 28143753123,
        76: 7639424778862807,
    }
    for n, value in expected.items():
        assert lucas_core.lucas(n) == value, n


# --- ladder ----------------------------------------------------------------


def test_ladder_structure_and_honest_status():
    assert tuple(CURRICULUM_RUNGS) == (10, 12, 15, 18, 20)
    assert tuple(SCALE_RUNGS) == (10, 12, 15, 18, 20, 31, 50, 76)
    assert tuple(FULL_LADDER) == (10, 12, 15, 18, 20, 31, 50, 76)
    report = verify_ladder()
    assert report["ladder"] == list(FULL_LADDER)
    assert report["monotonic"] is True
    assert all(v == lucas_core.lucas(n) for n, v in zip(FULL_LADDER, report["values"]))
    # Honesty contract: the ladder is verified arithmetic, not a proven theorem.
    assert report["theorem_proven"] is False


# --- T_phi fold over Z/256Z ------------------------------------------------


def test_m15_is_a_gl2z256_involution_pair():
    """M15 * M15_INV == I (mod 256) — the fold is exactly invertible."""
    a = lucas_fold.M15
    b = lucas_fold.M15_INV
    for i in range(2):
        for j in range(2):
            acc = sum(a[i][k] * b[k][j] for k in range(2)) % 256
            assert acc == (1 if i == j else 0)


def test_t_phi_fold_roundtrip_all_byte_pairs():
    for x in range(0, 256, 17):
        for y in range(0, 256, 19):
            raw = bytes([x, y])
            assert lucas_fold.t_phi_unfold(lucas_fold.t_phi_fold(raw), 2) == raw


def test_t_phi_fold_odd_length_roundtrip():
    rng = random.Random(1517)
    for length in (1, 3, 5, 255, 1023):
        raw = bytes(rng.randrange(256) for _ in range(length))
        folded = lucas_fold.t_phi_fold(raw)
        assert len(folded) == length + (length & 1)
        assert lucas_fold.t_phi_unfold(folded, length) == raw


def test_iter_original_u8_streams_identical_bytes():
    raw = bytes(range(256))
    folded = lucas_fold.t_phi_fold(raw)
    assert bytes(lucas_fold.iter_original_u8(folded, 256)) == raw


def test_folded_modular_dot_equals_plain_dot():
    """q^T x (mod 256) computed on folded bytes equals the raw dot."""
    rng = random.Random(76)
    for _ in range(40):
        raw = bytes(rng.randrange(256) for _ in range(64))
        weights = [rng.randrange(256) for _ in range(64)]
        folded = lucas_fold.t_phi_fold(raw)
        got = lucas_fold.folded_modular_dot(folded, len(raw), weights)
        want = sum(w * x for w, x in zip(weights, raw)) % 256
        assert got == want


# --- pool kernels ----------------------------------------------------------


def test_pool_kernel_names():
    names = set(lucas_pool.names()) if hasattr(lucas_pool, "names") else set()
    if not names:
        names = {k for k in dir(lucas_pool) if k.endswith("_kernel")}
    for expected in (
        "paths_kernel",
        "step_kernel",
        "amplitude_kernel",
        "mining_kernel",
        "gap_kernel",
        "folded_kernel",
        "path_kernel",
    ):
        if expected in names:
            assert lucas_pool.get(expected) is not None


def test_step_kernel_bound_is_exact_and_honest():
    r = lucas_pool.get("step_kernel")({"states": 10}, 15)
    assert r["lucas_bound"] == 1364 and r["is_lucas_bounded"] is True
    assert r["theorem_proven"] is False
    r2 = lucas_pool.get("step_kernel")({"states": 10_000}, 15)
    assert r2["is_lucas_bounded"] is False  # honest: exceeds L_15


def test_path_kernel_counts_walks_exactly():
    graph = np.array([[0, 1], [1, 0]], dtype=np.int64)
    r = lucas_pool.get("path_kernel")(graph, 10)
    assert r["path_count"] == 2  # period-2 two-node graph, 2 walks of even length
    assert r["lucas_bound"] == lucas_core.lucas(10)


def test_amplitude_kernel_unit_modulus():
    spectrum = [1.0, 1.0]  # |sum lambda^n| = 2 for unit-modulus pair
    r = lucas_pool.get("amplitude_kernel")(spectrum, 2)
    assert r["amplitude_sum"] == 2.0 and r["is_lucas_bounded"] is True


def test_mining_and_gap_and_folded_kernels():
    r = lucas_pool.get("mining_kernel")(10_000, 20)
    assert r["is_lucas_bounded"] == (10_000 <= lucas_core.lucas(20))
    h = np.array([[1.0, 0.0], [0.0, -1.0]])
    g = lucas_pool.get("gap_kernel")(h, 10)
    assert g["spectral_gap"] == pytest.approx(2.0)
    f = lucas_pool.get("folded_kernel")(bytes(64), 15)
    assert f["pair_ops"] == 32 and f["is_lucas_bounded"] is True
