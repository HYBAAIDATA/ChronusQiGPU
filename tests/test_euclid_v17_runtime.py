"""EUCLID v17 adaptive intelligence inside the governed EuclidRuntime."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aethel.enterprise.custody import EnterpriseCustody

from euclid.cognition.baselines import DelegatorExecutor
from euclid.cognition.reachability import ReachabilityStage
from euclid.cognition.worlds import MechanismWorld, WorldExecutor, generate_task
from euclid.runtime import EuclidRuntime

CUSTODY_KEY = b"v17-runtime-custody-key-32b!"


class AdaptiveRuntime(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.custody = EnterpriseCustody(self.root / "custody", hmac_key=CUSTODY_KEY)

    def tearDown(self) -> None:
        self.custody.close()
        self._tmp.cleanup()

    def _runtime(self) -> EuclidRuntime:
        return EuclidRuntime(creator_id="creator-1", state_dir=self.root)

    def test_tasks_execute_only_through_governed_delegation(self) -> None:
        runtime = self._runtime()
        runtime.compose_adaptive_intelligence(custody=self.custody)
        spec, truth = generate_task("program-transformation", seed=12, partition="evaluation")
        world = MechanismWorld(spec, truth, seed=1)
        result = runtime.solve_task(spec, WorldExecutor(world), seed=1)
        delegated = [r for r in runtime.evidence.records if r.kind == "delegation-result"]
        self.assertEqual(len(delegated), len(world.ledger))
        self.assertEqual(result.solved, world.solved)
        self.assertFalse(runtime.rights.permits("creator-1", "task-world-1",
                                                "task-world-1.execute", "dispatch"))
        with self.assertRaises(PermissionError):
            DelegatorExecutor(runtime.delegator, "task-world-1", "task-world-1.execute").execute(
                "probe", {"kind": "intervention", "program": [spec.operators[0]]})
        cognition = [r for r in runtime.evidence.records if r.kind.startswith("cognition-")]
        self.assertTrue(any(r.kind == "cognition-consolidate" for r in cognition))

    def test_knowledge_persists_and_restart_is_verified(self) -> None:
        runtime = self._runtime()
        runtime.compose_adaptive_intelligence(custody=self.custody)
        for seed in (3, 4):
            spec, truth = generate_task("symbolic-rewriting", seed=seed, partition="train")
            runtime.solve_task(spec, WorldExecutor(MechanismWorld(spec, truth)), seed=seed)
        episodes = runtime.adaptive.knowledge.episodes
        memories = sorted(runtime.adaptive.knowledge.memory.items)
        # F5: canonical custody owns the durable adaptive state — no private file.
        self.assertFalse((self.root / "adaptive_knowledge.json").exists())
        body = json.loads(
            self.custody.get("euclid-adaptive-knowledge-creator-1").decode("utf-8")
        )
        self.assertEqual(body["schema"], "euclid.adaptive-knowledge/1")
        self.assertEqual(body["creator_id"], "creator-1")
        persisted = [
            r for r in runtime.evidence.records if r.kind == "adaptive-knowledge-persisted"
        ]
        self.assertTrue(persisted)
        component = EuclidRuntime.ADAPTIVE_COMPONENTS[0]
        self.assertEqual(runtime.reachability.stage(component), ReachabilityStage.PERSISTED)

        restarted = self._runtime()
        restarted.compose_adaptive_intelligence(custody=self.custody)
        self.assertEqual(restarted.adaptive.knowledge.episodes, episodes)
        self.assertEqual(sorted(restarted.adaptive.knowledge.memory.items), memories)
        self.assertEqual(restarted.reachability.stage(component),
                         ReachabilityStage.RESTART_VERIFIED)

    def test_uncomposed_runtime_refuses_tasks(self) -> None:
        runtime = self._runtime()
        spec, truth = generate_task("causal-circuit", seed=2, partition="evaluation")
        with self.assertRaises(RuntimeError):
            runtime.solve_task(spec, WorldExecutor(MechanismWorld(spec, truth)))


if __name__ == "__main__":
    unittest.main()
