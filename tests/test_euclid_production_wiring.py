"""Production wiring for the EUCLID cognition loop.

Regression tests for the *composition* layer, not the reasoning layer (which
``euclid/tests/test_cognition_core.py`` covers):

* ``EuclidRuntime.production()`` — the production composition root — must
  actually construct.  It previously raised ``TypeError`` because
  ``_compose_cognition`` passed ``episode_learner``,
  ``representation_controller`` and ``objective_controller`` to
  ``GeneralIntelligenceCore``, whose signature accepted none of them, so nothing
  could build a production runtime at all.
* Cognition outcomes must reach the governed ``LearningService`` rather than
  terminating in telemetry.
* The representation and objective controllers must change behaviour, not
  merely be constructed.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, List, Mapping

from euclid import EuclidRuntime
from euclid.cognition.adaptive import (
    ObjectiveController,
    PersistentStrategyLearner,
    RepresentationController,
)
from euclid.cognition.baselines import (
    ConsequenceDeducer,
    DivergenceDiscriminator,
    InMemoryMemorySystem,
    RuleAbducer,
    StaticSkillComposer,
    StructuralAnalogyEngine,
    WeightedObjective,
)
from euclid.cognition.core import GeneralIntelligenceCore
from euclid.cognition.production import TOECognitivePlanner, TOEMetaController
from euclid.cognition.state import CandidateAction
from euclid.evidence import EvidenceChain

PROBLEM: Dict[str, Any] = {
    "problem_id": "wire-1",
    "goal": "reduce coupling",
    "problem_class": "refactor",
    "structure": ["coupling", "duplication"],
    "observations": ["a -> b", "a -> c"],
}


EXPLANATIONS: Dict[str, Dict[str, str]] = {
    "dependency-fault": {"inspect": "dependency-evidence", "test": "test-evidence"},
    "implementation-fault": {"inspect": "source-evidence", "test": "test-evidence"},
}


MENU = [
    CandidateAction(
        action_id="inspect", description="inspect the failing module",
        origin="declared-skill",
        features={"correctness_estimate": 0.6, "cost": 0.1,
                  "uncertainty": 0.4, "novelty": 0.3, "transfer_value": 0.2},
    ),
    CandidateAction(
        action_id="test", description="run the failing test",
        origin="declared-skill",
        features={"correctness_estimate": 0.5, "cost": 0.2,
                  "uncertainty": 0.5, "novelty": 0.2, "transfer_value": 0.2},
    ),
]


class RecordingEpisodeLearner:
    """Stands in for ``LearningServiceEpisodeAdapter``."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def record_episode(
        self, state: Any, *, success: bool, cycle: int, result: Mapping[str, Any]
    ) -> str:
        self.calls.append({"success": success, "cycle": cycle, "result": dict(result)})
        return f"experience-{len(self.calls)}"


class ExplodingEpisodeLearner:
    def record_episode(self, state: Any, **kwargs: Any) -> str:
        raise RuntimeError("learner is unavailable")


class UnavailableWorldModel:
    """A world model that predicts, so the episode reaches metacontrol."""

    def __init__(self) -> None:
        self.outcomes: List[Dict[str, Any]] = []

    def predict(self, context: str, action: str) -> Any:
        from euclid.cognition.state import PredictionRecord

        return PredictionRecord(
            f"pred-{len(self.outcomes)}", context, action,
            "dependency-evidence", 0.5, False,
        )

    def rollout(self, context: str, actions: Any) -> Any:
        return []

    def update(self, context: str, action: str, observed: str) -> float:
        self.outcomes.append({"context": context, "action": action,
                              "observed": observed})
        return 0.0

    def health(self) -> Any:
        from euclid.cognition.interfaces import ModelHealth

        return ModelHealth(status="healthy", mean_error=0.0, detail="stub")

    def observe(self, *args: Any, **kwargs: Any) -> None:
        return None


class GoverningExecutor:
    """Minimal governed boundary: reports the goal unmet, but its
    intervention observation confirms ``dependency-fault`` so the episode
    keeps one active hypothesis and actually reaches metacontrol/learning
    (an observation-less result refutes every hypothesis and aborts)."""

    def execute(self, action: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "action": action,
            "goal_met": False,
            "cycle": payload.get("cycle"),
            "observation": "dependency-evidence",
        }


def build_core(
    *, episode_learner: Any = None, objective_controller: Any = None,
    representation_controller: Any = None, memory: Any = None,
    strategy_path: str | None = None,
    executor: Any = None,
) -> GeneralIntelligenceCore:
    with TemporaryDirectory() as holder:
        learner_path = strategy_path or str(Path(holder) / "strategy.json")
        return GeneralIntelligenceCore(
            world_model=UnavailableWorldModel(),
            memory=memory or InMemoryMemorySystem(),
            analogy=StructuralAnalogyEngine(),
            abducer=RuleAbducer(EXPLANATIONS),
            deducer=ConsequenceDeducer(EXPLANATIONS),
            discriminator=DivergenceDiscriminator(),
            metacontroller=TOEMetaController(),
            metalearner=PersistentStrategyLearner(learner_path),
            planner=TOECognitivePlanner(),
            skills=StaticSkillComposer(MENU),
            objective=WeightedObjective({
                "correctness_estimate": 0.6, "cost": -0.1,
                "uncertainty": -0.2, "novelty": 0.1, "transfer_value": 0.1,
            }),
            executor=executor if executor is not None else GoverningExecutor(),
            episode_learner=episode_learner,
            representation_controller=representation_controller,
            objective_controller=objective_controller,
            evidence=EvidenceChain(),
        )


class TestProductionCompositionRoot(unittest.TestCase):
    def test_production_runtime_actually_constructs(self) -> None:
        """Regression: this raised TypeError and made production unwireable."""
        with TemporaryDirectory() as root:
            runtime = EuclidRuntime.production(creator_id="tester", state_dir=root)
            try:
                report = runtime.startup_report()
                self.assertIs(report["cognition"]["composed"], True)
                for key in ("world_model", "memory", "planner", "skills"):
                    self.assertIn(key, report["cognition"])
            finally:
                runtime.close()


class TestEpisodeLearnerWiring(unittest.TestCase):
    def test_outcome_reaches_the_episode_learner(self) -> None:
        learner = RecordingEpisodeLearner()
        state = build_core(episode_learner=learner).solve(PROBLEM)
        self.assertTrue(learner.calls, "the episode learner was never called")
        self.assertIn("success", learner.calls[0])
        self.assertIn("learn", [t.phase for t in state.transitions])

    def test_learner_failure_is_recorded_not_fatal(self) -> None:
        state = build_core(episode_learner=ExplodingEpisodeLearner()).solve(PROBLEM)
        state.verify_transitions()
        summaries = [t.summary for t in state.transitions]
        self.assertTrue(
            any("rejected the outcome" in s for s in summaries),
            "a failing episode learner must be recorded in the ledger",
        )


class TestControllersChangeBehaviour(unittest.TestCase):
    def test_representation_controller_runs_a_measured_trial(self) -> None:
        plain = build_core().solve(PROBLEM)
        searched = build_core(
            representation_controller=RepresentationController()
        ).solve(PROBLEM)

        self.assertEqual(plain.representation["representation_kind"], "literal")
        self.assertIn("representation_trial", searched.representation)
        details = [
            t.details for t in searched.transitions if t.phase == "represent"
        ]
        self.assertTrue(details, "no represent transition recorded")
        self.assertIn("baseline_utility", details[-1])
        self.assertIn("candidate_utility", details[-1])
        self.assertIn("rationale", details[-1])

    def test_objective_controller_reports_measured_signals(self) -> None:
        state = build_core(objective_controller=ObjectiveController()).solve(PROBLEM)
        objective_transitions = [t for t in state.transitions if t.phase == "objective"]
        self.assertTrue(objective_transitions, "no objective transition recorded")
        details = objective_transitions[-1].details
        for signal in ("uncertainty", "contradictions",
                       "evidence_gap", "prediction_error"):
            self.assertIn(signal, details)

    def test_absent_controllers_leave_behaviour_unchanged(self) -> None:
        state = build_core().solve(PROBLEM)
        self.assertNotIn("objective", [t.phase for t in state.transitions])
        self.assertEqual(state.representation["representation_kind"], "literal")


if __name__ == "__main__":
    unittest.main()
