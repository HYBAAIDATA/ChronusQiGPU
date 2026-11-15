# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""End to end in one process: every kernel, route enforcement, a lying worker, key pinning, CLI."""

import contextlib
import io
import json
import unittest
from pathlib import Path

from chronus.fleet import cli
from chronus.fleet.adapters import AdapterRegistry, ReferenceAdapter, SimdAdapter
from chronus.fleet.auth import write_token_file
from chronus.fleet.canonical import deterministic_bytes, sha256_hex
from chronus.fleet.errors import TransportError, VerificationError
from chronus.fleet.executor import FleetExecutor
from chronus.fleet.kernels import default_registry
from chronus.fleet.worker import FleetWorker, WorkerConfig
from chronus.fleet.workunit import WorkUnit
from tests.fleet_support import state_dir


def units():
    gf_words = [(i * 7919 + 13) % 65521 for i in range(40 * 40 + 40)]
    pv_values = [{"a": str(i - 200), "b": str((i * 37) % 101 - 50), "denominator": str(1 + i % 3)} for i in range(500)]
    return [
        WorkUnit("m15_fold", deterministic_bytes("e2e-fold", 100_000)),
        WorkUnit("m15_unfold", deterministic_bytes("e2e-unfold", 30_002), virtual_units=800),
        WorkUnit("dual_space_query", deterministic_bytes("e2e-dual", 40_000), virtual_units=80),
        WorkUnit("gf_matvec", b"".join(w.to_bytes(4, "little") for w in gf_words), {"p": 65521, "rows": 40, "cols": 40}),
        WorkUnit("pv_lattice_fold", json.dumps(pv_values).encode(), {"order": 33}, virtual_units=800),
    ]


class EmbeddedFleetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = state_dir()
        cls.fleet = FleetExecutor.embedded(
            Path(cls.tmp.name) / "state", local_workers=2, worker_routes=["simd", "reference"],
            sample_rate_ppm=250_000, fabric_tick_ms=200,
        )
        cls.reference = default_registry(plugins=[])

    @classmethod
    def tearDownClass(cls):
        cls.fleet.close()
        cls.tmp.cleanup()

    def test_every_builtin_kernel_is_exact_and_receipted(self):
        for unit in units():
            result = self.fleet.submit(unit, timeout=120)
            expected = self.reference.get(unit.kernel).reference_output(unit.params, unit.payload)
            self.assertEqual(result.output, expected, unit.kernel)
            self.assertTrue(result.verified, result.check.reasons)
            receipt = result.receipt
            self.assertEqual(receipt["work_unit"]["digest"], unit.digest())
            self.assertEqual(receipt["lattice"]["virtual_units"], unit.virtual_units)
            self.assertIn("not physical cores", receipt["lattice"]["label"])
            summary = receipt["verification"]["summary"]
            self.assertGreaterEqual(summary["tiles_checked_against_reference"], len(receipt["devices"]))
            self.assertEqual(summary["mismatches"], 0)
            self.assertEqual(sum(d["tiles"] for d in receipt["devices"]), receipt["lattice"]["tiles"])
            for device in receipt["devices"]:
                self.assertTrue(device["measured"])
                self.assertEqual(device["silicon"], ["cpu"])
                self.assertEqual(device["modes"], ["A"])
                self.assertGreater(device["exec_ns"], 0)
            self.assertTrue(receipt["tier"]["check_at_admission"]["within_entitlement"])
            self.assertEqual(receipt["tier"]["entitlement"]["label"], "Tier 1")
            self.assertEqual(receipt["backend"]["requested_backend"], unit.route)
            self.assertEqual(set(receipt["backend"]["executed_backends"]), set(receipt["routes"]["executed_tiles"]))

    def test_explicit_routes_run_only_there(self):
        for route in ("simd", "reference"):
            result = self.fleet.submit(WorkUnit("m15_fold", deterministic_bytes(route, 20_000), route=route), timeout=120)
            self.assertEqual(set(result.receipt["routes"]["executed_tiles"]), {route})

    def test_absent_route_fails_closed(self):
        for route in ("metal", "opencl", "cpp-simd"):
            with self.assertRaises(TransportError) as caught:
                self.fleet.submit(WorkUnit("m15_fold", b"\x01\x02" * 64, route=route), timeout=30)
            self.assertEqual(caught.exception.status, 409)
            self.assertIn("failing closed", str(caught.exception))

    def test_a_receipt_from_another_key_is_refused(self):
        coordinator = self.fleet.coordinator
        with state_dir() as other:
            from chronus.fleet.signing import FleetSigner

            stranger = FleetSigner.from_state_dir(other)
            pinned = FleetExecutor(coordinator.url, token=coordinator.config.token, public_key=stranger.public_key)
            with self.assertRaises(VerificationError):
                pinned.submit(WorkUnit("m15_fold", b"\x05\x06" * 100), timeout=60)

    def test_status_reports_measured_nodes_and_the_tier(self):
        status = self.fleet.status()
        self.assertTrue(status["entitlement_check"]["within_entitlement"])
        self.assertEqual(status["tier"]["current"]["label"], "Tier 1")
        self.assertEqual(status["tier"]["demand"]["logical_warps"], 500)
        self.assertEqual(status["tier"]["scale"], "scale available: Tier 2")
        self.assertEqual(len([n for n in status["nodes"] if n["alive"]]), 2)
        self.assertEqual(status["composed_lattice"]["logical_lanes"], 16_000)
        self.assertEqual(status["crossbar"]["diameter"], 5)
        self.assertEqual(status["signer"]["algorithm"], "ML-DSA-65")

    def test_cli_status_and_verify_receipt(self):
        coordinator = self.fleet.coordinator
        with state_dir() as tmp:
            token_file = write_token_file(Path(tmp) / "token", coordinator.config.token)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = cli.main(["status", "--coordinator", coordinator.url, "--token-file", str(token_file), "--json"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out.getvalue())["fleet_id"], coordinator.fleet_id)
            result = self.fleet.submit(WorkUnit("m15_fold", b"\x07\x08" * 500), timeout=60)
            receipt_path = Path(tmp) / "receipt.json"
            receipt_path.write_text(json.dumps(result.receipt))
            with contextlib.redirect_stdout(io.StringIO()):
                ok = cli.main(["verify-receipt", str(receipt_path), "--public-key", coordinator.signer.public_key.hex(),
                               "--ledger", str(coordinator.ledger.path)])
            self.assertEqual(ok, 0)
            broken = dict(result.receipt, submitter="someone else")
            receipt_path.write_text(json.dumps(broken))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["verify-receipt", str(receipt_path)]), 1)


class PartitionTests(unittest.TestCase):
    def test_a_partitioned_worker_rejoins_and_work_continues(self):
        with state_dir() as tmp:
            fleet = FleetExecutor.embedded(Path(tmp) / "state", local_workers=1, worker_routes=["simd", "reference"])
            try:
                coordinator = fleet.coordinator
                worker = fleet._embedded.workers[0]
                first_id = worker.node_id
                with coordinator._lock:
                    coordinator._retire(coordinator.nodes[first_id], "lost", "node-lost: simulated partition")
                rejoined = False
                for _ in range(200):
                    if worker.node_id != first_id and worker.node_id in coordinator.nodes:
                        rejoined = True
                        break
                    worker._stop.wait(0.05)
                self.assertTrue(rejoined, "worker did not rejoin after the partition")
                self.assertFalse(coordinator.nodes[first_id].alive)
                result = fleet.submit(WorkUnit("m15_fold", deterministic_bytes("partition", 8000)), timeout=60)
                self.assertEqual({d["node_id"] for d in result.receipt["devices"]}, {worker.node_id})
                self.assertGreaterEqual(worker.stats["rejoins"], 1)
            finally:
                fleet.close()


class LyingSimdAdapter(SimdAdapter):
    """Passes every known answer (they bypass execute) but corrupts real work consistently."""

    def execute(self, kernel, params, tile, start, stop, **kwargs):
        output, record = super().execute(kernel, params, tile, start, stop, **kwargs)
        bad = bytearray(output)
        bad[0] ^= 0x55
        record.output_sha256 = sha256_hex(bytes(bad))
        return bytes(bad), record


class LyingWorkerTests(unittest.TestCase):
    def test_same_hash_verification_catches_and_corrects_a_lying_device(self):
        with state_dir() as tmp:
            fleet = FleetExecutor.embedded(
                Path(tmp) / "state", local_workers=2, worker_routes=["simd", "reference"], sample_rate_ppm=200_000
            )
            liar = FleetWorker(
                WorkerConfig(fleet.coordinator.url, fleet.coordinator.config.token, label="liar", measure=False),
                adapters=AdapterRegistry(adapters=[LyingSimdAdapter()]),
            )
            try:
                liar.start_thread()
                self.assertTrue(liar.wait_joined(60))
                unit = WorkUnit("m15_fold", deterministic_bytes("liar", 400_000), route="simd")
                result = fleet.submit(unit, timeout=180)
                expected = default_registry(plugins=[]).get("m15_fold").reference_output({}, unit.payload)
                self.assertEqual(result.output, expected)
                self.assertTrue(result.verified)
                summary = result.receipt["verification"]["summary"]
                self.assertGreaterEqual(summary["mismatches"], 1)
                self.assertGreaterEqual(summary["tile_status"].get("reference-corrected", 0), 1)
                liars = [n for n in fleet.status()["nodes"] if n["label"] == "liar"]
                self.assertTrue(liars[0]["quarantined"])
                self.assertTrue(all(m["node_id"] == liar.node_id for m in result.receipt["verification"]["mismatches"]))
            finally:
                liar.stop(leave=False)
                fleet.close()


class BenchAndInitTests(unittest.TestCase):
    def test_bench_and_init(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["bench", "--route", "reference", "--route", "simd", "--kernel", "m15_fold",
                             "--budget-ms", "20", "--json"])
        self.assertEqual(code, 0)
        report = json.loads(out.getvalue())
        self.assertTrue(all(m["measured"] for m in report["measurements"]))
        self.assertTrue(all(not c["measured"] for c in report["capabilities"]))
        with state_dir() as tmp:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["init", "--state-dir", tmp, "--tls-host", "localhost"]), 0)
            for name in ("token", "coordinator_mldsa65.seed", "tls/coordinator-cert.pem", "tls/coordinator-key.pem"):
                self.assertTrue((Path(tmp) / name).exists(), name)

    def test_reference_adapter_is_always_present(self):
        self.assertTrue(ReferenceAdapter().available)


if __name__ == "__main__":
    unittest.main()
