"""Smoke tests for the Hendrix-vs-Grover benchmark harness."""

import sys
from math import gcd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmarks.common import rng_for, uniform_winners
from benchmarks.hendrix_vs_grover import (
    grover_walk_index,
    hendrix_index,
    hendrix_stride,
)


def _simulated_grover_walk(n: int):
    """Ground-truth walk order identical to GroverStyleSearch.search."""
    from turing_universal_quantum_computer.search import GroverStyleSearch

    k = GroverStyleSearch.optimal_iterations(n)
    visited = [False] * n
    next_unseen = 0
    idx = 0
    order = {}
    probed = 0
    while probed < n:
        if not visited[idx]:
            visited[idx] = True
            order[idx] = probed
            probed += 1
        idx = (idx + k) % n
        if visited[idx]:
            while next_unseen < n and visited[next_unseen]:
                next_unseen += 1
            if next_unseen >= n:
                break
            idx = next_unseen
    return order


def test_grover_index_formula_matches_simulated_walk():
    for n in (64, 256, 1024, 4096):
        truth = _simulated_grover_walk(n)
        assert len(truth) == n
        for w in (0, 1, n // 3, n - 1, n // 2):
            assert grover_walk_index(w, n) == truth[w]


def test_hendrix_schedule_is_bijection():
    n = 1021  # deliberately non-power-of-two
    stride = hendrix_stride(n)
    assert gcd(stride, n) == 1
    idxs = {hendrix_index(w, n, stride) for w in range(n)}
    assert idxs == set(range(n))


def test_uniform_winner_model_bounds():
    winners = uniform_winners(rng_for("t", 0), 4.0, 1024)
    assert all(0 <= w < 1024 for w in winners)


def test_model_arm_small_run_parity():
    """On uniform winners every ordering's first-hit mean ≈ N/(K+1)."""
    n = 4096
    stride = hendrix_stride(n)
    seq, hen, gro = [], [], []
    for t in range(200):
        rng = rng_for("smoke", t)
        winners = uniform_winners(rng, 4.0, n)
        if not winners:
            continue
        seq.append(min(winners) + 1)
        hen.append(min(hendrix_index(w, n, stride) for w in winners) + 1)
        gro.append(min(grover_walk_index(w, n) for w in winners) + 1)
    import statistics

    for vals in (seq, hen, gro):
        assert abs(statistics.fmean(vals) / (n / 5.0) - 1.0) < 0.25
