"""Tests for the recursive self-learning substrate (Strange Loop port).

Honest metrics: adaptivity, measured irreducibility, geometric refold,
narrative self-model. No consciousness claims — scores or low scores only.
"""

from Intelligence.recursive_self_learning import RecursiveSelfLearningSubstrate


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
