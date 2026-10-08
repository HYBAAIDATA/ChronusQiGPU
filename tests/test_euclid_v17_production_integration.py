"""Production-integration regressions for EUCLID 17 runtime closure."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from aethel.enterprise.lifecycle import CompositionRoot
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


_FRESH_PROCESS_WRITER = r"""
import json
import sys
from pathlib import Path
from aethel.enterprise.lifecycle import CompositionRoot
from euclid.cognition.worlds import MechanismWorld, WorldExecutor, generate_task
from euclid.runtime import EuclidRuntime

custody_root = Path(sys.argv[1])
local_root = Path(sys.argv[2])
receipt_path = Path(sys.argv[3])
lifecycle = CompositionRoot(
    custody_root, tenant="tenant-euclid-v17", hmac_key=b"k" * 32
)
lifecycle.start()
try:
    port = lifecycle.data_port("euclid")
    runtime = EuclidRuntime(creator_id="creator-1", state_dir=local_root)
    runtime.bind_adaptive_data_port(port)
    runtime.compose_adaptive_intelligence()
    spec, truth = generate_task("program-transformation", seed=31, partition="evaluation")
    runtime.solve_task(spec, WorldExecutor(MechanismWorld(spec, truth)), seed=31)
    receipt = runtime.adaptive_restart_receipt()
    receipt_path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
finally:
    lifecycle.stop()
"""

_FRESH_PROCESS_READER = r"""
import json
import sys
from pathlib import Path
from aethel.enterprise.lifecycle import CompositionRoot
from euclid.cognition.worlds import MechanismWorld, WorldExecutor, generate_task
from euclid.runtime import EuclidRuntime

custody_root = Path(sys.argv[1])
local_root = Path(sys.argv[2])
prior = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
lifecycle = CompositionRoot(
    custody_root, tenant="tenant-euclid-v17", hmac_key=b"k" * 32
)
lifecycle.start()
try:
    port = lifecycle.data_port("euclid")
    runtime = EuclidRuntime(creator_id="creator-1", state_dir=local_root)
    runtime.bind_adaptive_data_port(port)
    runtime.compose_adaptive_intelligence()
    verification = runtime.verify_adaptive_restart_receipt(prior)
    before = runtime.adaptive_restart_receipt()
    spec, truth = generate_task("program-transformation", seed=32, partition="evaluation")
    runtime.solve_task(spec, WorldExecutor(MechanismWorld(spec, truth)), seed=32)
    after = runtime.adaptive_restart_receipt()
    latest = port.latest(runtime.ADAPTIVE_KNOWLEDGE_KIND)
    print(json.dumps({
        "verification": verification,
        "before": before,
        "after": after,
        "parents": list(latest.parent_binding_ids),
    }, sort_keys=True))
finally:
    lifecycle.stop()
"""

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

    def test_f3_f5_fresh_process_restart_replays_shared_adaptive_state(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            part for part in (str(repo_root), env.get("PYTHONPATH", "")) if part
        )
        custody_root = self.root / "fresh-process-custody"
        receipt_path = self.root / "restart-receipt.json"

        first = subprocess.run(
            [
                sys.executable,
                "-c",
                _FRESH_PROCESS_WRITER,
                str(custody_root),
                str(self.root / "fresh-local-a"),
                str(receipt_path),
            ],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        prior = json.loads(receipt_path.read_text(encoding="utf-8"))

        second = subprocess.run(
            [
                sys.executable,
                "-c",
                _FRESH_PROCESS_READER,
                str(custody_root),
                str(self.root / "fresh-local-b"),
                str(receipt_path),
            ],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        self.assertEqual(second.returncode, 0, second.stderr)
        observed = json.loads(second.stdout.strip().splitlines()[-1])

        self.assertTrue(observed["verification"]["passed"])
        self.assertNotEqual(
            observed["verification"]["current_process_id"],
            observed["verification"]["prior_process_id"],
        )
        self.assertEqual(observed["before"]["binding_id"], prior["binding_id"])
        self.assertEqual(
            observed["before"]["knowledge_seal"], prior["knowledge_seal"]
        )
        self.assertEqual(observed["before"]["episodes"], prior["episodes"])
        self.assertGreater(observed["after"]["episodes"], prior["episodes"])
        self.assertNotEqual(observed["after"]["binding_id"], prior["binding_id"])
        self.assertIn(prior["binding_id"], observed["parents"])
        self.assertFalse((self.root / "fresh-local-b" / "adaptive_knowledge.json").exists())

    def test_f5_adaptive_state_recovers_from_shared_ovid_theseus_custody(self) -> None:
        custody_root = self.root / "shared-custody"
        key = b"k" * 32

        first_lifecycle = CompositionRoot(
            custody_root,
            tenant="tenant-euclid-v17",
            hmac_key=key,
        )
        first_lifecycle.start()
        try:
            first_port = first_lifecycle.data_port("euclid")
            first_runtime = EuclidRuntime(
                creator_id="creator-1",
                state_dir=self.root / "local-a",
            )
            first_runtime.bind_adaptive_data_port(first_port)
            first_runtime.compose_adaptive_intelligence()
            spec, truth = self._spec(27)
            first_runtime.solve_task(
                spec,
                WorldExecutor(MechanismWorld(spec, truth)),
                seed=6,
            )
            episodes = first_runtime.adaptive.knowledge.episodes
            binding = first_port.latest(first_runtime.ADAPTIVE_KNOWLEDGE_KIND)
            self.assertIsNotNone(binding)
            self.assertTrue(
                first_port.fabric.verify(binding.binding_id)["passed"]
            )
        finally:
            first_lifecycle.stop()

        second_lifecycle = CompositionRoot(
            custody_root,
            tenant="tenant-euclid-v17",
            hmac_key=key,
        )
        second_lifecycle.start()
        try:
            second_port = second_lifecycle.data_port("euclid")
            second_runtime = EuclidRuntime(
                creator_id="creator-1",
                state_dir=self.root / "local-b",
            )
            second_runtime.bind_adaptive_data_port(second_port)
            second_runtime.compose_adaptive_intelligence()
            self.assertEqual(second_runtime.adaptive.knowledge.episodes, episodes)
            self.assertIsNotNone(
                second_port.latest(second_runtime.ADAPTIVE_KNOWLEDGE_KIND)
            )
            self.assertFalse(
                (self.root / "local-b" / "adaptive_knowledge.json").exists()
            )
        finally:
            second_lifecycle.stop()

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
