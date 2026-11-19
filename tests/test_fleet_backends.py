# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Backend selection: the operator's option drives the choice; ours (the Chronus iGPU) by default."""

import types
import unittest
from pathlib import Path

from chronus.fleet import kernels as K
from chronus.fleet.adapters import MODE_B, AdapterRegistry, DeviceAdapter, IGPUAdapter, ReferenceAdapter
from chronus.fleet.auth import new_token
from chronus.fleet.backends import select_backend
from chronus.fleet.canonical import deterministic_bytes
from chronus.fleet.capacity import HostCapacity
from chronus.fleet.coordinator import CoordinatorConfig, FleetCoordinator
from chronus.fleet.cuda import CudaAdapter
from chronus.fleet.errors import DeviceUnavailableError
from chronus.fleet.executor import FleetExecutor
from chronus.fleet.worker import FleetWorker, WorkerConfig
from chronus.fleet.workunit import WorkUnit
from tests.fleet_support import state_dir
import pytest

pytestmark = pytest.mark.simulated


class FakeHostGPU(DeviceAdapter):
    """Stands in for a host GPU that is present and passes its self-test (route metal, Mode B)."""

    route = "metal"
    name = "fake-host-gpu"
    silicon = "gpu"
    mode = MODE_B

    def _detect(self):
        return True, {"name": "fake host GPU (tests)"}, None, types.SimpleNamespace(ops={"m15_pairs"})


class FoldWithHostGPU(K.M15FoldKernel):
    """m15_fold with a host GPU implementation that is the NumPy path (byte-identical)."""

    def run_metal(self, ctx, params, tile, start, stop):
        return self.run_simd(ctx, params, tile, start, stop)


def machine_with_a_host_gpu():
    registry = AdapterRegistry(adapters=[IGPUAdapter(), FakeHostGPU(), ReferenceAdapter()])
    kernels = K.KernelRegistry([FoldWithHostGPU()])
    registry.prepare(kernels, measure=False)
    return registry, kernels


class SelectionTests(unittest.TestCase):
    def test_prefer_ours_picks_the_chronus_igpu_even_with_a_host_gpu(self):
        registry, _ = machine_with_a_host_gpu()
        selection = registry.selection("auto", "ours")
        self.assertEqual(selection.executed_backend, "igpu")
        self.assertEqual(selection.detected_backends, ("igpu", "reference", "metal"))
        self.assertIsNone(selection.fallback_reason)
        self.assertEqual(registry.selection("auto").executed_backend, "igpu")

    def test_prefer_host_picks_the_host_gpu(self):
        registry, kernels = machine_with_a_host_gpu()
        selection = registry.selection("auto", "host")
        self.assertEqual(selection.executed_backend, "metal")
        self.assertIsNone(selection.fallback_reason)
        adapter, reason = registry.select("auto", kernels.get("m15_fold"), {}, deterministic_bytes("h", 64), 0, 32,
                                          prefer="host")
        self.assertEqual((adapter.route, reason), ("metal", None))
        adapter, reason = registry.select("auto", kernels.get("m15_fold"), {}, deterministic_bytes("o", 64), 0, 32,
                                          prefer="ours")
        self.assertEqual((adapter.route, reason), ("igpu", None))

    def test_prefer_host_without_a_host_gpu_runs_the_igpu_and_says_why(self):
        registry = AdapterRegistry(["igpu", "metal", "opencl", "cuda", "reference"])
        registry.prepare(K.KernelRegistry([K.M15FoldKernel()]), measure=False)
        if any(route in registry.selection("auto", "host").detected_backends for route in ("metal", "opencl", "cuda")):
            self.skipTest("this machine has a host GPU")
        selection = registry.selection("auto", "host")
        self.assertEqual(selection.executed_backend, "igpu")
        self.assertTrue(selection.fallback_reason.startswith("prefer=host: metal "))
        self.assertIn("selected igpu", selection.fallback_reason)
        # Device rejection reasons may explain that CPU OpenCL is excluded.
        # Assert the actual route, rather than censoring its diagnostic text.
        self.assertNotIn(selection.executed_backend, ("opencl", "cuda", "metal"))
        self.assertNotIn("opencl", selection.detected_backends)

    def test_a_named_backend_that_is_absent_fails_closed(self):
        registry, _ = machine_with_a_host_gpu()
        for backend in ("cuda", "opencl", "simd"):
            selection = registry.selection(backend, "ours")
            self.assertIsNone(selection.executed_backend)
            self.assertIn("failing closed", selection.fallback_reason)
            with self.assertRaises(DeviceUnavailableError):
                selection.require()
        self.assertEqual(registry.selection("metal", "ours").executed_backend, "metal")
        self.assertEqual(registry.selection("igpu", "host").executed_backend, "igpu")
        with self.assertRaises(DeviceUnavailableError):
            select_backend({}, "warp-drive")
        with self.assertRaises(DeviceUnavailableError):
            select_backend({}, "auto", "theirs")

    def test_the_cuda_stub_fails_closed_without_a_cuda_runtime(self):
        adapter = CudaAdapter()
        record = adapter.probe(K.KernelRegistry([K.M15FoldKernel()]))
        if record.available:
            self.assertFalse(adapter.self_test(K.KernelRegistry([K.M15FoldKernel()])).passed)
        else:
            self.assertTrue(record.reason)
            with self.assertRaises(DeviceUnavailableError):
                adapter.require_available()

    def test_tile_records_carry_the_backend_fields(self):
        registry, kernels = machine_with_a_host_gpu()
        kernel = kernels.get("m15_fold")
        selection = registry.selection("auto", "ours")
        tile = deterministic_bytes("record", 64)
        adapter, reason = registry.select("auto", kernel, {}, tile, 0, 32, prefer="ours")
        output, record = adapter.execute(kernel, {}, tile, 0, 32, requested_route="auto", fallback_reason=reason,
                                         preference="ours", detected_backends=selection.detected_backends)
        self.assertEqual(output, kernel.run_reference(None, {}, tile, 0, 32))
        fields = record.to_dict()
        self.assertEqual(fields["requested_backend"], "auto")
        self.assertEqual(fields["executed_backend"], "igpu")
        self.assertEqual(fields["executed_route"], "igpu")
        self.assertEqual(fields["preference"], "ours")
        self.assertEqual(fields["detected_backends"], ["igpu", "reference", "metal"])
        self.assertIsNone(fields["fallback_reason"])


class WorkerSelectionTests(unittest.TestCase):
    def test_a_worker_with_a_named_absent_backend_fails_closed_before_joining(self):
        worker = FleetWorker(
            WorkerConfig("http://127.0.0.1:9", new_token(), label="no-cuda", backend="cuda", measure=False),
            kernels=K.KernelRegistry([K.M15FoldKernel()]),
            adapters=AdapterRegistry(["igpu", "cuda", "reference"]),
        )
        worker.prepare()
        if worker.selection.ok:
            self.skipTest("this machine has a CUDA device")
        with self.assertRaises(DeviceUnavailableError):
            worker.join()

    def test_receipts_record_the_backend_each_preference_selected(self):
        with state_dir() as tmp:
            token = new_token()
            coordinator = FleetCoordinator(
                CoordinatorConfig(token=token, state_dir=Path(tmp) / "state", port=0, fabric_tick_ms=200)
            ).start()
            registry, kernels = machine_with_a_host_gpu()
            worker = FleetWorker(WorkerConfig(coordinator.url, token, label="mac-with-gpu", measure=False),
                                 kernels=kernels, adapters=registry,
                                 host=HostCapacity(8, 6, (300000, 100000), 16 * 1024**3, "test-fixture"))
            try:
                worker.start_thread()
                self.assertTrue(worker.wait_joined(60))
                node = coordinator.nodes[worker.node_id]
                self.assertEqual(node.backend["executed_backend"], "igpu")
                self.assertEqual(node.backend["preference"], "ours")
                self.assertIn("metal", node.backend["detected_backends"])
                self.assertEqual(node.host_capacity["available_cpus"], 3)
                self.assertEqual(node.host_capacity["memory_bytes"], 16 * 1024**3)
                self.assertEqual(node.host_capacity["memory_source"], "test-fixture")
                self.assertFalse(node.host_capacity["measured"])
                self.assertIn("not independently verified", node.host_capacity["source"])
                self.assertEqual(node.public()["host_capacity"], node.host_capacity)
                with FleetExecutor(coordinator.url, token=token) as fleet:
                    data = deterministic_bytes("backends", 8192)
                    ours = fleet.submit(WorkUnit("m15_fold", data, virtual_units=80), timeout=120)
                    host = fleet.submit(WorkUnit("m15_fold", data, virtual_units=80, prefer="host"), timeout=120)
                    named = fleet.submit(WorkUnit("m15_fold", data, virtual_units=80, route="metal"), timeout=120)
                self.assertEqual(ours.output, host.output)
                self.assertEqual(set(ours.receipt["backend"]["executed_backends"]), {"igpu"})
                self.assertEqual(ours.receipt["backend"]["preference"], "each worker's --prefer")
                self.assertEqual(set(host.receipt["backend"]["executed_backends"]), {"metal"})
                self.assertEqual(host.receipt["backend"]["preference"], "host")
                self.assertEqual(named.receipt["backend"]["requested_backend"], "metal")
                self.assertEqual(set(named.receipt["backend"]["executed_backends"]), {"metal"})
                device = ours.receipt["devices"][0]
                self.assertEqual(device["host_capacity"]["available_cpus"], 3)
                self.assertEqual(device["host_capacity"]["memory_bytes"], 16 * 1024**3)
                self.assertFalse(device["host_capacity"]["measured"])
                self.assertEqual(device["preferences"], ["ours"])
                self.assertEqual(device["detected_backends"], ["igpu", "metal", "reference"])
                self.assertEqual(device["backend"]["executed_backend"], "igpu")
                anchor = coordinator.ledger.find(host.receipt["receipt_id"])
                self.assertEqual(anchor["meta"]["preference"], "host")
                self.assertEqual(set(anchor["meta"]["executed_backends"]), {"metal"})
            finally:
                worker.stop()
                coordinator.stop()


if __name__ == "__main__":
    unittest.main()
