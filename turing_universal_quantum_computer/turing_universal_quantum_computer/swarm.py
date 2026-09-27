"""Quantum-driven swarm — agents sampling exact Born distributions.

"Swarming" here is a first-principles construct: a population of agents
whose collective spatial distribution after each step IS the exact
quantum Born distribution of an underlying walk/state.  Each agent is a
classical point mass; its step is a seeded draw from the exact
probability measure (the same labelled classical boundary as
``QuantumRegister.measure(seed)``).  The ensemble statistics — not the
individual draws — are the quantum object.

Honest boundary (AGENTS.md): the quantum maths (amplitudes, interference,
Born measure) is exact; the per-agent draw is classical sampling OF that
measure, not a quantum collapse claim.  Seeded => fully reproducible.
"""

from __future__ import annotations

import random
from fractions import Fraction
from typing import Any, Callable, Dict, List

import sympy as sp


def _as_float(p) -> float:
    return float(sp.N(p)) if not isinstance(p, (int, float, Fraction)) else float(p)


def _sample_index(dist: Dict[int, Any], r: float) -> int:
    """Draw one index from an exact distribution with uniform r in [0,1).

    The distribution itself is exact; float comparison happens only at
    this classical boundary (documented convention).
    """
    cumulative = 0.0
    last = None
    for k in sorted(dist):
        cumulative += _as_float(dist[k])
        last = k
        if r < cumulative:
            return k
    return last


class QuantumSwarm:
    """A swarm of agents whose step law is an exact quantum distribution.

    ``distribution_fn(step_index)`` must return an exact dict
    {outcome: exact_probability} — e.g. a quantum-walk position
    distribution or a stabilizer/amplitude-weighted candidate law.
    """

    def __init__(
        self,
        n_agents: int,
        distribution_fn: Callable[[int], Dict[int, Any]],
        *,
        seed: int = 0,
        start: int = 0,
    ):
        if n_agents < 1:
            raise ValueError("n_agents must be >= 1")
        self.n_agents = int(n_agents)
        self.distribution_fn = distribution_fn
        self.seed = int(seed)
        self.positions = [int(start)] * self.n_agents
        self.history: List[List[int]] = [list(self.positions)]

    def step(self, step_index: int) -> None:
        dist = self.distribution_fn(step_index)
        rng = random.Random(self.seed + step_index)
        self.positions = [
            p + _sample_index(dist, rng.random()) for p in self.positions
        ]
        self.history.append(list(self.positions))

    def run(self, steps: int) -> "QuantumSwarm":
        for t in range(int(steps)):
            self.step(t)
        return self

    def empirical_distribution(self) -> Dict[int, Fraction]:
        """Exact empirical histogram of current positions (Fractions)."""
        counts: Dict[int, int] = {}
        for p in self.positions:
            counts[p] = counts.get(p, 0) + 1
        return {k: Fraction(v, self.n_agents) for k, v in sorted(counts.items())}

    def dispersion(self) -> Fraction:
        """Exact variance of agent positions (rational, sample quantity)."""
        n = self.n_agents
        mean = Fraction(sum(self.positions), n)
        return sum((Fraction(p) - mean) ** 2 for p in self.positions) / n

    def status(self) -> Dict[str, Any]:
        return {
            "n_agents": self.n_agents,
            "seed": self.seed,
            "truth_class": "exact_quantum_distribution_classical_sampling",
            "steps_recorded": len(self.history) - 1,
        }


__all__ = ["QuantumSwarm"]
