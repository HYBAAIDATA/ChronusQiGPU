"""TOEMachine — the reasoning core composed end to end.

Pins the brief's executable claims: P(Y|X) differs from P(Y|do X); a
counterfactual needs an abducted unit; identifiability refusal; futures
are labelled predictions; planning consumes the futures model and beats
greedy under a budget; value of information gates action; precision
escalates to exact arithmetic; disagreement is arbitrated, not averaged;
the domain label never changes the reasoning.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from kellogg.scales import lucas
from toe.adapters import (
    CodeStructureAdapter,
    GraphAdapter,
    LinearSystemAdapter,
    RecurrenceAdapter,
    TabularAdapter,
)
from toe.machine import ACQUIRE_EVIDENCE, ACT, NAVIGATE, PREDICTED, REFUSED, TOEMachine
from toe.planning import OperatorSpec
from toe.policy import Constraint, Objective
from toe.problem import Problem, Structure
from toe.relationships import EFFECT_IDENTIFIED, EFFECT_NOT_IDENTIFIED
from toe.voyage import (
    DOMAINS,
    fixture_code,
    fixture_graph,
    fixture_linear_system,
    fixture_recurrence,
    fixture_recurrence_negative,
    fixture_tabular,
    voyage_problem,
)


@pytest.fixture(scope="module")
def machine() -> TOEMachine:
    return TOEMachine()


@pytest.fixture(scope="module")
def tabular_episode(machine):
    return machine.run(TabularAdapter().to_problem(fixture_tabular()))


def test_association_differs_from_intervention(tabular_episode):
    lad = tabular_episode["understanding"]["causal_ladder"]
    assoc = lad["rung1_association"]["slope_E_y_given_x"]
    do = lad["rung2_interventional"]["effect_per_unit_E_y_do_x"]
    # The confounder makes the raw association positive; the effect is negative.
    assert assoc > 0 > do
    est = tabular_episode["identity"]["estimated_from_samples"]["promo->sales"]
    assert abs(est["estimate"] - (-0.5)) < 4 * est["standard_error"]


def test_effect_released_only_when_identified(tabular_episode):
    rel = tabular_episode["understanding"]["relationships"]
    assert rel["reached"][-1] == EFFECT_IDENTIFIED
    assert rel["effect_released"] is True
    assert tabular_episode["governance"]["causal"]["released"] is True


def test_identifiability_refusal_is_an_answer(machine):
    latent = Problem(
        domain="test",
        structure=Structure.of([("u", "x", 1.0), ("u", "y", 1.0), ("x", "y", 1.0)], latent=["u"]),
        samples={"x": [float(i % 7) for i in range(40)], "y": [float(i % 5) for i in range(40)]},
        query=("x", "y"),
    )
    ep = machine.run(latent)
    rel = ep["understanding"]["relationships"]
    assert EFFECT_NOT_IDENTIFIED in rel["levels"]
    assert rel["effect_released"] is False
    assert ep["understanding"]["identifiability"]["verdict"] == "NOT_IDENTIFIED"


def test_counterfactual_needs_an_abducted_unit(tabular_episode, machine):
    lad = tabular_episode["understanding"]["causal_ladder"]
    assert "unit_outcome_if_treatment_plus_1" in lad["rung3_counterfactual"]
    no_unit = TabularAdapter().to_problem({**fixture_tabular(), "current": {"promo": 1.0}})
    ep = machine.run(no_unit)
    cf = ep["understanding"]["causal_ladder"]["rung3_counterfactual"]
    assert cf["available"] is False and "abducted unit" in cf["reason"]


def test_disagreement_is_arbitrated_not_averaged(tabular_episode):
    arb = tabular_episode["arbitration"]
    assert arb["status"] == "DISAGREEMENT"
    assert arb["resolution"]["surface"] == "causal_interventional"
    assert tabular_episode["decision"]["selected_action"] == "set_promo=0.0"


def test_futures_are_labelled_predictions(machine):
    ep = machine.run(voyage_problem())
    for f in ep["futures"]["actions"]:
        assert f["epistemic_status"] == PREDICTED
        assert f["horizon_degradation"]
    assert ep["decision"]["predicted_future_status"] == PREDICTED


def test_plan_beats_greedy_and_consumes_futures(machine):
    adapter, fixture = DOMAINS["causal_system"]
    ep = machine.run(adapter().to_problem(fixture()))
    assert ep["plan"]["plan_strictly_better"] is True
    assert ep["plan"]["plan"]["objective_value"] == pytest.approx(4.0)
    assert ep["plan"]["greedy"]["objective_value"] == pytest.approx(3.0)
    assert ep["recommendation"]["kind"] == "plan"
    assert ep["recommendation"]["sequence"] == ["small_step+2", "small_step+2"]
    assert "futures_env" in ep["plan"]["env"]
    assert ep["arbitration"]["resolution"]["surface"] == "planning"


def test_chance_constraint_binds_a_quantile(machine):
    p = Problem(
        domain="test",
        structure=Structure.of([("x", "y", 1.0)]),
        operators=(OperatorSpec("set_x", "x", (1.0, 3.0)),),
        objective=Objective("y"),
        constraints=(Constraint("p95 cap", "y@p95", "<=", 4.0),),
        noise_sd={"x": 0.0, "y": 1.0},
    )
    ep = machine.run(p)
    # mean of set_x=3 is 3 <= 4, but its 95th percentile (3 + 1.645*phi) is not
    assert ep["decision"]["selected_action"] == "set_x=1.0"


def test_value_of_information_gates_action(machine):
    ep = machine.run(voyage_problem())
    assert ep["status"] == ACQUIRE_EVIDENCE
    assert ep["meta"]["evidence_plan"][0]["experiment"] == "intervene on x and observe y"
    invariant = replace(voyage_problem(), uncertain={"edge:x->y": (1.5, 2.0, 2.5)})
    ep2 = machine.run(invariant)
    assert ep2["status"] == ACT
    assert ep2["meta"]["value_of_information"]["edge:x->y"]["decision_invariant"] is True


def test_precision_escalates_to_exact(machine):
    ep = machine.run(LinearSystemAdapter().to_problem(fixture_linear_system()))
    prec = ep["decision"]["precision"]
    assert prec["regime"] == "exact-required"
    assert ep["decision"]["selected_action"] == "do_a=1.0"


def test_domain_label_never_changes_reasoning(machine):
    p = voyage_problem(domain="label.one")
    q = replace(p, domain="label.two")
    a, b = machine.run(p), machine.run(q)
    assert p.content_digest() == q.content_digest()

    def reasoning(ep):
        # The decision SHA binds the model identity (namespace@revision) —
        # provenance, which is label-scoped by design. Everything the
        # reasoning produced must be label-invariant.
        return {
            k: v
            for k, v in ep["decision"]["policy"].items()
            if k not in ("model_id", "decision_sha256")
        }

    assert reasoning(a) == reasoning(b)
    assert a["status"] == b["status"] and a["meta"]["verdict"] == b["meta"]["verdict"]
    assert a["backends"] == b["backends"]
    assert a["identity"]["namespace"] != b["identity"]["namespace"]


def test_invalid_problem_is_refused(machine):
    bad = Problem(domain="test", structure=Structure.of([("x", "y", float("nan"))]))
    ep = machine.run(bad)
    assert ep["status"] == REFUSED and ep["refusal"]["reasons"]
    unknown = Problem(domain="test", structure=Structure.of([("x", "y")]))
    assert machine.run(unknown)["status"] == REFUSED  # no weight, no samples


def test_navigation_representation_changes_solvability(machine):
    ep = machine.run(GraphAdapter().to_problem(fixture_graph()))
    assert ep["status"] == NAVIGATE
    reps = {r["name"]: r for r in ep["navigation"]["representations"]}
    assert reps["euclidean_greedy"]["delivered"] is False
    assert reps["hyperbolic_greedy"]["delivered"] is True
    assert reps["topological_bfs"]["delivered"] is True


def test_code_structure_reachability(machine):
    adapter = CodeStructureAdapter()
    ep = machine.run(adapter.to_problem(fixture_code()))
    assert ep["navigation"]["reachable"] is True
    assert ep["navigation"]["unreachable_from_source"] == ["legacy_export"]
    assert "hyperbolic_rejected" in ep["navigation"]  # call edges are directed
    assert adapter.interpret(ep)["unreachable_functions"] == ["legacy_export"]


def test_exact_recurrence_forecast_and_negative_case(machine):
    ep = machine.run(RecurrenceAdapter().to_problem(fixture_recurrence()))
    fc = ep["forecast"]
    assert fc["family"] == "golden"
    assert int(fc["value"]) == lucas(10 + 1000)
    assert fc["operation_count"]["matrix_multiplications"] < 25
    neg = machine.run(RecurrenceAdapter().to_problem(fixture_recurrence_negative()))
    assert neg["forecast"]["available"] is False  # no approximate extrapolation


def test_measured_lens_policy_skips_lenses_that_never_matter():
    m = TOEMachine(lens_policy="measured")
    for _ in range(3):
        m.run(voyage_problem())
    ep = m.run(voyage_problem())
    skipped = {name for name, _why in ep["representation"]["skipped_by_measured_utility"]}
    assert "tensor" in skipped and "causal_graph" not in skipped


def test_replay_reproduces_the_decision(machine):
    ep = machine.run(voyage_problem())
    r = machine.replay(ep["episode_sha256"])
    assert r["identical"] is True


def test_explanations_are_computational(tabular_episode):
    ex = tabular_episode["explanation"]
    assert ex["decision"]["available"] is True
    assert ex["contrastive"]["selected"] == "set_promo=0.0"
    assert "available" in ex["falsification"]
