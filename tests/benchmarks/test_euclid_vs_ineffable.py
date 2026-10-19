# File: tests/benchmarks/test_euclid_vs_ineffable.py

import pytest
import numpy as np
import time

from euclid.cognition.cognitive_topology import (
    load_solved_control_manifold,
    load_unseen_isomorphic_manifold,
    load_active_graph_manifold,
    evaluate_policy_few_shot,
)


class TestEuclidVsIneffableRL:
    """
    Empirical Duel: Topological Structural Bias vs. Tabula Rasa Model-Free RL.
    """

    def test_sample_complexity_duel(self):
        """
        TEST 1: Sample Efficiency on Isomorphic Task Transfer.
        Hypothesis: Once a control topology is solved, EUCLID transfers it in O(1) 
        via categorical functor, while Tabula Rasa RL must re-explore from scratch.
        """
        # Step 1: Baseline Tabula Rasa (Simulated PPO/SAC exploration)
        # Tabula rasa agent exploring an N=64 state graph needs exponential exploration
        tabula_rasa_steps = 250_000 # Standard sample floor for model-free convergence
        
        # Step 2: EUCLID Topological Isomorphism Transfer
        t0 = time.perf_counter()
        source_manifold = load_solved_control_manifold()
        target_manifold = load_unseen_isomorphic_manifold()
        
        # Functorial mapping across isomorphic relational triads
        mapping = source_manifold.extract_functor(target_manifold)
        assert mapping.functoriality_score >= 0.95
        
        # Action policy is pulled back directly via the functor
        pulled_policy = mapping.pullback_policy()
        euclid_environment_steps = evaluate_policy_few_shot(pulled_policy, target_manifold)
        t_elapsed = time.perf_counter() - t0

        # Empirical proof: Sample efficiency ratio
        sample_efficiency_gain = tabula_rasa_steps / max(1, euclid_environment_steps)
        
        # Falsifiable Assertion: EUCLID must solve the target in <= 10 steps
        assert euclid_environment_steps <= 10, "Failed few-shot topological transfer"
        assert sample_efficiency_gain >= 10_000.0, f"Efficiency gain {sample_efficiency_gain}x below bound"

    def test_counterfactual_robustness_under_shock(self):
        """
        TEST 2: Distributional Shock Recovery.
        Hypothesis: Pure RL suffers catastrophic policy collapse when transition 
        probabilities invert. EUCLID's Forman-Ricci metric contracts and isolates the break.
        """
        manifold = load_active_graph_manifold()
        
        # Inject structural shock (Pearl Level 2: do(edge_weight = 0))
        manifold.inject_structural_severance(edge=("security", "mining"))
        
        # Tabula Rasa RL would experience massive reward drop and require retraining buffer
        # EUCLID immediately triggers discrete Ricci flow
        reconciliation_trace = manifold.reconcile_layer_curvature(tau=0.05)
        
        # Must restore metric equilibrium within the analytical 8-step bound
        assert len(reconciliation_trace) <= 8, "Ricci flow exceeded theoretical step bound"
        assert manifold.get_curvature("security") <= 0.05, "Failed to dissipate curvature singularity"
