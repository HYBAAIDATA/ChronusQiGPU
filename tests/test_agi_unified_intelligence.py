"""Unified-intelligence substrate: real measurements, honest reporting.

These tests assert measured properties of the implementation, not that symbols
exist:

* the substrate's integrability check is a genuine linear-algebra assertion;
* the entropy is a real von Neumann entropy of the coherence field;
* AHP produces a normalised principal eigenvector and a real consistency ratio;
* Monte Carlo is reproducible for a fixed seed and uses supplied samples;
* the validator reports measured criteria and refuses to overstate its meaning.
"""

import asyncio
import math

import numpy as np

from agi.unified_intelligence import (
    AxiomSet,
    ComputationalSubstrate,
    McKinseyDecisionContext,
    McKinseyDecisionEngine,
    ScientificValidator,
    UnifiedIntelligenceFactory,
)

# === TESTS ===


def test_substrate_passes_its_own_integrability_check():
    s = ComputationalSubstrate(n_nodes=8, seed=7)
    assert s.check_integrability() is True
    # The check is real: perturbing degrees must break it.
    s.degrees = s.degrees + 1.0
    assert s.check_integrability() is False


def test_total_information_is_a_real_entropy():
    s = ComputationalSubstrate(n_nodes=8, seed=7)
    total = s.calculate_total_information()
    probs = np.abs(s.psi_field) ** 2
    probs = probs / probs.sum()
    expected = float(-(probs * np.log(probs)).sum())
    assert math.isclose(total, expected, rel_tol=1e-12)
    assert 0.0 <= total <= math.log(s.n_nodes) + 1e-9


def test_substrate_is_deterministic_for_a_fixed_seed():
    a = ComputationalSubstrate(n_nodes=8, seed=7)
    b = ComputationalSubstrate(n_nodes=8, seed=7)
    assert np.allclose(a.phi_field, b.phi_field)
    c = ComputationalSubstrate(n_nodes=8, seed=99)
    assert not np.allclose(a.phi_field, c.phi_field)


def test_phi_field_is_bounded():
    s = ComputationalSubstrate(n_nodes=8, seed=7)
    assert np.all(s.phi_field >= 0.0)
    assert np.all(s.phi_field <= 1.0)


def test_gauge_curvature_is_finite_and_non_negative():
    s = ComputationalSubstrate(n_nodes=8, seed=7)
    curvature = s.calculate_gauge_curvature()
    assert math.isfinite(curvature)
    assert curvature >= 0.0


# --- axioms ---------------------------------------------------------------


def test_every_axiom_reports_a_value_and_a_boolean():
    axioms = AxiomSet(ComputationalSubstrate(n_nodes=8, seed=7))
    results = axioms.evaluate_all({"phi_feedback": 0.9})
    assert results
    for result in results.values():
        assert "value" in result
        assert isinstance(result["holds"], bool)


def test_all_hold_agrees_with_evaluate_all():
    axioms = AxiomSet(ComputationalSubstrate(n_nodes=8, seed=7))
    metrics = {"phi_feedback": 0.9}
    expected = all(r["holds"] for r in axioms.evaluate_all(metrics).values())
    assert axioms.all_hold(metrics) is expected


def test_recursive_self_reference_is_contractive_for_unit_gain():
    axioms = AxiomSet(ComputationalSubstrate(n_nodes=8, seed=7))
    substrate_mean = float(substrate_mean_of(axioms))
    result = axioms.recursive_self_reference({"phi_feedback": 1.0})
    assert math.isclose(result["value"], substrate_mean, rel_tol=1e-12)
    assert result["holds"] is True


def substrate_mean_of(axioms: AxiomSet) -> float:
    """Helper: the mean phi-field of the axiom set's substrate."""
    return float(axioms.substrate.phi_field.mean())


def test_quantum_classical_duality_preserves_the_probability_norm():
    substrate = ComputationalSubstrate(n_nodes=8, seed=7)
    axioms = AxiomSet(substrate)
    rotated = axioms.quantum_classical_duality(substrate, math.pi / 4.0)
    before = float(np.abs(substrate.psi_field).sum())
    after = float(np.abs(rotated.psi_field).sum())
    assert math.isclose(before, after, rel_tol=1e-12)


# --- endpoint lifecycle ---------------------------------------------------


def test_endpoint_cycle_returns_the_documented_fields():
    endpoint = UnifiedIntelligenceFactory.create_agi_endpoint(8)
    record = asyncio.run(endpoint.run_intelligence_loop())
    for key in (
        "cycle",
        "total_information",
        "gauge_curvature",
        "integrability_satisfied",
        "axioms",
        "axioms_held",
        "axioms_total",
    ):
        assert key in record
    assert record["cycle"] == 1
    assert 0 <= record["axioms_held"] <= record["axioms_total"]


def test_endpoint_cycles_increment_and_are_recorded():
    endpoint = UnifiedIntelligenceFactory.create_agi_endpoint(8)
    asyncio.run(endpoint.run_intelligence_loop())
    asyncio.run(endpoint.run_intelligence_loop())
    report = asyncio.run(endpoint.report())
    assert report["cycles_completed"] == 2
    assert len(endpoint.history()) == 2


def test_endpoint_report_disclaims_consciousness():
    report = asyncio.run(UnifiedIntelligenceFactory.create_agi_endpoint(8).report())
    assert "does not assert" in report["claim"]


def test_factory_roles_use_distinct_substrates():
    agi = UnifiedIntelligenceFactory.create_agi_endpoint(8)
    pci = UnifiedIntelligenceFactory.create_pci_endpoint(8)
    assert agi.role == "agi" and pci.role == "pci"
    agi_report = asyncio.run(agi.report())
    pci_report = asyncio.run(pci.report())
    assert agi_report["total_information"] != pci_report["total_information"]


# --- decision context / AHP ----------------------------------------------


def test_context_normalises_weights_and_handles_zero_weights():
    ctx = McKinseyDecisionContext(
        alternatives={"a": {"cost": 1}}, criteria_weights={"cost": 3.0, "risk": 1.0}
    )
    weights = ctx.normalised_weights()
    assert math.isclose(sum(weights.values()), 1.0, rel_tol=1e-12)

    zero = McKinseyDecisionContext(alternatives={"a": {"cost": 1}}, criteria_weights={"cost": 0.0})
    assert math.isclose(sum(zero.normalised_weights().values()), 1.0, rel_tol=1e-12)


def test_empty_context_is_reported_invalid_not_crashed():
    engine = McKinseyDecisionEngine()
    empty = McKinseyDecisionContext()
    assert empty.is_valid() is False
    assert engine.analytic_hierarchy_process(empty)["status"] == "invalid_context"
    assert engine.monte_carlo_simulation(empty)["status"] == "invalid_context"


def test_ahp_weights_are_normalised_and_ranked_descending():
    ctx = McKinseyDecisionContext(
        alternatives={
            "expand": {"cost": 3, "risk": 1},
            "hold": {"cost": 2, "risk": 3},
        },
        criteria_weights={"cost": 0.6, "risk": 0.4},
    )
    result = McKinseyDecisionEngine().analytic_hierarchy_process(ctx)
    assert result["status"] == "ok"
    total = sum(r["weight"] for r in result["rankings"])
    assert math.isclose(total, 1.0, rel_tol=1e-9)
    weights = [r["weight"] for r in result["rankings"]]
    assert weights == sorted(weights, reverse=True)


def test_ahp_reports_a_real_consistency_ratio():
    ctx = McKinseyDecisionContext(
        alternatives={"a": {"cost": 1}, "b": {"cost": 2}},
        criteria_weights={"cost": 1.0},
    )
    result = McKinseyDecisionEngine().analytic_hierarchy_process(ctx)
    assert result["consistency_ratio"] >= 0.0
    assert result["lambda_max"] >= 2.0
    assert result["random_index"] == McKinseyDecisionEngine._RI[2]


def test_ahp_is_deterministic():
    ctx = McKinseyDecisionContext(
        alternatives={"a": {"cost": 1}, "b": {"cost": 3}},
        criteria_weights={"cost": 1.0},
    )
    engine = McKinseyDecisionEngine()
    assert engine.analytic_hierarchy_process(ctx) == engine.analytic_hierarchy_process(ctx)


# --- Monte Carlo ---------------------------------------------------------


def test_monte_carlo_is_reproducible_for_a_fixed_seed():
    ctx = McKinseyDecisionContext(
        alternatives={"a": {"mean": 1.0, "std": 0.5}},
        criteria_weights={"cost": 1.0},
    )
    engine = McKinseyDecisionEngine()
    first = engine.monte_carlo_simulation(ctx, iterations=1000)
    second = engine.monte_carlo_simulation(ctx, iterations=1000)
    assert first == second
    assert first["distributions"]["a"]["method"] == "normal"


def test_monte_carlo_uses_supplied_samples_empirically():
    samples = [1.0, 2.0, 3.0, 4.0]
    ctx = McKinseyDecisionContext(
        alternatives={"a": {"samples": samples}}, criteria_weights={"cost": 1.0}
    )
    result = McKinseyDecisionEngine().monte_carlo_simulation(ctx)
    dist = result["distributions"]["a"]
    assert dist["method"] == "empirical"
    assert math.isclose(dist["mean"], float(np.mean(samples)), rel_tol=1e-12)
    assert dist["iterations"] == len(samples)


def test_monte_carlo_reports_risk_measures_in_range():
    ctx = McKinseyDecisionContext(
        alternatives={"a": {"mean": 2.0, "std": 1.0}},
        criteria_weights={"cost": 1.0},
    )
    dist = McKinseyDecisionEngine().monte_carlo_simulation(ctx, iterations=5000)["distributions"][
        "a"
    ]
    assert 0.0 <= dist["probability_positive"] <= 1.0
    assert dist["std"] > 0.0
    assert math.isfinite(dist["var_95"])


# --- validator -----------------------------------------------------------


def test_validator_reports_measured_criteria_and_its_limits():
    result = ScientificValidator().validate_unified_intelligence(
        UnifiedIntelligenceFactory.create_agi_endpoint(8),
        UnifiedIntelligenceFactory.create_pci_endpoint(8),
    )
    assert result["status"] == "ok"
    assert result["criteria_total"] == len(result["criteria"])
    assert result["criteria_passed"] == sum(1 for c in result["criteria"] if c["passed"])
    assert math.isclose(
        result["score"], result["criteria_passed"] / result["criteria_total"], rel_tol=1e-12
    )
    # The payload must not overstate its own meaning.
    assert "not a claim of" in result["interpretation"]


def test_validator_is_reproducible():
    validator = ScientificValidator()
    a = validator.validate_unified_intelligence(
        UnifiedIntelligenceFactory.create_agi_endpoint(8),
        UnifiedIntelligenceFactory.create_pci_endpoint(8),
    )
    b = validator.validate_unified_intelligence(
        UnifiedIntelligenceFactory.create_agi_endpoint(8),
        UnifiedIntelligenceFactory.create_pci_endpoint(8),
    )
    assert a == b
    assert a["reproducible"] is True
