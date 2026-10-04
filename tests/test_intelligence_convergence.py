from __future__ import annotations

import hashlib
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from euclid.contracts import RewardAuthority
from euclid.cognition import AblationConfig, Outcome
from euclid.cognition.production import (
    DurableCognitiveMemory,
    TOECognitivePlanner,
    TOEMetaController,
    TOEWorldModelAdapter,
    V16SkillSearchAdapter,
)
from euclid.cognition.reachability import ReachabilityStage
from euclid.runtime import EuclidRuntime


class FakeRepoEngineer:
    def __init__(self, *args, **kwargs):
        self.calls = []

    def ask(self, prompt):
        self.calls.append(prompt)
        return {
            "task_id": f"task-{len(self.calls)}",
            "routes": ["repository_map", "import_audit", "focused_tests"],
            "evidence": {"import_audit": {"finding_count": 0, "files_audited": 1}},
        }


class MeasuredExecutor:
    def execute(self, action, payload):
        return {
            "observation": "measured-pass",
            "goal_met": True,
            "reward": 1.0,
            "reward_authority": RewardAuthority.MEASURED_ENVIRONMENT.value,
        }


def problem(problem_id, strategy="primitive-compose"):
    return {
        "problem_id": problem_id,
        "goal": "diagnose and verify repository wiring",
        "problem_class": "repository-wiring",
        "structure": ["rel:dependency-chain", "rel:action-outcome"],
        "observations": ["an integration import is under review"],
        "initial_code": "def candidate(x):\n    return x\n",
        "strategy": strategy,
    }


class IntelligenceConvergenceTests(unittest.TestCase):
    def production(self, root):
        with patch("Intelligence.repo_engineer.RepoEngineer", FakeRepoEngineer):
            return EuclidRuntime.production(creator_id="andre", state_dir=root)

    @contextmanager
    def runtime_for(self, directory):
        """Own a runtime's whole lifetime inside one state directory.

        The runtime holds a SQLite handle and a snapshot writer; closing it
        after the temporary directory is removed would leak the handle and make
        the directory undeletable.  The context manager keeps close() strictly
        inside the directory's lifetime, which is also the real deployment order.
        """
        runtime = self.production(directory)
        try:
            yield runtime
        finally:
            runtime.close()

    def test_production_root_composes_real_repository_implementations(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.runtime_for(directory) as runtime:
                self.assertIsInstance(runtime.cognition.world_model, TOEWorldModelAdapter)
                self.assertIsInstance(runtime.cognition.memory, DurableCognitiveMemory)
                self.assertIsInstance(runtime.cognition.planner, TOECognitivePlanner)
                self.assertIsInstance(runtime.cognition.metacontroller, TOEMetaController)
                self.assertIsInstance(runtime.cognition.skills, V16SkillSearchAdapter)
                self.assertIs(runtime.cognition.evidence, runtime.evidence)
                self.assertIs(
                    runtime.cognition.episode_learner.service, runtime.learning
                )
    def test_episode_calls_toe_changes_state_executes_and_closes_feedback(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.runtime_for(directory) as runtime:
                runtime.cognition.executor = MeasuredExecutor()
                state = runtime.solve_repository_problem(problem("repo-1"))
                self.assertEqual(state.outcome, Outcome.SOLVED)
                phases = {transition.phase for transition in state.transitions}
                self.assertTrue({"deduce", "plan", "compose", "execute", "compare", "learn"} <= phases)
                self.assertTrue(runtime.cognition.world_model.model.outcomes)
                self.assertTrue(
                    any(update["kind"] == "canonical-learning-service"
                        for update in state.learning_updates)
                )
                self.assertTrue(runtime.learning.experience_learner.transitions)
                runtime.reachability.require(
                    "toe.world_model", ReachabilityStage.FEEDBACK_CLOSED
                )
    def test_v16_mcts_and_evolution_are_selectable_and_change_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.runtime_for(directory) as runtime:
                runtime.cognition.executor = MeasuredExecutor()
                mcts = runtime.solve_repository_problem(problem("repo-mcts", "mcts-v16"))
                evolution = runtime.solve_repository_problem(
                    problem("repo-evolution", "evolution-v16")
                )
                self.assertEqual(mcts.candidates[0].origin, "euclid-v16:mcts")
                self.assertEqual(evolution.candidates[0].origin, "euclid-v16:evolution")
                self.assertNotEqual(mcts.candidates[0].action_id, evolution.candidates[0].action_id)
                self.assertIn("mcts-v16", runtime.cognition.skills.calls)
                self.assertIn("evolution-v16", runtime.cognition.skills.calls)
    def test_representation_and_mathematical_ablation_change_episode_path(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.runtime_for(directory) as runtime:
                runtime.cognition.executor = MeasuredExecutor()
                represented_problem = problem("repo-representation", "primitive-compose")
                represented_problem["representation_evidence"] = {
                    "literal": {"utility": 0.1, "cost": 0.1},
                    "relational": {"utility": 0.8, "cost": 0.1},
                }
                represented = runtime.solve_repository_problem(represented_problem)
                self.assertEqual(
                    represented.representation["active_representation"], "relational"
                )

                runtime.cognition.ablations = AblationConfig(
                    mathematical_structure=False
                )
                ablated = runtime.solve_repository_problem(
                    problem("repo-math-ablation", "mcts-v16")
                )
                self.assertIn("mathematical_structure", ablated.ablations)
                self.assertTrue(all(
                    candidate.origin == "euclid-v16:ASTPrimitives"
                    for candidate in ablated.candidates
                ))
    def test_durable_memory_replay_guard_restart_and_transfer(self):
        with tempfile.TemporaryDirectory() as directory:
            first = self.production(directory)
            first.cognition.executor = MeasuredExecutor()
            state = first.solve_repository_problem(problem("repo-first"))
            result = MeasuredExecutor().execute("x", {})
            first.cognition.episode_learner.record_episode(
                state, success=True, cycle=0, result=result,
            )
            with self.assertRaises(ValueError):
                first.cognition.episode_learner.record_episode(
                    state, success=True, cycle=0, result=result,
                )
            self.assertGreater(
                first.learning.memory_database.verify()["memories"], 0
            )
            first.close()

            with self.runtime_for(directory) as second:
                second.cognition.executor = MeasuredExecutor()
                related = second.solve_repository_problem(problem("repo-related"))
                self.assertTrue(related.retrieved_memory_refs)
                second.reachability.require(
                    "euclid.memory_database", ReachabilityStage.TRANSFER_VERIFIED
                )

    def test_cognition_does_not_change_bitcoin_consensus_semantics(self):
        header = bytes(range(80))
        before = hashlib.sha256(hashlib.sha256(header).digest()).digest()
        with tempfile.TemporaryDirectory() as directory:
            with self.runtime_for(directory) as runtime:
                runtime.cognition.executor = MeasuredExecutor()
                runtime.solve_repository_problem(problem("repo-consensus-boundary"))
            after = hashlib.sha256(hashlib.sha256(header).digest()).digest()
            self.assertEqual(before, after)

if __name__ == "__main__":
        unittest.main()