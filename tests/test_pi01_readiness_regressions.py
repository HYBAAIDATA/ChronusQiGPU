"""Local fail-closed aggregation and relocation contracts, not fleet evidence."""

from copy import deepcopy
import unittest

from Intelligence.chain_verification import mandatory_stages_pass
from euclid.production_harness import checkpoint_state


class ReadinessRegressions(unittest.TestCase):
    def test_missing_or_nonboolean_stage_never_passes(self):
        self.assertTrue(mandatory_stages_pass({"a": {"correct": True}}, ["a"]))
        for value in ({}, {"correct": False}, {"correct": "PASS"}, {"passed": "true"}, None):
            self.assertFalse(mandatory_stages_pass({"a": value}, ["a"]))
        self.assertFalse(mandatory_stages_pass({"a": {"correct": True}}, ["a", "b"]))
        self.assertFalse(mandatory_stages_pass({}, []))

    def test_new_process_identity_is_not_a_durable_state_mutation(self):
        before = {
            "schema": "test",
            "creator_id": "owner",
            "worlds": {"w": {"x": 1}},
            "rights": {"grants": ["read"]},
            "evidence": {"head": "retained"},
            "producer_process": {"token": "old"},
            "seal": "old-seal",
        }
        after = deepcopy(before)
        after.update(producer_process={"token": "new"}, seal="new-seal")
        self.assertEqual(checkpoint_state(before), checkpoint_state(after))
        for field in ("schema", "creator_id", "worlds", "rights", "evidence"):
            changed = deepcopy(after)
            changed[field] = "tampered"
            self.assertNotEqual(checkpoint_state(before), checkpoint_state(changed))
