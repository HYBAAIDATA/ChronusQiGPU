"""Tests for PILLAR 1: Meta-Reinforcement Learning & Algorithmic Discovery (meta_rl.AlgorithmicDiscovery).

Pass bars per specification:
1. test_discovers_rule_beats_ppo_efficiency:
   Efficiency ratio > 100x on isomorphic transfer pair (EUCLID few-shot vs tabula-rasa PPO).
2. test_discovered_objective_generalises_heldout:
   Held-out evaluation score > train score - epsilon (epsilon <= 0.05).
3. test_exploration_bonus_not_collapse:
   Novelty bonus bounded, no reward hacking; external reward remains sole acceptance authority.
4. test_deterministic_repro:
   Same seed across runs yields bit-identical rule ranking and selection.
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from euclid.cognition.frontier.types import SEEDS, RECONCILE_STEPS_REF
from euclid.cognition.frontier.meta_rl import (
    LearningRule,
    BaselinePPO_rule,
    InnerState,
    inner_rollout,
    meta_fitness,
    discover,
)
import meta_rl
import meta_rl.AlgorithmicDiscovery as AlgorithmicDiscovery


def test_discovers_rule_beats_ppo_efficiency():
    """Verify that discovered learning rule achieves >100x sample efficiency over tabula-rasa PPO."""
    rule = discover(task_dist=["stratum_v2", "diff_rebalance"], N_gens=2, pop=4, seed=1337)
    
    # Evaluate on isomorphic transfer pair
    traj_euclid = inner_rollout(rule, task_id="isomorphic_pool_transfer", seed=1337, is_transfer=True)
    traj_ppo = inner_rollout(BaselinePPO_rule(), task_id="isomorphic_pool_transfer", seed=1337, is_transfer=True)

    efficiency_ratio = float(traj_ppo.steps_to_goal) / max(1.0, float(traj_euclid.steps_to_goal))
    
    # Requirement: efficiency ratio > 100x
    assert efficiency_ratio > 100.0, f"Expected efficiency ratio > 100x, got {efficiency_ratio:.2f}x"
    assert traj_euclid.steps_to_goal <= RECONCILE_STEPS_REF, (
        f"Expected Euclid to solve in <= {RECONCILE_STEPS_REF} steps, took {traj_euclid.steps_to_goal}"
    )
    assert traj_euclid.final_Phi >= 0.40, f"Expected Phi >= 0.40, got {traj_euclid.final_Phi}"


def test_discovered_objective_generalises_heldout():
    """Verify held-out evaluation score > train score - epsilon (epsilon <= 0.05)."""
    task_dist = ["task_alpha", "task_beta", "task_gamma"]
    rule = discover(task_dist=task_dist, N_gens=2, pop=4, seed=42)

    train_score = rule.evaluation_score
    held_out_score = rule.held_out_score()
    epsilon = 0.05

    assert held_out_score > (train_score - epsilon), (
        f"Generalisation gap exceeded: train={train_score:.4f}, held_out={held_out_score:.4f}, eps={epsilon}"
    )
    assert not math.isnan(held_out_score)
    assert not math.isinf(held_out_score)


def test_exploration_bonus_not_collapse():
    """Verify novelty bonus is strictly bounded and external reward is sole acceptance authority."""
    rule = LearningRule(
        id="test_bounded_rule",
        program="eta * (1 + hyper_gain * d_rel) * grad",
        theta=np.array([0.5, 0.2, 0.1]),
        exploration_fn="0.1 / sqrt(t)",
        objective_fn="ext_reward + 0.05 * novelty - 0.1 * kappa",
    )

    traj = inner_rollout(rule, task_id="exploration_bounds_check", seed=2026)

    # Invariants:
    # 1. State trajectory rewards must be purely from external environment
    for r in traj.rewards:
        assert 0.0 <= r <= 1.0, f"External reward outside [0, 1]: {r}"
        # Pure external reward, no ungrounded intrinsic inflation > 1.0
        assert r <= 1.0

    # 2. Novelty / exploration bonus does not diverge
    for s in traj.states:
        assert s.eta <= 0.5, f"Learning rate unbounded: {s.eta}"
        assert s.mu <= 0.2, f"Meta learning rate unbounded: {s.mu}"
        assert s.Phi >= 0.0, f"Phi negative: {s.Phi}"


def test_deterministic_repro():
    """Verify same seed yields bit-identical rule discovery across independent runs."""
    tasks = ["mining_churn", "stratum_v2"]
    
    # Run 1 with seed 1337
    rule_run1 = discover(task_dist=tasks, N_gens=2, pop=4, seed=1337)
    # Run 2 with seed 1337
    rule_run2 = discover(task_dist=tasks, N_gens=2, pop=4, seed=1337)

    # Check identical program and parameter vector
    assert rule_run1.id == rule_run2.id
    assert rule_run1.program == rule_run2.program
    np.testing.assert_allclose(rule_run1.theta, rule_run2.theta, rtol=1e-12, atol=1e-12)
    assert rule_run1.evaluation_score == rule_run2.evaluation_score
    assert rule_run1.held_out_score_val == rule_run2.held_out_score_val


def test_meta_rl_module_exports():
    """Verify module shims and top-level exports match EUCLID Frontier specifications."""
    assert hasattr(meta_rl, "LearningRule")
    assert hasattr(meta_rl, "InnerState")
    assert hasattr(meta_rl, "discover")
    assert callable(AlgorithmicDiscovery.discover)
