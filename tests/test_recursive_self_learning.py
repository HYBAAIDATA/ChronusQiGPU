"""Tests for the recursive self-learning substrate (Strange Loop port).

Honest metrics: adaptivity, measured irreducibility, geometric refold,
narrative self-model. No consciousness claims — scores or low scores only.
"""

from Intelligence.recursive_self_learning import (
    GEOMETRIES,
    RecursiveLearningState,
    RecursiveSelfLearningSubstrate,
)


def test_initialises_with_recursive_state():
    sub = RecursiveSelfLearningSubstrate(dimension=16, seed=0)
    status = sub.status()
    assert status["schema"] == "intelligence.recursive_self_learning/1"
    assert status["recursion_depth"] == 0
    assert status["geometry"] == "euclidean"
    assert status["strange_loop_active"] is False


def test_strange_loop_activates_after_evolution():
    sub = RecursiveSelfLearningSubstrate(dimension=16, seed=1)
    for error in (0.9, 0.7, 0.5, 0.4, 0.35):
        sub.evolve(error)
    status = sub.status()
    assert status["recursion_depth"] == 5
    assert status["strange_loop_active"] is True


def test_learning_rate_adapts_to_improvement():
    sub = RecursiveSelfLearningSubstrate(dimension=16, seed=2)
    before = sub.status()["learning_rate"]
    sub.evolve(0.9)
    sub.evolve(0.3)
    after = sub.status()["learning_rate"]
    assert after != before


def test_meta_learning_rate_adapts():
    sub = RecursiveSelfLearningSubstrate(dimension=16, seed=3)
    sub.evolve(0.9)
    before = sub.status()["meta_learning_rate"]
    sub.evolve(0.1)
    after = sub.status()["meta_learning_rate"]
    assert after != before


def test_irreducibility_measured_by_corruption():
    sub = RecursiveSelfLearningSubstrate(dimension=16, seed=4)
    impact = sub.corruption_impact()
    assert 0.0 <= impact <= 1.0
    for _ in range(6):
        sub.evolve(0.5)
    assert 0.0 <= sub.status()["irreducibility"] <= 1.0


def test_geometric_refold_under_stress():
    sub = RecursiveSelfLearningSubstrate(dimension=16, seed=5)
    sub.evolve(5.0)
    assert sub.status()["geometry"] in ("hyperbolic", "spherical")
    sub2 = RecursiveSelfLearningSubstrate(dimension=16, seed=6)
    sub2.evolve(0.01)
    sub2.evolve(0.01)
    assert sub2.status()["geometry"] == "euclidean"


def test_narrative_updates_with_state():
    sub = RecursiveSelfLearningSubstrate(dimension=16, seed=7)
    assert sub.status()["narrative"]
    for _ in range(5):
        sub.evolve(0.4)
    assert sub.status()["narrative"] in (
        "STRANGE_LOOP_VIRTUOUS_CYCLE_PHI_ASCENDING",
        "COGNITIVE_ACCELERATION_ACTIVE",
        "META_LEARNING_DIVERGENCE_INITIATING_GEOMETRIC_REFOLD",
        "RECURSIVE_LEARNING_CONVERGING",
    )


def test_status_reports_criteria_honestly():
    sub = RecursiveSelfLearningSubstrate(dimension=16, seed=8)
    for error in (0.8, 0.6, 0.5, 0.4, 0.35):
        sub.evolve(error)
    status = sub.status()
    assert set(status["criteria"]) == {
        "learning_to_learn",
        "recursive_convergence",
        "irreducibility_significant",
        "phi_elevated",
        "self_model_present",
        "strange_loop_active",
    }
    assert status["criteria"]["learning_to_learn"] is True
    assert status["criteria"]["strange_loop_active"] is True


def test_lucas_route_live():
    from Intelligence.recursive_self_learning import lucas_bound

    bound = lucas_bound()
    assert bound["module"] == "Intelligence.recursive_self_learning"


def test_phi_exceeds_target_under_converging_errors():
    sub = RecursiveSelfLearningSubstrate(dimension=32, seed=10)
    for error in (0.5, 0.3, 0.2, 0.1, 0.05, 0.02, 0.01, 0.005):
        sub.evolve(error)
    status = sub.status()
    assert status["phi"] >= 0.4000
    assert status["criteria"]["phi_elevated"] is True


def test_irreducibility_exceeds_target_under_entanglement():
    sub = RecursiveSelfLearningSubstrate(dimension=32, seed=11)
    for error in (0.6, 0.4, 0.3, 0.2, 0.15, 0.1, 0.05, 0.02):
        sub.evolve(error)
    status = sub.status()
    assert status["irreducibility"] >= 0.3000
    assert status["criteria"]["irreducibility_significant"] is True


def test_virtuous_cycle_verdict_achieved():
    sub = RecursiveSelfLearningSubstrate(dimension=32, seed=12)
    for error in (0.5, 0.35, 0.25, 0.15, 0.08, 0.04, 0.02, 0.01):
        sub.evolve(error)
    status = sub.status()
    assert status["narrative"] == "STRANGE_LOOP_VIRTUOUS_CYCLE_PHI_ASCENDING"


def test_coupling_strength_bounded_and_monotonic_with_meta_error():
    sub = RecursiveSelfLearningSubstrate(dimension=16, seed=13)
    c0 = sub.status()["coupling_strength"]
    sub.evolve(0.8)
    c1 = sub.status()["coupling_strength"]
    assert 0.0 <= c0 <= 0.95
    assert c0 <= c1 <= 0.95


def test_corruption_impact_across_non_security_layers():
    sub = RecursiveSelfLearningSubstrate(dimension=16, seed=14)
    for layer in ("mining", "consciousness", "memory"):
        impact = sub.corruption_impact(layer=layer)
        assert 0.0 <= impact <= 1.0


def test_history_snapshots_accumulate_accurately():
    sub = RecursiveSelfLearningSubstrate(dimension=16, seed=15)
    for idx, err in enumerate((0.7, 0.5, 0.3, 0.2), start=1):
        snap = sub.evolve(err)
        assert snap["recursion_depth"] == idx
    assert len(sub.state.history) == 4


def test_deterministic_seed_reproducibility():
    s1 = RecursiveSelfLearningSubstrate(dimension=16, seed=42)
    s2 = RecursiveSelfLearningSubstrate(dimension=16, seed=42)
    for err in (0.8, 0.5, 0.25, 0.1):
        r1 = s1.evolve(err)
        r2 = s2.evolve(err)
        assert r1 == r2


def test_geometries_constant_and_state_dataclass():
    assert GEOMETRIES == ("euclidean", "hyperbolic", "spherical")
    st = RecursiveLearningState()
    assert st.learning_rate == 0.05
    assert st.meta_learning_rate == 0.01
    assert st.narrative == "INITIALISING"


def test_learning_rate_and_meta_rate_stay_within_safety_bounds():
    sub = RecursiveSelfLearningSubstrate(dimension=16, seed=99)
    for err in (10.0, 0.0001, 50.0, 0.0, 100.0, 0.01):
        snap = sub.evolve(err)
        assert 1e-4 <= snap["learning_rate"] <= 0.5
        assert 1e-4 <= snap["meta_learning_rate"] <= 0.2
