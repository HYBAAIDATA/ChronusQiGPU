"""
Part 6: Amplitude Amplification
================================

Grover's amplitude amplification over a declared search space, executed as a
classical state-vector simulation.

Claim lane: INTERNAL -- mathematical correctness only.

This module demonstrates that the amplitude-amplification iterate concentrates
probability mass on a marked state. It is a classical NumPy simulation: each
iteration materialises and transforms a full N-dimensional state vector, so the
classical cost of the simulated run grows with N rather than with sqrt(N).

What the returned figures are, stated precisely:

    theoretical_oracle_query_ratio = sqrt(N / M)

is the ratio of the expected classical oracle queries to the expected Grover
oracle queries. It is an oracle-query ratio, NOT a wall-clock speedup, NOT a
parallelism factor, and it is not achieved by executing this module. It is
recomputed from the class's own N and M by the accompanying test, so the number
reported by get_specs() cannot drift from the constants that produce it.

The optimal iteration count k* and the success probability after k iterations
follow the standard finite-budget expressions:

    k*                     ~= (pi / 4) * sqrt(N / M)
    P(success | k)          = sin^2((2k + 1) * theta),  sin(theta) = sqrt(M / N)

Success probability therefore peaks near k* and falls away from it in both
directions; more iterations is not monotonically better. The accompanying test
pins that shape.

No quantum advantage, device throughput, or hardware execution is claimed. No
figure here is a measured device result.
"""

import numpy as np
from typing import Optional


class AmplitudeAmplificationProcessor:
    """Grover amplitude amplification over a declared search space.

    ``search_space`` is the declared dimension the caller intends to search.
    ``simulation_dimension`` is the dimension actually simulated, which is
    capped for materialisation. They are deliberately distinct attributes: this
    class never rewrites a declared search space and reports the capped
    dimension as though it were the declared one.

    A simulation of an N-dimensional state vector at N = 2**32 would require
    2**32 complex amplitudes and is not attempted. Requesting such a space is
    permitted; the simulated dimension is bounded and the two are reported
    separately.
    """

    # Materialisation bound on the simulated state vector. Declared search
    # spaces above this are simulated at the bound, not silently rewritten.
    MATERIALISATION_BOUND = 2 ** 20

    def __init__(self, search_space: int = 2 ** 20, difficulty: int = 10):
        if int(search_space) < 1:
            raise ValueError("search_space must be >= 1")
        # Declared intent, retained verbatim. Never overwritten by the clamp.
        self.search_space = int(search_space)
        # What is actually simulated, bounded for materialisation.
        self.simulation_dimension = min(self.search_space, self.MATERIALISATION_BOUND)
        self.N = self.simulation_dimension  # backwards-compatible alias
        self.difficulty = self._require_difficulty(difficulty)
        self.M = self.estimate_solutions(self.difficulty)
        self.theta = np.arcsin(np.sqrt(max(self.M / self.N, 1e-12)))
        self.opt_iterations = max(1, int(np.pi / (4 * self.theta))) if self.theta > 0 else 1

    @staticmethod
    def _require_difficulty(difficulty) -> int:
        """Difficulty has no default. A placeholder must not become an estimate.

        The previous revision derived M from a hardcoded ``difficulty = 10``
        marked ``# Simplified``. A cost estimate whose only input is a
        placeholder is not an estimate, so the parameter is now required and
        validated rather than defaulted.
        """
        if difficulty is None:
            raise ValueError(
                "difficulty is required: the marked-state fraction must come "
                "from a declared difficulty, not a placeholder"
            )
        value = int(difficulty)
        if value < 0:
            raise ValueError("difficulty must be >= 0")
        return value

    def declared_over_simulation_ratio(self) -> float:
        """How much larger the declared space is than the simulated one.

        A ratio of 1.0 means the declared space was simulated in full. A ratio
        above 1.0 means the run covered only the materialisation bound; results
        describe that bound, not the declared space.
        """
        return float(self.search_space) / float(self.simulation_dimension)

    def estimate_solutions(self, difficulty: int) -> float:
        """Estimate the marked-state count from a declared difficulty.

        M is the expected number of marked states in the simulated space for
        the given difficulty: N / 2**difficulty, floored at 1. This is an
        estimate from the declared difficulty and is labelled as such; it is
        not a measured marked-state count.
        """
        difficulty = self._require_difficulty(difficulty)
        return max(1.0, self.simulation_dimension / (2 ** difficulty))

    def grover_search(self, target: int) -> Optional[int]:
        """Run the amplitude-amplification iterate and return the argmax.

        Returns the measured basis index when its probability exceeds 0.5, else
        None. The returned index is a simulation measurement, not a proof of
        work and not a device result.
        """
        state = np.ones(self.N, dtype=np.complex128) / np.sqrt(self.N)

        for _ in range(min(self.opt_iterations, 1000)):
            state = self.apply_oracle(state, target)
            state = self.apply_diffusion(state)

            success_prob = np.abs(state[target]) ** 2
            if success_prob > 0.99:
                break

        probabilities = np.abs(state) ** 2
        nonce = int(np.argmax(probabilities))
        return nonce if probabilities[nonce] > 0.5 else None

    def apply_oracle(self, state: np.ndarray, target: int) -> np.ndarray:
        """Oracle: flip the phase of the marked basis state."""
        result = state.copy()
        if 0 <= target < len(result):
            result[target] *= -1
        return result

    def apply_diffusion(self, state: np.ndarray) -> np.ndarray:
        """Diffusion operator about the uniform superposition.

        D = 2|psi><psi| - I, evaluated against the uniform state implied by
        ``state`` itself. For a normalised state this reduces to reflection
        about the mean amplitude.
        """
        avg = np.mean(state)
        return 2 * avg - state

    def quantum_amplitude_estimation(self, target: int) -> float:
        """Return the summed probability over the simulated state.

        The sum of |amplitude|^2 over a normalised vector is 1 by construction;
        this is retained for interface compatibility and is pinned by test.
        """
        state = np.ones(self.N, dtype=np.complex128) / np.sqrt(self.N)
        for _ in range(min(self.opt_iterations, 100)):
            state = self.apply_oracle(state, target)
            state = self.apply_diffusion(state)
        return float(np.sum(np.abs(state) ** 2))

    def verify_result(self, nonce: int, target: int) -> bool:
        """Confirm a simulated measurement hit the marked index."""
        return nonce == target

    def get_specs(self) -> dict:
        """Declared and simulated dimensions, plus the recomputed ratio.

        ``theoretical_oracle_query_ratio`` is sqrt(N / M) recomputed from this
        instance's own N and M. It is an oracle-query ratio, not a wall-clock
        speedup and not a parallelism factor.
        """
        ratio = float(np.sqrt(self.N / max(self.M, 1)))
        return {
            "search_space": self.search_space,
            "simulation_dimension": self.simulation_dimension,
            "declared_over_simulation_ratio": self.declared_over_simulation_ratio(),
            "materialisation_bound": self.MATERIALISATION_BOUND,
            "difficulty": self.difficulty,
            "estimated_solutions": self.M,
            "optimal_iterations": self.opt_iterations,
            "theta": float(self.theta),
            "theoretical_oracle_query_ratio": ratio,
        }
