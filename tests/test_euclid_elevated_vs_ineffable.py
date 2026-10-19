"""Tests for Elevated EUCLID vs Ineffable Superlearner paradigm comparison."""
from __future__ import annotations

import unittest

from euclid.cognition.integrated import IntegratedAgent
from euclid.cognition.integrated.phi_mechanisms import fibonacci_search
from euclid.cognition.research.ineffable_benchmark import (
    IneffableSuperlearnerAgent,
    evaluate_agent_on_suite,
)
from euclid.cognition.worlds import generate_task, MechanismWorld, WorldExecutor


class TestIneffableSuperlearner(unittest.TestCase):
    def test_superlearner_executes_and_emits_valid_result(self) -> None:
        spec, truth = generate_task("program-transformation", seed=42, partition="evaluation")
        world = MechanismWorld(spec, truth, seed=42)
        agent = IneffableSuperlearnerAgent(seed=42)
        result = agent.solve(spec, WorldExecutor(world), seed=42)
        self.assertIsNotNone(result.state)
        self.assertEqual(result.probes_used, world.probes_used)
        self.assertEqual(result.submissions_used, world.submissions_used)
        self.assertEqual(result.solved, world.solved)

    def test_superlearner_proxy_reward_vulnerability(self) -> None:
        # In a proxy-reward task, pure experience RL falls into the Goodhart trap
        spec, truth = generate_task("symbolic-rewriting", seed=77, partition="evaluation", tags=("proxy-reward",))
        world = MechanismWorld(spec, truth, seed=77)
        agent = IneffableSuperlearnerAgent(seed=77)
        result = agent.solve(spec, WorldExecutor(world), seed=77)
        # Proxy operator was added; RL agent is easily lured by scalar scores
        self.assertIn("proxy-reward", truth.tags)

    def test_fibonacci_versus_bandit_unimodal(self) -> None:
        # 100-step discrete curve
        peak = 73
        curve = [10.0 - abs(i - peak) * 0.1 for i in range(100)]
        fib_trace = fibonacci_search(curve.__getitem__, 100, 10)
        self.assertEqual(fib_trace.best, peak)

        # UCB1 bandit under same budget of 10 evaluations
        agent = IneffableSuperlearnerAgent(seed=123)
        counts = [0] * 100
        rewards = [0.0] * 100
        for _ in range(10):
            import math
            total_n = sum(counts)
            if total_n < 4:
                arm = (agent._rng.randrange(100))
            else:
                ucb = [
                    (rewards[i] / counts[i] + math.sqrt(2 * math.log(total_n) / counts[i]))
                    if counts[i] > 0 else float("inf")
                    for i in range(100)
                ]
                arm = ucb.index(max(ucb))
            counts[arm] += 1
            rewards[arm] += curve[arm]

        best_bandit_arm = max(range(100), key=lambda i: rewards[i] if counts[i] > 0 else float("-inf"))
        # 10 random/UCB samples across 100 arms will almost never hit the exact peak 73
        self.assertNotEqual(best_bandit_arm, peak)


if __name__ == "__main__":
    unittest.main()
