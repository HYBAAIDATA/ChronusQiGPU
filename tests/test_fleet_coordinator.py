# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Coordinator protocol rules: no silicon mislabelling, no route relabelling, late results compared."""

import unittest
from pathlib import Path

from chronus.fleet.auth import new_token
from chronus.fleet.canonical import b64decode, b64encode, deterministic_bytes, iso_utc, sha256_hex
from chronus.fleet.coordinator import CoordinatorConfig, FleetCoordinator
from chronus.fleet.kernels import M15FoldKernel
from chronus.fleet.receipts import verify_receipt
from chronus.fleet.workunit import WorkUnit
from tests.fleet_support import state_dir


def join(coordinator, label, routes):
    payload = {
        "label": label,
        "resident_units": 800,
        "kernels": {"m15_fold": "1"},
        "routes": {
            route: {"silicon": silicon, "self_test_passed": True, "verified_kernels": ["m15_fold"]}
            for route, silicon in routes.items()
        },
    }
    return coordinator.handle("POST", "/v1/join", f"join:{label}", payload)


def answer(lease, node_id, **overrides):
    """Honest results for a lease, with record fields optionally overridden."""
    kernel = M15FoldKernel()
    tiles = []
    for tile in lease["tiles"]:
        output = kernel.run_reference(None, {}, b64decode(tile["input_b64"]), tile["start"], tile["stop"])
        record = {
            "requested_route": lease["route"], "executed_route": "reference", "fallback_reason": None,
            "adapter": "pure-python-reference", "silicon": "cpu", "mode": "A", "kernel": "m15_fold",
            "kernel_version": "1", "tile_index": tile["index"], "items": tile["stop"] - tile["start"],
            "bytes_in": len(tile["input_b64"]), "bytes_out": len(output), "output_sha256": sha256_hex(output),
            "started_at": iso_utc(), "finished_at": iso_utc(), "duration_ns": 1000, "measured": True,
            "requested_backend": lease["route"], "detected_backends": ["reference"], "preference": "ours",
            "executed_backend": "reference",
        }
        record.update(overrides)
        tiles.append({"index": tile["index"], "output_b64": b64encode(output), "output_sha256": sha256_hex(output),
                      "record": record})
    return {"node_id": node_id, "lease_id": lease["lease_id"], "job_id": lease["job_id"], "tiles": tiles, "failure": None}


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = state_dir()
        self.coordinator = FleetCoordinator(
            CoordinatorConfig(token=new_token(), state_dir=Path(self.tmp.name), port=0, sample_rate_ppm=0)
        )

    def tearDown(self):
        self.tmp.cleanup()

    def lease_for(self, node_id):
        status, body = self.coordinator.handle("POST", "/v1/lease", node_id, {"node_id": node_id})
        self.assertEqual(status, 200, body)
        return body["lease"]

    def test_join_with_mislabelled_silicon_is_refused(self):
        status, body = join(self.coordinator, "liar", {"reference": "gpu"})
        self.assertEqual(status, 400)
        self.assertIn("silicon", body["error"])

    def test_a_record_claiming_gpu_for_cpu_work_quarantines_the_node(self):
        _, first = join(self.coordinator, "a", {"reference": "cpu"})
        _, second = join(self.coordinator, "b", {"reference": "cpu"})
        job = self.coordinator.submit(WorkUnit("m15_fold", deterministic_bytes("silicon", 4096), virtual_units=80))
        lease = self.lease_for(first["node_id"])
        status, body = self.coordinator.handle(
            "POST", "/v1/result", first["node_id"], answer(lease, first["node_id"], silicon="gpu", mode="B")
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["accepted"], 0)
        self.assertTrue(self.coordinator.nodes[first["node_id"]].quarantined)
        self.assertTrue(job.incidents)
        self.assertTrue(all(r["reason"].startswith("record names the wrong silicon") for r in job.rejected))
        self.assertIsNone(self.lease_for(first["node_id"]))
        self.assertIsNotNone(self.lease_for(second["node_id"]))

    def test_explicit_route_relabelling_quarantines_the_node(self):
        _, node = join(self.coordinator, "a", {"simd": "cpu", "reference": "cpu"})
        self.coordinator.submit(WorkUnit("m15_fold", deterministic_bytes("relabel", 4096), route="simd", virtual_units=80))
        lease = self.lease_for(node["node_id"])
        _, body = self.coordinator.handle(
            "POST", "/v1/result", node["node_id"], answer(lease, node["node_id"], requested_route="simd")
        )
        self.assertEqual(body["accepted"], 0)
        self.assertIn("relabelling refused", body["rejected"][0]["reason"])
        self.assertTrue(self.coordinator.nodes[node["node_id"]].quarantined)

    def test_a_record_naming_another_backend_quarantines_the_node(self):
        _, node = join(self.coordinator, "a", {"reference": "cpu"})
        self.coordinator.submit(WorkUnit("m15_fold", deterministic_bytes("backend", 4096), virtual_units=80))
        lease = self.lease_for(node["node_id"])
        _, body = self.coordinator.handle(
            "POST", "/v1/result", node["node_id"], answer(lease, node["node_id"], executed_backend="metal")
        )
        self.assertEqual(body["accepted"], 0)
        self.assertIn("relabelling refused", body["rejected"][0]["reason"])
        self.assertTrue(self.coordinator.nodes[node["node_id"]].quarantined)

    def test_honest_results_complete_the_job_with_a_signed_receipt(self):
        self.coordinator.start()
        try:
            _, node = join(self.coordinator, "a", {"reference": "cpu"})
            unit = WorkUnit("m15_fold", deterministic_bytes("honest", 4096), virtual_units=80)
            job = self.coordinator.submit(unit)
            for _ in range(100):
                lease = self.lease_for(node["node_id"])
                if lease is None:
                    break
                status, body = self.coordinator.handle("POST", "/v1/result", node["node_id"], answer(lease, node["node_id"]))
                self.assertEqual(status, 200, body)
            self.assertTrue(job.done.wait(30), job.progress())
            self.assertEqual(job.status, "completed", job.error)
            self.assertEqual(job.output, M15FoldKernel().reference_output({}, unit.payload))
            self.assertGreaterEqual(job.receipt["verification"]["summary"]["checks_by_reason"]["min-per-device"], 1)
            check = verify_receipt(job.receipt, public_key=self.coordinator.signer.public_key, output=job.output,
                                   ledger_path=self.coordinator.ledger.path)
            self.assertTrue(check.valid, check.reasons)
            backend = job.receipt["backend"]
            self.assertEqual(backend["requested_backend"], "auto")
            self.assertEqual(backend["executed_backends"], {"reference": len(job.tiles)})
            self.assertEqual(job.receipt["devices"][0]["executed_backends"], {"reference": len(job.tiles)})
            self.assertEqual(job.receipt["devices"][0]["preferences"], ["ours"])
            device = job.receipt["devices"][0]
            verified_items = sum(r.record["items"] for r in job.results.values()
                                 if r.status.startswith(("verified", "recovered-blind")))
            self.assertEqual(device["verified_items"], verified_items)
            self.assertGreater(device["items"], device["verified_items"])

            self.assertEqual(job.receipt["tier"]["entitlement"]["label"], "Tier 1")
            anchor = self.coordinator.ledger.find(job.receipt["receipt_id"])
            self.assertEqual(anchor["meta"]["requested_backend"], "auto")
            self.assertEqual(anchor["meta"]["executed_backends"], {"reference": len(job.tiles)})
        finally:
            self.coordinator.stop()

    def test_unknown_nodes_and_late_results(self):
        status, _ = self.coordinator.handle("POST", "/v1/heartbeat", "ghost", {"node_id": "ghost"})
        self.assertEqual(status, 404)
        status, _ = self.coordinator.handle("POST", "/v1/heartbeat", "a", {"node_id": "b"})
        self.assertEqual(status, 404)
        _, node = join(self.coordinator, "a", {"reference": "cpu"})
        self.coordinator.submit(WorkUnit("m15_fold", deterministic_bytes("late", 4096), virtual_units=80))
        lease = self.lease_for(node["node_id"])
        stale = dict(answer(lease, node["node_id"]), lease_id="0" * 24)
        status, body = self.coordinator.handle("POST", "/v1/result", node["node_id"], stale)
        self.assertEqual(status, 200)
        self.assertTrue(body["late"])
        self.assertEqual(body["accepted"], 0)

    def test_unknown_routes_are_404(self):
        status, _ = self.coordinator.handle("GET", "/v1/nothing", "x", {})
        self.assertEqual(status, 404)
        status, _ = self.coordinator.handle("GET", "/v1/jobs/job-0000000000000000", "x", {})
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
