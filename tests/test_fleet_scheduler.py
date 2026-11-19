# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""HERMES-style lease scheduling: weighted apportionment, expiry, stealing, pools; secret sampling."""

import threading
import unittest

from chronus.fleet import kernels as K
from chronus.fleet.canonical import deterministic_bytes, sha256_hex
from chronus.fleet.crossbar import H4Crossbar
from chronus.fleet.scheduler import LeaseScheduler, apportion, split_groups
from chronus.fleet.verification import ReferenceVerifier, SamplingPolicy, VerificationTask
import pytest

pytestmark = pytest.mark.real

SECOND = 1_000_000_000


def scheduler(nodes, prefill=1000, decode=1000):
    crossbar = H4Crossbar()
    for node in nodes:
        crossbar.place(node)
    sched = LeaseScheduler(crossbar, 5 * SECOND, 60 * SECOND, {"prefill": prefill, "decode": decode})
    for node in nodes:
        sched.add_node(node)
    return sched


def always(group):
    return True


class ApportionTests(unittest.TestCase):
    def test_largest_remainder_is_proportional_and_complete(self):
        shares = apportion({"mac": 300, "imac": 100, "server": 100}, 10)
        self.assertEqual(sum(shares.values()), 10)
        self.assertEqual(shares, {"mac": 6, "imac": 2, "server": 2})
        self.assertEqual(apportion({"a": 1, "b": 1}, 0), {"a": 0, "b": 0})

    def test_split_groups_is_contiguous_and_complete(self):
        groups = split_groups("job", 103, 10, "decode")
        self.assertEqual(groups[0].first_tile, 0)
        self.assertEqual(groups[-1].stop_tile, 103)
        self.assertTrue(all(a.stop_tile == b.first_tile for a, b in zip(groups, groups[1:])))
        self.assertEqual(len(split_groups("job", 3, 10, "decode")), 3)


class LeaseTests(unittest.TestCase):
    def test_measured_capability_decides_the_deal(self):
        sched = scheduler(["fast", "slow"])
        dealt = sched.plan("job", 800, "decode", {"fast": 3_000_000, "slow": 1_000_000})
        tiles = {node: sum(g.size for g in groups) for node, groups in dealt.items()}
        self.assertEqual(sum(tiles.values()), 800)
        self.assertEqual(len(dealt["fast"]), 3 * len(dealt["slow"]))

    def test_own_queue_then_steal_nearest_tail(self):
        sched = scheduler(["a", "b", "c"])
        sched.plan("job", 120, "decode", {"a": 1, "b": 1})
        head = sched.queues["a"][0]
        lease, source = sched.acquire("a", always, 0)
        self.assertEqual(source, "own-queue")
        self.assertIs(lease.group, head)
        stolen, source = sched.acquire("c", always, 0)
        self.assertTrue(source.startswith("stolen-from:"))
        victim = source.split(":", 1)[1]
        others = {n: sched.crossbar.vertex_of(n) for n in ("a", "b")}
        self.assertEqual(victim, sched.crossbar.steal_order("c", others)[0])
        tails = [g.stop_tile for g in sched.queues[victim]]
        self.assertTrue(all(stolen.group.first_tile >= t for t in tails))

    def test_leases_expire_unless_renewed_and_never_beyond_the_hard_limit(self):
        sched = scheduler(["a"])
        sched.plan("job", 64, "decode", {"a": 1})
        lease, _ = sched.acquire("a", always, 0)
        self.assertEqual(sched.renew("a", [lease.lease_id], 4 * SECOND), 1)
        self.assertEqual(sched.expired(6 * SECOND), [])
        self.assertEqual(sched.renew("b", [lease.lease_id], 8 * SECOND), 0)
        self.assertEqual([x.lease_id for x in sched.expired(10 * SECOND)], [lease.lease_id])
        lease2, _ = sched.acquire("a", always, 0)
        for t in range(1, 70):
            sched.renew("a", [lease2.lease_id], t * SECOND)
        self.assertEqual(lease2.expires_ns, 60 * SECOND)

    def test_pool_budget_holds_back_leases(self):
        sched = scheduler(["a"], prefill=10, decode=1000)
        sched.plan("job", 40, "prefill", {"a": 1})
        first, _ = sched.acquire("a", always, 0)
        self.assertEqual(first.group.size, 10)
        self.assertIsNone(sched.acquire("a", always, 0))
        sched.release(first.lease_id)
        self.assertIsNotNone(sched.acquire("a", always, 0))

    def test_unusable_groups_are_skipped_and_dropped_nodes_hand_back_work(self):
        sched = scheduler(["a", "b"])
        sched.plan("job", 64, "decode", {"a": 1})
        self.assertIsNone(sched.acquire("b", lambda g: False, 0))
        handed = sched.drop_node("a")
        self.assertTrue(handed)
        _, source = sched.acquire("b", always, 0)
        self.assertEqual(source, "unassigned")


class EligibilityTests(unittest.TestCase):
    def node(self, **changes):
        from chronus.fleet.scheduler import NodeInfo

        fields = dict(
            node_id="n", label="n", owner="hyba", resident_units=8000, warps=250, lanes=8000,
            routes={"simd": {"verified_kernels": ["m15_fold"]}}, kernels={"m15_fold": "1"},
            vertex=0, joined_at="t", last_seen_ns=0,
        )
        fields.update(changes)
        return NodeInfo(**fields)

    def test_stale_versions_routes_and_states_are_not_eligible(self):
        self.assertTrue(self.node().eligible("m15_fold", "1", "auto"))
        self.assertTrue(self.node().eligible("m15_fold", "1", "simd"))
        self.assertFalse(self.node(kernels={"m15_fold": "2"}).eligible("m15_fold", "1", "auto"))
        self.assertFalse(self.node().eligible("m15_fold", "1", "metal"))
        self.assertFalse(self.node(alive=False).eligible("m15_fold", "1", "auto"))
        self.assertFalse(self.node(quarantined="wrong answer").eligible("m15_fold", "1", "auto"))
        self.assertFalse(self.node().eligible("m15_fold", "1", "auto", excluded=["n"]))

    def test_unmeasured_nodes_weigh_one_and_say_so(self):
        self.assertEqual(self.node().weight("m15_fold", "auto"), (1, False))
        measured = self.node(throughput={("m15_fold", "simd"): 5_000_000})
        self.assertEqual(measured.weight("m15_fold", "auto"), (5_000_000, True))


class SamplingTests(unittest.TestCase):
    def test_sampling_is_secret_dependent_and_close_to_its_rate(self):
        one, two = SamplingPolicy(125_000, b"1" * 32), SamplingPolicy(125_000, b"2" * 32)
        picks_one = [one.sampled("job", t) for t in range(8000)]
        picks_two = [two.sampled("job", t) for t in range(8000)]
        self.assertNotEqual(picks_one, picks_two)
        self.assertTrue(800 < sum(picks_one) < 1200)
        self.assertTrue(all(SamplingPolicy(1_000_000).sampled("j", t) for t in range(50)))
        self.assertFalse(any(SamplingPolicy(0).sampled("j", t) for t in range(50)))
        with self.assertRaises(ValueError):
            SamplingPolicy(1_000_001)


class ReferenceVerifierTests(unittest.TestCase):
    def test_matches_and_mismatches_are_reported(self):
        kernel = K.M15FoldKernel()
        tile = deterministic_bytes("verify", 256)
        good = sha256_hex(kernel.run_reference(None, {}, tile, 0, 128))
        outcomes, done = [], threading.Event()

        def collect(outcome):
            outcomes.append(outcome)
            if len(outcomes) == 2:
                done.set()

        verifier = ReferenceVerifier(collect, threads=2)
        try:
            for claimed in (good, "0" * 64):
                verifier.submit(VerificationTask("job", 0, "n", kernel, {}, tile, 0, 128, claimed, "sampled"))
            self.assertTrue(done.wait(10))
        finally:
            verifier.stop()
        self.assertEqual(sorted(o.match for o in outcomes), [False, True])
        self.assertTrue(all(o.reference_sha256 == good for o in outcomes))


if __name__ == "__main__":
    unittest.main()
