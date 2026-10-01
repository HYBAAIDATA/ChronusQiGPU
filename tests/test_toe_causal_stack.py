"""Causal capability stack — elevation §§6-10.

The §7 battery is the brief's own list: observed confounder, latent
confounder, collider, mediator, instrument, clean DAG, M-bias, and
insufficient variables. Refusal to answer is a capability and is tested
as such. §8 discovery must return an equivalence class, not an invented
unique DAG.
"""

from __future__ import annotations

import pytest

from toe.causal_ladder import (
    CausalGraph,
    StructuralCausalModel,
    identify_frontdoor,
)
from toe.causal_stack import (
    IDENTIFIED,
    NOT_IDENTIFIED,
    PARTIALLY_IDENTIFIED,
    STAGE_COUNTERFACTUAL_GENERATED,
    STAGE_EFFECT_IDENTIFIED,
    STAGE_EFFECT_NOT_IDENTIFIED,
    STAGE_GRAPH_LEARNED,
    STAGE_INTERVENTION_EXECUTED,
    UNAVAILABLE,
    compare_worlds,
    discover_structures,
    evaluate_futures,
    identifiability,
)


def _g(edges):
    return CausalGraph.from_edges(edges)


class TestIdentifiabilityBattery:
    """Each scenario is a DAG the literature has a known answer for."""

    def test_clean_dag_no_adjustment(self):
        g = _g([("x", "y")])
        r = identifiability(g, "x", "y")
        assert r["verdict"] == IDENTIFIED
        assert r["strategy"] == "no_adjustment"
        assert r["adjustment_set"] == []
        assert r["stage"] == STAGE_EFFECT_IDENTIFIED

    def test_observed_confounder_backdoor(self):
        g = _g([("z", "x"), ("z", "y"), ("x", "y")])
        r = identifiability(g, "x", "y")
        assert r["verdict"] == IDENTIFIED
        assert r["strategy"] == "backdoor"
        assert r["adjustment_set"] == ["z"]

    def test_latent_confounder_refused(self):
        g = _g([("u", "x"), ("u", "y"), ("x", "y")])
        r = identifiability(g, "x", "y", observed={"x", "y"})
        assert r["verdict"] == NOT_IDENTIFIED
        assert r["stage"] == STAGE_EFFECT_NOT_IDENTIFIED
        assert "u" in r["reason"]

    def test_mediator_identified_no_adjustment(self):
        # x -> m -> y: no backdoor at all -> identified with empty set
        g = _g([("x", "m"), ("m", "y")])
        r = identifiability(g, "x", "y")
        assert r["verdict"] == IDENTIFIED
        assert r["adjustment_set"] == []

    def test_frontdoor_when_latent_confounder_but_observed_mediator(self):
        # u latent confounds x,y; m observed mediator x->m->y
        g = _g([("u", "x"), ("u", "y"), ("x", "m"), ("m", "y")])
        r = identifiability(g, "x", "y", observed={"x", "m", "y"})
        assert r["verdict"] == IDENTIFIED
        assert r["strategy"] == "frontdoor"
        assert r["adjustment_set"] == ["m"]

    def test_collider_not_conditioned(self):
        # x -> c <- y: effect of x on y is zero; adjusting c is a trap
        g = _g([("x", "c"), ("y", "c")])
        r = identifiability(g, "x", "y")
        assert r["verdict"] == IDENTIFIED
        assert r["adjustment_set"] == []
        assert "c" in r["warnings"]

    def test_m_bias_covariate_excluded_with_warning(self):
        # classic M-graph: a->z<-b, a->x, b->y, x->y. Empty set is
        # admissible; conditioning on z would OPEN a path.
        g = _g(
            [
                ("a", "z"),
                ("b", "z"),
                ("a", "x"),
                ("b", "y"),
                ("x", "y"),
            ]
        )
        r = identifiability(g, "x", "y")
        assert r["verdict"] == IDENTIFIED
        assert r["adjustment_set"] == []
        assert "z" in r["warnings"]

    def test_instrument_partial(self):
        # z -> x, x -> y, u confounds x,y (latent). z is an instrument.
        g = _g([("z", "x"), ("x", "y"), ("u", "x"), ("u", "y")])
        r = identifiability(g, "x", "y", observed={"z", "x", "y"})
        assert r["verdict"] == PARTIALLY_IDENTIFIED
        assert r["strategy"] == "instrument"
        assert r["instruments"] == ["z"]

    def test_insufficient_variables_refused(self):
        # u1 -> x, u1 -> u2 -> y, u2 -> x  (all unobserved except x,y)
        g = _g(
            [
                ("u1", "x"),
                ("u1", "u2"),
                ("u2", "y"),
                ("u2", "x"),
                ("x", "y"),
            ]
        )
        r = identifiability(g, "x", "y", observed={"x", "y"})
        assert r["verdict"] == NOT_IDENTIFIED

    def test_unavailable_no_graph(self):
        r = identifiability(None, "x", "y")
        assert r["verdict"] == UNAVAILABLE

    def test_unavailable_not_dag(self):
        g = _g([("x", "y"), ("y", "x")])
        r = identifiability(g, "x", "y")
        assert r["verdict"] == UNAVAILABLE
        assert "DAG" in r["reason"]


class TestStrictFrontdoor:
    def test_frontdoor_requires_all_paths_intercepted(self):
        # x -> m -> y AND x -> y direct: m is a mediator but does NOT
        # intercept every directed path -> no frontdoor identification.
        g = _g([("u", "x"), ("u", "y"), ("x", "m"), ("m", "y"), ("x", "y")])
        assert identify_frontdoor(g, "x", "y") is None

    def test_frontdoor_true_case(self):
        g = _g([("u", "x"), ("u", "y"), ("x", "m"), ("m", "y")])
        assert identify_frontdoor(g, "x", "y") == ["m"]


class TestDiscovery:
    def test_recovers_v_structure_class(self):
        import random

        rng = random.Random(3)
        rows = {"a": [], "b": [], "c": []}
        for _ in range(400):
            ea, eb, ec = rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)
            rows["a"].append(ea)
            rows["b"].append(eb)
            rows["c"].append(0.9 * ea + 0.9 * eb + 0.2 * ec)
        out = discover_structures(rows)
        assert out["available"] and out["stage"] == STAGE_GRAPH_LEARNED
        assert ("a", "c") in out["skeleton"] and ("b", "c") in out["skeleton"]
        # a,b marginally independent -> v-structure a->c<-b oriented
        assert ("a", "c", "b") in out["v_structures"]

    def test_chain_returns_equivalence_class_not_unique_dag(self):
        import random

        rng = random.Random(5)
        rows = {"x": [], "m": [], "y": []}
        for _ in range(400):
            ex, em, ey = rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)
            rows["x"].append(ex)
            rows["m"].append(ex + em)
            rows["y"].append(0.8 * rows["m"][-1] + 0.5 * ey)
        out = discover_structures(rows)
        assert out["available"]
        # Markov chain x-m-y: multiple DAGs share the skeleton with no
        # v-structure; the class must hold more than one member.
        assert out["equivalence_class_size"] > 1
        assert len(out["undirected_edges"]) >= 1

    def test_too_few_samples_unavailable(self):
        out = discover_structures({"a": [1, 2, 3], "b": [1, 2, 3]})
        assert out["available"] is False


class TestCompareWorlds:
    def _scm(self):
        g = _g([("x", "m"), ("m", "y")])
        return StructuralCausalModel(graph=g)

    def test_multi_world_comparison(self):
        scm = self._scm()
        scm.graph.edge_weights[("x", "m")] = 1.0
        scm.graph.edge_weights[("m", "y")] = 2.0
        factual = {"x": 1.0, "m": 1.0, "y": 2.0}
        out = compare_worlds(
            scm,
            factual,
            [
                {"name": "A", "interventions": {"x": 3.0}},
                {"name": "B", "interventions": {"x": 0.0}},
            ],
            ["y"],
        )
        worlds = {w["world"]: w for w in out["worlds"]}
        assert worlds["A"]["outcome_values"]["y"] == pytest.approx(6.0)
        assert worlds["B"]["outcome_values"]["y"] == pytest.approx(0.0)
        assert worlds["A"]["delta_vs_factual"]["y"] == pytest.approx(4.0)
        assert out["invariant_variables"] == []
        assert out["ledger_verify"]
        assert worlds["A"]["stage"] == STAGE_COUNTERFACTUAL_GENERATED
        assert worlds["A"]["receipt"]

    def test_world_with_missing_evidence_is_refused_not_fabricated(self):
        scm = self._scm()
        out = compare_worlds(
            scm,
            {},  # no factual evidence
            [{"name": "A", "interventions": {"x": 1.0}}],
            ["y"],
        )
        assert out["worlds"][0]["available"] is False
        assert "m" in out["worlds"][0]["missing_evidence"] or out["worlds"][0][
            "missing_evidence"
        ]


class TestEvaluateFutures:
    def test_distributions_and_depth_degradation(self):
        # chain x -> m -> y; noise accumulates with depth
        g = _g([("x", "m"), ("m", "y")])
        scm = StructuralCausalModel(graph=g)
        out = evaluate_futures(
            scm,
            [{"name": "A1", "interventions": {"x": 2.0}}, {"name": "A2", "interventions": {"x": -1.0}}],
            ["x", "m", "y"],
        )
        for f in out["actions"]:
            assert f["available"]
            assert f["stage"] == STAGE_INTERVENTION_EXECUTED
        a1 = out["actions"][0]
        # intervention pins x: variance 0; sd grows down the chain
        d = a1["outcome_distributions"]
        assert d["x"]["variance"] == 0.0
        assert d["m"]["sd"] > 0 and d["y"]["sd"] > d["m"]["sd"]
        assert d["y"]["depth"] == 2
        assert a1["outcome_distributions"]["y"]["p05"] < a1["outcome_distributions"]["y"]["mean"] < a1["outcome_distributions"]["y"]["p95"]
        assert out["ledger_verify"]

    def test_empty_action_is_refused(self):
        g = _g([("x", "y")])
        scm = StructuralCausalModel(graph=g)
        out = evaluate_futures(scm, [{"name": "noop", "interventions": {}}])
        assert out["actions"][0]["available"] is False
