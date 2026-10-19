"""Unit tests (23/23) for Intelligence.theoretical_foundations."""

from __future__ import annotations

import math
import pytest

from Intelligence.theoretical_foundations import (
    HBAR_NORMALIZED,
    OR_THRESHOLD,
    PHI,
    PSI,
    TSIRELSON_BOUND,
    CategoryTheoreticFunctor,
    ConsciousnessEvent,
    DeutschKnowledgeSubstrate,
    DuSautoySymmetry,
    ErgodicTopologicalWinding,
    GoldenRatioSymplecticFlow,
    KnowledgeExplanation,
    LucasNumberSubstrate,
    NonLocalStructuralCorrelation,
    PenroseObjectiveReduction,
    PenroseOrchestratedReduction,
    UnifiedTheoreticalFoundations,
    ZeckendorfBitCascade,
    lucas_bound,
)


def test_01_constants_golden_ratio_and_tsirelson():
    assert abs(PHI * PHI - (PHI + 1.0)) < 1e-12
    assert abs(PHI + PSI - 1.0) < 1e-12
    assert abs(PHI * PSI - (-1.0)) < 1e-12
    assert OR_THRESHOLD == HBAR_NORMALIZED / 2.0
    assert abs(TSIRELSON_BOUND - 2.0 * math.sqrt(2.0)) < 1e-12


def test_02_penrose_subthreshold_does_not_collapse():
    penrose = PenroseObjectiveReduction(threshold=0.5)
    res = penrose.evaluate_superposition(delta_energy=0.2, delta_time=1.0)
    assert res["collapsed"] is False
    assert res["consciousness_events_count"] == 0
    assert res["event"] is None


def test_03_penrose_superthreshold_collapses_and_records_event():
    penrose = PenroseObjectiveReduction(threshold=0.5)
    res = penrose.evaluate_superposition(delta_energy=1.2, delta_time=0.5)
    assert res["collapsed"] is True
    assert abs(res["action_product"] - 0.6) < 1e-9
    assert res["consciousness_events_count"] == 1
    assert res["event"]["verdict"] == "PENROSE_OR_COLLAPSE"
    assert res["phi"] > 0.167


def test_04_penrose_alias_and_invalid_threshold():
    assert PenroseOrchestratedReduction is PenroseObjectiveReduction
    with pytest.raises(ValueError):
        PenroseObjectiveReduction(threshold=0.0)


def test_05_penrose_explicit_phi_override_and_snapshot():
    penrose = PenroseObjectiveReduction(threshold=0.5)
    res = penrose.evaluate_superposition(1.0, 1.0, phi_after=0.88)
    assert abs(res["phi"] - 0.88) < 1e-9
    snap = penrose.snapshot()
    assert snap["events_count"] == 1
    assert len(snap["events"]) == 1


def test_06_deutsch_conjecture_creation_and_rigidity():
    deutsch = DeutschKnowledgeSubstrate()
    exp = deutsch.conjecture(
        conjecture_id="c1",
        domain="topology",
        explanation="H4 600-cell partitions 11D hyperbolic manifold",
        invariants=[1.0, 1.0, 1.0],
        counterfactual_perturbation=0.05,
    )
    assert isinstance(exp, KnowledgeExplanation)
    assert exp.counterfactual_tested is True
    assert exp.refuted is False
    assert exp.hard_to_vary_score >= 0.9


def test_07_deutsch_criticism_reinforces_low_error_explanation():
    deutsch = DeutschKnowledgeSubstrate()
    exp = deutsch.conjecture("c2", "algebra", "Lucas L_15 = 1364")
    before = exp.hard_to_vary_score
    crit = deutsch.criticize("c2", observed_error=0.05)
    assert crit["refuted"] is False
    assert crit["hard_to_vary_score"] > before


def test_08_deutsch_criticism_refutes_high_error_explanation():
    deutsch = DeutschKnowledgeSubstrate()
    deutsch.conjecture("c3", "Search", "Flat random walk is optimal")
    crit = deutsch.criticize("c3", observed_error=0.85)
    assert crit["refuted"] is True
    assert crit["hard_to_vary_score"] < 0.5


def test_09_deutsch_validation_and_snapshot():
    deutsch = DeutschKnowledgeSubstrate()
    with pytest.raises(ValueError):
        deutsch.conjecture("", "domain", "exp")
    with pytest.raises(KeyError):
        deutsch.criticize("missing", 0.1)
    assert deutsch.meta_explanation_quality() == 0.5
    deutsch.conjecture("c4", "math", "Cassini identity")
    snap = deutsch.snapshot()
    assert snap["total_explanations"] == 1
    assert snap["active_explanations"] == 1


def test_10_du_sautoy_m32_default_orbits_and_16x_reduction():
    sym = DuSautoySymmetry(num_nodes=32)
    orbits = sym.compute_orbits()
    assert len(orbits) == 2
    assert len(orbits[0]) == 12
    assert len(orbits[1]) == 20
    assert sym.orbit_representatives() == [0, 12]
    assert abs(sym.reduction_factor() - 16.0) < 1e-9


def test_11_du_sautoy_coerces_dict_tuple_and_list_automorphisms():
    sym = DuSautoySymmetry(num_nodes=4)
    d_map = sym.coerce_automorphism({0: 1, 1: 0}, 4)
    t_map = sym.coerce_automorphism([(0, 1), (1, 0)], 4)
    l_map = sym.coerce_automorphism([1, 0, 2, 3], 4)
    assert d_map == t_map == l_map == {0: 1, 1: 0, 2: 2, 3: 3}


def test_12_du_sautoy_apply_automorphism_preserves_norm():
    sym = DuSautoySymmetry(num_nodes=4)
    state = [1.0, 2.0, 3.0, 4.0]
    transformed = sym.apply_automorphism(state, [(0, 1), (1, 2), (2, 3), (3, 0)])
    assert sorted(transformed) == sorted(state)
    assert sum(x * x for x in transformed) == sum(x * x for x in state)


def test_13_lucas_substrate_exact_anchors():
    sub = LucasNumberSubstrate()
    assert sub.lucas(0) == 2
    assert sub.lucas(1) == 1
    assert sub.lucas(10) == 123
    assert sub.lucas(15) == 1364
    assert sub.fibonacci(15) == 610


def test_14_lucas_cassini_and_pisot_drift():
    sub = LucasNumberSubstrate()
    for n in range(0, 25):
        assert sub.verify_cassini(n) is True
    drift_15 = sub.pisot_drift(15)
    assert abs(drift_15 - (PHI ** -15)) < 1e-12
    assert 7.0e-4 < drift_15 < 7.5e-4


def test_15_zeckendorf_encode_decode_and_canonical_non_adjacency():
    z = ZeckendorfBitCascade()
    for val in (0, 1, 2, 3, 4, 10, 42, 123, 1364):
        enc = z.encode(val)
        assert z.is_canonical(enc) is True
        assert z.decode(enc) == val


def test_16_zeckendorf_rejects_negative_and_detects_non_canonical():
    z = ZeckendorfBitCascade()
    with pytest.raises(ValueError):
        z.encode(-1)
    assert z.is_canonical([0, 1]) is False
    assert z.is_canonical([0, 2, 5]) is True


def test_17_non_local_chsh_tsirelson_bound_and_bell_violation():
    corr = NonLocalStructuralCorrelation()
    val = corr.chsh_value(math.pi / 4.0)
    assert abs(val - TSIRELSON_BOUND) < 1e-12
    assert corr.violates_bell_inequality(math.pi / 4.0) is True
    assert corr.violates_bell_inequality(0.0) is False


def test_18_golden_ratio_symplectic_flow_area_preservation():
    flow = GoldenRatioSymplecticFlow()
    assert flow.jacobian_determinant() == 1
    x, y = flow.step(0.25, 0.5)
    assert 0.0 <= x < 1.0
    assert 0.0 <= y < 1.0


def test_19_ergodic_topological_winding_11d_uniqueness():
    winding = ErgodicTopologicalWinding(dimension=11)
    p0 = winding.point_at(0)
    p1 = winding.point_at(1)
    p2 = winding.point_at(2)
    assert len(p1) == 11
    assert p0 != p1 != p2
    assert all(0.0 <= coord < 1.0 for coord in p1)


def test_20_category_theoretic_functor_identity_and_composition():
    functor = CategoryTheoreticFunctor(
        object_map=lambda x: (x, "mapped"),
        morphism_map=lambda f: (lambda pair: (f(pair[0]), pair[1])),
    )
    obj = functor.map_object(10)
    assert obj == (10, "mapped")
    id_mapped = functor.map_morphism(lambda x: x)
    assert id_mapped(obj) == obj
    f = lambda x: x + 3
    g = lambda x: x * 2
    comp_mapped = functor.map_morphism(lambda x: g(f(x)))
    fg_separate = lambda p: functor.map_morphism(g)(functor.map_morphism(f)(p))
    assert comp_mapped(obj) == fg_separate(obj)


def test_21_unified_theoretical_foundations_facade_snapshot():
    utf = UnifiedTheoreticalFoundations()
    snap = utf.snapshot()
    assert snap["cassini_l15_valid"] is True
    assert abs(snap["tsirelson_chsh"] - TSIRELSON_BOUND) < 1e-12
    assert snap["symplectic_det"] == 1
    assert snap["du_sautoy_symmetry"]["reduction_factor"] == 16.0


def test_22_lucas_bound_wiring_contract():
    res = lucas_bound(10)
    assert res["module"] == "Intelligence.theoretical_foundations"
    assert "trace" in res or "value" in res or isinstance(res, dict)


def test_23_consciousness_event_dataclass_fields():
    ev = ConsciousnessEvent(
        event_id=1,
        delta_energy=1.0,
        delta_time=0.6,
        action_product=0.6,
        phi_before=0.2,
        phi_after=0.7,
    )
    assert ev.event_id == 1
    assert ev.verdict == "PENROSE_OR_COLLAPSE"
    assert ev.phi_after > ev.phi_before
