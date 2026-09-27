# pythagoras/asi/universal_intelligence.py — NEW

import math
from dataclasses import dataclass
from typing import Callable


@dataclass
class EnvironmentResult:
    environment_id: str
    goal_achieved: bool
    efficiency: float  # 0-1, normalised performance vs optimal
    steps_to_goal: int
    surprise: float  # cumulative prediction error


class UniversalIntelligenceEvaluator:
    """Evaluates intelligence per Legg-Hutter definition: performance across
    a wide range of environments, weighted by environment complexity.

    Intelligence = sum over environments: p(env) * performance(env, agent)
    where p(env) is the Solomonoff prior (simpler environments weighted higher).
    """

    def __init__(self):
        self.results: list[EnvironmentResult] = []

    def evaluate_across_environments(
        self, agent_fn: Callable, environments: list, goal_fns: list
    ) -> dict:
        """Run agent across multiple environments and compute weighted intelligence score."""
        for env, goal_fn in zip(environments, goal_fns):
            result = self._run_single(agent_fn, env, goal_fn)
            self.results.append(result)

        return {
            "n_environments": len(self.results),
            "mean_efficiency": self._mean_efficiency(),
            "generalisation_score": self._generalisation_score(),
            "compression_ratio": self._compression_ratio(),
            "intelligence_score": self._intelligence_score(),
        }

    def _run_single(self, agent_fn, env, goal_fn) -> EnvironmentResult:
        steps = 0
        achieved = False
        surprise = 0.0
        for step in range(1000):
            steps += 1
            action = agent_fn(env)
            env, reward, done, info = env.step(action)
            surprise += info.get("prediction_error", 0.0)
            if goal_fn(env):
                achieved = True
                break
        efficiency = 1.0 / (1.0 + steps / 100.0) if achieved else 0.0
        return EnvironmentResult(
            env.id if hasattr(env, "id") else str(id(env)), achieved, efficiency, steps, surprise
        )

    def _mean_efficiency(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.efficiency for r in self.results) / len(self.results)

    def _generalisation_score(self) -> float:
        """Score = fraction of environments where goal was achieved."""
        if not self.results:
            return 0.0
        achieved = sum(1 for r in self.results if r.goal_achieved)
        return achieved / len(self.results)

    def _compression_ratio(self) -> float:
        """Compression = total steps taken vs minimum possible.
        Lower steps = better compression of the solution."""
        if not self.results:
            return 0.0
        total_steps = sum(r.steps_to_goal for r in self.results if r.goal_achieved)
        min_possible = len(self.results) * 10  # heuristic minimum
        return min_possible / max(total_steps, 1)

    def _intelligence_score(self) -> float:
        """Legg-Hutter inspired: weighted sum of efficiencies across environments.
        Simpler environments (lower complexity) weighted higher (Solomonoff prior)."""
        if not self.results:
            return 0.0
        total = 0.0
        for i, r in enumerate(self.results):
            complexity = math.log2(i + 2)  # approximate Solomonoff prior
            weight = 1.0 / complexity
            total += weight * r.efficiency
        return total / len(self.results)
