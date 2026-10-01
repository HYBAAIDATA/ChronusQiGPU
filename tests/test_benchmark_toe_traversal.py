"""Smoke tests for the TOE traversal benchmark harness."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent / "chronus/mla1517_platform" / "python"),
)

from benchmarks.common import corpus_digest, synthetic_header
from benchmarks.toe_traversal_benchmark import toe_rank_map


def test_synthetic_header_is_80_bytes_and_stable():
    h = synthetic_header(800_000)
    assert len(h) == 80
    assert h == synthetic_header(800_000)


def test_corpus_digest_stable_small():
    d1 = corpus_digest(range(800_000, 800_010))
    d2 = corpus_digest(range(800_000, 800_010))
    assert d1 == d2 and len(d1) == 64


def test_toe_rank_is_permutation_of_window():
    rank = toe_rank_map(0)
    window = 1 << 10
    ranks = {rank(w) for w in range(window)}
    assert ranks == set(range(window))


def test_toe_rank_matches_solver_traversal():
    from chronus.mla1517.mining.solver import M32SearchSolver

    rank = toe_rank_map(0)
    solver = M32SearchSolver()
    for step, (nonce, _lane) in enumerate(solver.candidates(0, 512)):
        assert rank(nonce) == step


def test_face_bias_rotates_rank():
    rank0 = toe_rank_map(0)
    rank17 = toe_rank_map(0, face_bias=17)
    # A nonce on lane 17 is probed first under the biased order.
    assert rank17(17) == 0
    assert rank0(17) != 0
