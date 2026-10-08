"""Production-integration regressions for EUCLID 17 runtime closure."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from euclid.cognition.baselines import DelegatorExecutor
from euclid.cognition.core import AblationConfig
from euclid.cognition.integrated.control import ContextualStrategyLearner
from euclid.cognition.reachability import ReachabilityStage
from euclid.cognition.worlds import MechanismWorld, WorldExecutor, generate_task
from euclid.runtime import EuclidRuntime


class _FailingExecutor:
    def __init__(self, exc: BaseException) -> None:
        self.exc = exc

    def execute(self, _action, _payload):
        raise self.exc


class EuclidV17ProductionIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _runtime(self) -> EuclidRuntime:
        return EuclidRuntime(creator_id="creator-1", state_dir=self.root)

    def _spec(self, seed: int = 21):
        return generate_task("program-transformation", seed=seed, partition="evaluation")

    def test_f1_solver_exception_revokes_episode_dispatch_right(self) -> None:
        runtime = self._runtime()
        runtime.compose_adaptive_intelligence()
        spec, _truth = self._spec()
        with self.assertRaises(RuntimeError):
            runtime.solve_task(spec, _FailingExecutor(RuntimeError("boom")), seed=1)

        self.assertFalse(
            runtime.rights.permits(
                "creator-1", "task-world-1", "task-world-1.execute", "dispatch"
            )
        )
        with self.assertRaises(PermissionError):
            DelegatorExecutor(
                runtime.delegator, "task-world-1", "task-world-1.execute"
            ).execute("probe", {"kind": "intervention", "program": [spec.operators[0]]})

    def test_f1_baseexception_also_revokes_episode_dispatch_right(self) -> None:
        runtime = self._runtime()
        runtime.compose_adaptive_intelligence()
        spec, _truth = self._spec(22)
        with self.assertRaises(KeyboardInterrupt):
            runtime.solve_task(spec, _FailingExecutor(KeyboardInterrupt()), seed=1)
        self.assertFalse(
            runtime.rights.permits(
                "creator-1", "task-world-1", "task-world-1.execute", "dispatch"
            )
        )

    def test_f2_ablated_components_do_not_receive_episode_credit(self) -> None:
        runtime = self._runtime()
        runtime.compose_adaptive_intelligence(
            ablations=AblationConfig(
                analogy=False,
                representation_restructuring=False,
            )
        )
        spec, truth = self._spec(23)
        runtime.solve_task(spec, WorldExecutor(MechanismWorld(spec, truth)), seed=2)

        self.assertEqual(
            runtime.reachability.stage("euclid.adaptive.analogy"),
            ReachabilityStage.REACHABLE,
        )
        self.assertEqual(
            runtime.reachability.stage("euclid.adaptive.representation"),
            ReachabilityStage.REACHABLE,
        )
        for component in EuclidRuntime.ADAPTIVE_COMPONENTS:
            self.assertLessEqual(
                runtime.reachability.stage(component),
                ReachabilityStage.USED_IN_EPISODE,
            )

    def test_f3_same_process_recomposition_is_not_restart_verified(self) -> None:
        runtime = self._runtime()
        runtime.compose_adaptive_intelligence()
        spec, truth = self._spec(24)
        runtime.solve_task(spec, WorldExecutor(MechanismWorld(spec, truth)), seed=3)

        runtime.compose_adaptive_intelligence()
        for component in EuclidRuntime.ADAPTIVE_COMPONENTS:
            self.assertLess(
                runtime.reachability.stage(component),
                ReachabilityStage.RESTART_VERIFIED,
            )

    def test_f6_harmful_imported_strategy_is_detected_and_abandoned(self) -> None:
        learner = ContextualStrategyLearner(seed=7)
        # Strong source/global evidence says imported-strategy is excellent.
        learner.global_stats["imported-strategy"] = [9.0, 10.0]

        reports = [
            learner.record_episode("target-class", "imported-strategy", 0.0)
            for _ in range(3)
        ]
        detected = reports[-1].get("negative_transfer")
        self.assertIsNotNone(detected)
        self.assertEqual(
            detected["remediation"],
            "suppress_imported_strategy_and_global_prior",
        )

        choice = learner.select_strategy(
            "target-class",
            ("imported-strategy", "class-local-fallback"),
        )
        self.assertEqual(choice.strategy_id, "class-local-fallback")
        self.assertIn("negative-transfer guard suppressed", choice.basis)
        self.assertTrue(
            any(
                event.get("event") == "abandon_negative_transfer"
                for event in learner.events
            )
        )

    def test_f4_recomposition_preserves_unique_task_organ_identity(self) -> None:
        runtime = self._runtime()
        runtime.compose_adaptive_intelligence()
        spec1, truth1 = self._spec(25)
        runtime.solve_task(spec1, WorldExecutor(MechanismWorld(spec1, truth1)), seed=4)

        runtime.compose_adaptive_intelligence()
        spec2, truth2 = self._spec(26)
        result = runtime.solve_task(
            spec2, WorldExecutor(MechanismWorld(spec2, truth2)), seed=5
        )
        self.assertIsNotNone(result)
        organ_ids = {row["organ_id"] for row in runtime.registry.report()}
        self.assertIn("task-world-1", organ_ids)
        self.assertIn("task-world-2", organ_ids)


if __name__ == "__main__":
    unittest.main()
