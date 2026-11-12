# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Three worker processes on one host; one is killed mid-job.

Asserts that the job still completes with output identical to the reference,
that the dead worker's leases were recovered through a blind check that passed
in one cycle, and that the receipt verifies (ML-DSA-65 signature, ledger
anchor, result digest).
"""

import json
import os
import signal
import subprocess
import time
import unittest
from pathlib import Path

from chronus.fleet.auth import new_token, write_token_file
from chronus.fleet.canonical import deterministic_bytes
from chronus.fleet.coordinator import CoordinatorConfig, FleetCoordinator
from chronus.fleet.kernels import M15FoldKernel, default_registry
from chronus.fleet.ledger import verify_ledger
from chronus.fleet.receipts import verify_receipt
from chronus.fleet.workunit import WorkUnit
from tests.fleet_support import PLUGIN_MODULE, PYTHON, child_env, state_dir

JOIN_TIMEOUT_S = 240
JOB_TIMEOUT_S = 240


def wait_for(predicate, timeout, interval=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


@unittest.skipUnless(hasattr(signal, "SIGKILL"), "needs POSIX process signals")
class KillOneWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = state_dir()
        self.root = Path(self.tmp.name)
        self.token = new_token()
        self.token_file = write_token_file(self.root / "token", self.token)
        self.coordinator = FleetCoordinator(
            CoordinatorConfig(
                token=self.token,
                state_dir=self.root / "coordinator",
                port=0,
                heartbeat_interval_ms=300,
                node_timeout_ms=4000,
                lease_ttl_ms=8000,
                sample_rate_ppm=250_000,
                fabric_tick_ms=500,
                kernels=default_registry(plugins=[PLUGIN_MODULE]),
            )
        ).start()
        self.workers = []
        env = child_env(CHRONUS_FLEET_KERNELS=PLUGIN_MODULE, CHRONUS_FLEET_TEST_PACE_MS="25")
        for i in range(3):
            log = open(self.root / f"worker-{i}.log", "w")
            command = [
                PYTHON, "-m", "chronus.fleet", "join",
                "--coordinator", self.coordinator.url,
                "--token-file", str(self.token_file),
                "--label", f"w{i}",
                "--route", "simd", "--route", "reference",
                "--no-measure",
            ]
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env)
            self.workers.append((process, log))

    def tearDown(self):
        for process, log in self.workers:
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            log.close()
        self.coordinator.stop()
        self.tmp.cleanup()

    def logs(self):
        with self.coordinator._lock:
            nodes = [(n.node_id, n.state, n.alive) for n in self.coordinator.nodes.values()]
            jobs = [j.progress() for j in self.coordinator.jobs.values()]
            leases = [(lease.node_id, lease.group.first_tile) for lease in self.coordinator.scheduler.inflight.values()]
        state = f"nodes={nodes}\njobs={jobs}\nleases={leases}\n"
        return state + "\n".join((self.root / f"worker-{i}.log").read_text()[-2000:] for i in range(3))

    def nodes_of(self, label):
        with self.coordinator._lock:
            return {n.node_id for n in self.coordinator.nodes.values() if n.label == label}

    def node_of(self, label):
        with self.coordinator._lock:
            return next(n.node_id for n in self.coordinator.nodes.values() if n.label == label and n.alive)

    def test_kill_one_worker_mid_job(self):
        def live_count():
            with self.coordinator._lock:
                return sum(n.alive for n in self.coordinator.nodes.values())
        joined = wait_for(lambda: live_count() == 3, JOIN_TIMEOUT_S)
        self.assertTrue(joined, "workers did not join:\n" + self.logs())
        victim_node = self.node_of("w0")
        victim_process = self.workers[0][0]

        payload = deterministic_bytes("multiprocess", 51_200)
        unit = WorkUnit("m15_fold_paced", payload, virtual_units=800)
        job = self.coordinator.submit(unit, submitter="test")

        def victim_is_busy():
            nonlocal victim_node
            with self.coordinator._lock:
                for node_id in self.nodes_of("w0"):
                    node = self.coordinator.nodes[node_id]
                    done = sum(1 for r in job.results.values() if r.node_id == node_id)
                    if node.alive and done >= 1 and self.coordinator.scheduler.leases_of(node_id):
                        victim_node = node_id
                        return True
                return False

        self.assertTrue(wait_for(victim_is_busy, 120), "victim never held a lease:\n" + self.logs())
        os.kill(victim_process.pid, signal.SIGKILL)
        victim_process.wait(timeout=30)

        self.assertTrue(job.done.wait(JOB_TIMEOUT_S), f"job did not finish: {job.progress()}\n" + self.logs())
        self.assertEqual(job.status, "completed", job.error)

        expected = M15FoldKernel().reference_output({}, payload)
        self.assertEqual(job.output, expected)
        self.assertEqual(len(job.output), len(payload))

        receipt = job.receipt
        check = verify_receipt(
            receipt,
            public_key=self.coordinator.signer.public_key,
            output=job.output,
            work_unit_digest=unit.digest(),
            ledger_path=self.coordinator.ledger.path,
        )
        self.assertTrue(check.valid, check.reasons)

        incidents = [i for i in receipt["recovery"] if i["failed_node"] == victim_node]
        self.assertTrue(incidents, json.dumps(receipt["recovery"], indent=2))
        for incident in incidents:
            self.assertTrue(incident["cause"].startswith("node-lost"), incident["cause"])
            self.assertEqual(incident["status"], "verified")
            self.assertTrue(incident["blind_check"]["passed"])
            self.assertGreaterEqual(incident["blind_check"]["tiles_checked"], 1)
            self.assertTrue(incident["one_cycle"])
            self.assertNotIn(victim_node, [a[3] for a in incident["recovery_path"]["assignments"]])

        tiles = receipt["lattice"]["tiles"]
        self.assertEqual(tiles, 800)
        self.assertEqual(sum(d["tiles"] for d in receipt["devices"]), tiles)
        self.assertEqual(receipt["verification"]["summary"]["mismatches"], 0)
        survivors = {self.node_of("w1"), self.node_of("w2")}
        self.assertTrue(survivors & {d["node_id"] for d in receipt["devices"]})
        self.assertGreaterEqual(receipt["verification"]["summary"]["tile_status"].get("recovered-blind-checked", 0), 1)

        with self.coordinator._lock:
            victim = self.coordinator.nodes[victim_node]
            self.assertFalse(victim.alive)
            self.assertEqual(victim.state, "lost")
        self.assertTrue(verify_ledger(self.coordinator.ledger.path).valid)
        kinds = [json.loads(line)["kind"] for line in self.coordinator.ledger.path.read_text().splitlines()]
        self.assertIn("incident", kinds)
        self.assertIn("receipt", kinds)

        for process, _ in self.workers[1:]:
            process.send_signal(signal.SIGTERM)
        for process, _ in self.workers[1:]:
            self.assertEqual(process.wait(timeout=30), 0)
        def any_alive():
            with self.coordinator._lock:
                return any(n.alive for n in self.coordinator.nodes.values())
        self.assertTrue(
            wait_for(lambda: not any_alive(), 10),
            "surviving workers did not leave cleanly",
        )


if __name__ == "__main__":
    unittest.main()
