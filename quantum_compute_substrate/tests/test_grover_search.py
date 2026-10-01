"""Tests for Grover's algorithm."""

import numpy as np
from quantum_compute_substrate.grover_search import GroverSearch


class TestGroverSearch:
    def test_finds_single_target(self):
        searcher = GroverSearch(dim=256, seed=42)
        result = searcher.search(target=100)
        assert result["found"]
        assert result["measured"] == 100

    def test_target_probability_increases(self):
        """After Grover iterations, target probability should be > initial."""
        searcher = GroverSearch(dim=256, seed=42)
        result = searcher.search(target=50)
        probs = result["probabilities"]
        assert probs[-1] > probs[0]
        # Initial probability should be 1/N
        assert abs(probs[0] - 1 / 256) < 1e-6

    def test_optimal_iterations_scale_as_sqrt_n(self):
        """Optimal iterations should scale as O(sqrt(N))."""
        for N in [64, 256, 1024]:
            searcher = GroverSearch(dim=N, seed=42)
            result = searcher.search(target=N // 3)
            expected = int(np.pi * np.sqrt(N) / 4)
            assert abs(result["iterations"] - expected) <= 1

    def test_speedup_ratio_greater_than_one(self):
        """Theoretical speedup ratio should be > 1."""
        searcher = GroverSearch(dim=1024, seed=42)
        result = searcher.search(target=500)
        assert result["speedup_ratio"] > 1

    def test_multiple_targets(self):
        searcher = GroverSearch(dim=256, seed=42)
        targets = [10, 50, 100, 200]
        result = searcher.search_multiple(targets)
        assert result["found"]
        assert result["measured"] in targets
        assert result["total_target_probability"] > 0.5

    def test_verify_quadratic_speedup(self):
        searcher = GroverSearch(dim=64, seed=42)
        verification = searcher.verify_quadratic_speedup(dims=[64, 128, 256])
        assert verification["speedup_confirmed"]
        for r in verification["results"]:
            assert r["found"]
            assert r["target_probability"] > 0.5

    def test_grover_not_brute_force(self):
        """Grover should find target in fewer iterations than classical."""
        N = 1024
        searcher = GroverSearch(dim=N, seed=42)
        result = searcher.search(target=333)
        assert result["found"]
        assert result["iterations"] < N / 2  # fewer than classical average
