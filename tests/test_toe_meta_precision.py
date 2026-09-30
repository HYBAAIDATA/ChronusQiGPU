"""Meta-reasoning, VOI, compute-aware routing, adaptive precision — §§27-31."""

from __future__ import annotations

from toe.causal_ladder import CausalGraph, StructuralCausalModel
from toe.meta_reasoning import (
    ACT_NOW,
    NO_ROUTE,
    RECOMMEND_GATHER_EVIDENCE,
    choose_path,
    meta_decide,
    value_of_information,
)
from toe.precision import (
    float_error_bound,
    measure_exactness,
    select_precision,
)


class TestMetaController:
    def test_gathers_evidence_when_unidentified_and_thin(self):
        out = meta_decide(
            identifiability="NOT_IDENTIFIED", evidence_count=1
        )
        assert out["recommendation"] == RECOMMEND_GATHER_EVIDENCE

    def test_gathers_evidence_on_near_tie(self):
        out = meta_decide(
            decision_margin=0.01, margin_tolerance=0.05,
            evidence_count=10, available_operators=["estimate_effect"],
        )
        assert out["recommendation"] == RECOMMEND_GATHER_EVIDENCE

    def test_acts_when_signals_justify(self):
        out = meta_decide(
            decision_margin=1.0, evidence_count=10,
            available_operators=["estimate_effect"],
        )
        assert out["recommendation"] == ACT_NOW
        assert out["operator"] == "estimate_effect"
        assert "signals" in out  # decisions tied to measured inputs

    def test_no_route_without_operators(self):
        out = meta_decide(decision_margin=1.0, evidence_count=10)
        assert out["recommendation"] == NO_ROUTE


class TestValueOfInformation:
    def test_irrelevant_evidence_not_requested(self):
        # decision invariant across the plausible range -> worthless
        out = value_of_information(
            parameter="noise_sd",
            plausible_range=[0.1, 0.5, 1.0],
            decision_fn=lambda p: "A",
        )
        assert out["decision_invariant"] is True
        assert out["recommend_evidence"] is False

    def test_decision_changing_evidence_requested(self):
        out = value_of_information(
            parameter="effect",
            plausible_range=[-1.0, 0.0, 1.0],
            decision_fn=lambda p: "A" if p > 0 else "B",
        )
        assert out["decision_invariant"] is False
        assert out["recommend_evidence"] is True
        assert out["flip_boundaries"] == 1


class TestComputeAware:
    def test_prefers_cheaper_adequate_path(self):
        out = choose_path(
            [
                {"name": "shapley-exact", "cost": 4096,
                 "correctness": "exact-answer"},
                {"name": "path-product", "cost": 8,
                 "correctness": "exact-answer"},
            ]
        )
        assert out["selected"] == "path-product"

    def test_never_trades_away_correctness(self):
        out = choose_path(
            [{"name": "heuristic", "cost": 1, "correctness": "heuristic"}],
            correctness_required="exact-answer",
        )
        assert out["selected"] is None
        assert "required correctness" in out["reason"]


def _chain(w: float = 1.0) -> StructuralCausalModel:
    g = CausalGraph.from_edges([("x", "y")])
    g.edge_weights[("x", "y")] = w
    return StructuralCausalModel(graph=g)


class TestAdaptivePrecision:
    def test_float_admissible_when_margin_large(self):
        scm = _chain()
        out = select_precision(
            scm, candidate_a={"x": 10.0}, candidate_b={"x": 1.0}, target="y"
        )
        assert out["regime"] == "float64"
        assert out["error_bound"] >= 0.0

    def test_exact_required_near_boundary(self):
        scm = _chain()
        tiny = 1e-16
        out = select_precision(
            scm,
            candidate_a={"x": 1.0 + tiny},
            candidate_b={"x": 1.0},
            target="y",
        )
        assert out["regime"] == "exact-required"

    def test_error_bound_is_honest(self):
        scm = _chain()
        b = float_error_bound(scm, {"x": 3.0})
        assert b["x"] == 0.0  # intervened input: no float error
        assert b["y"] >= 0.0


class TestExactnessResource:
    def test_float_error_flips_ordering_on_cancellation(self):
        # y = a - b on huge nearly-equal magnitudes: float catastrophically
        # cancels, exact arithmetic resolves. a,b -> y with weights +1, -1.
        g = CausalGraph.from_edges([("a", "y"), ("b", "y")])
        g.edge_weights[("a", "y")] = 1.0
        g.edge_weights[("b", "y")] = -1.0
        scm = StructuralCausalModel(graph=g)
        big = 10**16
        out = measure_exactness(
            scm,
            [
                # ints keep sub-ulp info for the exact path: a-b = 1 in
                # case A vs 0 in case B. fp64 cannot represent 1e16+1
                # (spacing 2) so the float path sees equal sums; the
                # ZPhi path preserves the +1 -> ordering flips.
                {"a": {"a": big + 1, "b": big}, "b": {"a": big, "b": big},
                 "target": "y"},
                # well-separated case: honest non-matter
                {"a": {"a": 10.0, "b": 0.0}, "b": {"a": 0.0, "b": 0.0},
                 "target": "y"},
            ],
        )
        c0, c1 = out["cases"]
        assert c0["ordering_changed"] is True
        assert c0["exactness_matters"] is True
        assert c1["exactness_matters"] is False
        assert out["matters_fraction"] == 0.5

    def test_constraint_satisfaction_flip(self):
        # constraint y <= 1e16 with a-b arithmetic at the boundary
        g = CausalGraph.from_edges([("a", "y"), ("b", "y")])
        g.edge_weights[("a", "y")] = 1.0
        g.edge_weights[("b", "y")] = -1.0
        scm = StructuralCausalModel(graph=g)
        out = measure_exactness(
            scm,
            [
                {
                    "a": {"a": 1e16, "b": 1.0},
                    "b": {"a": 0.0, "b": 0.0},
                    "target": "y",
                    "constraint": ("y", "<=", 1e16 - 1),
                },
            ],
        )
        assert "cases" in out
