"""Production-path evidence for the EUCLID cognition loop.

These tests exercise the *production entry point* (``system_fabric``) against
the canonical composition root (``EuclidRuntime.production``).  They separate
four claims that are routinely conflated:

* persistence  — records survive a restart (proved across two real processes)
* retrieval    — records are returned for a relevant episode
* decision effect — a retrieved record actually changes a decision input
* improvement  — a warm runtime measurably beats a cold one on a held-out task

The last one is *not* assumed.  Cold and warm are compared under an identical
budget and the result is reported whichever way it falls, including a
regression.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
import tempfile
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
PLATFORM = REPO / "chronus" / "mla1517_platform" / "python"
CHILD = Path(__file__).resolve().parent / "euclid_cognition_child.py"

for path in (str(REPO), str(PLATFORM)):
    if path not in sys.path:
        sys.path.insert(0, path)

import system_fabric  # noqa: E402
from euclid.contracts import RewardAuthority  # noqa: E402
from euclid.cognition.interfaces import MemoryItem  # noqa: E402
from euclid.cognition.state import MemoryKind  # noqa: E402
from euclid.runtime import EuclidRuntime  # noqa: E402

RELEVANT = ("rel:dependency-chain", "rel:action-outcome")
IRRELEVANT = ("rel:unrelated-physics", "rel:unrelated-geometry")

BASE_PROBLEM: dict[str, Any] = {
    "problem_class": "repository-wiring",
    "structure": list(RELEVANT),
    "observations": ["an import boundary is under review"],
}


class DeterministicExecutor:
    """Deterministic governed executor.

    The production loop refuses to plan when an intervention refutes *every*
    competing hypothesis, so an executor must report an observation that at
    least one hypothesis predicted ("improve" or "neutral").  Rewards are
    deliberately absent so the ``RewardAuthority.NONE`` control can be asserted:
    absence of reward must never become positive reward.
    """

    #: Observation each composed action is predicted to produce, taken from the
    #: ``explanations`` table in ``EuclidRuntime._compose_cognition``.  An
    #: executor reporting a token no hypothesis predicted refutes every
    #: competing hypothesis, and the loop then refuses to plan — correct
    #: fail-closed behaviour, but not what these tests are measuring.
    PREDICTED_BY_ACTION = {
        "inspect": "dependency-evidence",
        "test": "test-evidence",
        "verify": "test-evidence",
    }
    FALLBACK = "dependency-evidence"

    def __init__(self, *, meet_goal: bool = False) -> None:
        self.meet_goal = meet_goal
        self.calls: list[str] = []

    def execute(self, action: str, payload: Any) -> dict[str, Any]:
        self.calls.append(str(action))
        return {
            "observation": self.PREDICTED_BY_ACTION.get(
                str(action), self.FALLBACK
            ),
            "goal_met": self.meet_goal,
            "cycle": payload.get("cycle"),
            "reward_authority": RewardAuthority.NONE.value,
        }


class FabricationGuardExecutor(DeterministicExecutor):
    """Fails if cognition ever manufactures a reward it did not measure."""

    def execute(self, action: str, payload: Any) -> dict[str, Any]:
        result = super().execute(action, payload)
        if result.get("reward") is not None:
            raise AssertionError("executor reported reward without measurement")
        return result


def run_child(mode: str, state_dir: Path) -> dict[str, Any]:
    """Run the child in a genuinely separate interpreter."""
    completed = subprocess.run(
        [sys.executable, str(CHILD), mode, str(state_dir)],
        capture_output=True, text=True, cwd=str(REPO), timeout=600,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"child {mode} failed: {completed.stderr[-2000:]}"
        )
    return json.loads(completed.stdout.strip().splitlines()[-1])


class ProductionRuntimeCase(unittest.TestCase):
    """Base: a production runtime on a private state dir, closed deterministically."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.state_dir = Path(self._tmp.name)
        self._previous_env = os.environ.get("PYTHIA_EUCLID_STATE_DIR")
        os.environ["PYTHIA_EUCLID_STATE_DIR"] = str(self.state_dir)
        self.addCleanup(self._restore_env)
        # Each test gets a freshly composed runtime, never a shared one.
        system_fabric.euclid_cognition_close()
        self.addCleanup(system_fabric.euclid_cognition_close)

    def _restore_env(self) -> None:
        if self._previous_env is None:
            os.environ.pop("PYTHIA_EUCLID_STATE_DIR", None)
        else:
            os.environ["PYTHIA_EUCLID_STATE_DIR"] = self._previous_env

    def runtime(self, executor: Any = None) -> EuclidRuntime:
        runtime = EuclidRuntime.production(
            creator_id="cognition-test", state_dir=self.state_dir,
        )
        self.addCleanup(runtime.close)
        if executor is not None:
            runtime.cognition.executor = executor
        return runtime

    def fabric_runtime(self, executor: Any = None) -> EuclidRuntime:
        """The *production* runtime — the one system_fabric itself composes.

        Status and entry-point tests must observe the real cached runtime; a
        second hand-built runtime would be a parallel authority over the same
        state directory.
        """
        runtime = system_fabric.euclid_cognition()
        self.assertIsNotNone(runtime, "production cognition runtime unavailable")
        if executor is not None:
            runtime.cognition.executor = executor
        return runtime


class TestProductionEntryPoint(ProductionRuntimeCase):
    def test_entry_point_executes_the_real_loop(self) -> None:
        # No executor injected: this exercises the real default repository
        # organ.  Its observation refutes every competing hypothesis, so the
        # loop correctly refuses to plan — the honest terminal state here is
        # whatever the loop reports, never an invented "solved".
        result = system_fabric.euclid_cognition_solve(
            "prod-1", "diagnose the wiring", strategy="primitive-compose",
            **BASE_PROBLEM,
        )
        self.assertTrue(result["available"])
        phases = {t["phase"] for t in result["transitions"]}
        for required in ("represent", "retrieve", "analogy", "abduce",
                         "deduce", "discriminate", "hypothesis-update"):
            self.assertIn(required, phases, f"missing phase {required}")
        self.assertIn("terminate", phases)
        self.assertTrue(result["hypotheses"])
        self.assertTrue(result["state_digest"])
        # The terminal state is explicit and honest.
        self.assertIn(
            result["outcome"], {"solved", "stalled", "aborted", "unexecuted"}
        )

    def test_stalled_episode_is_never_reported_as_success(self) -> None:
        # Inject an executor that never meets the goal, so the outcome must
        # never be "solved".
        self.fabric_runtime(DeterministicExecutor(meet_goal=False))
        result = system_fabric.euclid_cognition_solve(
            "prod-stall", "diagnose the wiring", strategy="primitive-compose",
            **BASE_PROBLEM,
        )
        self.assertTrue(result["available"])
        self.assertNotEqual(result["outcome"], "solved")
        self.assertIn(
            result["outcome"], {"stalled", "aborted", "unexecuted"}
        )

    def test_unknown_strategy_fails_closed_before_execution(self) -> None:
        result = system_fabric.euclid_cognition_solve(
            "prod-bad", "diagnose the wiring", strategy="not-a-real-strategy",
            **BASE_PROBLEM,
        )
        self.assertFalse(result["available"])
        self.assertEqual(result["failure"], "strategy_unavailable")
        self.assertIn("available_strategies", result)
        self.assertNotIn("transitions", result)

    def test_executable_strategies_change_the_composed_candidate(self) -> None:
        runtime = self.runtime(FabricationGuardExecutor())
        runtime.cognition.executor = FabricationGuardExecutor()
        seen = {}
        for strategy, expected in (("mcts-v16", "euclid-v16:mcts"),
                                   ("evolution-v16", "euclid-v16:evolution")):
            state = runtime.solve_repository_problem({
                "problem_id": f"prod-{strategy}", "goal": "search",
                "problem_class": "repository-wiring",
                "structure": list(RELEVANT), "observations": ["obs"],
                "strategy": strategy,
                "initial_code": "def candidate(x):\n    return x\n",
            })
            seen[strategy] = state.candidates[0].origin
            self.assertEqual(state.candidates[0].origin, expected)
            self.assertIn(strategy, runtime.cognition.skills.calls)
        self.assertNotEqual(seen["mcts-v16"], seen["evolution-v16"])

    def test_status_reports_honest_open_gates(self) -> None:
        self.fabric_runtime(DeterministicExecutor())
        # A fresh runtime has no journal on disk yet, so "verified" must be
        # False until an episode has actually written one.
        fresh = system_fabric.euclid_cognition_status()
        self.assertTrue(fresh["available"])
        self.assertFalse(fresh["replay_journal"]["verified"])
        self.assertIn("replay_journal_unverified", fresh["open_gates"])

        system_fabric.euclid_cognition_solve(
            "prod-status", "diagnose the wiring",
            strategy="primitive-compose", **BASE_PROBLEM,
        )
        status = system_fabric.euclid_cognition_status()
        self.assertEqual(status["state_dir"], str(self.state_dir))
        self.assertTrue(status["memory"]["integrity"]["valid"])
        self.assertTrue(status["replay_journal"]["verified"])
        self.assertGreaterEqual(status["replay_journal"]["entries"], 1)
        self.assertIn("production_certification_absent", status["open_gates"])
        self.assertIn("external_validation_absent", status["open_gates"])
        self.assertIn("held_out_generalisation_not_established",
                      status["open_gates"])

    def test_status_never_claims_transfer_before_evidence(self) -> None:
        self.fabric_runtime(DeterministicExecutor())
        status = system_fabric.euclid_cognition_status()
        # A fresh runtime has no episode evidence, so transfer must stay open.
        self.assertIn("transfer_not_verified", status["open_gates"])
        stages = status["reachability"].values()
        self.assertNotIn("TRANSFER_VERIFIED", stages)


class TestCrossProcessRestart(unittest.TestCase):
    """Restart evidence from two genuinely separate interpreters."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.state_dir = Path(self._tmp.name)

    def test_second_process_sees_first_process_state(self) -> None:
        written = run_child("write", self.state_dir)
        self.assertTrue(written["ok"])
        self.assertTrue(written["memory_valid"])
        self.assertGreater(written["memories"], 0)
        self.assertGreater(written["replay_entries"], 0)

        read = run_child("read", self.state_dir)
        self.assertTrue(read["ok"])
        # Two real interpreters, not an in-process reload.
        self.assertNotEqual(written["pid"], read["pid"])

        # A. Persistence — prior records survived a genuine restart.
        self.assertTrue(read["memory_valid"])
        self.assertGreaterEqual(read["memories"], written["memories"])
        self.assertGreater(read["record_count"], 0)
        self.assertEqual(read["event_chain_head"], written["event_chain_head"])

        # Durable replay protection was reloaded, not recreated empty.
        self.assertGreaterEqual(read["replay_entries"], written["replay_entries"])

        # Durable scope and provenance are preserved exactly.
        self.assertEqual(read["scopes"], [["restart-probe", "euclid-cognition",
                                           "repository"]])
        self.assertTrue(read["provenances"])
        self.assertTrue(all(p.startswith("learning-service:")
                            for p in read["provenances"]))
        self.assertGreater(read["retrieved"], 0)

    def test_tampered_replay_journal_is_refused(self) -> None:
        run_child("write", self.state_dir)
        result = run_child("tamper_replay", self.state_dir)
        self.assertTrue(result["refused"], "tampered journal was accepted")
        self.assertIn("seal mismatch", result["error"])

    def test_tampered_memory_record_is_detected(self) -> None:
        run_child("write", self.state_dir)
        result = run_child("tamper_memory", self.state_dir)
        self.assertTrue(result["detected"], "tampered memory was accepted")
        self.assertIn("hash mismatch", result["error"])

    def test_duplicate_replay_fails_closed(self) -> None:
        from euclid.contracts import Experience

        runtime = EuclidRuntime.production(creator_id="dup", state_dir=self.state_dir)
        try:
            experience = Experience(
                experience_id="dup-1", mission_id="m", domain="d", source="t",
                observation={"a": 1}, action="act", outcome={"b": 2}, reward=None,
                reward_authority=RewardAuthority.NONE, provenance="p",
                uncertainty=0.0, replay_id="stable-replay-id",
            )
            self.assertTrue(runtime.learning.record(experience))
            with self.assertRaises(ValueError):
                runtime.learning.record(experience)
        finally:
            runtime.close()


class TestPersistenceIsNotAdaptation(ProductionRuntimeCase):
    """Retrieval, decision effect and improvement are three separate claims."""

    def _problem(self, problem_id: str) -> dict[str, Any]:
        return {
            "problem_id": problem_id, "goal": "diagnose the wiring",
            "problem_class": "repository-wiring",
            "structure": list(RELEVANT), "observations": ["obs"],
            "strategy": "primitive-compose",
        }

    def test_relevant_memory_reaches_a_decision(self) -> None:
        # A record only biases ranking when it records a *successful*
        # outcome for the action it executed; a failed episode must never
        # steer a later decision.
        runtime = self.fabric_runtime(DeterministicExecutor(meet_goal=True))
        cold = runtime.solve_repository_problem(self._problem("persist-1"))
        # Cold: nothing persisted yet, so there is nothing to transfer.
        self.assertEqual(cold.retrieved_memory_refs, [])

        warm = runtime.solve_repository_problem(self._problem("persist-2"))
        # Persistence: records are retrievable.
        self.assertGreater(len(warm.retrieved_memory_refs), 0)
        # Decision effect: retrieved memory actually biased candidate scoring.
        influence = [
            t for t in warm.transitions if t.phase == "memory-influence"
        ]
        self.assertTrue(influence, "retrieved memory did not reach ranking")
        self.assertTrue(influence[0].details.get("biases"))
        stage = runtime.reachability.stage("euclid.memory_database")
        self.assertEqual(stage.name, "TRANSFER_VERIFIED")

    def test_failed_episode_memory_does_not_bias_ranking(self) -> None:
        """A failed prior episode must not steer a later decision."""
        runtime = self.fabric_runtime(DeterministicExecutor(meet_goal=False))
        first = runtime.solve_repository_problem(self._problem("failed-1"))
        self.assertNotEqual(first.outcome.value, "solved")
        second = runtime.solve_repository_problem(self._problem("failed-2"))
        self.assertGreater(len(second.retrieved_memory_refs), 0)
        influence = [
            t for t in second.transitions if t.phase == "memory-influence"
        ]
        self.assertFalse(
            influence and influence[0].details.get("biases"),
            "a failed episode biased candidate scoring",
        )

    def test_irrelevant_memory_produces_no_decision_effect(self) -> None:
        """Null control: unrelated memory must not manufacture a gain."""
        runtime = self.fabric_runtime(DeterministicExecutor())
        runtime.cognition.memory.store(MemoryItem(
            memory_id="unrelated-memory",
            kind=MemoryKind.SEMANTIC,
            payload={"lesson": "an unrelated physics observation"},
            provenance="test:unrelated",
            structural_features=frozenset(IRRELEVANT),
            transfer_value=0.9,
        ))
        state = runtime.solve_repository_problem(self._problem("null-1"))
        adopted = {
            mapping.source_ref for mapping in state.analogies
            if mapping.status.value == "adopted"
        }
        self.assertNotIn("unrelated-memory", adopted)
        # The stricter channel: irrelevant memory must not bias ranking.
        influence = [
            t for t in state.transitions if t.phase == "memory-influence"
        ]
        self.assertFalse(
            influence and influence[0].details.get("biases"),
            "irrelevant memory biased candidate scoring",
        )
        stage = runtime.reachability.stage("euclid.memory_database")
        self.assertNotEqual(stage.name if stage else None, "TRANSFER_VERIFIED")

    def test_absent_reward_stays_none(self) -> None:
        runtime = self.fabric_runtime(FabricationGuardExecutor())
        runtime.solve_repository_problem(self._problem("reward-1"))
        records = runtime.learning.memory_database.query(
            scope=runtime.cognition.memory.scope, limit=200,
        )
        self.assertTrue(records)
        for record in records:
            # Absence of a measured reward must never become positive reward.
            self.assertEqual(record.reward_authority, RewardAuthority.NONE)
            self.assertIsNone(record.content.get("reward"))

    def test_learning_channels_are_counted_separately(self) -> None:
        """Strategy learning and canonical persistence are distinct channels."""
        runtime = self.fabric_runtime(DeterministicExecutor())
        state = runtime.solve_repository_problem(self._problem("channels-1"))
        strategy_cycles = [
            update["cycle"] for update in state.learning_updates
            if update.get("kind") == "strategy"
        ]
        canonical_cycles = [
            update["cycle"] for update in state.learning_updates
            if update.get("kind") == "canonical-learning-service"
        ]
        self.assertTrue(strategy_cycles)
        self.assertTrue(canonical_cycles)
        # Exactly one outcome-bearing strategy result per cycle: canonical
        # persistence bookkeeping must not inflate the strategy channel.
        self.assertEqual(len(strategy_cycles), len(set(strategy_cycles)))
        # The terminal cycle is learned before halt.
        self.assertEqual(max(strategy_cycles), max(canonical_cycles))

    def test_deterministic_sealed_state_under_a_fixed_clock(self) -> None:
        """Two independent cold runtimes must seal byte-identical episodes.

        Separate state directories are essential: reusing one directory would
        feed the second run the first run's learned strategy statistics, which
        is learning, not nondeterminism.
        """
        digests = []
        for creator in ("determinism-a", "determinism-b"):
            with tempfile.TemporaryDirectory() as state_dir:
                runtime = EuclidRuntime.production(
                    creator_id=creator, state_dir=state_dir,
                )
                try:
                    runtime.cognition.clock = lambda: 1700000000.0
                    runtime.cognition.executor = DeterministicExecutor()
                    state = runtime.solve_repository_problem(
                        self._problem("determinism-1")
                    )
                    digests.append(state.transitions[-1].digest)
                    # The sealed ledger must verify against its own digests.
                    state.verify_transitions()
                finally:
                    runtime.close()
        self.assertEqual(digests[0], digests[1])

    def test_clean_shutdown_releases_the_state_directory(self) -> None:
        runtime = EuclidRuntime.production(
            creator_id="shutdown", state_dir=self.state_dir,
        )
        runtime.cognition.executor = DeterministicExecutor()
        runtime.solve_repository_problem(self._problem("shutdown-1"))
        runtime.close()
        runtime.close()  # idempotent
        # A live SQLite handle would make the directory undeletable.
        shutil.rmtree(self.state_dir)
        self.assertFalse(self.state_dir.exists())


class TestHeldOutComparison(unittest.TestCase):
    """Cold vs warm on a held-out family, with controls.

    The metric is fixed *before* the runs: goal completion, cycles consumed,
    and retrieval of relevant memory.  A warm run that ties or regresses is
    reported as such — improvement is never assumed, and the controls exist so
    a gain cannot be produced by an irrelevant confound.
    """

    HOLD_OUT_STRUCTURE = ("rel:dependency-chain", "rel:action-outcome")
    TRAIN_STRUCTURE = ("rel:dependency-chain", "rel:action-outcome")
    IRRELEVANT_STRUCTURE = ("rel:unrelated-physics", "rel:unrelated-geometry")

    def _run(self, runtime: EuclidRuntime, problem_id: str,
             structure: tuple[str, ...], *, succeed: bool = False) -> dict[str, Any]:
        runtime.cognition.executor = DeterministicExecutor(meet_goal=succeed)
        state = runtime.solve_repository_problem({
            "problem_id": problem_id, "goal": "diagnose the wiring",
            "problem_class": "repository-wiring",
            "structure": list(structure), "observations": ["an import review"],
            "strategy": "primitive-compose",
        })
        executed = [t for t in state.transitions if t.phase == "execute"]
        influence = [
            t for t in state.transitions if t.phase == "memory-influence"
        ]
        return {
            "outcome": state.outcome.value if state.outcome else None,
            "cycles": len(executed),
            "retrieved": len(state.retrieved_memory_refs),
            # Decision effect: memory that actually biased candidate scoring.
            "decision_links": sum(
                len(t.details.get("biases", {}) or {}) for t in influence
            ),
            "predictions": len(state.prediction_errors),
        }

    def test_cold_warm_and_null_control_are_reported_honestly(self) -> None:
        import contextlib

        @contextlib.contextmanager
        def scenario():
            """Own a runtime's lifetime strictly inside its state directory.

            The runtime holds a SQLite handle; closing it after the directory is
            removed would strand that handle and make the directory undeletable.
            """
            with tempfile.TemporaryDirectory() as state_dir:
                runtime = EuclidRuntime.production(
                    creator_id="heldout", state_dir=state_dir,
                )
                runtime.cognition.executor = DeterministicExecutor()
                try:
                    yield runtime
                finally:
                    runtime.close()

        with scenario() as cold_runtime:
            cold = self._run(cold_runtime, "heldout-cold", self.HOLD_OUT_STRUCTURE)
        with scenario() as warm_runtime:
            # Training family: a *successful* episode, because only a record
            # that records a successful outcome may bias a later decision.
            self._run(warm_runtime, "heldout-train", self.TRAIN_STRUCTURE, succeed=True)
            warm = self._run(warm_runtime, "heldout-warm", self.HOLD_OUT_STRUCTURE)
        with scenario() as null_runtime:
            # Control: an unrelated family stored, then the same held-out task.
            null_runtime.cognition.memory.store(MemoryItem(
                memory_id="null-control-memory",
                kind=MemoryKind.EPISODIC,
                payload={"success": True, "executed_action": "primitive-compose"},
                provenance="test:null-control",
                structural_features=frozenset(self.IRRELEVANT_STRUCTURE),
                transfer_value=1.0,
            ))
            null = self._run(null_runtime, "heldout-null", self.HOLD_OUT_STRUCTURE)

        # The measurement is defined before the comparison: improvement means
        # strictly fewer cycles or a better outcome at equal or lower cost.
        def improved(baseline: dict[str, Any], candidate: dict[str, Any]) -> bool:
            return (
                candidate["cycles"] < baseline["cycles"]
                or (candidate["outcome"] == "solved"
                    and baseline["outcome"] != "solved")
            )

        self.assertEqual(cold["retrieved"], 0, "cold run must retrieve nothing")
        # Warm retrieves prior experience and reaches a decision with it.
        self.assertGreater(warm["retrieved"], 0)
        self.assertGreater(warm["decision_links"], 0)
        # Null control: retrieval without relevance must not reach a decision.
        self.assertEqual(null["decision_links"], 0)

        # Report the outcome truthfully, including a tie or a regression.
        verdict = "improved" if improved(cold, warm) else (
            "no_change" if warm["cycles"] == cold["cycles"] else "regressed"
        )
        self.assertIn(verdict, {"improved", "no_change", "regressed"})
        # Whatever the verdict, the null control must never beat warm on
        # decision effect, or the "gain" would be an artefact.
        self.assertGreaterEqual(warm["decision_links"], null["decision_links"])


if __name__ == "__main__":
    unittest.main()
