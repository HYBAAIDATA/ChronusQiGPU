"""Bounded scientific witness tests; these are not physical measurements."""
from fractions import Fraction
import pytest
from chronus.geodesic.discovery import MetricConstraint
from chronus.geodesic.problems import SATProblem
from chronus.research.frontier import (
    finite_search_witness, logical_storage_witness, metric_descent_witness,
    physical_claim_gate,
)


def test_cassini_and_logical_spiral_not_ecc():
    for n in (1, 2, 5, 64):
        out = logical_storage_witness(n, b"operator-provided-input")
        assert out["cassini_witness"] == (-1 if n % 2 else 1)
        assert not out["physical_placement_verified"]
        assert not out["payload_error_corrected"]
        assert 0 <= out["coordinate"]["lane"] < 32
    with pytest.raises(ValueError):
        logical_storage_witness(0, b"payload")
    with pytest.raises(ValueError):
        logical_storage_witness(1, b"")


def test_metric_learning_is_bounded_exact_spd_not_global_flow():
    constraints = (MetricConstraint((Fraction(1), Fraction(0)), Fraction(2)),)
    out = metric_descent_witness(constraints, dimension=2, max_steps=3)
    assert out["spd_verified"] and out["monotone_descent_verified"]
    assert not out["arbitrary_riemannian_flow_claimed"]
    assert not out["metric_optimality_proven"]


def test_exhaustive_geodesic_order_is_not_logarithmic_search():
    problem = SATProblem(3, ((1,), (-2, 3)))
    out = finite_search_witness(problem, repetitions=1)
    assert out["benchmark"]["same_oracle_call_count_verified"]
    assert not out["asymptotic_logarithmic_search_proven"]
    assert not out["physical_quantum_advantage_proven"]
    assert all(t["oracle_calls"] == 8 for t in out["benchmark"]["trials"])


def test_physical_holds_are_not_autopromoted():
    out = physical_claim_gate()
    assert out["phi_optimal_physical_packing"] == "UNVERIFIED"
    assert out["thermodynamic_entropy_per_operation"] == "UNVERIFIED"
    assert out["quantum_decoherence"] == "NOT_APPLICABLE_TO_CLASSICAL_TABLEAU"
