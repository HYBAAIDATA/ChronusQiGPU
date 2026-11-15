# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Scheduling lattice rungs and tier entitlements: provisioning, never performance claims."""

import json
import unittest
from fractions import Fraction
from pathlib import Path

from chronus.fleet import phase as P
from chronus.fleet.auth import new_token
from chronus.fleet.canonical import deterministic_bytes
from chronus.fleet.coordinator import CoordinatorConfig, FleetCoordinator
from chronus.fleet.errors import FleetError, LatticeError, TierGateRejected
from chronus.fleet.lattice import LATTICE_LABEL, RESIDENT_RUNGS, SchedulingLattice, resident_config
from chronus.fleet.scheduler import pool_budgets
from chronus.fleet.workunit import WorkUnit
from tests.fleet_support import state_dir


class LatticeTests(unittest.TestCase):
    def test_only_the_three_resident_rungs(self):
        self.assertEqual(RESIDENT_RUNGS, (80, 800, 8000))
        for rung in RESIDENT_RUNGS:
            self.assertEqual(resident_config(rung).virtual_units, rung)
        for bad in (0, 79, 81, 1000, 8001, 65536, True, "8000"):
            with self.assertRaises(LatticeError):
                SchedulingLattice(bad)

    def test_tiles_cover_every_item_exactly_once(self):
        for rung in RESIDENT_RUNGS:
            lattice = SchedulingLattice(rung)
            for items in (1, 31, 32, 33, 1000, 255_999, 10**6):
                tiles = lattice.plan(items)
                self.assertLessEqual(len(tiles), rung)
                self.assertEqual(sum(t.items for t in tiles), items)
                self.assertEqual([t.index for t in tiles], list(range(len(tiles))))
                if items >= 32:
                    self.assertGreaterEqual(min(t.items for t in tiles), 32)

    def test_the_lattice_is_labelled_logical(self):
        description = SchedulingLattice(8000).describe()
        self.assertEqual(description["label"], LATTICE_LABEL)
        self.assertIn("not physical cores", description["label"])
        self.assertEqual(description["physical_cores_claimed"], 0)
        self.assertEqual((description["logical_warps"], description["logical_lanes"]), (250, 8000))


class TierConstantTests(unittest.TestCase):
    def test_tier_entitlements(self):
        self.assertEqual([t.warps for t in P.TIERS], [1024, 10_000, 40_000, 160_000])
        self.assertEqual([t.storage_tb for t in P.TIERS], [100, 1000, 10_000, 100_000])
        self.assertEqual([t.label for t in P.TIERS], ["Tier 1", "Tier 2", "Tier 3", "Tier 4"])
        for tier in P.TIERS:
            self.assertEqual(tier.simd_lanes, tier.warps * P.WARP_LANES)
            self.assertEqual(tier.to_dict()["kind"], "provisioned entitlement (not a performance claim)")
        self.assertEqual(P.scale_available_message(P.TIER_1), "scale available: Tier 2")
        self.assertEqual(P.scale_available_message(P.TIER_4), "scale available: Scale (contract figure)")

    def test_footprint_of_the_rungs(self):
        self.assertEqual(P.lattice_footprint(80), (3, 80))
        self.assertEqual(P.lattice_footprint(800), (25, 800))
        self.assertEqual(P.lattice_footprint(8000), (250, 8000))


class EntitlementTests(unittest.TestCase):
    connectors = {P.CONNECTOR_FLEET_HTTP}

    def test_within_the_entitlement(self):
        self.assertTrue(P.TIER_GATE(P.TIER_1, 1024, 32_768, 100, self.connectors))
        self.assertIs(P.PHASE_GATE, P.TIER_GATE)

    def test_each_dimension_is_reported_on_its_own(self):
        cases = [
            (1025, 32_768, 100, "active_warps"),
            (1024, 32_769, 100, "simd_lanes"),
            (1024, 32_768, Fraction(100_000_000_000_001, 10**12), "storage"),
        ]
        for warps, lanes, storage, word in cases:
            check = P.evaluate_entitlement(P.TIER_1, warps, lanes, storage, self.connectors)
            self.assertFalse(check.within_entitlement)
            self.assertTrue(any(word in f and "entitlement" in f for f in check.over_entitlement), check.over_entitlement)
        check = P.evaluate_entitlement(P.TIER_1, 1, 32, 0, set())
        self.assertEqual(check.missing_connectors, (P.CONNECTOR_FLEET_HTTP,))

    def test_tier_two_needs_tls(self):
        self.assertFalse(P.TIER_GATE(P.TIER_2, 1, 32, 0, {P.CONNECTOR_FLEET_HTTP}))
        self.assertTrue(P.TIER_GATE(P.TIER_2, 1, 32, 0, {P.CONNECTOR_FLEET_HTTP, P.CONNECTOR_FLEET_TLS}))
        with self.assertRaises(TierGateRejected):
            P.require_connectors(P.TIER_2, {P.CONNECTOR_FLEET_HTTP}, "test")

    def test_pool_ratios(self):
        self.assertEqual(pool_budgets(32_768), {"prefill": 8192, "decode": 24_576})
        with self.assertRaises(TierGateRejected):
            pool_budgets(32_768, Fraction(1, 2), Fraction(2, 3))


def join_payload(label, units=8000):
    return {
        "label": label,
        "resident_units": units,
        "kernels": {"m15_fold": "1"},
        "routes": {"reference": {"silicon": "cpu", "self_test_passed": True, "verified_kernels": ["m15_fold"]}},
    }


class CoordinatorTierTests(unittest.TestCase):
    def coordinator(self, tmp, **options):
        return FleetCoordinator(CoordinatorConfig(token=new_token(), state_dir=Path(tmp) / "state", port=0, **options))

    def test_lease_groups_never_exceed_their_pool(self):
        with state_dir() as tmp:
            coordinator = self.coordinator(tmp)
            status, body = coordinator.handle("POST", "/v1/join", "join:a", join_payload("a", 80))
            self.assertEqual(status, 200, body)
            coordinator.scheduler.pool_lanes = pool_budgets(3 * P.WARP_LANES)
            budget = coordinator.scheduler.pool_lanes["prefill"]
            self.assertEqual(budget, 24)
            job = coordinator.submit(WorkUnit("m15_fold", deterministic_bytes("pool", 51_200), virtual_units=800, pool="prefill"))
            sizes = [g.size for queue in coordinator.scheduler.queues.values() for g in queue]
            self.assertEqual(sum(sizes), len(job.tiles))
            self.assertLessEqual(max(sizes), budget)

    def test_a_pool_without_lanes_is_refused(self):
        with state_dir() as tmp:
            coordinator = self.coordinator(tmp, prefill_ratio=Fraction(0))
            coordinator.handle("POST", "/v1/join", "join:a", join_payload("a"))
            with self.assertRaises(TierGateRejected):
                coordinator.submit(WorkUnit("m15_fold", b"\x01\x02" * 64, pool="prefill"))

    def test_starting_above_tier_one_without_a_grant_starts_at_tier_one(self):
        with state_dir() as tmp:
            coordinator = self.coordinator(tmp, tier=2, tls_cert="unused.pem", tls_key="unused.pem")
            self.assertEqual(coordinator.tier.label, "Tier 1")
            self.assertEqual(coordinator.tier_status()["scale"], "scale available: Tier 2")

    def test_explicit_route_with_no_node_fails_closed(self):
        with state_dir() as tmp:
            coordinator = self.coordinator(tmp)
            coordinator.handle("POST", "/v1/join", "join:a", join_payload("a"))
            with self.assertRaises(FleetError) as caught:
                coordinator.submit(WorkUnit("m15_fold", deterministic_bytes("metal", 64), route="metal"))
            self.assertIn("failing closed", str(caught.exception))

    def test_fabric_tick_snapshots_the_tier(self):
        with state_dir() as tmp:
            coordinator = self.coordinator(tmp)
            coordinator.handle("POST", "/v1/join", "join:a", join_payload("a"))
            self.assertTrue(coordinator.run_fabric_tick().within_entitlement)
            entries = [json.loads(line) for line in coordinator.ledger.path.read_text().splitlines()]
            snapshots = [e for e in entries if e["kind"] == "fabric_snapshot"]
            self.assertTrue(snapshots)
            self.assertEqual(snapshots[-1]["meta"]["tier"], "TIER_1")


if __name__ == "__main__":
    unittest.main()
