"""Action intelligence, declared-operator generation, planning — §§16-18."""

from __future__ import annotations

from toe.causal_ladder import CausalGraph, StructuralCausalModel
from toe.planning import (
    OperatorSpec,
    compare_plan_vs_greedy,
    generate_actions,
    plan,
    scm_env,
)
from toe.policy import (
    Constraint,
    Objective,
    counterfactual_futures,
    decide_multiobjective,
)


def _chain() -> StructuralCausalModel:
    g = CausalGraph.from_edges([("x", "m"), ("m", "y")])
    g.edge_weights[("x", "m")] = 1.0
    g.edge_weights[("m", "y")] = 1.0
    return StructuralCausalModel(graph=g)


class TestActionGeneration:
    def test_only_declared_operators_produce_actions(self):
        ops = [OperatorSpec("set_x", "x", levels=(0.0, 1.0))]
        acts = generate_actions(ops, {"x": 0.0})
        assert len(acts) == 2
        assert all(a["interventions"]["x"] in (0.0, 1.0) for a in acts)
        assert all(a["operators"] == ["set_x"] for a in acts)

    def test_deltas_apply_relative_to_state(self):
        ops = [OperatorSpec("bump", "x", deltas=(2.0, -1.0), cost=0.5)]
        acts = generate_actions(ops, {"x": 3.0})
        assert sorted(a["interventions"]["x"] for a in acts) == [2.0, 5.0]
        assert all(a["cost"] == 0.5 for a in acts)

    def test_no_arbitrary_actions(self):
        # operators for node x only -> no y intervention can appear
        ops = [OperatorSpec("set_x", "x", levels=(1.0,))]
        assert not any("y" in a["interventions"] for a in generate_actions(ops, {}))


class TestMultiObjective:
    def test_pareto_front_and_weights(self):
        scm = _chain()
        factual = {"x": 0.0, "m": 0.0, "y": 0.0}
        futures = counterfactual_futures(scm)
        out = decide_multiobjective(
            factual,
            {"A": {"x": 4.0}, "B": {"x": 1.0}, "C": {"x": 2.0}},
            futures=futures,
            objectives=[
                Objective(target="y", sense="maximize"),
                Objective(target="m", sense="minimize"),
            ],
            model_id="scm",
        )
        assert out["available"]
        # y=m under unit weights; maximize y & minimize m conflict equally
        # weighted equal -> tie broken by name; but all three are
        # non-dominated? A: y4 m4; B: y1 m1; C: y2 m2 — with equal weights
        # score_A=0, all equal -> none dominates (dominance needs strict
        # better on one and no worse on any) — A vs B: y better, m worse
        # -> neither dominates. Front = all.
        assert set(out["pareto_front"]) == {"A", "B", "C"}
        out2 = decide_multiobjective(
            factual,
            {"A": {"x": 4.0}, "B": {"x": 1.0}},
            futures=futures,
            objectives=[
                Objective(target="y", sense="maximize"),
                Objective(target="m", sense="minimize"),
            ],
            weights={"y": 3.0, "m": 0.1},
            model_id="scm",
        )
        assert out2["selected_action"] == "A"


class TestPlanning:
    def test_two_step_beats_one_step_when_joint_needed(self):
        # z = x + m: no single node reaches z=5; both must be set.
        g = CausalGraph.from_edges([("x", "z"), ("m", "z")])
        g.edge_weights[("x", "z")] = 1.0
        g.edge_weights[("m", "z")] = 1.0
        scm = StructuralCausalModel(graph=g)
        env = scm_env(scm)
        ops = [
            OperatorSpec("set_x", "x", levels=(3.0,)),
            OperatorSpec("set_m", "m", levels=(2.0,)),
        ]
        out = compare_plan_vs_greedy(
            env, ops, objective=Objective(target="z"), depth=2
        )
        assert out["greedy"]["objective_value"] == 3.0
        assert out["plan"]["objective_value"] == 5.0
        assert out["plan_strictly_better"] is True
        assert len(out["plan"]["sequence"]) == 2

    def test_budget_trap_greedy_locally_good_globally_bad(self):
        # Linear world y=x. Operators: bump +2 (cost 1) or +3 (cost 2).
        # Budget 2: greedy one-shot picks +3 (y=3). Two +2 bumps (cost 2)
        # reach y=4 — greedy is locally optimal, globally worse.
        g = CausalGraph.from_edges([("x", "y")])
        g.edge_weights[("x", "y")] = 1.0
        scm = StructuralCausalModel(graph=g)
        env = scm_env(scm)
        ops = [
            OperatorSpec("small_bump", "x", deltas=(2.0,), cost=1.0),
            OperatorSpec("big_bump", "x", deltas=(3.0,), cost=2.0),
        ]
        out = compare_plan_vs_greedy(
            env, ops, objective=Objective(target="y"), depth=2, budget=2.0
        )
        assert out["greedy"]["objective_value"] == 3.0
        assert out["plan"]["objective_value"] == 4.0
        assert out["plan_strictly_better"] is True
        names = [s["name"] for s in out["plan"]["sequence"]]
        assert names == ["small_bump+2", "small_bump+2"]

    def test_intermediate_constraint_prunes_paths(self):
        # x -> y; constraint y <= 4 during the plan blocks the big move.
        g = CausalGraph.from_edges([("x", "y")])
        g.edge_weights[("x", "y")] = 1.0
        scm = StructuralCausalModel(graph=g)
        env = scm_env(scm)
        ops = [OperatorSpec("set_x", "x", levels=(2.0, 9.0))]
        out = plan(
            env,
            ops,
            objective=Objective(target="y"),
            constraints=[Constraint("cap", "y", "<=", 4.0)],
            depth=2,
        )
        assert out["objective_value"] == 2.0  # x=9 pruned at step 1

    def test_linear_parity_honest(self):
        # With free budget and single-node additive effects, a linear SCM
        # plan cannot beat greedy — asserting that parity is the honest
        # negative control.
        g = CausalGraph.from_edges([("x", "y")])
        g.edge_weights[("x", "y")] = 1.0
        scm = StructuralCausalModel(graph=g)
        env = scm_env(scm)
        ops = [OperatorSpec("set_x", "x", levels=(5.0,))]
        out = compare_plan_vs_greedy(
            env, ops, objective=Objective(target="y"), depth=3
        )
        assert out["greedy"]["objective_value"] == 5.0
        assert out["plan"]["objective_value"] == 5.0
        assert out["plan_strictly_better"] is False

    def test_no_feasible_plan_reports_unavailable(self):
        g = CausalGraph.from_edges([("x", "y")])
        scm = StructuralCausalModel(graph=g)
        env = scm_env(scm)
        ops = [OperatorSpec("set_x", "x", levels=(9.0,))]
        out = plan(
            env,
            ops,
            objective=Objective(target="y"),
            constraints=[Constraint("cap", "y", "<=", 1.0)],
            depth=2,
        )
        assert out["available"] is False
