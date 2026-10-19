import os
import sys
import json
import time
from math import gcd
from pathlib import Path

os.environ["PYTHIA_ALLOW_QUARANTINED_MINING"] = "1"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from benchmarks.common import rng_for, uniform_winners
from benchmarks.hendrix_vs_grover import (
    grover_walk_index,
    hendrix_index,
    hendrix_stride,
)


def _simulated_grover_walk(n: int):
    """Ground-truth walk order identical to GroverStyleSearch.search."""
    from mining.search import GroverStyleSearch

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


def test_grover_index_formula_matches_simulated_walk(tmp_path, monkeypatch):
    # Explicit numerical reference fixture; never production evidence or approval.
    from chronus.reference_contract import reference_execution

    approval = tmp_path / "reference-approval.json"
    approval.write_text(
        json.dumps(
            {
                "schema": "chronos.reference_approvals/1",
                "approvals": {
                    "benchmark-fixture": {
                        "approved": True,
                        "approved_by": "unit-test-fixture",
                        "purpose": "numerical schedule regression only",
                        "mode": "reference",
                        "expires_unix": time.time() + 60,
                        "capabilities": ["mining.GroverStyleSearch"],
                    }
                },
            }
        )
    )
    monkeypatch.setenv("CHRONOS_REFERENCE_APPROVALS_FILE", str(approval))
    with reference_execution("benchmark-fixture"):
        _assert_reference_walk()


def _assert_reference_walk():
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


def test_numerical_reference_fixture_never_unlocks_production():
    import pytest
    from mining.search import GroverStyleSearch
    from chronus.reference_contract import ReferenceUnavailable

    with pytest.raises(ReferenceUnavailable):
        GroverStyleSearch.optimal_iterations(64)


def test_unconditional_search_parity_honest_accounting():
    """Honest accounting: On a uniform random oracle, no permutation has an
    unconditional advantage over any other. The expected iterations to first hit
    under any bijection sigma:[N]->[N] is identically (N+1)/(K+1)."""
    import random
    import statistics

    n = 1024
    stride = hendrix_stride(n)
    seq_hits, hen_hits, gro_hits = [], [], []

    rng = random.Random(42)
    for _ in range(500):
        # 1 uniform marked winner
        w = rng.randrange(n)
        seq_hits.append(w + 1)
        hen_hits.append(hendrix_index(w, n, stride) + 1)
        gro_hits.append(grover_walk_index(w, n) + 1)

    mean_seq = statistics.fmean(seq_hits)
    mean_hen = statistics.fmean(hen_hits)
    mean_gro = statistics.fmean(gro_hits)

    # Parity: all means converge to (N+1)/2 = 512.5 within 5% sampling noise
    assert abs(mean_hen - mean_seq) / mean_seq < 0.08
    assert abs(mean_gro - mean_seq) / mean_seq < 0.08


def test_boundaries_per_hendrix_scaling_research():
    """Locks the non-claims boundary: permutation is ordering, not advantage."""
    from lucas.scaling_research import research_report

    report = research_report()
    for claim in [
        "mining advantage",
        "scheduling advantage",
        "hardware speedup",
        "production qualification",
    ]:
        assert claim in report["non_claims"]

