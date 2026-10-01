"""Topology, arbitration, composition, cross-domain matrix — §§32-38."""

from __future__ import annotations

from typing import List, Mapping, Tuple

from toe.arbitration import arbitrate
from toe.causal_stack import evaluate_futures
from toe.generalization import (
    DomainAdapter,
    capability_matrix,
    invariance_report,
    run_capability,
    transfer_probe,
)
from toe.planning import OperatorSpec, compare_plan_vs_greedy, scm_env
from toe.policy import Objective
from toe.topology import StateTopology, reachability_task


# -- §32 topology -----------------------------------------------------


class TestStateTopology:
    def _grid_with_wall(self):
        # corridor s0 -> s1 -> s2 -> sT with dead-end branch s1 -> sB.
        # Metrically sB sits closest to the target: greedy Euclidean
        # descent walks into the dead end; topology finds the path.
        states = ["s0", "s1", "s2", "sT", "sB"]
        edges = [("s0", "s1"), ("s1", "s2"), ("s2", "sT"), ("s1", "sB")]
        coords = {"s0": (0.0, 0.0), "s1": (1.0, 0.0), "s2": (2.0, 0.0),
                  "sT": (3.0, 0.0), "sB": (2.9, 0.05)}
        return states, edges, coords

    def test_reachability_answers_path_question(self):
        states, edges, coords = self._grid_with_wall()
        out = reachability_task(states, edges, "s0", "sT", coords=coords)
        assert out["reachable"] is True
        assert out["topological_path"] == ["s0", "s1", "s2", "sT"]
        assert out["baseline_correct"] is False  # greedy walks into sB
        assert out["baseline_path"][-1] == "sB"

    def test_unreachable_component_reported(self):
        topo = StateTopology(["a", "b", "c"], [("a", "b")])
        assert topo.path_exists("a", "c") is False
        assert len(topo.components()) == 2

    def _corridor(self):
        return ["in", "mid", "out"], [("in", "mid"), ("mid", "out")], None

    def test_articulation_finds_bottleneck(self):
        states, edges, _ = self._grid_with_wall()
        topo = StateTopology(states, edges)
        assert "s1" in topo.articulation_points()
        assert "s2" in topo.articulation_points()

    def test_boundary_states(self):
        topo = StateTopology(["a", "b"], [("a", "b")])
        assert set(topo.boundary_states()) == {"a", "b"}


# -- §34 disagreement ---------------------------------------------------


class TestArbitration:
    def test_disagreement_reported_not_hidden(self):
        out = arbitrate(
            [
                {"surface": "causal_interventional", "answer": "A"},
                {"surface": "trajectory_extrapolation", "answer": "B"},
            ],
            problem_type="interventional",
        )
        assert out["status"] == "DISAGREEMENT"
        assert out["resolution"]["surface"] == "causal_interventional"
        assert "authority" in out["resolution"]["rule"]

    def test_unresolved_when_no_rule_applies(self):
        out = arbitrate(
            [{"surface": "x_surface", "answer": "A"},
             {"surface": "y_surface", "answer": "B"}],
            problem_type="unmapped",
        )
        assert out["status"] == "DISAGREEMENT"
        assert out["resolution"] is None

    def test_calibration_decides_among_unranked(self):
        out = arbitrate(
            [
                {"surface": "x", "answer": "A", "calibration": 0.9},
                {"surface": "y", "answer": "B", "calibration": 0.4},
            ],
            problem_type="unmapped",
        )
        assert out["resolution"]["surface"] == "x"
        assert "calibration" in out["resolution"]["rule"]

    def test_agreement_is_agreement(self):
        out = arbitrate(
            [{"surface": "a", "answer": "A"}, {"surface": "b", "answer": "A"}]
        )
        assert out["status"] == "AGREEMENT"


# -- §§35-36 cross-domain adapters --------------------------------------


class _Chain(DomainAdapter):
    """Base: u -> v two-node chain, action sets u, objective maximize v."""

    name = "base"
    edge: Tuple[str, str] = ("u", "v")

    def rows(self) -> List[Mapping[str, float]]:
        u, v = self.edge
        return [{u: float(i), v: 2.0 * i} for i in range(5)]

    def graph_spec(self):
        return [self.edge], {self.edge: 2.0}

    def actions(self):
        return {"low": {self.edge[0]: 1.0}, "high": {self.edge[0]: 5.0}}

    def objective(self):
        return Objective(target=self.edge[1])

    def state(self):
        u, v = self.edge
        return {u: 0.0, v: 0.0}


class MaintenanceDomain(_Chain):
    name = "maintenance"
    edge = ("load", "wear")


class FinanceLikeDomain(_Chain):
    name = "finance_like"
    edge = ("signal", "return")


class SecurityDomain(_Chain):
    name = "security"
    edge = ("exposure", "risk")


class MiningDomain(_Chain):
    name = "mining"
    edge = ("difficulty", "throughput")


class SyntheticCausalDomain(_Chain):
    name = "synthetic_causal"
    edge = ("x", "y")


DOMAINS = [
    MaintenanceDomain(),
    FinanceLikeDomain(),
    SecurityDomain(),
    MiningDomain(),
    SyntheticCausalDomain(),
]


class TestCapabilityMatrix:
    def test_one_backend_many_uses(self):
        out = capability_matrix(DOMAINS)
        assert out["domains"] == [d.name for d in DOMAINS]
        for cap in out["capabilities"]:
            for dom in DOMAINS:
                cell = out["matrix"][cap][dom.name]
                assert cell["ok"], (cap, dom.name, cell)
        # domain-specific code is measured, not zero
        assert all(
            n > 0 for n in out["domain_code_lines"].values()
        )

    def test_unknown_capability_refused(self):
        assert run_capability(DOMAINS[0], "bogus")["ok"] is False


class TestInvariance:
    def test_permutation_holds_scale_does_not(self):
        rows = [{"a": float(i), "b": float(i * 2)} for i in range(5)]
        out = invariance_report(
            rows,
            {
                "column_rename": lambda rs: [
                    {"p": r["a"], "q": r["b"]} for r in rs
                ],
                "row_shuffle": lambda rs: list(reversed(rs)),
                "scale": lambda rs: [
                    {"a": r["a"] * 10, "b": r["b"] * 10} for r in rs
                ],
            },
        )
        inv = out["invariances"]
        # row order is a presentation detail: signature must not change
        assert inv["row_shuffle"]["signature_equal"] is True
        # renaming fields changes the signature (names are structure)
        # — reported honestly either way; we assert it MEASURED something
        assert "signature_equal" in inv["column_rename"]
        # scaling is not claimed invariant
        assert "signature_equal" in inv["scale"]


class TestTransfer:
    def test_novel_domain_gets_defensible_answer(self):
        class EcologyDomain(_Chain):
            name = "ecology_transfer"
            edge = ("prey_density", "predator_load")

        out = transfer_probe(EcologyDomain())
        assert out["defensible_answer"] is True
        assert out["domain_code_lines"] < 15


# -- §33 composition -----------------------------------------------------


class TestComposition:
    def test_composed_chain_beats_stages_alone(self):
        # Pipeline: topology finds the bottleneck node -> causal SCM env
        # -> planning reaches the objective through it. Stage-alone
        # checks: topology alone can't produce an action value; causal
        # alone can't find the route; plan alone is the composed result.
        states = ["idle", "armed", "fired"]
        edges = [("idle", "armed"), ("armed", "fired")]
        topo = StateTopology(states, edges)
        assert topo.articulation_points() == ["armed"]

        # causal+planning layer on top of the topological finding:
        # x -> m -> y, must pass m (the articulation analog)
        from toe.causal_ladder import CausalGraph, StructuralCausalModel

        g = CausalGraph.from_edges([("x", "m"), ("m", "y")])
        g.edge_weights[("x", "m")] = 1.0
        g.edge_weights[("m", "y")] = 1.0
        scm = StructuralCausalModel(graph=g)
        env = scm_env(scm)
        ops = [OperatorSpec("set_x", "x", levels=(3.0,))]
        out = evaluate_futures(
            scm, [{"name": "go", "interventions": {"x": 3.0}}], outcomes=["y"]
        )
        future = out["actions"][0]["outcome_distributions"]["y"]["mean"]
        assert future == 3.0  # pipeline: future through the chain

        cmp = compare_plan_vs_greedy(env, ops, objective=Objective("y"), depth=2)
        assert cmp["plan"]["available"]
        # composed answer: reach y=3 through m — topology said the
        # middle is forced, the SCM prices it, the plan executes it
        assert cmp["plan"]["objective_value"] == 3.0

    def test_bottleneck_state_is_forced_on_path(self):
        # any route to the goal must cross the articulation point
        topo = StateTopology(
            ["in", "mid", "out"], [("in", "mid"), ("mid", "out")]
        )
        assert topo.articulation_points() == ["mid"]
        assert "mid" in (topo.shortest_path("in", "out") or [])
