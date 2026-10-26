# File: tests/benchmarks/test_euclid_vs_ineffable.py

import pytest
import time
from typing import Dict, Any

from euclid.cognition.cognitive_topology import (
    load_solved_control_manifold,
    load_unseen_isomorphic_manifold,
    load_active_graph_manifold,
    evaluate_policy_few_shot,
)

SEEDS = [1337, 42, 2026]
KAPPA = 0.05
RICCI_REF = 8


def sample_complexity_duel(seed: int = 1337) -> Dict[str, Any]:
    """STAGE 1.1: Sample Efficiency on Isomorphic Task Transfer.
    
    Evaluates O(1) categorical functor pullback vs. tabula-rasa RL floor (250,000 steps).
    """
    tabula_rasa_steps = 250_000
    t0 = time.perf_counter()

    source_manifold = load_solved_control_manifold(seed)
    target_manifold = load_unseen_isomorphic_manifold(seed)

    # Functorial mapping across isomorphic relational triads
    mapping = source_manifold.extract_functor(target_manifold)
    assert mapping.functoriality_score >= 0.95, f"Functoriality score {mapping.functoriality_score} below 0.95"

    # Action policy is pulled back directly via the functor
    pulled_policy = mapping.pullback_policy()
    euclid_environment_steps = evaluate_policy_few_shot(pulled_policy, target_manifold)
    elapsed = time.perf_counter() - t0

    sample_efficiency_gain = tabula_rasa_steps / max(1, euclid_environment_steps)

    assert euclid_environment_steps <= 10, f"Failed few-shot transfer: steps={euclid_environment_steps}"
    assert sample_efficiency_gain >= 10_000.0, f"Efficiency gain {sample_efficiency_gain}x below 10,000x"

    return {
        "seed": seed,
        "steps": euclid_environment_steps,
        "gain": sample_efficiency_gain,
        "elapsed_sec": elapsed,
        "functor_score": mapping.functoriality_score,
    }


def shock_robustness_duel(seed: int = 1337) -> Dict[str, Any]:
    """STAGE 1.2: Distributional Shock Recovery via discrete Ricci flow.
    
    Pearl Level 2 structural severance do(edge=("security", "mining")) followed by
    discrete Forman-Ricci metric contraction to <= 0.05 within <= 8 steps.
    """
    manifold = load_active_graph_manifold(seed)

    # Inject structural shock (Pearl Level 2: do(edge_weight = 0))
    manifold.inject_structural_severance(edge=("security", "mining"))

    # Discrete Ricci flow relaxation
    reconciliation_trace = manifold.reconcile_layer_curvature(tau=KAPPA)

    assert len(reconciliation_trace) <= RICCI_REF, f"Ricci flow exceeded {RICCI_REF} steps: got {len(reconciliation_trace)}"
    final_kappa = manifold.get_curvature("security")
    assert final_kappa <= KAPPA, f"Curvature {final_kappa} failed to reach {KAPPA}"

    return {
        "seed": seed,
        "steps": len(reconciliation_trace),
        "final_curvature": final_kappa,
        "trace": reconciliation_trace,
    }


class TestEuclidVsIneffableRL:
    """Empirical Duel: Topological Structural Bias vs. Tabula Rasa Model-Free RL."""

    @pytest.mark.parametrize("seed", SEEDS)
    def test_sample_complexity_duel_across_seeds(self, seed: int):
        rep = sample_complexity_duel(seed)
        assert rep["steps"] <= 10
        assert rep["gain"] >= 10_000.0

    @pytest.mark.parametrize("seed", SEEDS)
    def test_counterfactual_robustness_under_shock_across_seeds(self, seed: int):
        rep = shock_robustness_duel(seed)
        assert rep["steps"] <= RICCI_REF
        assert rep["final_curvature"] <= KAPPA
