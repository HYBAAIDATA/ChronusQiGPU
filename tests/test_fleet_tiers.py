# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Tiers with the option to scale: admission, queue then admit, grants, expiry, downgrade, Scale."""

import contextlib
import dataclasses
import io
import json
import unittest
from pathlib import Path

from chronus.fleet import cli
from chronus.fleet import phase as P
from chronus.fleet.auth import new_token, write_token_file
from chronus.fleet.canonical import deterministic_bytes, utc_now_ns
from chronus.fleet.coordinator import CoordinatorConfig, FleetCoordinator
from chronus.fleet.errors import ScaleGrantRejected
from chronus.fleet.scale import issue_grant, issue_selection, parse_duration, verify_grant, write_document
from chronus.fleet.signing import FleetSigner
from chronus.fleet.workunit import WorkUnit
from tests.fleet_support import state_dir

DAY = 86_400


def mac(label, units=8000):
    return {
        "label": label,
        "resident_units": units,
        "kernels": {"m15_fold": "1"},
        "routes": {"igpu": {"silicon": "cpu", "self_test_passed": True, "verified_kernels": ["m15_fold"]}},
        "backend": {"requested_backend": "auto", "preference": "ours", "detected_backends": ["igpu", "reference"],
                    "executed_backend": "igpu", "fallback_reason": None},
    }


class TierFleet:
    """A coordinator with TLS configured (Tier 2 and above need it), driven through its handler."""

    def __init__(self, tmp, tls=True):
        options = {"tls_cert": "unused-cert.pem", "tls_key": "unused-key.pem"} if tls else {}
        self.state = Path(tmp) / "state"
        self.coordinator = FleetCoordinator(
            CoordinatorConfig(token=new_token(), state_dir=self.state, port=0, **options)
        )

    def join(self, label, units=8000):
        status, body = self.coordinator.handle("POST", "/v1/join", f"join:{label}", mac(label, units))
        assert status == 200, body
        return body

    def grant(self, tier, seconds=30 * DAY, **figure):
        return issue_grant(self.coordinator.signer, self.coordinator.fleet_id, tier, seconds, **figure)

    def selection(self, tier):
        return issue_selection(self.coordinator.signer, self.coordinator.fleet_id, tier)

    def lease(self, node_id):
        return self.coordinator.handle("POST", "/v1/lease", node_id, {"node_id": node_id})[1]


class AdmissionTests(unittest.TestCase):
    def test_four_macs_are_admitted_at_tier_one(self):
        with state_dir() as tmp:
            fleet = TierFleet(tmp)
            for i in range(4):
                self.assertEqual(fleet.join(f"mac-{i}")["state"], "active")
            status = fleet.coordinator.tier_status()
            self.assertEqual(status["current"]["label"], "Tier 1")
            self.assertEqual(status["demand"]["logical_warps"], 1000)
            self.assertTrue(status["within_entitlement"])
            self.assertEqual(status["scale"], "scale available: Tier 2")
            self.assertEqual(fleet.coordinator.scale_events, [])

    def test_a_fifth_mac_waits_then_joins_at_tier_two_after_a_grant(self):
        with state_dir() as tmp:
            fleet = TierFleet(tmp)
            for i in range(4):
                fleet.join(f"mac-{i}")
            fifth = fleet.join("mac-4")
            self.assertEqual(fifth["state"], "waiting")
            self.assertEqual(fifth["scale"], "scale available: Tier 2")
            self.assertEqual(fleet.lease(fifth["node_id"])["state"], "waiting")
            event = fleet.coordinator.scale_events[-1]
            self.assertEqual((event.kind, event.outcome, event.next_tier), ("join", "queued", "Tier 2"))
            self.assertEqual(event.demand["warps"], 1250)
            self.assertEqual(event.entitlement["warps"], 1024)
            self.assertTrue(event.recorded_at)
            status = fleet.coordinator.tier_status()
            self.assertFalse(status["within_entitlement"])
            self.assertEqual(status["demand"]["waiting_machines"], 1)

            grant = fleet.coordinator.install_grant(fleet.grant(2))
            node = fleet.coordinator.nodes[fifth["node_id"]]
            self.assertEqual(node.state, "active")
            self.assertEqual(node.resident_units, 8000)
            self.assertEqual(fleet.coordinator.tier.label, "Tier 2")
            self.assertEqual(fleet.coordinator.tier_status()["demand"]["admitted_logical_warps"], 1250)
            self.assertNotIn("state", fleet.lease(fifth["node_id"]))
            kinds = [json.loads(line)["kind"] for line in fleet.coordinator.ledger.path.read_text().splitlines()]
            self.assertIn("scale", kinds)
            self.assertIn("tier", kinds)
            self.assertTrue(fleet.coordinator.ledger.verify().valid)
            self.assertTrue(grant.valid_at())

    def test_with_a_grant_in_place_the_fifth_mac_is_admitted_on_join(self):
        with state_dir() as tmp:
            fleet = TierFleet(tmp)
            fleet.coordinator.install_grant(fleet.grant(2))
            self.assertEqual(fleet.coordinator.tier.label, "Tier 1")
            for i in range(5):
                self.assertEqual(fleet.join(f"mac-{i}")["state"], "active")
            self.assertEqual(fleet.coordinator.tier.label, "Tier 2")
            event = fleet.coordinator.scale_events[-1]
            self.assertEqual(event.outcome, "admitted")
            self.assertTrue(event.grant_id.startswith("grant-"))

    def test_a_job_queues_then_runs_once_a_grant_covers_it(self):
        with state_dir() as tmp:
            fleet = TierFleet(tmp)
            node = fleet.join("mac-0")
            fleet.coordinator._storage_bytes = lambda: 100 * P.BYTES_PER_TB
            job = fleet.coordinator.submit(WorkUnit("m15_fold", deterministic_bytes("queued", 4096), virtual_units=80))
            self.assertEqual(job.status, "queued")
            self.assertEqual(job.scale, "scale available: Tier 2")
            self.assertIsNone(fleet.lease(node["node_id"])["lease"])
            status, view = fleet.coordinator.handle("GET", f"/v1/jobs/{job.job_id}", "x", {})
            self.assertEqual((status, view["status"]), (200, "queued"))
            fleet.coordinator.install_grant(fleet.grant(2))
            self.assertEqual(job.status, "running")
            self.assertEqual(job.tier_at_admission["label"], "Tier 2")
            self.assertTrue(job.grant_id.startswith("grant-"))
            self.assertIsNotNone(fleet.lease(node["node_id"])["lease"])

    def test_tier_two_without_tls_stays_queued_and_says_why(self):
        with state_dir() as tmp:
            fleet = TierFleet(tmp, tls=False)
            for i in range(4):
                fleet.join(f"mac-{i}")
            fleet.coordinator.install_grant(fleet.grant(2))
            fifth = fleet.join("mac-4")
            self.assertEqual(fifth["state"], "waiting")
            self.assertIn("--tls", fifth["scale"])


class GrantTests(unittest.TestCase):
    def test_grants_from_another_key_altered_or_for_another_fleet_are_rejected(self):
        with state_dir() as tmp, state_dir() as other:
            fleet = TierFleet(tmp)
            stranger = FleetSigner.from_state_dir(other)
            with self.assertRaises(ScaleGrantRejected):
                fleet.coordinator.install_grant(issue_grant(stranger, fleet.coordinator.fleet_id, 2, DAY))
            altered = fleet.grant(2)
            altered["tier"] = 4
            altered["warps"] = 160_000
            with self.assertRaises(ScaleGrantRejected):
                fleet.coordinator.install_grant(altered)
            forged = fleet.grant(2)
            forged["signature"]["value"] = forged["signature"]["value"][:-8] + "00000000"
            with self.assertRaises(ScaleGrantRejected):
                fleet.coordinator.install_grant(forged)
            with self.assertRaises(ScaleGrantRejected):
                fleet.coordinator.install_grant(issue_grant(fleet.coordinator.signer, "fleet-elsewhere", 2, DAY))
            self.assertEqual(fleet.coordinator.grants, {})
            write_document(fleet.state, issue_grant(stranger, fleet.coordinator.fleet_id, 3, DAY))
            fleet.coordinator.run_fabric_tick()
            self.assertEqual(fleet.coordinator.grants, {})
            notes = [json.loads(line) for line in fleet.coordinator.ledger.path.read_text().splitlines()]
            self.assertTrue(any(n["meta"].get("event") == "tier-document-rejected" for n in notes))

    def test_expired_grants_are_refused_and_expiry_moves_the_fleet_down(self):
        with state_dir() as tmp:
            fleet = TierFleet(tmp)
            past = issue_grant(fleet.coordinator.signer, fleet.coordinator.fleet_id, 2, DAY,
                               now_ns=utc_now_ns() - 2 * DAY * 10**9)
            with self.assertRaises(ScaleGrantRejected):
                fleet.coordinator.install_grant(past)
            grant = fleet.coordinator.install_grant(fleet.grant(2))
            joined = [fleet.join(f"mac-{i}") for i in range(5)]
            self.assertEqual(fleet.coordinator.tier.label, "Tier 2")
            fleet.coordinator.grants[grant.grant_id] = dataclasses.replace(grant, expires_at_ns=utc_now_ns() - 1)
            fleet.coordinator.run_fabric_tick()
            self.assertEqual(fleet.coordinator.tier.label, "Tier 1")
            states = [fleet.coordinator.nodes[j["node_id"]].state for j in joined]
            self.assertEqual(states.count("active"), 4)
            self.assertEqual(states.count("waiting"), 1)
            self.assertFalse(fleet.coordinator.tier_status()["grants"][0]["valid"])

    def test_durations_and_tier_names(self):
        self.assertEqual(parse_duration("30d"), 30 * DAY)
        self.assertEqual(parse_duration("12h"), 12 * 3600)
        for bad in ("", "0d", "30", "thirty days", "-1d"):
            with self.assertRaises(ScaleGrantRejected):
                parse_duration(bad)
        with state_dir() as tmp:
            fleet = TierFleet(tmp)
            with self.assertRaises(ScaleGrantRejected):
                fleet.grant(1)
            with self.assertRaises(ScaleGrantRejected):
                fleet.grant(7)


class DowngradeTests(unittest.TestCase):
    def test_downgrade_moves_the_newest_machine_back_to_the_queue_and_retires_the_grant(self):
        with state_dir() as tmp:
            fleet = TierFleet(tmp)
            fleet.coordinator.install_grant(fleet.grant(2))
            joined = [fleet.join(f"mac-{i}") for i in range(5)]
            self.assertEqual(fleet.coordinator.tier.label, "Tier 2")
            fleet.coordinator.select_tier(fleet.selection(1))
            self.assertEqual(fleet.coordinator.tier.label, "Tier 1")
            self.assertEqual(fleet.coordinator.nodes[joined[-1]["node_id"]].state, "waiting")
            self.assertEqual(fleet.coordinator.grants, {})
            self.assertEqual(len(fleet.coordinator.retired_grants), 1)
            fleet.coordinator.run_fabric_tick()
            self.assertEqual(fleet.coordinator.tier.label, "Tier 1")
            self.assertEqual(fleet.coordinator.tier_status()["scale"], "scale available: Tier 2")

    def test_moving_up_needs_a_grant(self):
        with state_dir() as tmp:
            fleet = TierFleet(tmp)
            with self.assertRaises(ScaleGrantRejected) as caught:
                fleet.coordinator.select_tier(fleet.selection(2))
            self.assertIn("scale available: Tier 2", str(caught.exception))
            fleet.coordinator.install_grant(fleet.grant(3))
            self.assertEqual(fleet.coordinator.select_tier(fleet.selection(2)).label, "Tier 2")
            self.assertEqual(fleet.coordinator.select_tier(fleet.selection(3)).label, "Tier 3")


class ScaleTierTests(unittest.TestCase):
    def test_the_scale_tier_takes_an_explicit_contract_figure(self):
        tier = P.scale_tier(500_000, 250_000, "HYBA-CONTRACT-0001")
        self.assertEqual((tier.label, tier.warps, tier.simd_lanes, tier.storage_tb), ("Scale", 500_000, 16_000_000, 250_000))
        self.assertEqual(tier.contract, "HYBA-CONTRACT-0001")
        for warps, storage, contract in ((None, 250_000, "c"), (float("inf"), 250_000, "c"), (500_000, None, "c"),
                                         (100_000, 250_000, "c"), (500_000, 250_000, ""), (True, 250_000, "c")):
            with self.assertRaises(ValueError):
                P.scale_tier(warps, storage, contract)

    def test_a_scale_grant_names_the_figure_and_the_fleet_moves_to_it(self):
        with state_dir() as tmp:
            fleet = TierFleet(tmp)
            with self.assertRaises(ScaleGrantRejected):
                fleet.grant("scale")
            document = fleet.grant("scale", warps=200_000, storage_tb=150_000, contract="HYBA-C-0001")
            grant = verify_grant(document, fleet.coordinator.signer.public_key, fleet.coordinator.fleet_id)
            self.assertEqual((grant.tier.label, grant.warps, grant.storage_tb), ("Scale", 200_000, 150_000))
            fleet.coordinator.install_grant(document)
            tier = fleet.coordinator.select_tier(fleet.selection("scale"))
            self.assertEqual((tier.label, tier.warps, tier.contract), ("Scale", 200_000, "HYBA-C-0001"))
            status = fleet.coordinator.tier_status()
            self.assertEqual(status["next_tier"], "Scale (contract figure)")
            self.assertEqual(status["current"]["kind"], "provisioned entitlement (not a performance claim)")


class TierCliTests(unittest.TestCase):
    def test_grant_set_and_status_from_the_command_line(self):
        with state_dir() as tmp:
            fleet = TierFleet(tmp)
            coordinator = fleet.coordinator
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = cli.main(["tier", "grant", "--tier", "2", "--expires", "30d", "--state-dir", str(fleet.state)])
            self.assertEqual(code, 0, out.getvalue())
            self.assertIn("Tier 2", out.getvalue())
            coordinator.run_fabric_tick()
            self.assertEqual(len(coordinator.grants), 1)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["tier", "set", "--tier", "2", "--state-dir", str(fleet.state)]), 0)
            coordinator.run_fabric_tick()
            self.assertEqual(coordinator.tier.label, "Tier 2")
            printed = io.StringIO()
            with contextlib.redirect_stdout(printed):
                cli._print_tier(coordinator.tier_status())
            self.assertIn("tier: Tier 2", printed.getvalue())
            self.assertIn("entitlement: 10,000 logical warps", printed.getvalue())
            self.assertIn("scale available: Tier 3", printed.getvalue())

    def test_tier_status_over_the_wire(self):
        with state_dir() as tmp:
            fleet = TierFleet(tmp, tls=False)
            coordinator = fleet.coordinator.start()
            try:
                fleet.join("mac-0")
                token_file = write_token_file(Path(tmp) / "token", coordinator.config.token)
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    code = cli.main(["tier", "status", "--coordinator", coordinator.url, "--token-file", str(token_file)])
                self.assertEqual(code, 0)
                self.assertIn("tier: Tier 1", out.getvalue())
                self.assertIn("demand: 250 logical warps", out.getvalue())
                self.assertIn("scale available: Tier 2", out.getvalue())
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    cli.main(["tier", "status", "--coordinator", coordinator.url, "--token-file", str(token_file), "--json"])
                self.assertEqual(json.loads(out.getvalue())["current"]["label"], "Tier 1")
            finally:
                coordinator.stop()


if __name__ == "__main__":
    unittest.main()
