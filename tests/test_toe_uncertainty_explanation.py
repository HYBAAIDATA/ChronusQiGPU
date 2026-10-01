"""Native uncertainty taxonomy + calibration + computational explanation
— elevation §§11-15."""

from __future__ import annotations

from toe.causal_ladder import CausalGraph, StructuralCausalModel
from toe.decision_explanation import (
    explain_contrastive,
    explain_decision,
    falsify_decision,
    falsify_explanation,
)
from toe.explanation import explain, structural_model
from toe.policy import Constraint, Objective, counterfactual_futures, decide
from toe.uncertainty import (
    EVIDENCE_MEASURED,
    EVIDENCE_PROPAGATED,
    EVIDENCE_STRUCTURALLY_ABSENT,
    calibrate_effects,
    calibrate_futures,
    uncertainty_report,
)


def _scm_confounded() -> StructuralCausalModel:
    g = CausalGraph.from_edges([("z", "x"), ("z", "y"), ("x", "y")])
    g.edge_weights[("z", "x")] = 0.8
    g.edge_weights[("z", "y")] = 0.7
    g.edge_weights[("x", "y")] = 0.5
    return StructuralCausalModel(graph=g)


class TestUncertaintyTaxonomy:
    def test_five_axes_present_and_separate(self):
        scm = _scm_confounded()
        samples = scm.sample(300, seed=1)
        rep = uncertainty_report(scm, "x", "y", samples=samples, do_values=(0.0, 1.0))
        assert set(rep["axes"]) == {
            "identifiability",
            "aleatoric",
            "model",
            "structural",
            "missing_evidence",
        }
        assert rep["axes"]["identifiability"] == "IDENTIFIED"
        assert rep["axes"]["aleatoric"] > 0
        assert rep["evidence_class"] == EVIDENCE_MEASURED
        assert rep["estimate"]["adjusted_effect"] is not None
        assert rep["confidence"] is None  # no fake probability

    def test_not_identified_is_structurally_absent(self):
        g = CausalGraph.from_edges([("u", "x"), ("u", "y"), ("x", "y")])
        scm = StructuralCausalModel(graph=g)
        rep = uncertainty_report(scm, "x", "y", observed={"x", "y"})
        assert rep["evidence_class"] == EVIDENCE_STRUCTURALLY_ABSENT
        assert rep["estimate"] is None

    def test_propagated_when_no_samples(self):
        scm = _scm_confounded()
        rep = uncertainty_report(scm, "x", "y")
        assert rep["evidence_class"] == EVIDENCE_PROPAGATED
        assert rep["axes"]["aleatoric"] is not None

    def test_model_axis_measures_class_spread(self):
        scm = _scm_confounded()
        samples = scm.sample(400, seed=3)
        rep = uncertainty_report(scm, "x", "y", samples=samples)
        # equivalence class must exist and spread is measured
        assert rep.get("model_axis_detail") is not None
        assert rep["model_axis_detail"]["equivalence_class_size"] >= 1


class TestCalibration:
    def test_effect_calibration_measured(self):
        scm = _scm_confounded()
        out = calibrate_effects(
            scm, "x", "y", k_experiments=12, n_samples=400, seed=21
        )
        assert out["usable"] >= 10
        # a well-calibrated estimator: rmse ≈ mean SE, 95% coverage ≈ 0.95
        assert out["coverage"]["95%"] is not None
        assert 0.5 < out["rmse_vs_mean_se_ratio"] < 2.0

    def test_future_bands_cover_near_nominal(self):
        scm = _scm_confounded()
        out = calibrate_futures(
            scm,
            [{"name": "A", "interventions": {"x": 1.0}}],
            ["z", "x", "y"],
            worlds=200,
            seed=4,
        )
        # Gaussian bands under a linear model: near 0.90 coverage
        assert 0.75 < out["empirical_coverage"] < 0.99


class TestDecisionExplanation:
    def _decision(self):
        scm = _scm_confounded()
        futures = counterfactual_futures(scm, outcomes=["z", "x", "y"])
        factual = {"z": 1.0, "x": 0.9, "y": 1.15}
        dec = decide(
            factual,
            {"A": {"x": 2.0}, "B": {"x": -1.0}, "C": {"x": 5.0}},
            futures=futures,
            objective=Objective(target="y", sense="maximize"),
            constraints=[Constraint(name="y_cap", variable="y", op="<", bound=3.0)],
            model_id="test-scm",
        )
        return dec, scm, factual

    def test_explain_decision_components(self):
        dec, scm, _ = self._decision()
        assert dec.available
        ex = explain_decision(dec, scm=scm)
        for key in (
            "objective",
            "active_causes",
            "causal_paths_to_target",
            "constraints",
            "rejected_alternatives",
            "provenance",
        ):
            assert key in ex
        assert ex["active_causes"] == ["x"]
        assert ex["causal_paths_to_target"]["x"] == [["x", "y"]]
        # C violates y<=3.0 (y = .5*5 + .7*z = 3.2) — rejected with reason
        c = [r for r in ex["rejected_alternatives"] if r["action"] == "C"][0]
        assert "violates" in (c["reason"] or "")

    def test_contrastive_exposes_decisive_factor(self):
        dec, scm, _ = self._decision()
        out = explain_contrastive(dec, "C", scm=scm)
        assert out["available"]
        assert out["constraint_delta"]["only_rejected_violates"] == ["y_cap"]
        assert "inadmissible" in out["decisive_factor"]
        # changing the decisive factor: remove the constraint, C wins
        scm2 = _scm_confounded()
        dec2 = decide(
            {"z": 1.0, "x": 0.9, "y": 1.15},
            {"A": {"x": 2.0}, "C": {"x": 5.0}},
            futures=counterfactual_futures(scm2, outcomes=["z", "x", "y"]),
            objective=Objective(target="y", sense="maximize"),
            constraints=[],
            model_id="test-scm",
        )
        assert dec2.selected_action == "C"

    def test_falsify_explanation_verifies_attributions(self):
        scm = _scm_confounded()
        model = structural_model(scm)
        instance = {"x": 1.5, "z": 1.0}
        background = {"x": 0.0, "z": 0.0}
        ex = explain(
            model, instance, target="y", background=background, model_id="m"
        )
        assert ex.available
        f = falsify_explanation(
            model, instance, background, ex.attributions, "y"
        )
        assert f["claims_tested"] == 2
        assert f["faithfulness"] == 1.0

    def test_falsify_decision_reproduces_ordering(self):
        dec, scm, factual = self._decision()
        futures = counterfactual_futures(scm, outcomes=["z", "x", "y"])
        out = falsify_decision(dec, futures_fn=futures, state=factual)
        assert out["available"]
        assert out["comparisons"] >= 1
        assert all(c["ordering_reproduced"] for c in out["checks"])
