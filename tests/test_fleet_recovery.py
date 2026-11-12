# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""P2c blind-check recovery: channel A never sees V; V is drawn after the commitment."""

import unittest

from chronus.fleet.errors import RecoveryError
from chronus.fleet.recovery import (
    ONE_CYCLE,
    BaselineChannel,
    FaultedState,
    Incident,
    RecoveryChannel,
    commitment_of,
)
from chronus.fleet.scheduler import LeaseGroup


def reference(job, tile):
    return f"{job}:{tile}".encode()


def faulted(groups=None):
    groups = groups or (LeaseGroup("job-a", 0, 4), LeaseGroup("job-a", 4, 6))
    return FaultedState("inc-1", "dead-node", "node-lost: heartbeat timeout", tuple(groups), "2026-11-11T00:00:00Z")


class ChannelATests(unittest.TestCase):
    def test_path_is_built_from_the_faulted_state_alone(self):
        channel = RecoveryChannel()
        state = faulted(tuple(LeaseGroup("job-a", 4 * i, 4 * i + 4) for i in range(4)))
        path = channel.construct_recovery_path(state, {"x": 3, "y": 1, "dead-node": 100})
        nodes = [node for _, node in path.assignments]
        self.assertNotIn("dead-node", nodes)
        self.assertEqual(sorted(nodes), ["x", "x", "x", "y"])
        for group, _ in path.assignments:
            self.assertEqual(group.incident, "inc-1")
            self.assertIn("dead-node", group.excluded)
            self.assertEqual(group.attempt, 1)
        self.assertEqual(path, channel.construct_recovery_path(state, {"x": 3, "y": 1}))
        self.assertIn("circuit", path.describe()["kind"])

    def test_no_survivor_and_no_work_are_refused(self):
        channel = RecoveryChannel()
        with self.assertRaises(RecoveryError):
            channel.construct_recovery_path(faulted(), {"dead-node": 5})
        with self.assertRaises(RecoveryError):
            channel.construct_recovery_path(FaultedState("i", "n", "c", (), "t"), {"x": 1})

    def test_channel_a_holds_nothing_of_channel_b(self):
        channel = RecoveryChannel()
        self.assertEqual(vars(channel), {})
        self.assertFalse(any(isinstance(v, BaselineChannel) for v in vars(channel).values()))


class ChannelBTests(unittest.TestCase):
    def recovered(self, corrupt=()):
        out = {}
        for tile in range(6):
            data = reference("job-a", tile)
            out[("job-a", tile)] = ("worker", b"bad" if tile in corrupt else data)
        return out

    def test_honest_recovery_passes(self):
        recovered = self.recovered()
        commitment = RecoveryChannel().commit(recovered)
        result = BaselineChannel(reference, sample_ppm=500_000).evaluate(commitment, recovered)
        self.assertTrue(result.passed)
        self.assertEqual(result.checked, 3)
        self.assertEqual(result.failed, 0)
        self.assertEqual(result.describe()["verification_set_drawn"], "after commitment, by the baseline channel")

    def test_a_wrong_recovered_tile_is_caught_when_v_covers_it(self):
        recovered = self.recovered(corrupt={2})
        commitment = RecoveryChannel().commit(recovered)
        result = BaselineChannel(reference, sample_ppm=1_000_000).evaluate(commitment, recovered)
        self.assertFalse(result.passed)
        self.assertEqual(result.failed_nodes, ("worker",))
        self.assertEqual(result.corrected[("job-a", 2)], reference("job-a", 2))

    def test_outputs_changed_after_commitment_are_refused(self):
        recovered = self.recovered()
        commitment = commitment_of(recovered)
        recovered[("job-a", 0)] = ("worker", b"swapped")
        with self.assertRaises(RecoveryError):
            BaselineChannel(reference).evaluate(commitment, recovered)

    def test_v_is_never_empty_and_is_drawn_afresh(self):
        recovered = self.recovered()
        commitment = commitment_of(recovered)
        channel = BaselineChannel(reference, sample_ppm=1)
        digests = {channel.evaluate(commitment, recovered).verification_set_digest for _ in range(40)}
        self.assertEqual(channel.evaluate(commitment, recovered).checked, 1)
        self.assertGreater(len(digests), 1)

    def test_the_verification_set_is_private_to_channel_b(self):
        channel = BaselineChannel(reference)
        self.assertFalse([name for name in vars(channel) if not name.startswith("_BaselineChannel__")])


class IncidentTests(unittest.TestCase):
    def test_one_cycle_flag(self):
        incident = Incident(faulted(), expected={("job-a", t) for t in range(6)})
        self.assertFalse(incident.complete)
        for tile in range(6):
            incident.recovered[("job-a", tile)] = ("x", reference("job-a", tile))
        self.assertTrue(incident.complete)
        incident.status = "verified"
        self.assertTrue(incident.describe()["one_cycle"])
        incident.round = ONE_CYCLE + 1
        self.assertFalse(incident.describe()["one_cycle"])


if __name__ == "__main__":
    unittest.main()
