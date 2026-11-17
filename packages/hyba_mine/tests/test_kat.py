# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Known-answer tests on real Bitcoin headers: Mode A lane, Metal kernel model, BIST."""

import hashlib
import struct
import unittest
from dataclasses import replace

import _support  # noqa: F401  (import paths)

from chronus.execution.asic_sha256 import _K
from chronus.stratum.gatekeeper import decode_nbits_target

from hyba_mine.bist import kat_lane, select_lane, vector_checks
from hyba_mine.igpu import ROUTE_MODE_A, LaneFault, LaneUnavailable, ModeALane
from hyba_mine.metal import NO_PROBE, PARAMS_FORMAT, chronus_kernel_text, metal_source, model_thread, pack_params
from hyba_mine.plan import MASK32, NoncePlan
from hyba_mine.vectors import GENESIS, REAL_HEADERS
from hyba_mine.work import Hit, UnitAborted, check_result_integrity, le_words, make_device_unit


def sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def _assert_abort_before_execute_refuses_the_unit(case, lane):
    """The dispatcher hands a unit to an executor thread and may abort it before the lane's
    execute() has registered it; the lane must remember the abort and refuse the unit."""
    plan = NoncePlan.for_header(GENESIS.prefix, 12)
    unit = make_device_unit(plan, 0, 1024, decode_nbits_target(GENESIS.nbits), "abort-before-execute")
    case.assertTrue(lane.abort(unit.unit_id))
    with case.assertRaises(UnitAborted) as caught:
        lane.execute(unit)
    case.assertEqual((caught.exception.unit_id, caught.exception.executed), (unit.unit_id, 0))
    case.assertEqual(caught.exception.route, lane.route)
    # The remembered abort is used once; an abort for another unit never stops this one.
    lane.abort("some-other-unit")
    result = lane.execute(unit)
    case.assertEqual(result.executed, unit.count)
    case.assertIsNone(check_result_integrity(unit, result))


class TestVectors(unittest.TestCase):
    def test_every_vector_hashes_to_its_published_block_hash(self):
        checks = vector_checks()
        self.assertEqual(len(checks), len(REAL_HEADERS))
        self.assertTrue(all(c.passed for c in checks), [c.name for c in checks if not c.passed])

    def test_vectors_include_the_genesis_header_used_by_existing_tests(self):
        self.assertEqual(GENESIS.nonce, _support.GENESIS_NONCE)
        self.assertEqual(sha256d(GENESIS.header)[::-1].hex(),
                         "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f")


class TestModeALaneKAT(unittest.TestCase):
    def setUp(self):
        self.lane = ModeALane(workers=1)

    def tearDown(self):
        self.lane.close()

    def test_mode_a_passes_every_known_answer_test(self):
        checks = kat_lane(self.lane, full_window=False)
        failed = [(c.name, c.detail) for c in checks if not c.passed]
        self.assertEqual(failed, [])
        self.assertGreaterEqual(len(checks), 3 * len(REAL_HEADERS) + 1)

    def test_genesis_nonce_found_at_its_plan_position_over_a_full_window(self):
        plan = NoncePlan.for_header(GENESIS.prefix)
        position = plan.position_of(GENESIS.nonce)
        start = position - position % plan.window_size
        unit = make_device_unit(plan, start, plan.window_size, decode_nbits_target(GENESIS.nbits), "full-window")
        result = self.lane.execute(unit)
        self.assertIsNone(check_result_integrity(unit, result))
        self.assertEqual(result.executed, plan.window_size)
        self.assertIn(Hit(position - start, GENESIS.nonce), result.hits)

    def test_planted_wrong_hit_is_caught_by_the_integrity_check(self):
        plan = NoncePlan.for_header(GENESIS.prefix)
        position = plan.position_of(GENESIS.nonce)
        unit = make_device_unit(plan, position, 1, decode_nbits_target(GENESIS.nbits), "planted")
        result = self.lane.execute(unit)
        forged = replace(result, hits=(Hit(0, (GENESIS.nonce + 1) & MASK32),))
        self.assertIn("not on the plan", check_result_integrity(unit, forged))
        short = replace(result, executed=0)
        self.assertIn("executed 0", check_result_integrity(unit, short))
        wrong_probe = replace(result, probe_words=tuple((w + 1) & MASK32 for w in result.probe_words))
        self.assertIn("probe digest", check_result_integrity(unit, wrong_probe))

    def test_an_abort_that_arrives_before_execute_refuses_the_unit(self):
        _assert_abort_before_execute_refuses_the_unit(self, self.lane)

    def test_kat_fails_for_a_planted_faulty_lane(self):
        class OffByOneLane:
            route = "planted_faulty_lane"

            def __init__(self, inner):
                self.inner = inner

            def execute(self, unit):
                result = self.inner.execute(unit)
                return replace(result, hits=tuple(Hit(h.offset, (h.nonce ^ 1)) for h in result.hits))

            def close(self):
                pass

        checks = kat_lane(OffByOneLane(self.lane), full_window=False)
        self.assertTrue(any(not c.passed for c in checks))


class TestMetalKernel(unittest.TestCase):
    def test_metal_source_reuses_the_chronus_sha256_core(self):
        source = metal_source()
        k_values = [int(v, 16) for v in source.split("constant uint K[64] = {")[1].split("};")[0].replace("U", "").split(",") if v.strip()]
        self.assertEqual(tuple(k_values), _K)
        self.assertIn("inline void compress(thread uint* state, thread uint* w)", source)
        self.assertNotIn("__constant", source)
        self.assertNotIn("__global", source)
        self.assertNotIn("#pragma", source)
        self.assertIn("kernel void hyba_sha256d_plan(", source)
        self.assertIn(chronus_kernel_text().split("inline uint rotr")[1].split("}")[0], source)

    def test_metal_lane_refuses_a_changed_chronus_kernel(self):
        with self.assertRaises(LaneFault):
            metal_source(chronus_kernel_text().replace("__constant uint K[64]", "__constant uint KK[64]"))
        with self.assertRaises(LaneFault):
            metal_source("no kernel here")

    def test_kernel_parameter_struct_matches_host_packing(self):
        source = metal_source()
        struct_body = source.split("struct HybaPlanParams {")[1].split("};")[0]
        fields = [line.strip().rstrip(";").split()[1] for line in struct_body.strip().splitlines()]
        self.assertEqual(fields, ["midstate[8]", "tail[3]", "target[8]", "offset", "stride", "window_bits",
                                  "lane_bits", "chunk_position", "count", "max_hits", "probe_index"])
        self.assertEqual(struct.calcsize(PARAMS_FORMAT), 4 * (8 + 3 + 8 + 8))

    def test_kernel_model_reproduces_real_blocks(self):
        for vector in REAL_HEADERS:
            plan = NoncePlan.for_header(vector.prefix)
            position = plan.position_of(vector.nonce)
            value = int.from_bytes(sha256d(vector.header), "little")
            for bound, expect in ((decode_nbits_target(vector.nbits), True), (value, True), (value - 1, False)):
                params = pack_params(plan.header_prefix, bound, plan.offset, plan.stride, plan.window_bits,
                                     position - 7, 64, 16, NO_PROBE)
                nonce, words, hit = model_thread(params, plan.lane_table, 7)
                self.assertEqual(nonce, vector.nonce, vector.name)
                self.assertEqual(words, le_words(value), vector.name)
                self.assertEqual(hit, expect, (vector.name, bound == value))

    def test_kernel_model_matches_the_plan_for_neighbouring_threads(self):
        plan = NoncePlan.for_header(GENESIS.prefix, 12)
        base = plan.window_size * 3 + plan.lane_size - 5
        params = pack_params(plan.header_prefix, (1 << 256) - 1, plan.offset, plan.stride, plan.window_bits,
                             base, 16, 16, NO_PROBE)
        for tid in range(16):
            nonce, words, hit = model_thread(params, plan.lane_table, tid)
            self.assertEqual(nonce, plan.nonce_at(base + tid))
            digest = sha256d(GENESIS.prefix + nonce.to_bytes(4, "little"))
            self.assertEqual(words, le_words(int.from_bytes(digest, "little")))
            self.assertTrue(hit)


class _FakeBuffer:
    def __init__(self, data: bytes):
        self.data = bytearray(data)

    def contents(self):
        buffer = self

        class _Contents:
            def as_buffer(self, nbytes):
                return memoryview(buffer.data)[:nbytes]

        return _Contents()


class _FakeMetal:
    """Stand-in for PyObjC's Metal module that runs the kernel model per thread."""

    MTLResourceStorageModeShared = 0
    MTLCommandBufferStatusCompleted = 4

    def __init__(self):
        self.dispatches = []
        self.source = None
        metal = self

        class Options:
            @classmethod
            def alloc(cls):
                return cls()

            def init(self):
                return self

        self.MTLCompileOptions = Options

        class Pipeline:
            def threadExecutionWidth(self):
                return 32

            def maxTotalThreadsPerThreadgroup(self):
                return 1024

        class Encoder:
            def __init__(self, command):
                self.command = command
                self.buffers = {}

            def setComputePipelineState_(self, pipeline):
                self.command.pipeline = pipeline

            def setBuffer_offset_atIndex_(self, buffer, offset, index):
                self.buffers[index] = buffer

            def dispatchThreadgroups_threadsPerThreadgroup_(self, groups, per_group):
                self.command.grid = (groups[0], per_group[0], dict(self.buffers))

            def endEncoding(self):
                pass

        class Command:
            def __init__(self):
                self.grid = None

            def computeCommandEncoder(self):
                return Encoder(self)

            def commit(self):
                groups, per_group, buffers = self.grid
                params = bytes(buffers[0].data)
                lane_table = struct.unpack("<256I", bytes(buffers[1].data))
                fields = struct.unpack(PARAMS_FORMAT, params)
                count, max_hits, probe_index = fields[24], fields[25], fields[26]
                metal.dispatches.append((groups * per_group, count, max_hits))
                found = 0
                for tid in range(min(groups * per_group, count)):
                    nonce, words, hit = model_thread(params, lane_table, tid)
                    if tid == probe_index:
                        buffers[4].data[:] = struct.pack("<8I", *words)
                    if hit:
                        if found < max_hits:
                            buffers[2].data[8 * found:8 * found + 8] = struct.pack("<2I", tid, nonce)
                        found += 1
                buffers[3].data[:] = struct.pack("<I", found)

            def waitUntilCompleted(self):
                pass

            def status(self):
                return _FakeMetal.MTLCommandBufferStatusCompleted

            def error(self):
                return None

            def GPUStartTime(self):
                return 10.0

            def GPUEndTime(self):
                return 10.001

        class Queue:
            def commandBuffer(self):
                return Command()

        class Library:
            def newFunctionWithName_(self, name):
                return name if name == "hyba_sha256d_plan" else None

        class Device:
            def name(self):
                return "Fake Apple GPU"

            def newLibraryWithSource_options_error_(self, source, options, error):
                metal.source = source
                return Library(), None

            def newComputePipelineStateWithFunction_error_(self, function, error):
                return Pipeline(), None

            def newCommandQueue(self):
                return Queue()

            def newBufferWithBytes_length_options_(self, data, length, options):
                assert length == len(data)
                return _FakeBuffer(bytes(data))

            def newBufferWithLength_options_(self, length, options):
                return _FakeBuffer(b"\x00" * length)

        self._device = Device()

    def MTLCreateSystemDefaultDevice(self):
        return self._device

    @staticmethod
    def MTLSizeMake(width, height, depth):
        return (width, height, depth)


class TestMetalLanePlumbing(unittest.TestCase):
    """MetalLane host code (buffers, chunks, probe, hit regrow) against the kernel model."""

    def _lane(self):
        from unittest import mock

        from hyba_mine.metal import MetalLane

        fake = _FakeMetal()
        with mock.patch.dict("sys.modules", {"Metal": fake}):
            lane = MetalLane.open()
        lane.MAX_THREADS = 512
        lane.MAX_HITS = 2
        return fake, lane

    def test_lane_compiles_the_derived_source_and_finds_real_nonces(self):
        fake, lane = self._lane()
        self.assertEqual(fake.source, metal_source())
        mode_a = ModeALane(workers=1)
        try:
            for vector in (GENESIS, REAL_HEADERS[3]):
                plan = NoncePlan.for_header(vector.prefix, 12)
                position = plan.position_of(vector.nonce)
                start = max(0, position - 700)
                unit = make_device_unit(plan, start, 1536, decode_nbits_target(vector.nbits), "fake-metal")
                result = lane.execute(unit)
                self.assertIsNone(check_result_integrity(unit, result), vector.name)
                self.assertIn(Hit(position - start, vector.nonce), result.hits)
                self.assertEqual(result.executed, 1536)
                self.assertEqual(result.detail["timing"], "gpu_timestamps")
                self.assertEqual(result.hits, mode_a.execute(unit).hits)
                self.assertEqual(result.probe_words, mode_a.execute(unit).probe_words)
        finally:
            mode_a.close()
        self.assertTrue(all(threads >= count for threads, count, _ in fake.dispatches))
        self.assertTrue(all(count <= 512 for _, count, _ in fake.dispatches))

    def test_an_abort_that_arrives_before_execute_refuses_the_unit(self):
        fake, lane = self._lane()
        _assert_abort_before_execute_refuses_the_unit(self, lane)

    def test_hit_buffer_regrows_so_no_hit_is_lost(self):
        fake, lane = self._lane()
        plan = NoncePlan.for_header(GENESIS.prefix, 12)
        unit = make_device_unit(plan, 4096, 600, (1 << 256) // 64, "fake-metal-easy")
        result = lane.execute(unit)
        self.assertIsNone(check_result_integrity(unit, result))
        expected = ModeALane(workers=1)
        try:
            self.assertEqual(result.hits, expected.execute(unit).hits)
        finally:
            expected.close()
        self.assertGreater(len(result.hits), 2)
        self.assertTrue(any(max_hits > 2 for _, _, max_hits in fake.dispatches))


class TestRouteSelection(unittest.TestCase):
    def test_auto_prefer_host_without_metal_runs_the_igpu_and_says_why(self):
        def absent():
            raise LaneUnavailable("no Metal device on this test host")

        route, lane, checks = select_lane("auto", prefer="host", mode_a_workers=1, open_metal=absent, full_window=False)
        try:
            self.assertEqual(route.requested, "auto")
            self.assertEqual(route.executed, ROUTE_MODE_A)
            self.assertTrue(route.fallback_reason.startswith("METAL_UNAVAILABLE"))
            self.assertEqual((route.executed_backend, route.preference), ("igpu", "host"))
            self.assertEqual(route.detected_backends, ("igpu",))
            self.assertTrue(all(c.passed for c in checks))
        finally:
            lane.close()

    def test_prefer_ours_picks_the_igpu_even_with_a_host_gpu_present(self):
        opened = []

        class FakeHostGPU:
            route = "chronus_igpu_metal"

            def __init__(self):
                self.inner = ModeALane(workers=1)
                opened.append(self)

            def execute(self, unit):
                return replace(self.inner.execute(unit), executed_route=self.route)

            def describe(self):
                return {"route": self.route}

            def close(self):
                self.inner.close()

        route, lane, checks = select_lane("auto", mode_a_workers=1, open_metal=FakeHostGPU, full_window=False)
        try:
            self.assertEqual(route.executed, ROUTE_MODE_A)
            self.assertEqual(route.to_dict()["executed_backend"], "igpu")
            self.assertEqual(route.to_dict()["detected_backends"], ["igpu", "metal"])
            self.assertEqual(route.to_dict()["preference"], "ours")
            self.assertIsNone(route.fallback_reason)
            self.assertTrue(all(c.passed for c in checks))
        finally:
            lane.close()
        route, lane, checks = select_lane("auto", prefer="host", mode_a_workers=1, open_metal=FakeHostGPU,
                                          full_window=False)
        try:
            self.assertEqual(route.executed, "chronus_igpu_metal")
            self.assertEqual((route.executed_backend, route.requested_backend), ("metal", "auto"))
            self.assertTrue(all(c.passed for c in checks))
        finally:
            lane.close()

    def test_a_named_backend_without_a_local_lane_fails_closed(self):
        for backend in ("cuda", "opencl", "simd", "reference"):
            route, lane, checks = select_lane(backend, mode_a_workers=1, open_metal=lambda: (_ for _ in ()).throw(
                LaneUnavailable("none")), full_window=False)
            self.assertIsNone(route)
            self.assertIsNone(lane)
            self.assertIn(f"{backend} lane present", [c.name for c in checks if not c.passed])
        route, lane, _ = select_lane("igpu", prefer="host", mode_a_workers=1, full_window=False,
                                     open_metal=lambda: (_ for _ in ()).throw(LaneUnavailable("none")))
        try:
            self.assertEqual((route.executed, route.executed_backend), (ROUTE_MODE_A, "igpu"))
        finally:
            lane.close()

    def test_metal_route_without_metal_fails_closed(self):
        def absent():
            raise LaneUnavailable("no Metal device on this test host")

        route, lane, checks = select_lane("metal", open_metal=absent, full_window=False)
        self.assertIsNone(route)
        self.assertIsNone(lane)
        self.assertFalse(all(c.passed for c in checks))

    def test_present_but_faulty_metal_blocks_even_under_auto(self):
        class FaultyMetal:
            route = "chronus_igpu_metal"

            def __init__(self):
                self.inner = ModeALane(workers=1)

            def execute(self, unit):
                result = self.inner.execute(unit)
                return replace(result, probe_words=tuple(0 for _ in range(8)))

            def describe(self):
                return {"route": self.route}

            def close(self):
                self.inner.close()

        route, lane, checks = select_lane("auto", prefer="host", mode_a_workers=1, open_metal=FaultyMetal,
                                          full_window=False)
        try:
            self.assertFalse(all(c.passed for c in checks))
            self.assertEqual(route.executed, ROUTE_MODE_A)
            self.assertTrue(route.fallback_reason.startswith("METAL_FAILED_BIST"))
        finally:
            if lane is not None:
                lane.close()

    def test_metal_build_fault_is_a_failed_check(self):
        def broken():
            raise LaneFault("the Metal compiler rejected the plan kernel")

        route, lane, checks = select_lane("auto", prefer="host", mode_a_workers=1, open_metal=broken, full_window=False)
        try:
            self.assertIn("Metal lane builds", [c.name for c in checks if not c.passed])
        finally:
            if lane is not None:
                lane.close()

    def test_real_metal_probe_on_this_host_is_honest(self):
        from hyba_mine.metal import MetalLane

        try:
            lane = MetalLane.open()
        except LaneUnavailable as exc:
            self.assertTrue(str(exc))
            return
        try:
            checks = kat_lane(lane, full_window=True)
            self.assertEqual([c.name for c in checks if not c.passed], [])
        finally:
            lane.close()


if __name__ == "__main__":
    unittest.main()
