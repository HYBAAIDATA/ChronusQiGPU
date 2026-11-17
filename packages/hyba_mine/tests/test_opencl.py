# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""OpenCL route: device policy (fake driver, any machine) and the real GPU when one is present."""

import threading
import time
import unittest
from types import SimpleNamespace

from _support import TempHome  # noqa: F401  (sets import paths)
from hyba_mine.bist import qualify_opencl, select_routes
from hyba_mine.igpu import BACKEND_OPENCL, ROUTE_MODE_A, LaneFault, backend_of, route_label
from hyba_mine.opencl import OpenCLLane, discover, opencl_source
from hyba_mine.plan import NoncePlan
from hyba_mine.vectors import GENESIS
from hyba_mine.work import UnitAborted, check_result_integrity, make_device_unit

from chronus.stratum.gatekeeper import decode_nbits_target


class FakeCL:
    """Just enough of pyopencl for discovery policy."""

    class Error(Exception):
        pass

    VERSION_TEXT = "fake"
    device_type = SimpleNamespace(CPU=2, GPU=4, ACCELERATOR=8)

    def __init__(self, platforms):
        self._platforms = platforms

    def get_platforms(self):
        return self._platforms


def dev(name, kind, topology=None):
    d = SimpleNamespace(name=name, type=kind, vendor="v", driver_version="1", version="OpenCL 2.0",
                        max_compute_units=1, max_work_group_size=256, global_mem_size=1 << 30)
    if topology:
        d.topology_amd = SimpleNamespace(bus=topology, device=0, function=0)
    return d


def plat(name, *devices):
    return SimpleNamespace(name=name, version="OpenCL 2.0", get_devices=lambda: list(devices))


class DiscoveryPolicyTests(unittest.TestCase):
    def test_disabled_by_environment(self):
        d = discover(env={"HYBA_MINE_DISABLE_OPENCL": "1"}, cl_module=FakeCL([]))
        self.assertFalse(d.available)
        self.assertIn("OPENCL_DISABLED", d.reason)

    def test_no_platform_is_a_reason_not_an_error(self):
        d = discover(env={}, cl_module=FakeCL([]))
        self.assertFalse(d.available)
        self.assertIn("OPENCL_NO_PLATFORM", d.reason)

    def test_cpu_devices_are_skipped_so_the_cpu_is_not_counted_twice(self):
        d = discover(env={}, cl_module=FakeCL([plat("Intel", dev("cpu", 2))]))
        self.assertEqual(d.gpus, ())
        self.assertIn("OPENCL_NO_GPU", d.reason)
        self.assertIn("Mode A", d.records()[0]["reason"])

    def test_amd_style_all_or_gpu_type_is_a_gpu(self):
        d = discover(env={}, cl_module=FakeCL([plat("AMD", dev("gfx", 0xFFFFFFFF & ~2 | 4))]))
        self.assertEqual([g.name for g in d.gpus], ["gfx"])

    def test_one_physical_gpu_seen_twice_is_hashed_once(self):
        d = discover(env={}, cl_module=FakeCL([
            plat("AMD", dev("gfx-a", 4, topology=3)),
            plat("AMD again", dev("gfx-b", 4, topology=3)),
            plat("OpenCLOn12", dev("gfx-c", 4)),
        ]))
        self.assertEqual([g.name for g in d.gpus], ["gfx-a"])
        reasons = " ".join(r["reason"] for r in d.records())
        self.assertIn("same physical GPU", reasons)
        self.assertIn("layered platform", reasons)

    def test_route_names_and_labels(self):
        d = discover(env={}, cl_module=FakeCL([plat("AMD", dev("gfx", 4))]))
        route = d.gpus[0].route
        self.assertEqual(route, "chronus_igpu_opencl_p0d0")
        self.assertEqual(backend_of(route), BACKEND_OPENCL)
        self.assertIn("OpenCL", route_label(route))

    def test_kernel_source_reuses_the_chronus_core_unchanged(self):
        source = opencl_source()
        self.assertEqual(source.count("inline void compress("), 1)
        self.assertIn("__kernel void hyba_sha256d_plan(", source)
        with self.assertRaises(LaneFault):
            opencl_source("not the chronus kernel")


def _real_gpus():
    d = discover(env={})
    return d.gpus if d.available else ()


REAL = _real_gpus()


@unittest.skipUnless(REAL, "no OpenCL GPU on this machine")
class RealGpuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lane = OpenCLLane.open(REAL[0])

    @classmethod
    def tearDownClass(cls):
        cls.lane.close()

    def test_genesis_nonce_at_its_plan_position_over_a_full_window(self):
        plan = NoncePlan.for_header(GENESIS.prefix)
        pos = plan.position_of(GENESIS.nonce)
        start = pos - pos % plan.window_size
        unit = make_device_unit(plan, start, plan.window_size, decode_nbits_target(GENESIS.nbits), "t-genesis")
        result = self.lane.execute(unit)
        self.assertIsNone(check_result_integrity(unit, result))
        self.assertEqual([(start + h.offset, h.nonce) for h in result.hits], [(pos, GENESIS.nonce)])
        self.assertEqual(result.executed_route, REAL[0].route)

    def test_abort_stops_a_running_unit_at_a_dispatch_boundary(self):
        plan = NoncePlan.for_header(GENESIS.prefix)
        unit = make_device_unit(plan, 0, 1 << 26, decode_nbits_target(GENESIS.nbits), "t-abort")
        timer = threading.Timer(0.3, self.lane.abort, args=(unit.unit_id,))
        timer.start()
        started = time.monotonic()
        with self.assertRaises(UnitAborted) as caught:
            self.lane.execute(unit)
        self.assertLess(time.monotonic() - started, 5.0)
        self.assertLess(caught.exception.executed, unit.count)

    def test_qualification_passes_on_this_device(self):
        lane, checks, record = qualify_opencl(REAL[0], lambda d: OpenCLLane.open(d), 20, True)
        try:
            self.assertIsNotNone(lane, [c.name for c in checks if not c.passed])
            self.assertEqual(record["stage"], "admitted")
            self.assertTrue(any("dispatch boundaries" in c.name and c.passed for c in checks))
        finally:
            if lane is not None:
                lane.close()


@unittest.skipUnless(REAL, "no OpenCL GPU on this machine")
class RealAutoSelectionTests(unittest.TestCase):
    def test_auto_admits_mode_a_and_the_gpu_and_leaves_a_core_for_it(self):
        selection = select_routes(("auto",), mode_a_workers=None, full_window=False,
                                  discover_opencl=lambda: discover(env={}), host_os="Windows")
        try:
            routes = [lane.route for lane in selection.lanes]
            self.assertIn(ROUTE_MODE_A, routes)
            self.assertIn(REAL[0].route, routes)
            self.assertIsNone(selection.degraded_reason)
            mode_a = next(lane for lane in selection.lanes if lane.route == ROUTE_MODE_A)
            self.assertGreaterEqual(mode_a.reserve_host_cores, 1)
        finally:
            selection.close()


if __name__ == "__main__":
    unittest.main()
