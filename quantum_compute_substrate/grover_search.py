"""
Grover's Algorithm — Real Implementation (General Purpose)
=========================================================

Implements the mathematically correct Grover's quantum search algorithm on
classical hardware. The algorithm provides a proven quadratic speedup over
classical search for unstructured databases: O(√N) vs O(N).

On classical hardware we SIMULATE the algorithm (which costs O(N) per
iteration since we manipulate the full state vector), so we cannot achieve
the actual speedup. However, the simulation demonstrates that the amplitude
amplification correctly concentrates probability mass on the target —
the mathematical foundation is sound.

Claim lane: INTERNAL — mathematical correctness demonstrated; no quantum
speedup claim on classical hardware.
"""

import numpy as np
from typing import Optional, List, Dict
from .phi_tensor_core import PhiTensorCore


class GroverSearch:
    """
    Full simulation of Grover's quantum search algorithm.

    Given a search space of dimension N with M target states, Grover's
    algorithm finds a target in O(√(N/M)) iterations, compared to O(N/M)
    for classical search.

    Optimal iterations: k* ≈ (π/4) √(N/M)
    Success probability after k iterations: sin²((2k+1)θ)
    where sin(θ) = √(M/N)
    """

    def __init__(self, dim: int = 1024, seed: Optional[int] = None):
        self.dim = dim
        self.core = PhiTensorCore(core_id=0, dim=dim, seed=seed)

    def search(self, target: int, num_iterations: Optional[int] = None) -> Dict:
        """
        Run Grover's algorithm to find a single target.

        Returns dict with:
            - found: whether the measurement hit the target
            - measured: the measured index
            - probability: probability of the target state
            - iterations: number of Grover iterations used
            - classical_expected_trials: equivalent classical trials
        """
        N = self.dim
        M = 1  # single target

        if num_iterations is None:
            num_iterations = max(1, int(np.pi * np.sqrt(N / M) / 4))

        state = self.core._initialize_state()
        probabilities = [self.core.measure_probability(state, target)]

        for _ in range(num_iterations):
            state = self.core.grover_iteration(state, target)
            probabilities.append(self.core.measure_probability(state, target))

        measured = self.core.measure(state)
        found = measured == target

        return {
            "found": found,
            "measured": measured,
            "target": target,
            "probability": probabilities[-1],
            "probabilities": probabilities,
            "iterations": num_iterations,
            "optimal_iterations": int(np.pi * np.sqrt(N / M) / 4),
            "classical_expected_trials": N / 2,
            "speedup_ratio": (N / 2) / num_iterations if num_iterations > 0 else 0,
        }

    def search_multiple(self, targets: List[int], num_iterations: Optional[int] = None) -> Dict:
        """Grover search with multiple targets (M > 1)."""
        N = self.dim
        M = len(targets)
        if num_iterations is None:
            num_iterations = max(1, int(np.pi * np.sqrt(N / M) / 4))

        state = self.core._initialize_state()

        for _ in range(num_iterations):
            for t in targets:
                state = self.core.grover_oracle(state, t)
            state = self.core.amplitude_amplification(state)

        measured = self.core.measure(state)
        found = measured in targets
        target_prob = sum(self.core.measure_probability(state, t) for t in targets)

        return {
            "found": found,
            "measured": measured,
            "targets": targets,
            "total_target_probability": target_prob,
            "iterations": num_iterations,
            "M": M,
            "N": N,
        }

    def verify_quadratic_speedup(self, dims: List[int] = None) -> Dict:
        """
        Empirically verify that Grover concentrates probability on the target
        in O(√N) iterations across multiple problem sizes.

        This demonstrates the mathematical correctness of the algorithm —
        NOT a runtime speedup on classical hardware.
        """
        if dims is None:
            dims = [64, 128, 256, 512, 1024]

        results = []
        for N in dims:
            target = N // 3
            searcher = GroverSearch(dim=N, seed=42)
            result = searcher.search(target)
            results.append(
                {
                    "N": N,
                    "sqrt_N": np.sqrt(N),
                    "iterations_used": result["iterations"],
                    "found": result["found"],
                    "target_probability": result["probability"],
                    "classical_trials": N / 2,
                }
            )

        return {
            "results": results,
            "speedup_confirmed": all(r["found"] for r in results),
            "note": (
                "Grover's algorithm correctly amplifies the target amplitude "
                "in O(sqrt(N)) iterations. On classical hardware, each iteration "
                "costs O(N), so this is a correctness demonstration, not a "
                "runtime speedup."
            ),
        }
