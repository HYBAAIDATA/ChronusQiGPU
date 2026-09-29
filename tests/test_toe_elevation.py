"""TOE elevation: causal effect, intervention, counterfactual, explanation,
agreement, action policy, provenance and exact phi, on the canonical TOE core.

Every expected value is derived from the structural model or by independent
arithmetic in the test, never copied from the implementation's output.
"""

from __future__ import annotations

import math
import random
import re
import sys
from fractions import Fraction
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lucas.algebra import PHI as EXACT_PHI  # noqa: E402
from lucas.algebra import ZPhi  # noqa: E402
from toe.agreement import evaluator_agreement  # noqa: E402
from toe.bridge import CAPABILITY_EVIDENCE, TOEBridge  # noqa: E402
from toe.causal_ladder import (  # noqa: E402
    ARITHMETIC_EXACT,
    PHI,
    CausalCapabilityUnavailable,
    CausalGraph,
    StructuralCausalModel,
    counterfactual_query,
    counterfactual_state,
    d_separated,
    do_operator,
    estimate_causal_effect,
    identify_backdoor,
    intervene,
)
from toe.explanation import explain, structural_model  # noqa: E402
from toe.policy import Constraint, Objective, counterfactual_futures, decide  # noqa: E402
from toe.receipts import ReceiptLedger, replay, verify_binding, verify_chain  # noqa: E402


def _graph(*edges):
    return CausalGraph.from_edges(edges)


def _confounded(a=1.5, gamma=1.2, beta=3.0):
    return StructuralCausalModel(_graph(("U", "X", a), ("U", "Y", gamma), ("X", "Y", beta)))


def _structural_effect(scm, treatment, outcome):
    """Truth from the model's own exact do(): E[Y|do(X=1)] - E[Y|do(X=0)]."""
    one = intervene(scm, {treatment: 1}, arithmetic=ARITHMETIC_EXACT)["exact_values"][outcome]
    zero = intervene(scm, {treatment: 0}, arithmetic=ARITHMETIC_EXACT)["exact_values"][outcome]
    diff = ZPhi(Fraction(one["a"]), Fraction(one["b"])) - ZPhi(
        Fraction(zero["a"]), Fraction(zero["b"])
    )
    assert diff.b == 0, "a linear effect with no noise has no phi component"
    return float(diff.a)


# === backdoor identification =================================================


def test_backdoor_confounded_fork_needs_u():
    assert identify_backdoor(_confounded().graph, "X", "Y") == ["U"]


def test_backdoor_empty_when_unconfounded():
    assert identify_backdoor(_graph(("X", "Y", 2.0)), "X", "Y") == []


def test_backdoor_instrument_is_not_adjusted_for():
    # Z -> X -> Y: Z is a parent of X but opens no backdoor path.
    assert identify_backdoor(_graph(("Z", "X", 1.0), ("X", "Y", 1.0)), "X", "Y") == []


def test_backdoor_minimal_set_not_all_parents():
    g = _graph(("U", "X", 1.0), ("Z", "X", 1.0), ("U", "Y", 1.0), ("X", "Y", 1.0))
    assert identify_backdoor(g, "X", "Y") == ["U"]


def test_backdoor_m_bias_collider_is_left_alone():
    # X <- A -> M <- B -> Y with M observed: conditioning on M would open
    # the path, so the minimal admissible set is empty.
    g = _graph(("A", "X", 1), ("A", "M", 1), ("B", "M", 1), ("B", "Y", 1), ("X", "Y", 1))
    assert identify_backdoor(g, "X", "Y") == []
    assert not d_separated(g.without_outgoing("X"), {"X"}, {"Y"}, {"M"})


def test_backdoor_latent_confounder_is_not_identified():
    assert identify_backdoor(_confounded().graph, "X", "Y", observed={"X", "Y"}) is None


def test_backdoor_non_dag_is_not_identified():
    assert identify_backdoor(_graph(("X", "Y", 1), ("Y", "X", 1)), "X", "Y") is None


# === adjusted causal-effect recovery =========================================


def test_adjusted_effect_recovers_structural_truth():
    scm = _confounded()
    truth = _structural_effect(scm, "X", "Y")
    assert truth == 3.0
    est = estimate_causal_effect(scm.sample(20_000, seed=1517), scm.graph, "X", "Y")
    assert est.available and est.method == "linear_regression"
    assert est.adjustment_set == ["U"]
    assert abs(est.adjusted_effect - truth) <= 4 * est.standard_error
    assert abs(est.naive_effect - truth) > 20 * est.standard_error
    assert abs(est.adjusted_effect - truth) < abs(est.naive_effect - truth) / 10
    means = est.interventional_means
    assert means["1.0"] - means["0.0"] == pytest.approx(est.adjusted_effect)
    assert est.provenance["data_sha256"] and est.provenance["graph_sha256"]


@pytest.mark.parametrize("seed", [101, 202, 303, 404, 505])
def test_adjusted_effect_generalises_across_seeds_and_coefficients(seed):
    rng = random.Random(seed)
    a, gamma, beta = rng.uniform(0.5, 2.0), rng.uniform(0.5, 2.0), rng.uniform(-3.0, 3.0)
    scm = _confounded(a=a, gamma=gamma, beta=beta)
    truth = _structural_effect(scm, "X", "Y")
    est = estimate_causal_effect(scm.sample(8_000, seed=seed), scm.graph, "X", "Y")
    assert abs(est.adjusted_effect - truth) <= 4 * est.standard_error
    assert abs(est.adjusted_effect - truth) < abs(est.naive_effect - truth)


def test_unconfounded_effect_needs_no_adjustment():
    scm = StructuralCausalModel(_graph(("X", "Y", 2.0)))
    est = estimate_causal_effect(scm.sample(5_000, seed=3), scm.graph, "X", "Y")
    assert est.adjustment_set == []
    assert abs(est.adjusted_effect - 2.0) <= 4 * est.standard_error


def test_latent_confounder_is_unavailable_not_naive():
    scm = _confounded()
    samples = scm.sample(5_000, seed=5)
    del samples["U"]
    est = estimate_causal_effect(samples, scm.graph, "X", "Y")
    assert est.available is False
    assert est.adjusted_effect is None and est.naive_effect is None
    assert "not identified" in est.reason


def _binary_confounded(n, seed):
    rng = random.Random(seed)
    cols = {"U": [], "X": [], "Y": []}
    for _ in range(n):
        u = 1.0 if rng.random() < 0.5 else 0.0
        x = 1.0 if rng.random() < (0.2 + 0.6 * u) else 0.0
        cols["U"].append(u)
        cols["X"].append(x)
        cols["Y"].append(2.0 * x + 3.0 * u + rng.gauss(0.0, 1.0))
    return cols


def test_stratified_effect_on_discrete_confounding():
    g = _graph(("U", "X", 1), ("U", "Y", 1), ("X", "Y", 1))
    est = estimate_causal_effect(_binary_confounded(20_000, 9), g, "X", "Y")
    assert est.method == "stratification"
    # truth 2.0; naive is inflated by 3 * (P(U|X=1) - P(U|X=0)) = 1.8
    assert abs(est.adjusted_effect - 2.0) <= 4 * est.standard_error
    assert est.naive_effect > 3.0


def test_positivity_violation_is_unavailable():
    g = _graph(("U", "X", 1), ("U", "Y", 1), ("X", "Y", 1))
    samples = _binary_confounded(2_000, 4)
    samples["X"] = list(samples["U"])  # X is determined by U
    est = estimate_causal_effect(samples, g, "X", "Y")
    assert est.available is False and "positivity" in est.reason


# === intervention with real incoming edges ===================================


def _cf_scm():
    """U -> X -> Y, U -> Y, Z -> X: the intervened node has two parents."""
    return StructuralCausalModel(
        _graph(("U", "X", 1.5), ("Z", "X", 0.5), ("U", "Y", 1.2), ("X", "Y", 3.0))
    )


def test_intervention_cuts_incoming_edges_on_a_copy():
    scm = _cf_scm()
    result = intervene(scm, {"X": 2.0})
    surgery = result["surgery"]
    assert surgery["incoming_edges_before"]["X"] == [["U", "X", 1.5], ["Z", "X", 0.5]]
    assert surgery["incoming_edges_after"]["X"] == []
    assert surgery["edges_cut"] == [["U", "X"], ["Z", "X"]]
    assert sorted(scm.graph.parents["X"]) == ["U", "Z"], "factual model must be untouched"
    assert result["values"]["X"] == 2.0
    assert result["values"]["Y"] == pytest.approx(6.0)  # noise at mean: 3 * 2


def test_do_operator_no_longer_mutates_the_callers_model():
    from kellogg.quantum_tensor import Observables, QuantumState

    scm = _cf_scm()
    obs = {n: Observables.position(32) for n in scm.graph.nodes}
    _, diag = do_operator(QuantumState.uniform_superposition(32), "X", 1.0, obs, scm)
    assert sorted(scm.graph.parents["X"]) == ["U", "Z"]
    assert diag["incoming_edges_after"]["X"] == []


# === counterfactual: abduction, action, prediction ===========================

NOISE = {"U": 0.2, "Z": -0.4, "X": 0.1, "Y": 0.3}


def _factual():
    return _cf_scm().evaluate_all(exogenous=NOISE)


def test_counterfactual_matches_independent_arithmetic():
    factual = _factual()
    result = counterfactual_state(_cf_scm(), {"X": 2.0}, factual, ["Y"])
    u = PHI * NOISE["U"]
    expected = 3.0 * 2.0 + 1.2 * u + PHI * NOISE["Y"]
    assert result["outcome_values"]["Y"] == pytest.approx(expected, abs=1e-12)
    assert result["abduced_exogenous"]["Y"] == pytest.approx(NOISE["Y"], abs=1e-12)
    assert result["values"]["X"] == 2.0
    assert result["factual_model_unchanged"] is True


def test_counterfactual_legacy_api_reports_surgery():
    factual = _factual()
    value, diag = counterfactual_query(
        _cf_scm(), None, "X", 2.0, observed=factual, observables={}, outcome_node="Y"
    )
    action = diag["step_2_action"]
    assert action["incoming_edges_before"] == [["U", "X", 1.5], ["Z", "X", 0.5]]
    assert action["incoming_edges_after"] == []
    assert diag["step_3_prediction"]["outcome_selection"] == "explicit"
    assert value == pytest.approx(6.0 + factual["Y"] - 3.0 * factual["X"], abs=1e-12)


def test_edge_cut_makes_z_irrelevant_to_the_counterfactual():
    # Z reaches Y only through X. With X's incoming edges cut, units that
    # differ only in Z (same noise elsewhere) share the counterfactual Y.
    scm = _cf_scm()
    base = scm.evaluate_all(exogenous=NOISE)
    shifted = scm.evaluate_all(exogenous={**NOISE, "Z": 3.0})
    assert base["Y"] != shifted["Y"]
    y1 = counterfactual_state(scm, {"X": 2.0}, base, ["Y"])["outcome_values"]["Y"]
    y2 = counterfactual_state(scm, {"X": 2.0}, shifted, ["Y"])["outcome_values"]["Y"]
    assert y1 == pytest.approx(y2, abs=1e-12)


def test_counterfactual_negative_controls():
    scm = _cf_scm()
    factual = _factual()
    at2 = counterfactual_state(scm, {"X": 2.0}, factual, ["Y"])["outcome_values"]["Y"]
    at3 = counterfactual_state(scm, {"X": 3.0}, factual, ["Y"])["outcome_values"]["Y"]
    assert at3 - at2 == pytest.approx(3.0, abs=1e-12)  # wrong value changes result
    same = counterfactual_state(scm, {"X": factual["X"]}, factual, ["Y"])
    assert same["outcome_values"]["Y"] == pytest.approx(factual["Y"], abs=1e-12)


def test_intervention_on_unrelated_node_fabricates_no_effect():
    scm = StructuralCausalModel(
        _graph(("U", "X", 1.5), ("U", "Y", 1.2), ("X", "Y", 3.0), ("W", "R", 4.0))
    )
    factual = scm.evaluate_all(exogenous={"U": 0.2, "X": 0.1, "Y": 0.3, "W": 1.0, "R": 0.5})
    result = counterfactual_state(scm, {"W": 50.0}, factual, ["Y"])
    assert result["outcome_values"]["Y"] == factual["Y"]
    assert result["abduced_exogenous"] == {}


def test_missing_structural_evidence_fails_closed():
    factual = _factual()
    del factual["U"]
    with pytest.raises(CausalCapabilityUnavailable) as err:
        counterfactual_state(_cf_scm(), {"X": 2.0}, factual, ["Y"])
    assert "U" in err.value.missing
    with pytest.raises(CausalCapabilityUnavailable):
        counterfactual_state(_cf_scm(), {"X": 2.0}, {**_factual(), "Y": float("nan")}, ["Y"])
    with pytest.raises(CausalCapabilityUnavailable):
        counterfactual_query(_cf_scm(), None, "X", 2.0, observed={"X": 1.0}, observables={})


# === exact phi ===============================================================


def test_exact_path_is_exact_in_q_phi():
    scm = StructuralCausalModel(_graph(("X", "Y", 2)))
    values = scm.evaluate_exact(interventions={"X": 1}, exogenous={"Y": 1})
    assert values["Y"] == ZPhi(2, 1)  # 2*1 + phi, structurally
    assert EXACT_PHI * EXACT_PHI == EXACT_PHI + ZPhi(1, 0)


def test_float_path_is_numerically_verified_against_exact():
    scm = _cf_scm()
    noise = {k: Fraction(v).limit_denominator(1000) for k, v in NOISE.items()}
    exact = scm.evaluate_exact(exogenous=noise)
    floats = scm.evaluate_all(exogenous={k: float(v) for k, v in noise.items()})
    for node, value in exact.items():
        projected = float(value.a) + float(value.b) * PHI
        assert floats[node] == pytest.approx(projected, rel=1e-12, abs=1e-12)


def test_exact_counterfactual_is_rational_and_exact():
    scm = StructuralCausalModel(
        _graph(
            ("U", "X", Fraction(3, 2)),
            ("Z", "X", Fraction(1, 2)),
            ("U", "Y", Fraction(6, 5)),
            ("X", "Y", 3),
        )
    )
    factual = {"U": Fraction(1, 3), "Z": Fraction(-2, 7), "X": Fraction(5, 4), "Y": Fraction(9, 2)}
    result = counterfactual_state(scm, {"X": 2}, factual, ["Y"], arithmetic=ARITHMETIC_EXACT)
    exact = result["exact_values"]["Y"]
    expected = 3 * 2 + Fraction(9, 2) - 3 * Fraction(5, 4)
    assert Fraction(exact["a"]) == expected and Fraction(exact["b"]) == 0


# === explanation: the adversarial suite ======================================


def _explanation_scm(beta1=3.0):
    return StructuralCausalModel(
        _graph(("X1", "Y", beta1), ("X2", "Y", 0.3), ("Z", "T", 2.0), ("W", "R", 1.0))
    )


def _background(w_scale=1.0, n=24):
    rng = random.Random(77)
    return [
        {
            "X1": rng.gauss(0, 1),
            "X2": rng.gauss(0, 1),
            "Z": rng.gauss(0, 1),
            "W": 1e6 * w_scale + rng.gauss(0, 1e5 * w_scale),
        }
        for _ in range(n)
    ]


def _instance(w_scale=1.0):
    return {"X1": 2.0, "X2": 2.0, "Z": 2.0, "W": 3e6 * w_scale}


def _explain(target="Y", beta1=3.0, w_scale=1.0, instance=None, background=None, **kw):
    scm = _explanation_scm(beta1)
    return explain(
        structural_model(scm),
        instance if instance is not None else _instance(w_scale),
        target=target,
        background=background if background is not None else _background(w_scale),
        model_id=kw.pop("model_id", scm.digest()),
        causal_parents=scm.graph.parents.get(target, []),
        **kw,
    )


def test_1_2_true_cause_outranks_irrelevant_and_huge_irrelevant():
    e = _explain()
    assert e.available
    assert e.ranking.index("X1") < e.ranking.index("Z")
    assert e.ranking.index("X1") < e.ranking.index("W")
    assert e.attributions["W"] == 0.0 and e.attributions["Z"] == 0.0
    assert e.relevant_inputs == ["X1", "X2"]
    total = sum(e.attributions.values())
    assert total == pytest.approx(e.factual_prediction - e.baseline_prediction, abs=1e-9)


@pytest.mark.parametrize("scale", [10.0, 1000.0])
def test_3_rescaling_w_does_not_alter_the_explanation(scale):
    base, scaled = _explain(), _explain(w_scale=scale)
    assert scaled.ranking[:2] == base.ranking[:2] == ["X1", "X2"]
    for name in ("X1", "X2", "Z", "W"):
        assert scaled.attributions[name] == pytest.approx(base.attributions[name], abs=1e-9)


def test_3b_unit_rescaling_of_a_true_cause_is_invariant():
    base = _explain()
    k = 1000.0
    scm = StructuralCausalModel(
        _graph(("X1", "Y", 3.0 / k), ("X2", "Y", 0.3), ("Z", "T", 2.0), ("W", "R", 1.0))
    )
    instance = {**_instance(), "X1": _instance()["X1"] * k}
    background = [{**row, "X1": row["X1"] * k} for row in _background()]
    scaled = explain(
        structural_model(scm), instance, target="Y", background=background, model_id="milli"
    )
    assert scaled.attributions["X1"] == pytest.approx(base.attributions["X1"], rel=1e-9)
    assert scaled.ranking == base.ranking


def test_4_input_order_does_not_alter_the_explanation():
    forward = _explain()
    reordered = _explain(instance=dict(reversed(list(_instance().items()))))
    assert reordered.attributions == forward.attributions
    assert reordered.evidence_sha256 == forward.evidence_sha256


def test_5_target_change_changes_the_explanation():
    on_y, on_t = _explain("Y"), _explain("T")
    assert on_y.ranking[0] == "X1" and on_t.ranking[0] == "Z"
    assert on_t.attributions["X1"] == 0.0 and on_y.attributions["Z"] == 0.0
    assert on_t.evidence_sha256 != on_y.evidence_sha256


def test_6_intervening_on_the_top_cause_moves_the_outcome_as_attributed():
    e = _explain()
    top = e.ranking[0]
    ablated = e.ablations[top]
    assert ablated["counterfactual_prediction"] < e.factual_prediction  # X1 above its mean
    assert math.copysign(1, ablated["delta"]) == math.copysign(1, e.attributions[top])


def test_7_removing_w_does_not_alter_the_output():
    e = _explain()
    no_w = _explain(
        instance={k: v for k, v in _instance().items() if k != "W"},
        background=[{k: v for k, v in r.items() if k != "W"} for r in _background()],
    )
    assert no_w.factual_prediction == pytest.approx(e.factual_prediction, abs=1e-12)
    for name in ("X1", "X2", "Z"):
        assert no_w.attributions[name] == pytest.approx(e.attributions[name], abs=1e-12)


def test_8_attribution_is_monotone_in_the_true_coefficient():
    values = [_explain(beta1=b).attributions["X1"] for b in (1.0, 2.0, 3.0, 4.0)]
    assert all(later > earlier for earlier, later in zip(values, values[1:]))


def test_9_repeated_execution_is_stable():
    runs = [_explain() for _ in range(3)]
    assert len({r.evidence_sha256 for r in runs}) == 1
    assert runs[0].attributions == runs[2].attributions


def test_10_missing_evidence_yields_unavailable_not_an_explanation():
    cases = [
        _explain(instance={**_instance(), "X1": None}),
        _explain(background=[]),
        _explain(model_id=None),
        _explain(target="Q"),
        _explain(background=[{"X1": 0.0}]),
    ]
    for case in cases:
        assert case.available is False
        assert case.reason
        assert case.attributions == {} and case.ranking == []


def test_legacy_magnitude_ranking_is_labelled_not_causal():
    causal = TOEBridge().explain_causality({"a": [1, 2, 3], "b": [3, 2, 1]})
    assert causal.diagnostics["ranking_basis"] == "expectation_magnitude"
    assert causal.diagnostics["causal_explanation"].startswith("UNAVAILABLE")


# === model agreement =========================================================


def test_agreement_is_unavailable_for_one_evaluator_or_duplicates():
    assert evaluator_agreement({"m": [1.0, 2.0]})["agreement"] is None
    dup = evaluator_agreement(
        {"a": [1.0, 2.0], "b": [5.0, -1.0]}, evaluator_ids={"a": "cfg", "b": "cfg"}
    )
    assert dup["available"] is False and dup["duplicates_merged"] == ["b"]


def test_agreement_drops_for_disagreeing_evaluators():
    agree = evaluator_agreement({"a": [1.0, 2.0, 3.0], "b": [1.0, 2.0, 3.05]})
    mild = evaluator_agreement({"a": [1.0, 2.0, 3.0], "b": [2.0, 1.0, 3.0]})
    oppose = evaluator_agreement({"a": [1.0, 2.0, 3.0], "b": [-1.0, -2.0, -3.0]})
    assert agree["agreement"] > 0.99
    assert agree["agreement"] > mild["agreement"] > oppose["agreement"]
    assert oppose["agreement"] == pytest.approx(0.0, abs=1e-12)


def test_bridge_agreement_is_no_longer_one_by_construction():
    bridge = TOEBridge()
    assert bridge.explain_causality({"a": 1.0, "b": 2.0, "c": 3.0}).model_agreement is None
    assert bridge.explain_causality(bytes(range(64))).model_agreement is None
    overlap = bridge.explain_causality({"a": [1, 2, 3, 4], "b": [1, 2, 3, 5]}).model_agreement
    partial = bridge.explain_causality({"a": [1, 1, 0, 0], "b": [0, 1, 1, 0]}).model_agreement
    assert overlap is not None and partial is not None
    assert partial < overlap
    assert overlap > 0.99 and partial < 0.9


# === action policy ===========================================================


def _policy_scm(xy_weight=5.0):
    return StructuralCausalModel(
        _graph(("S", "X", 0.5), ("S", "Y", 1.0), ("X", "Y", xy_weight), ("X", "C", 1.0))
    )


STATE = {"S": 1.0, "X": 1.0, "C": 1.0, "Y": 4.0}
CANDIDATES = {"A": {"X": 1.0}, "B": {"X": 2.0}, "C": {"X": 3.0}}
BUDGET = [Constraint("budget", "C", "<=", 2.5)]


def _decide(scm, candidates=CANDIDATES, arithmetic="float64"):
    return decide(
        STATE,
        candidates,
        futures=counterfactual_futures(scm, arithmetic=arithmetic),
        objective=Objective("Y"),
        constraints=BUDGET,
        model_id=scm.digest(),
    )


def test_policy_selects_known_optimum_and_excludes_constraint_violation():
    d = _decide(_policy_scm(), arithmetic=ARITHMETIC_EXACT)
    values = {f["action"]: f["objective_value"] for f in d.futures}
    assert values == {"A": 4.0, "B": 9.0, "C": 14.0}
    assert d.selected_action == "B"
    c = next(f for f in d.futures if f["action"] == "C")
    assert c["admissible"] is False and c["violated"] == ["budget"]
    assert d.margin == pytest.approx(5.0)


def test_perturbing_the_model_flips_the_choice():
    d = _decide(_policy_scm(xy_weight=-1.0), arithmetic=ARITHMETIC_EXACT)
    values = {f["action"]: f["objective_value"] for f in d.futures}
    assert values["A"] == 4.0 and values["B"] == 3.0
    assert d.selected_action == "A"
    assert d.decision_sha256 != _decide(_policy_scm()).decision_sha256


def test_policy_follows_futures_not_names():
    renamed = {"B": {"X": 1.0}, "A": {"X": 2.0}, "C": {"X": 3.0}}
    assert _decide(_policy_scm(), candidates=renamed).selected_action == "A"


def test_policy_refuses_when_nothing_is_admissible():
    d = _decide(_policy_scm(), candidates={"C": {"X": 3.0}, "D": {"X": 4.0}})
    assert d.available is False and d.selected_action is None


def test_policy_excludes_candidates_whose_future_is_unavailable():
    scm = _policy_scm()
    d = decide(
        {"X": 1.0, "Y": 4.0},  # no evidence for S or C
        CANDIDATES,
        futures=counterfactual_futures(scm),
        objective=Objective("Y"),
        constraints=BUDGET,
        model_id=scm.digest(),
    )
    assert d.available is False
    assert all("future unavailable" in f["excluded_because"] for f in d.futures)


# === provenance receipts =====================================================


def _explanation_receipt(ledger, beta1=3.0):
    e = _explain(beta1=beta1)
    return ledger.issue(
        "explanation",
        inputs={"instance": _instance()},
        config={"model_id": _explanation_scm(beta1).digest(), "target": "Y"},
        output=e.as_dict(),
    )


def test_receipt_replays_and_detects_parameter_mutation():
    ledger = ReceiptLedger(run_id="test")
    receipt = _explanation_receipt(ledger)
    assert replay(receipt, lambda: _explain().as_dict())["ok"]
    assert not replay(receipt, lambda: _explain(beta1=3.1).as_dict())["ok"]
    binding = verify_binding(
        receipt, config={"model_id": _explanation_scm(3.1).digest(), "target": "Y"}
    )
    assert binding["mismatches"] == ["model/config does not match the receipt"]


def test_receipt_detects_state_mutation():
    receipt = _explanation_receipt(ReceiptLedger())
    assert verify_binding(receipt, inputs={"instance": _instance()})["ok"]
    mutated = {"instance": {**_instance(), "X1": 2.5}}
    assert not verify_binding(receipt, inputs=mutated)["ok"]


def test_receipt_detects_explanation_mutation():
    ledger = ReceiptLedger()
    receipt = _explanation_receipt(ledger)
    receipt.output["attributions"]["W"] = 99.0
    problems = {f["problem"] for f in ledger.verify()["failures"]}
    assert "output altered after issue" in problems


def test_receipt_detects_action_mutation_and_reordering():
    bridge = TOEBridge()
    scm = _policy_scm()
    bridge.decide(
        STATE,
        CANDIDATES,
        model=scm,
        objective={"target": "Y"},
        constraints=[{"name": "budget", "variable": "C", "op": "<=", "bound": 2.5}],
    )
    _explanation_receipt(bridge.receipts)
    assert bridge.verify_receipts()["ok"]
    action = bridge.receipts.records[0]
    assert action.output["selected_action"] == "B"
    action.output["selected_action"] = "C"
    assert not bridge.verify_receipts()["ok"]
    action.output["selected_action"] = "B"
    assert bridge.verify_receipts()["ok"]
    swapped = list(reversed(bridge.receipts.records))
    problems = {f["problem"] for f in verify_chain(swapped)["failures"]}
    assert "chain broken (reordered, inserted or removed)" in problems


# === canonical bridge wiring =================================================


def _reason_task(samples=True):
    edges = [
        ("U", "X", 1.5),
        ("Z", "X", 0.5),
        ("U", "Y", 1.2),
        ("X", "Y", 3.0),
        ("X", "C", 1.0),
        ("C", "Y", 0.0),
    ]
    scm = StructuralCausalModel(CausalGraph.from_edges(edges))
    task = {
        "graph": edges,
        "state": scm.evaluate_all(exogenous={**NOISE, "C": 0.0}),
        "treatment": "X",
        "outcome": "Y",
        "intervention": {"X": 2.0},
        "candidates": CANDIDATES,
        "objective": {"target": "Y", "sense": "maximize"},
        "constraints": [{"name": "budget", "variable": "C", "op": "<=", "bound": 2.5}],
    }
    if samples:
        task["samples"] = scm.sample(4_000, seed=11)
    return task


def test_reason_runs_the_full_sequence_through_the_bridge():
    out = TOEBridge().reason(_reason_task())
    assert out["available"] is True and out["unavailable"] == []
    effect = out["causal_analysis"]["effect"]
    assert effect["adjustment_set"] == ["U"]
    assert abs(effect["adjusted_effect"] - 3.0) <= 4 * effect["standard_error"]
    assert out["intervention"]["surgery"]["incoming_edges_after"]["X"] == []
    assert out["explanation"]["ranking"][0] == "X"
    assert out["explanation"]["attributions"]["C"] == 0.0
    assert out["explanation"]["context"]["edges_cut"] == [["U", "X"], ["Z", "X"]]
    assert out["action_policy"]["selected_action"] == "B"
    assert out["provenance"]["ledger"]["ok"] and len(out["provenance"]["receipts"]) == 4


def test_reason_reports_missing_sections_without_values():
    out = TOEBridge().reason(_reason_task(samples=False))
    assert out["available"] is False
    assert out["causal_analysis"]["available"] is False
    assert out["causal_analysis"]["effect"]["reason"] == "no observational samples supplied"
    assert "adjusted_effect" not in out["causal_analysis"]["effect"]
    assert {"section": "causal_analysis", "reason": None} not in out["unavailable"]


def test_status_states_claim_boundaries():
    status = TOEBridge().status()
    assert "reason" in status["capabilities"]
    assert status["capability_evidence"]["causal_discovery"].startswith("NOT ESTABLISHED")
    assert CAPABILITY_EVIDENCE["phi_arithmetic"].startswith("float path NUMERICALLY VERIFIED")


def test_predict_envelope_still_serves_downstream_adapters():
    result = TOEBridge().predict(bytes(range(64)))
    assert result["available"] is True
    assert result["causal_analysis"]["model_agreement"] is None


# Mining-specific tokens. "Stratum" is matched case-sensitively as the
# protocol name; lower-case "stratum" is the statistical term used by the
# stratification estimator, and lucas/ calls itself a "pool".
_DOMAIN_TERMS = re.compile(
    r"\bStratum\b|(?i:\b(nonces?|extranonce\w*|hashrate|mining|miners?|bitcoin|sha256d"
    r"|wallets?|viabtc|nicehash|braiins|ckpool|share_\w+|pool_\w+|mining\.\w+)\b)"
)


@pytest.mark.parametrize("module", ["explanation.py", "agreement.py", "policy.py", "receipts.py"])
def test_new_toe_core_modules_carry_no_mining_semantics(module):
    source = (ROOT / "toe" / module).read_text(encoding="utf-8")
    assert _DOMAIN_TERMS.findall(source) == []


def test_causal_ladder_carries_no_mining_semantics():
    source = (ROOT / "toe" / "causal_ladder.py").read_text(encoding="utf-8")
    assert _DOMAIN_TERMS.findall(source) == []


def test_domain_term_detector_catches_real_mining_vocabulary():
    # Negative control for the two tests above: the mining-authority module
    # under toe/intelligences/ is flagged, so an empty result means clean.
    source = (ROOT / "toe" / "intelligences" / "counterfactual.py").read_text(encoding="utf-8")
    assert "nonce" in {m.lower() for m in _DOMAIN_TERMS.findall(source)}


# === the harness is fail-closed ==============================================


def _probe():
    import importlib

    return importlib.import_module("scripts.probe_hyba_capability")


def test_probe_harness_passes_on_intact_code(tmp_path, capsys):
    report = tmp_path / "bench.json"
    code = _probe().main(["--only", "counterfactual,action_policy", "--report", str(report)])
    assert code == 0
    assert "STATUS        : PASS" in capsys.readouterr().out
    assert '"status": "PASS"' in report.read_text(encoding="utf-8")


def test_probe_harness_exits_nonzero_on_a_broken_invariant(monkeypatch, capsys):
    probe = _probe()
    real = probe.counterfactual_query

    def off_by_one(*args, **kwargs):
        value, diag = real(*args, **kwargs)
        return value + 1.0, diag

    monkeypatch.setattr(probe, "counterfactual_query", off_by_one)
    code = probe.main(["--only", "counterfactual"])
    out = capsys.readouterr().out
    assert code == 1
    assert "STATUS        : FAIL" in out and "STATUS        : PASS" not in out


def test_probe_harness_counts_a_crashed_section_as_failure(monkeypatch, capsys):
    probe = _probe()

    def crash(*_args, **_kwargs):
        raise RuntimeError("substrate missing")

    monkeypatch.setattr(probe, "intervene", crash)
    assert probe.main(["--only", "intervention"]) == 1
    assert "section ran without crashing" in capsys.readouterr().out


def test_probe_harness_reports_unavailable_as_incomplete(monkeypatch, capsys):
    probe = _probe()

    def no_sklearn(h):
        h.mark_unavailable("prediction", "scikit-learn is not installed")
        return {"available": False, "accuracy_mean": None}

    monkeypatch.setattr(probe, "section_prediction", no_sklearn)
    assert probe.main(["--only", "prediction"]) == 2
    assert "STATUS        : INCOMPLETE" in capsys.readouterr().out


def test_pythia_orchestrator_exposes_toe_reason():
    from Intelligence.orchestrator import IntelligenceOrchestrator

    out = IntelligenceOrchestrator().toe_reason(
        {
            "graph": [("X", "Y", 2.0)],
            "state": {"X": 1.0, "Y": 2.5},
            "outcome": "Y",
            "intervention": {"X": 3.0},
            "background": [{"X": 0.0}],
        }
    )
    # Y_cf = 2 * 3 + (2.5 - 2 * 1): the unit's own noise carries over.
    assert out["counterfactual"]["outcome_values"]["Y"] == pytest.approx(6.5)
    assert out["explanation"]["attributions"] == {"X": 2.0}
    assert out["available"] is False
    assert {u["section"] for u in out["unavailable"]} == {"causal_analysis", "action_policy"}
