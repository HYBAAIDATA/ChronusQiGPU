"""Deterministic tests for the DeepMind-grade research evaluation harness.

Every test is seeded and reproducible: same seed, same verdict.
No global RNG, no wall-clock, no network, no mining authority.
"""

from __future__ import annotations

import math

from Intelligence.research_calibration import (
    bootstrap_ci,
    brier_score,
    expected_calibration_error,
    paired_bootstrap_diff,
)
from Intelligence.research_coherence import (
    equal_block_coherence,
    negative_control_iid,
    negative_control_shuffle,
)
from Intelligence.research_evaluation import (
    content_hash,
    environment_fingerprint,
    heldout_split,
    instrumented_run,
    seeded_rng,
)


class TestSeededPrimitives:
    def test_same_seed_same_stream(self):
        a = [seeded_rng(7).random() for _ in range(5)]
        b = [seeded_rng(7).random() for _ in range(5)]
        assert a == b

    def test_content_hash_stable(self):
        assert content_hash({"b": 1, "a": 2}) == content_hash({"a": 2, "b": 1})

    def test_env_fingerprint_keys(self):
        env = environment_fingerprint()
        assert {"python", "platform", "theorem_proven"} <= set(env)


class TestCalibration:
    def test_brier_needs_pairs(self):
        assert brier_score([0.5], [1.0])["available"] is False

    def test_brier_perfect_is_zero(self):
        out = brier_score([0.0, 1.0, 0.0, 1.0], [0.0, 1.0, 0.0, 1.0])
        assert out["available"] and out["brier"] == 0.0

    def test_brier_worst_is_one(self):
        out = brier_score([0.0, 1.0, 0.0, 1.0], [1.0, 0.0, 1.0, 0.0])
        assert out["brier"] == 1.0

    def test_ece_perfect_is_zero(self):
        pred = [0.05] * 10 + [0.95] * 10
        obs = [0.0] * 10 + [1.0] * 10
        out = expected_calibration_error(pred, obs, n_bins=10)
        assert out["available"] and out["ece"] < 0.06

    def test_bootstrap_ci_covers_mean(self):
        out = bootstrap_ci([1.0, 2.0, 3.0, 4.0], n_resamples=500, seed=0)
        assert out["available"] and out["lo"] <= out["mean"] <= out["hi"]

    def test_paired_diff_detects_shift(self):
        a = [1.0] * 20
        b = [0.0] * 20
        out = paired_bootstrap_diff(a, b, n_resamples=500, seed=0)
        assert out["available"] and out["excludes_zero"] is True

    def test_paired_diff_null_overlaps_zero(self):
        rng = seeded_rng(3)
        base = [rng.gauss(0.0, 1.0) for _ in range(30)]
        out = paired_bootstrap_diff(base, list(base), n_resamples=500, seed=0)
        assert out["available"] and out["excludes_zero"] is False


class TestCoherenceProbe:
    SIGNAL = [math.sin(i * 0.6180339887498949) for i in range(4000)]

    def test_equal_blocks_all_scales(self):
        out = equal_block_coherence(self.SIGNAL, [123, 322, 1364], blocks_per_scale=8, seed=0)
        assert out["available"] is True
        counts = {v["n_blocks"] for v in out["per_scale"].values()}
        assert counts == {8}

    def test_deterministic_across_runs(self):
        a = equal_block_coherence(self.SIGNAL, [123, 322], seed=5)
        b = equal_block_coherence(self.SIGNAL, [123, 322], seed=5)
        assert a["per_scale"] == b["per_scale"]

    def test_short_signal_fails_closed(self):
        out = equal_block_coherence([0.1, 0.2], [123, 322], seed=0)
        assert out["available"] is False

    def test_shuffle_kills_structure(self):
        real = equal_block_coherence(self.SIGNAL, [50, 100, 200], seed=0)
        null = equal_block_coherence(negative_control_shuffle(self.SIGNAL, seed=1), [50, 100], seed=0)
        assert real["available"] and null["available"]
        assert abs(null["mean_coherence"]) < abs(real["mean_coherence"]) + 0.5

    def test_iid_control_reproducible(self):
        assert negative_control_iid(10, seed=9) == negative_control_iid(10, seed=9)


class TestHeldoutAndRun:
    def test_split_is_partition(self):
        ids = [f"t{i}" for i in range(10)]
        split = heldout_split(ids, n_train=6, seed=0)
        assert len(split["train"]) == 6 and len(split["heldout"]) == 4
        assert sorted(split["train"] + split["heldout"]) == sorted(ids)

    def test_instrumented_run_scores(self):
        tasks = ["a", "b", "c", "d"]

        def system(task):
            return (1.0 if task in ("a", "b") else 0.0, 0.75)

        out = instrumented_run(tasks, system, seed=0)
        assert out["n_tasks"] == 4
        assert out["scores"] == [1.0, 1.0, 0.0, 0.0]
        assert out["brier"]["available"] is True
        assert out["mean_ci"]["available"] is True
