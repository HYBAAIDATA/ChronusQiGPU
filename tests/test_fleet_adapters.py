# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Device adapters: fail-closed routes, self-test gating, route records and timed measurement."""

import json
import sys
import unittest
from contextlib import contextmanager

import numpy as np

from chronus.fleet import kernels as K
from chronus.fleet.adapters import (
    MODE_A,
    MODE_B,
    AdapterRegistry,
    CppSimdAdapter,
    ReferenceAdapter,
    SimdAdapter,
)
from chronus.fleet.canonical import deterministic_bytes, sha256_hex
from chronus.fleet.errors import DeviceUnavailableError, SelfTestFailedError
from chronus.fleet.metal import MetalAdapter, MLXEngine
from chronus.fleet.opencl import OpenCLAdapter


def builtin():
    return K.default_registry(plugins=[])


class CorruptSimdFold(K.M15FoldKernel):
    """Same kernel, but the simd route flips one bit: the self-test must catch it."""

    def run_simd(self, ctx, params, tile, start, stop):
        out = bytearray(super().run_simd(ctx, params, tile, start, stop))
        out[0] ^= 1
        return bytes(out)


class ProbeTests(unittest.TestCase):
    def test_probes_are_never_measurements_and_name_their_silicon(self):
        for adapter in (ReferenceAdapter(), SimdAdapter()):
            record = adapter.probe(builtin())
            self.assertTrue(record.available)
            self.assertFalse(record.measured)
            self.assertEqual(record.silicon, "cpu")
            self.assertEqual(record.mode, MODE_A)
            self.assertEqual(record.to_dict()["mode_label"], "Chronus iGPU, Mode A (software-defined GPU, resident lattice)")
            self.assertNotIn("CPU", record.to_dict()["mode_label"])
        self.assertEqual(MetalAdapter.mode, MODE_B)
        self.assertEqual(OpenCLAdapter.silicon, "gpu")

    def test_absent_device_routes_fail_closed(self):
        registry = AdapterRegistry()
        kernel = K.M15FoldKernel()
        tile = deterministic_bytes("absent", 64)
        registry.prepare(builtin(), measure=False)
        for route in ("metal", "opencl", "cpp-simd"):
            adapter = registry.get(route)
            if adapter.available:
                continue  # real hardware present on this machine; nothing absent to test
            self.assertTrue(adapter.probe().reason)
            with self.assertRaises(DeviceUnavailableError):
                registry.select(route, kernel, {}, tile, 0, 32)
            with self.assertRaises(DeviceUnavailableError):
                adapter.execute(kernel, {}, tile, 0, 32)

    @unittest.skipIf(sys.platform == "darwin", "Metal may be present on macOS")
    def test_metal_is_absent_off_macos(self):
        record = MetalAdapter().probe()
        self.assertFalse(record.available)
        self.assertIn("macOS", record.reason)

    def test_cpp_simd_needs_the_native_library(self):
        adapter = CppSimdAdapter()
        if adapter.available:
            self.skipTest("libchronus_igpu is loaded on this machine")
        self.assertIn("libchronus_igpu", adapter.probe().reason)

    def test_unknown_route_is_refused(self):
        with self.assertRaises(DeviceUnavailableError):
            AdapterRegistry(["warp-drive"])


class SelfTestTests(unittest.TestCase):
    def test_reference_and_simd_pass_every_known_answer(self):
        for adapter in (ReferenceAdapter(), SimdAdapter()):
            record = adapter.self_test(builtin())
            self.assertTrue(record.passed, record.error)
            self.assertEqual(sorted(record.verified_kernels), sorted(k.name for k in builtin()))
            self.assertTrue(all(r["match"] for r in record.results if r.get("applicable")))

    def test_a_wrong_answer_fails_the_route_and_blocks_execution(self):
        registry = K.KernelRegistry([CorruptSimdFold()])
        adapter = SimdAdapter()
        record = adapter.self_test(registry)
        self.assertFalse(record.passed)
        self.assertIn("digest mismatch", record.error)
        self.assertEqual(record.verified_kernels, [])
        with self.assertRaises(SelfTestFailedError):
            adapter.execute(CorruptSimdFold(), {}, b"\x01\x02", 0, 1)

    def test_auto_never_selects_a_route_that_failed_its_self_test(self):
        kernel = CorruptSimdFold()
        registry = AdapterRegistry(["simd", "reference"])
        registry.prepare(K.KernelRegistry([kernel]), measure=False)
        tile = deterministic_bytes("auto", 64)
        adapter, reason = registry.select("auto", kernel, {}, tile, 0, 32)
        self.assertEqual(adapter.route, "reference")
        self.assertIn("simd self-test failed", reason)
        with self.assertRaises(SelfTestFailedError):
            registry.select("simd", kernel, {}, tile, 0, 32)

    def test_execution_requires_a_self_test(self):
        with self.assertRaises(DeviceUnavailableError):
            SimdAdapter().execute(K.M15FoldKernel(), {}, b"\x01\x02", 0, 1)


class ExecutionRecordTests(unittest.TestCase):
    def setUp(self):
        self.registry = AdapterRegistry(["simd", "reference"])
        self.registry.prepare(builtin(), measure=False)

    def test_explicit_route_records_exactly_what_ran(self):
        kernel = K.M15FoldKernel()
        tile = deterministic_bytes("record", 1000)
        adapter, reason = self.registry.select("simd", kernel, {}, tile, 0, 500)
        output, record = adapter.execute(kernel, {}, tile, 0, 500, requested_route="simd", tile_index=7)
        self.assertEqual((record.requested_route, record.executed_route, record.fallback_reason), ("simd", "simd", None))
        self.assertEqual((record.silicon, record.mode, record.tile_index, record.items), ("cpu", MODE_A, 7, 500))
        self.assertEqual(record.output_sha256, sha256_hex(output))
        self.assertTrue(record.measured)
        self.assertTrue(record.started_at.endswith("Z") and record.finished_at >= record.started_at)
        self.assertGreaterEqual(record.duration_ns, 0)

    def test_auto_reports_why_the_first_choice_declined(self):
        kernel = K.PVLatticeFoldKernel()
        self.registry.record_throughput(kernel.name, "simd", 10**9)
        payload = json.dumps([{"a": str((1 << 62) - 1), "b": "1", "denominator": "1"}]).encode()
        prepared = kernel.prepare({"order": 85}, payload)
        tile = kernel.tile_input(prepared, 0, 1)
        adapter, reason = self.registry.select("auto", kernel, prepared.params, tile, 0, 1)
        self.assertEqual(adapter.route, "reference")
        self.assertIn("simd declined", reason)
        with self.assertRaises(DeviceUnavailableError):
            self.registry.select("simd", kernel, prepared.params, tile, 0, 1)

    def test_measurement_comes_from_timed_runs(self):
        measurement = self.registry.get("simd").measure(K.M15FoldKernel(), budget_ns=20_000_000)
        self.assertTrue(measurement.measured)
        self.assertGreater(measurement.items_per_second, 0)
        self.assertGreaterEqual(measurement.repeats, 1)
        self.assertTrue(measurement.started_at <= measurement.finished_at)
        self.assertEqual(measurement.items, 1 << 17)


class FakeArray:
    def __init__(self, data):
        self.a = np.asarray(data)

    def astype(self, dtype):
        return FakeArray(self.a.astype(dtype))

    def __getitem__(self, key):
        return FakeArray(self.a[key])

    def __mul__(self, other):
        return FakeArray(self.a * (other.a if isinstance(other, FakeArray) else other))

    __rmul__ = __mul__

    def __add__(self, other):
        return FakeArray(self.a + (other.a if isinstance(other, FakeArray) else other))

    def item(self):
        return self.a.item()

    def __array__(self, dtype=None, copy=None):
        return self.a if dtype is None else self.a.astype(dtype)


class FakeMX:
    """NumPy stand-in for mlx.core with 32-bit integer semantics, run on the host."""

    uint8 = np.uint8
    uint16 = np.uint16
    uint32 = np.uint32
    gpu = "gpu"

    def array(self, data):
        return FakeArray(np.array(data))

    def remainder(self, x, m):
        return FakeArray(x.a % np.uint32(m))

    def stack(self, arrays, axis=0):
        return FakeArray(np.stack([a.a for a in arrays], axis=axis))

    def sum(self, x, axis=None):
        return FakeArray(np.sum(x.a, axis=axis, dtype=x.a.dtype))

    def eval(self, *arrays):
        return None

    @contextmanager
    def stream(self, where):
        yield


class MLXArithmeticTests(unittest.TestCase):
    """The MLX kernels' integer arithmetic, checked under 32-bit lanes without a GPU."""

    def test_field_scaling_uint16_and_uint32_arithmetic(self):
        import struct
        from chronus.execution.pv_scale_fleet import PVFieldScaleKernel
        engine = MLXEngine(FakeMX(), np)
        kernel = PVFieldScaleKernel()
        for answer in kernel.known_answers():
            output = engine.pv_field_scale(answer.payload, int(answer.params['scale_index']))
            self.assertEqual(output, kernel.reference_output(answer.params, answer.payload))
            self.assertTrue(all(v <= 256 for pair in struct.iter_unpack('<HH',output) for v in pair))

    def setUp(self):
        self.engine = MLXEngine(FakeMX(), np)

    def test_m15_pairs_match_reference(self):
        tile = deterministic_bytes("mlx-m15", 4096)
        for kernel in (K.M15FoldKernel(), K.M15UnfoldKernel()):
            expected = kernel.run_reference(None, {}, tile, 0, 2048)
            self.assertEqual(kernel.run_metal(self.engine, {}, tile, 0, 2048), expected)

    def test_dual_space_matches_reference(self):
        kernel = K.DualSpaceQueryKernel()
        tile = deterministic_bytes("mlx-dual", 8192)
        self.assertEqual(kernel.run_metal(self.engine, {}, tile, 0, 2048), kernel.run_reference(None, {}, tile, 0, 2048))

    def test_gf_matvec_matches_reference_at_the_32_bit_bound(self):
        kernel = K.GFMatVecKernel()
        p, rows, cols = 65521, 7, 300
        words = [(p - 1 - i) % p for i in range(rows * cols + cols)]
        payload = b"".join(w.to_bytes(4, "little") for w in words)
        prepared = kernel.prepare({"p": p, "rows": rows, "cols": cols}, payload)
        tile = kernel.tile_input(prepared, 0, rows)
        self.assertIsNone(kernel.accepts("metal", self.engine, prepared.params, tile, 0, rows))
        self.assertEqual(
            kernel.run_metal(self.engine, prepared.params, tile, 0, rows),
            kernel.run_reference(None, prepared.params, tile, 0, rows),
        )

    def test_metal_declines_fields_beyond_32_bit_lanes(self):
        kernel = K.GFMatVecKernel()
        self.assertIsNotNone(kernel.accepts("metal", self.engine, {"p": 65537, "cols": 2}, b"", 0, 1))


if __name__ == "__main__":
    unittest.main()
