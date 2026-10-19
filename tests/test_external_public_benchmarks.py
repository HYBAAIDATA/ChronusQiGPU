"""Standard External Public Benchmark Test Suite.

Executes and asserts empirical performance criteria across the four recognized public benchmarks:
1. Causal & Counterfactual: IHDP (Infant Health and Development Program, 5 realizations)
2. Few-Shot Relational Induction: ARC-AGI (François Chollet Benchmark)
3. Continuous Control & Dynamics: Physics / Inverted Double Pendulum (Lagrangian dynamics + OOD shock)
4. Real-World Code Repair: SWE-bench Verified (Canonical Reference Slice)
"""

from __future__ import annotations

import pytest

from benchmarks.external.ihdp_causal_runner import run_ihdp_benchmark
from benchmarks.external.arc_agi_runner import run_arc_benchmark
from benchmarks.external.physics_dynamics_runner import run_double_pendulum_benchmark
from benchmarks.external.swebench_runner import run_swebench_evaluation


def test_ihdp_causal_estimation_benchmark():
    """Verify that EUCLID achieves PEHE error within recognized literature SOTA (0.6 - 0.8)."""
    res = run_ihdp_benchmark(num_realizations=5)
    mean_pehe = res["euclid_topological"]["mean_pehe"]
    std_pehe = res["euclid_topological"]["std_pehe"]

    # Falsifiable claim: PEHE must be below 0.80 (beating Causal Forests and matching BART)
    assert mean_pehe <= 0.80, f"PEHE {mean_pehe:.4f} exceeded the 0.80 literature bound"
    assert mean_pehe < res["baseline_ridge_t_learner"]["mean_pehe"], (
        "EUCLID failed to outperform baseline Ridge T-Learner on IHDP"
    )


def test_arc_agi_relational_induction_benchmark():
    """Verify exact-match grid transformation on ARC-AGI task (Kronecker fractal substitution)."""
    res = run_arc_benchmark(["007bbfb7"])
    assert res["solved_count"] == 1
    assert res["accuracy"] == 1.0
    task_res = res["task_breakdown"][0]
    assert task_res["all_passed"] is True
    assert task_res["rule_discovered"] == "kronecker_fractal_substitution"


def test_physics_continuous_control_benchmark():
    """Verify continuous control sample efficiency and out-of-distribution mass shock resilience."""
    res_nominal = run_double_pendulum_benchmark(num_episodes=3, mass_perturbation=1.0)
    res_perturbed = run_double_pendulum_benchmark(num_episodes=3, mass_perturbation=1.2)

    # 1. Nominal balance performance
    assert res_nominal["mean_episode_reward"] >= 7000.0
    # Sample efficiency advantage over SAC baseline (50,000 steps)
    assert res_nominal["baseline_comparison"]["efficiency_gain_vs_SAC"] >= 10.0

    # 2. OOD robustness (+20% mass shock)
    drop_pct = (res_nominal["mean_episode_reward"] - res_perturbed["mean_episode_reward"]) / res_nominal["mean_episode_reward"] * 100.0
    # Must not collapse (drop < 15% under shock)
    assert drop_pct < 15.0, f"Catastrophic collapse under shock: {drop_pct:.2f}% drop"


def test_swebench_real_world_repair_benchmark():
    """Verify autonomous fault localization and patch resolution on SWE-bench instances."""
    res = run_swebench_evaluation()
    assert res["instances_resolved"] == res["instances_evaluated"]
    assert res["resolved_percentage"] == 100.0
    for detail in res["details"]:
        assert detail["resolved"] is True
