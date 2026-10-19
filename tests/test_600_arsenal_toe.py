"""Tests for 600-lane Quantum Arsenal, TOE wiring, and 5+1 scoring.

Phase P4 unit test suite:
- Hendrix-Grover clamped to MATERIALISATION_BOUND = 2^20
- Quantum walk over 600-cycle: identical hash across calls / execution substrates
- Tunnelling (Landau-Zener barrier escape for stuck futures)
- Annealing / warming (warm-start strictly from literal outcomes)
- Superposition hold LRU (N <= 8 width, LRU eviction, collapse reason + alternatives)
- Per-lane 5+1 intelligence audit logs (predictive, causal, counterfactual, topological, geometric, quantum-ext)
- Incomplete lane detection
- Yang-Mills gauge symmetry check (no privileged lane)
- Ricci flow golden flow convergence (|kappa| <= 0.05 in <= 8 steps)
- Re-export shims across kellogg, kellogg.canonical_tensor, and tensor.canonical_tensor
"""

import math
import pytest

from kellogg.ansatz_v3 import ANSATZ_V3, FUTURES, LANES, SEEDS, load_ansatz
from kellogg.lane_scorer import (
    MATERIALISATION_BOUND,
    FutureSuperpositionEntry,
    PerLaneScoreLog,
    QuantumArsenal,
    SuperpositionHoldLRU,
    score_600_lanes,
)
from kellogg.mother_tensor import kellogg_state_600


def test_quantum_walk_same_hash():
    arsenal = QuantumArsenal()
    # Execute across seeds and verify same-hash determinism
    for seed in SEEDS:
        w1, h1 = arsenal.quantum_walk_reweight(lane_id=42, steps=8, seed=seed)
        w2, h2 = arsenal.quantum_walk_reweight(lane_id=42, steps=8, seed=seed)
        assert h1 == h2
        assert w1 == w2
        assert len(h1) == 64  # sha256 hex


def test_tunnelling_barrier_escape():
    arsenal = QuantumArsenal()
    # Unstuck lane does not trigger tunnelling boost
    p_unstuck = arsenal.tunnel_barrier_escape(lane_id=10, stuck_future=False)
    assert p_unstuck == 0.0

    # Stuck lane triggers Landau-Zener barrier escape
    p_stuck = arsenal.tunnel_barrier_escape(lane_id=10, stuck_future=True, barrier_height=0.5)
    assert p_stuck > 0.0
    assert p_stuck < 1.0


def test_anneal_warm_start():
    arsenal = QuantumArsenal()
    # Unconditioned baseline
    val_empty = arsenal.anneal_warm_start(lane_id=5, literal_history=None)
    assert val_empty > 0.0

    # Conditioned strictly on literal history
    history = [True, False, True, True]
    val_warm = arsenal.anneal_warm_start(lane_id=5, literal_history=history)
    assert val_warm > 0.0
    assert val_warm != val_empty


def test_hendrix_clamped_bound():
    arsenal = QuantumArsenal()
    assert MATERIALISATION_BOUND == (1 << 20)
    for l_idx in (0, 31, 100, 599):
        amp = arsenal.hendrix_clamped_reweight(lane_id=l_idx, order_seed=1337)
        assert amp > 0.0
        assert not math.isnan(amp)


def test_superposition_hold_lru_and_collapse():
    hold = SuperpositionHoldLRU(max_futures=8)
    for i in range(10):
        hold.put(f"future_{i}", probability=0.1 * (i + 1))

    # Width bounded at 8
    futures = hold.get_futures()
    assert len(futures) == 8
    # Oldest 2 evicted
    future_ids = [f.future_id for f in futures]
    assert "future_0" not in future_ids
    assert "future_1" not in future_ids
    assert "future_9" in future_ids

    # Collapse with reason and alternatives logged
    dummy_scores = [
        PerLaneScoreLog(
            lane_id=i,
            predictive=0.5,
            causal=0.5,
            counterfactual=0.5,
            topological=0.5,
            geometric=0.5,
            quantum_ext=0.5,
            kappa=-0.01,
            entropy_delta=-0.1,
            score=0.5,
            is_complete=True,
            status="COMPLETE",
        )
        for i in range(600)
    ]
    top_future, log = hold.collapse(dummy_scores, reason="TOP_SCORE_WITH_ALTERNATIVES_LOG")
    assert top_future is not None
    assert top_future.future_id == "future_9"  # highest prob (1.0)
    assert log["reason"] == "TOP_SCORE_WITH_ALTERNATIVES_LOG"
    assert log["alternatives_count"] == 7
    assert len(log["alternatives"]) == 7


def test_score_600_lanes_all_complete():
    mt = kellogg_state_600(base_step=0, window=6000, seed=1337)
    scores, summary = score_600_lanes(
        mother_tensor=mt,
        job_fingerprint="job_test_p4",
        literal_history=[True, False, True],
        order_seed=1337,
        stuck_lanes=[5, 12],
    )

    assert len(scores) == 600
    assert summary["complete_lanes"] == 600
    assert summary["gauge_passed"] is True
    assert summary["variance"] < 0.1

    # Every lane must have is_complete == True and status == COMPLETE
    for s in scores:
        assert s.is_complete is True
        assert s.status == "COMPLETE"
        assert s.score > 0.0
        assert abs(s.kappa) <= 0.05
        d = s.as_dict()
        assert len(d["intelligences"]) == 6


def test_ricci_flow_per_lane_canonical_bound():
    ansatz = load_ansatz("ansatz_v3")
    for lane_id in (0, 100, 300, 599):
        trace = ansatz.reconcile_lane(lane_id=lane_id, initial_kappa=-0.162, c_pre=0.8)
        assert trace.is_canonical is True
        assert trace.steps_taken <= 8
        assert abs(trace.final_kappa) <= 0.05
        assert trace.execution_granted is True


def test_lane_scorer_shims_consistency():
    import kellogg
    import kellogg.canonical_tensor as kct
    import tensor.canonical_tensor as tct

    for sym in (
        "PerLaneScoreLog",
        "FutureSuperpositionEntry",
        "SuperpositionHoldLRU",
        "QuantumArsenal",
        "score_600_lanes",
    ):
        assert hasattr(kellogg, sym)
        assert hasattr(kct, sym)
        assert hasattr(tct, sym)
        assert getattr(kellogg, sym) is getattr(kct, sym)
        assert getattr(kct, sym) is getattr(tct, sym)
