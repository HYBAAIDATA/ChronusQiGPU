from __future__ import annotations

import unittest

from euclid.kairos_control_plane import (
    FoldEvent,
    FoldOutcome,
    KairosRuntime,
    RuntimeBoundary,
    RuntimeRole,
    WorldLifecycle,
)


class KairosRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = KairosRuntime()
        self.world = self.runtime.create_world("kairos-lab", "sha256:" + "a" * 64)
        self.runtime.bootstrap_world(self.world.world_id)
        self.session = self.runtime.activate_session(self.runtime.open_session("andre").session_id)

    def fold(self, **changes):
        base = {
            "domain_from": "frontier_city",
            "domain_to": "symbolic_orchard",
            "intent": "build",
            "payload": {"structure": "bridge"},
            "constraints": {},
            "provenance": {"intent_hash": "sha256:" + "b" * 64},
        }
        base.update(changes)
        return FoldEvent(**base)

    def test_lifecycle_and_single_operator_session_are_governed(self):
        self.assertEqual(self.world.lifecycle, WorldLifecycle.ACTIVE)
        with self.assertRaises(PermissionError):
            self.runtime.open_session("other")
        with self.assertRaises(PermissionError):
            self.runtime.open_session("creator", RuntimeRole.CREATOR)

    def test_accepted_fold_updates_state_and_chronicle(self):
        before = self.world.state_hash
        result = self.runtime.dispatch_fold(self.world.world_id, self.session.session_id, self.fold())
        self.assertEqual(result.outcome, FoldOutcome.ACCEPTED)
        self.assertNotEqual(before, result.world_hash)
        self.assertEqual(self.world.state["domains"]["symbolic_orchard"]["resonance_from"], "frontier_city")
        self.assertGreater(self.world.state["volatility"], 0)
        self.assertEqual(self.world.chronicle[-1].kind, "fold")

    def test_forbidden_and_self_transition_reject_without_mutation(self):
        before = self.world.state_hash
        forbidden = self.runtime.dispatch_fold(self.world.world_id, self.session.session_id, self.fold(intent="erase_history"))
        self.assertEqual(forbidden.outcome, FoldOutcome.REJECTED)
        self.assertEqual(before, forbidden.world_hash)
        self.assertEqual(self.world.lifecycle, WorldLifecycle.ACTIVE)
        self_transition = self.runtime.dispatch_fold(self.world.world_id, self.session.session_id, self.fold(domain_to="frontier_city"))
        self.assertEqual(self_transition.outcome, FoldOutcome.REJECTED)
        self.assertEqual(before, self_transition.world_hash)

    def test_deferred_fold_has_no_state_mutation(self):
        before = self.world.state_hash
        result = self.runtime.dispatch_fold(self.world.world_id, self.session.session_id, self.fold(constraints={"defer": True}))
        self.assertEqual(result.outcome, FoldOutcome.DEFERRED)
        self.assertEqual(before, result.world_hash)
        self.assertEqual(self.world.chronicle[-1].kind, "fold_deferred")

    def test_checkpoint_restore_and_replay_are_hash_linked(self):
        accepted = self.runtime.dispatch_fold(self.world.world_id, self.session.session_id, self.fold())
        checkpoint = self.runtime.checkpoint_world(self.world.world_id)
        self.runtime.dispatch_fold(self.world.world_id, self.session.session_id, self.fold(domain_from="symbolic_orchard", domain_to="geometric_plane", intent="cultivate"))
        self.runtime.restore_world(self.world.world_id, checkpoint)
        self.assertEqual(self.world.state_hash, accepted.world_hash)
        replay = self.runtime.replay_world(self.world.world_id)
        self.assertEqual(replay["world_hash"], accepted.world_hash)
        self.assertTrue(all(value.startswith("sha256:") for value in replay["event_hashes"]))

    def test_load_and_cns_snapshot_preserve_hash_linked_record(self):
        self.runtime.dispatch_fold(self.world.world_id, self.session.session_id, self.fold())
        snapshot = self.runtime.record_cns_snapshot(self.world.world_id, phase="COHERENT", mood="CURIOUS", risk=0.1, volatility=0.05)
        loaded = self.runtime.load_world(self.world.world_id)
        self.assertEqual(loaded.world_id, self.world.world_id)
        self.assertEqual(snapshot.kind, "cns_snapshot")
        self.assertEqual(self.world.chronicle[-1].event_hash, snapshot.event_hash)

    def test_declared_invariant_violation_rejects_without_mutation(self):
        before = self.world.state_hash
        result = self.runtime.dispatch_fold(self.world.world_id, self.session.session_id, self.fold(constraints={"invariant_violations": ["history_retained"]}))
        self.assertEqual(result.outcome, FoldOutcome.REJECTED)
        self.assertEqual(result.world_hash, before)

    def test_invalid_lifecycle_transition_fails_closed_and_is_chronicled(self):
        self.runtime.archive_world(self.world.world_id)
        with self.assertRaises(RuntimeError):
            self.runtime.checkpoint_world(self.world.world_id)
        self.assertEqual(self.world.lifecycle, WorldLifecycle.FAILED_CLOSED)
        self.assertEqual(self.world.chronicle[-1].kind, "failed_closed")

    def test_boundary_cannot_be_opened_without_future_evidence_gate(self):
        with self.assertRaises(ValueError):
            RuntimeBoundary(network_enabled=True)
        with self.assertRaises(ValueError):
            RuntimeBoundary(multi_user_enabled=True)


if __name__ == "__main__":
    unittest.main()
