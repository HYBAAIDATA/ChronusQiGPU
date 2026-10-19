"""Property-based tests (13/13) for Intelligence.theoretical_foundations using Hypothesis."""

from __future__ import annotations

import math
from hypothesis import HealthCheck, given, settings, strategies as st

from Intelligence.theoretical_foundations import (
    OR_THRESHOLD,
    PHI,
    TSIRELSON_BOUND,
    CategoryTheoreticFunctor,
    DeutschKnowledgeSubstrate,
    DuSautoySymmetry,
    ErgodicTopologicalWinding,
    GoldenRatioSymplecticFlow,
    LucasNumberSubstrate,
    NonLocalStructuralCorrelation,
    PenroseObjectiveReduction,
    ZeckendorfBitCascade,
)


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    de=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    dt=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
)
def test_prop_01_penrose_threshold_equivalence(de: float, dt: float):
    penrose = PenroseObjectiveReduction(threshold=OR_THRESHOLD)
    res = penrose.evaluate_superposition(de, dt)
    assert res["collapsed"] == (abs(de) * max(0.0, dt) >= OR_THRESHOLD)
    assert 0.0 <= res["phi"] <= 1.0


@settings(max_examples=25, deadline=None)
@given(
    de=st.floats(min_value=1.0, max_value=50.0, allow_nan=False, allow_infinity=False),
    dt=st.floats(min_value=1.0, max_value=50.0, allow_nan=False, allow_infinity=False),
)
def test_prop_02_penrose_monotonic_phi_on_collapse(de: float, dt: float):
    penrose = PenroseObjectiveReduction(threshold=0.5)
    phi_0 = penrose.current_phi
    res = penrose.evaluate_superposition(de, dt)
    assert res["collapsed"] is True
    assert res["phi"] >= phi_0


@settings(max_examples=25, deadline=None)
@given(
    perturbation=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    err=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
def test_prop_03_deutsch_hard_to_vary_bounded(perturbation: float, err: float):
    deutsch = DeutschKnowledgeSubstrate()
    exp = deutsch.conjecture(
        "prop_c",
        "math",
        "Invariant explanation",
        invariants=[1.0, 2.0, 3.0],
        counterfactual_perturbation=perturbation,
    )
    assert 0.0 <= exp.hard_to_vary_score <= 1.0
    crit = deutsch.criticize("prop_c", err)
    assert 0.0 <= crit["hard_to_vary_score"] <= 1.0
    assert crit["refuted"] == (err > 0.5)


@settings(max_examples=20, deadline=None)
@given(n=st.integers(min_value=2, max_value=40))
def test_prop_04_du_sautoy_orbits_partition_set(n: int):
    sym = DuSautoySymmetry(num_nodes=n)
    orbits = sym.compute_orbits()
    flat = [node for orb in orbits for node in orb]
    assert sorted(flat) == list(range(n))
    assert len(set(flat)) == n


@settings(max_examples=25, deadline=None)
@given(
    vec=st.lists(
        st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        min_size=4,
        max_size=16,
    )
)
def test_prop_05_du_sautoy_automorphism_l2_norm_invariance(vec: list[float]):
    n = len(vec)
    sym = DuSautoySymmetry(num_nodes=n)
    shift = {i: (i + 1) % n for i in range(n)}
    mapped = sym.apply_automorphism(vec, shift)
    norm_before = sum(x * x for x in vec)
    norm_after = sum(x * x for x in mapped)
    assert math.isclose(norm_before, norm_after, rel_tol=1e-9, abs_tol=1e-9)


@settings(max_examples=30, deadline=None)
@given(n=st.integers(min_value=0, max_value=60))
def test_prop_06_lucas_cassini_identity_exact(n: int):
    sub = LucasNumberSubstrate()
    assert sub.verify_cassini(n) is True


@settings(max_examples=30, deadline=None)
@given(n=st.integers(min_value=2, max_value=60))
def test_prop_07_lucas_recurrence_and_fibonacci_bridge(n: int):
    sub = LucasNumberSubstrate()
    assert sub.lucas(n) == sub.lucas(n - 1) + sub.lucas(n - 2)
    assert sub.lucas(n) == sub.fibonacci(n - 1) + sub.fibonacci(n + 1)


@settings(max_examples=25, deadline=None)
@given(n=st.integers(min_value=1, max_value=30))
def test_prop_08_pisot_drift_strictly_decreasing(n: int):
    sub = LucasNumberSubstrate()
    assert sub.pisot_drift(n + 1) < sub.pisot_drift(n)
    assert math.isclose(sub.pisot_drift(n) / sub.pisot_drift(n + 1), PHI, rel_tol=1e-9)


@settings(max_examples=35, deadline=None)
@given(val=st.integers(min_value=0, max_value=100_000))
def test_prop_09_zeckendorf_bijection_and_non_adjacency(val: int):
    z = ZeckendorfBitCascade()
    indices = z.encode(val)
    assert z.is_canonical(indices) is True
    assert z.decode(indices) == val


@settings(max_examples=25, deadline=None)
@given(theta=st.floats(min_value=-2.0 * math.pi, max_value=2.0 * math.pi, allow_nan=False, allow_infinity=False))
def test_prop_10_chsh_bounded_by_tsirelson(theta: float):
    corr = NonLocalStructuralCorrelation()
    val = corr.chsh_value(theta)
    assert abs(val) <= TSIRELSON_BOUND + 1e-12


@settings(max_examples=25, deadline=None)
@given(
    x=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    y=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
def test_prop_11_symplectic_flow_stays_on_unit_torus(x: float, y: float):
    flow = GoldenRatioSymplecticFlow()
    nx, ny = flow.step(x, y)
    assert 0.0 <= nx < 1.0
    assert 0.0 <= ny < 1.0
    assert flow.jacobian_determinant() == 1


@settings(max_examples=25, deadline=None)
@given(
    k1=st.integers(min_value=0, max_value=500),
    k2=st.integers(min_value=501, max_value=1000),
)
def test_prop_12_ergodic_winding_injectivity_on_torus(k1: int, k2: int):
    winding = ErgodicTopologicalWinding(dimension=11)
    assert winding.point_at(k1) != winding.point_at(k2)


@settings(max_examples=25, deadline=None)
@given(
    x=st.integers(min_value=-1000, max_value=1000),
    a=st.integers(min_value=-50, max_value=50),
    b=st.integers(min_value=-50, max_value=50),
)
def test_prop_13_functor_composition_law(x: int, a: int, b: int):
    functor = CategoryTheoreticFunctor(
        object_map=lambda v: [v],
        morphism_map=lambda fn: (lambda boxed: [fn(boxed[0])]),
    )
    f = lambda v: v + a
    g = lambda v: v * b
    lhs = functor.map_morphism(lambda v: g(f(v)))(functor.map_object(x))
    rhs = functor.map_morphism(g)(functor.map_morphism(f)(functor.map_object(x)))
    assert lhs == rhs
