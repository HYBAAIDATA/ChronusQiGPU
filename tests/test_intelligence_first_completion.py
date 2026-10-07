"""Regression coverage for the recovered intelligence-first workstream."""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from euclid.adapter import EuclidEngineAdapter, ProgramSearchEngine
from euclid.cognition.adaptive import PersistentStrategyLearner
from euclid.cognition.core import GeneralIntelligenceCore
from euclid.cognition.credit import assign_discounted_credit
from euclid.cognition.generalisation import (
    HeldOutGeneralisationTrial,
    evaluate_held_out_generalisation,
    validate_generalisation_report,
)
from euclid.cognition.mining import MiningCognitionProblem
from euclid.cognition.problem import CognitionObjective, CognitionProblem
from euclid.cognition.production import TOEWorldModelAdapter
from euclid.cognition.state import CognitiveState, PlanNode
from euclid.contracts import RewardAuthority
from toe.intelligences.authority_boundary import (
    CANONICAL_EUCLID_INTELLIGENCES,
    is_forbidden,
    is_pythia_final,
)


def test_cognition_problem_requires_reward_authority():
    with pytest.raises(ValueError):
        CognitionProblem(
            "p",
            "g",
            "test",
            measured_reward=0.5,
            reward_authority=RewardAuthority.NONE,
        )


def test_cognition_problem_serialises_objectives_and_digest():
    problem = CognitionProblem(
        "p",
        "g",
        "test",
        objectives=(CognitionObjective("o", "utility", "maximize", weight=1.0),),
    )
    payload = problem.to_mapping()
    assert payload["problem_digest"] == problem.digest
    assert payload["declared_objectives"][0]["metric"] == "utility"


def test_mining_problem_uses_measured_share_reward_only():
    snapshot = {
        "outcomes": {
            "accepted_ratio": 0.8,
            "rejected_ratio": 0.1,
            "unknown_ratio": 0.05,
            "stale_ratio": 0.05,
        },
        "counters": {"submitted": 20, "accepted": 16, "rejected": 2, "unknown": 1},
    }
    problem = MiningCognitionProblem.from_snapshot(
        snapshot,
        state={"ready": True},
        baseline_dispatch_breadth=32,
        current_dispatch_breadth=32,
        recovery_mode="normal",
        hashrate_hs=1000.0,
    )
    assert problem.problem.reward_authority is RewardAuthority.MEASURED_ENVIRONMENT
    assert problem.problem.measured_reward == pytest.approx(0.6)
    assert problem.breadth_for("reduce") == 16
    assert problem.breadth_for("restore") == 32


def test_mining_problem_without_outcome_has_no_reward():
    problem = MiningCognitionProblem.from_snapshot(
        {},
        state={"ready": False},
        baseline_dispatch_breadth=32,
        current_dispatch_breadth=8,
        recovery_mode="unknown",
        hashrate_hs=None,
    )
    assert problem.problem.measured_reward is None
    assert problem.problem.reward_authority is RewardAuthority.NONE


@pytest.mark.parametrize(
    "domain",
    ["sha256d", "target", "share-validation", "submission", "credentials"],
)
def test_mining_cognition_keeps_pythia_domains_forbidden(domain):
    problem = MiningCognitionProblem.from_snapshot(
        {},
        state={"ready": False},
        baseline_dispatch_breadth=32,
        current_dispatch_breadth=32,
        recovery_mode=None,
        hashrate_hs=None,
    )
    forbidden = set(problem.problem.constraints["forbidden"])
    assert domain in forbidden
    assert is_forbidden(domain) or is_pythia_final(domain)


def test_canonical_euclid_five_are_stable():
    assert CANONICAL_EUCLID_INTELLIGENCES == (
        "predictive",
        "causal",
        "counterfactual",
        "topological",
        "geometric",
    )


def test_program_search_name_is_unambiguous_and_backward_compatible():
    assert EuclidEngineAdapter is ProgramSearchEngine
    source = inspect.getsource(ProgramSearchEngine)
    assert "program-search" in source.lower()
    assert "not the EUCLID cognition" in source


def test_world_model_has_non_linear_features_without_changing_cold_start_weights():
    adapter = TOEWorldModelAdapter()
    assert adapter.feature_augmented is True
    assert {"context_sq", "action_sq", "context_action"} <= set(adapter.model.nodes)
    for feature in ("context_sq", "action_sq", "context_action"):
        assert adapter.model.dynamics["outcome"][feature] == 0.0


def test_discounted_credit_reaches_earlier_actions():
    rows = assign_discounted_credit(["a", "b", "c"], 1.0, gamma=0.5)
    assert [row.credit for row in rows] == pytest.approx([0.25, 0.5, 1.0])


def test_long_horizon_credit_changes_persistent_strategy_selection(tmp_path):
    learner = PersistentStrategyLearner(tmp_path / "strategy.json")
    learner.update_credit("family", "second", 1.0)
    choice = learner.select_strategy("family", ("first", "second"))
    assert choice.strategy_id == "second"


class _CounterfactualWorld:
    def counterfactual(self, _context, actions):
        values = {
            "no-intervention": 1.0,
            "inspect": 1.25,
            "verify": 1.5,
        }
        return [
            {
                "action": action,
                "future": {"outcome": values[action]},
                "epistemic_status": "predicted",
                "imagined": True,
            }
            for action in actions
        ]


class _CreditLearner:
    def __init__(self):
        self.rows = []

    def update_credit(self, problem_class, strategy, credit, detail=""):
        self.rows.append((problem_class, strategy, credit, detail))


def _core(world_model=None, metalearner=None):
    return GeneralIntelligenceCore(
        world_model=world_model or _CounterfactualWorld(),
        memory=None,
        analogy=None,
        abducer=None,
        deducer=None,
        discriminator=None,
        metacontroller=None,
        metalearner=metalearner or _CreditLearner(),
        planner=None,
        skills=None,
        objective=None,
    )


def test_counterfactual_plan_is_scored_against_no_intervention():
    state = CognitiveState("p", {})
    state.plan = [
        PlanNode("1", "inspect"),
        PlanNode("2", "verify"),
    ]
    core = _core()
    core._evaluate_plan_counterfactual(state, "context", stage="test")
    report = state.representation["counterfactual_plan_evaluation"]
    assert report["baseline_outcome"] == 1.0
    assert report["best_delta"] == 0.5
    assert any(t.phase == "counterfactual-plan" for t in state.transitions)


def test_long_horizon_credit_feeds_strategy_learner():
    learner = _CreditLearner()
    state = CognitiveState(
        "p",
        {"reward_authority": RewardAuthority.MEASURED_ENVIRONMENT.value, "measured_reward": 0.8},
    )
    core = _core(metalearner=learner)
    core._assign_long_horizon_credit(
        state,
        "family",
        [
            {"action": "a", "strategy": "s"},
            {"action": "b", "strategy": "s"},
        ],
        solved=True,
    )
    assert len(learner.rows) == 2
    assert learner.rows[-1][2] == pytest.approx(0.8)
    assert any(update["kind"] == "long-horizon-credit" for update in state.learning_updates)


def test_generalisation_requires_multiple_held_out_families():
    report = evaluate_held_out_generalisation(
        [HeldOutGeneralisationTrial("one", 0.5, 0.7)]
    )
    assert report["passed"] is False
    assert report["verdict"] == "insufficient_families"
    assert validate_generalisation_report(report) is False


def test_generalisation_gate_accepts_non_regressing_multi_family_evidence():
    report = evaluate_held_out_generalisation(
        [
            HeldOutGeneralisationTrial("one", 0.5, 0.7),
            HeldOutGeneralisationTrial("two", 0.3, 0.35),
        ]
    )
    assert report["passed"] is True
    assert report["verdict"] == "improved"
    assert validate_generalisation_report(report) is True


def test_generalisation_tamper_is_rejected():
    report = evaluate_held_out_generalisation(
        [
            HeldOutGeneralisationTrial("one", 0.5, 0.7),
            HeldOutGeneralisationTrial("two", 0.3, 0.35),
        ]
    )
    report["mean_delta"] = 999.0
    assert validate_generalisation_report(report) is False


def test_direct_cognition_status_route_is_present():
    source = Path(
        "chronus/mla1517_platform/python/control_api.py"
    ).read_text(encoding="utf-8")
    assert '"/api/v1/intelligence/cognition/status"' in source
    assert "euclid_cognition_status()" in source


def test_readme_is_intelligence_first_without_transferring_mining_authority():
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "## Intelligence-first composition" in readme
    assert "EUCLID is the system's canonical intelligence" in readme
    assert "PYTHIA      final mining authority" in readme
