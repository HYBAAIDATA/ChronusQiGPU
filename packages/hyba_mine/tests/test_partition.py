# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Concurrent routes on disjoint nonce ranges: registry, selection and the runtime end to end."""

import asyncio
import threading
import unittest
from dataclasses import replace
from fractions import Fraction

import _support
from _support import FakeClock, TempHome, VerifyingPool, fake_sleeper

from chronus.execution.elevation import Route
from chronus.execution.hashrate_cap import HashrateCap, override_process_cap

from hyba_mine.bist import parse_routes, select_routes
from hyba_mine.dispatch import LocalIGPUDispatcher
from hyba_mine.igpu import ROUTE_LABELS, ROUTE_METAL, ROUTE_MODE_A, BackendRoute, LaneFault, LaneUnavailable, ModeALane
from hyba_mine.ledger import Ledger
from hyba_mine.plan import PythiaItinerary, UnitSpec
from hyba_mine.runtime import EXIT_DEVICE_FAULT, EXIT_OK, EXIT_SCHEDULER_FAULT, MinerRuntime, RuntimeOptions
from hyba_mine.schedule import InFlightRegistry, SchedulerInvariantError, WorkScheduler, make_slot, unit_key
from hyba_mine.status import summarize
from hyba_mine.throttle import CapGate
from hyba_mine.status import render_text
from hyba_mine.work import MiningJob, UnitAborted, make_unit

from chronus.execution.stratum import StratumJob

STAND_IN = "test_stand_in_lane"
MODE_A_ROUTE = BackendRoute("auto", ROUTE_MODE_A, None, "auto", "ours", ("igpu",), "igpu")


class StandInLane:
    """Test double: computes on Chronus iGPU Mode A and labels its results with a test-only route.

    It stands in for a second local route (on this test host there is no Apple GPU), so
    the scheduler can be exercised with two routes. It is not a Metal result.
    """

    def __init__(self, route: str = STAND_IN, mutate=None) -> None:
        self.route = route
        self.inner = ModeALane(workers=1)
        self.mutate = mutate

    def execute(self, unit):
        try:
            result = replace(self.inner.execute(unit), executed_route=self.route)
        except UnitAborted as exc:
            raise UnitAborted(exc.unit_id, exc.executed, exc.device_ns, self.route, exc.node, exc.hits_found) from None
        return self.mutate(unit, result) if self.mutate is not None else result

    def abort(self, unit_id):
        return self.inner.abort(unit_id)

    def describe(self):
        return {"route": self.route, "label": "test stand-in (computes on Mode A)"}

    def close(self):
        self.inner.close()


def _mode_a():
    return LocalIGPUDispatcher(ModeALane(workers=1), MODE_A_ROUTE)


class HoldUntilAborted:
    """Lane wrapper: a unit of ``job_id`` does not start until the runtime aborts it.

    Every route therefore deterministically still holds its unit when the stale signal
    lands. On the abort the inner lane is told first and only then released, so the
    inner lane always sees the abort BEFORE its execute() registers the unit (the race a
    lane must survive: it has to refuse the unit, not hash it to the end).
    """

    def __init__(self, inner, job_id: str = "genesis") -> None:
        self.inner, self.route, self.job_id = inner, inner.route, job_id
        self._lock = threading.Lock()
        self._released: dict = {}

    def _event(self, unit_id: str) -> threading.Event:
        with self._lock:
            return self._released.setdefault(unit_id, threading.Event())

    def execute(self, unit):
        if unit.job is not None and unit.job.job_id == self.job_id:
            if not self._event(unit.unit_id).wait(timeout=30):
                raise LaneFault("test lane: the held unit was never aborted")
        return self.inner.execute(unit)

    def abort(self, unit_id):
        signalled = self.inner.abort(unit_id)
        self._event(unit_id).set()
        return signalled

    def describe(self):
        return self.inner.describe()

    def close(self):
        self.inner.close()


def _stand_in(route: str = STAND_IN, mutate=None, slot_route: str = None):
    return LocalIGPUDispatcher(StandInLane(route, mutate), Route("auto", slot_route or route, None))


class Recording:
    """Logs every unit a route receives; optionally waits on a barrier so routes overlap in time."""

    def __init__(self, inner, log: list, box: dict, barrier=None) -> None:
        self.inner, self.log, self.box, self.barrier = inner, log, box, barrier
        self.route = inner.route

    def describe(self):
        return self.inner.describe()

    async def run(self, unit):
        self.log.append((self.route.executed, unit.job.job_id, unit.en2_counter, unit.start, unit.count, unit.unit_id))
        runtime = self.box.get("runtime")
        if runtime is not None:
            registry = runtime.scheduler.registry
            registry.assert_disjoint()
            self.box["peak"] = max(self.box.get("peak", 0), len(registry))
        if self.barrier is not None:
            await self.barrier(self, unit)
        return await self.inner.run(unit)

    async def abort(self, unit_id, grace):
        return await self.inner.abort(unit_id, grace)

    def close(self):
        self.inner.close()


def _small_units(count: int, en2: int = 0, size: int = 4096) -> tuple:
    return tuple(UnitSpec(en2, i * size, size) for i in range(count))


def _of(records, kind: str) -> list:
    return [r["data"] for r in records if r["kind"] == kind]


def _run(dispatchers, units, *, difficulty=Fraction(1, 10 ** 7), box=None, gate=None, cap=None, **options):
    box = box if box is not None else {}

    async def scenario(home):
        pool = VerifyingPool(difficulty=difficulty)
        await pool.start()
        home.put_login("viabtc")
        ledger = Ledger(home.layout.ledger, home.layout.ledger_lock)
        defaults = dict(endpoints={"viabtc": (pool.endpoint(),)}, backoff=(0.05,), stats_interval=0.2,
                        control_interval=0.1, submit_timeout=5.0, itinerary=PythiaItinerary(override=units),
                        stop_when_itinerary_ends=True)
        defaults.update(options)
        built = dispatchers(pool, box) if callable(dispatchers) else dispatchers
        runtime = MinerRuntime(home.layout, ledger, home.store(), built, "viabtc", RuntimeOptions(**defaults))
        if gate is not None:
            runtime.gate = gate
        box["runtime"] = runtime
        code = await runtime.run()
        await pool.stop()
        for dispatcher in built:
            dispatcher.close()
        return code, list(ledger.records()), ledger.verify().ok, pool

    with TempHome() as home:
        if cap is not None:
            with override_process_cap(cap):
                return _support.run(scenario(home), timeout=120)
        return _support.run(scenario(home), timeout=120)


def _job(job_id: str = "j1") -> MiningJob:
    params = list(VerifyingPool().notify_message("genesis", True)["params"])
    params[0] = job_id
    return MiningJob(job=StratumJob.from_notify(params), pool_id="viabtc", generation=1, epoch=0,
                     extranonce1=b"", extranonce2_size=4, difficulty=Fraction(1), received_at="test")


def _unit(job, en2, start, count):
    return make_unit(job, en2, start, count, Fraction(1), 20)


class TestRegistry(unittest.TestCase):
    def test_overlapping_inflight_units_on_two_routes_are_refused(self):
        registry = InFlightRegistry()
        job = _job()
        registry.claim("r0", ROUTE_MODE_A, _unit(job, 0, 0, 8192))
        with self.assertRaises(SchedulerInvariantError) as caught:
            registry.claim("r1", STAND_IN, _unit(job, 0, 4096, 8192))
        self.assertIn(ROUTE_MODE_A, caught.exception.reason)
        self.assertEqual(caught.exception.conflict["start"], 0)
        self.assertEqual(len(registry), 1)

    def test_reissue_of_a_completed_range_within_a_job_is_refused(self):
        registry = InFlightRegistry()
        job = _job()
        first = _unit(job, 0, 0, 4096)
        registry.claim("r0", ROUTE_MODE_A, first)
        registry.release(first.unit_id)
        with self.assertRaises(SchedulerInvariantError) as caught:
            registry.claim("r1", STAND_IN, _unit(job, 0, 2048, 4096))
        self.assertEqual(caught.exception.reason, "range already issued for this job")
        registry.retire_job(job.key)
        registry.claim("r1", STAND_IN, _unit(_job("j2"), 0, 0, 4096))
        registry.claim("r0", ROUTE_MODE_A, _unit(job, 0, 0, 4096))

    def test_same_range_for_another_en2_job_or_version_is_allowed(self):
        registry = InFlightRegistry()
        job, other = _job("j1"), _job("j2")
        registry.claim("r0", ROUTE_MODE_A, _unit(job, 0, 0, 4096))
        registry.claim("r1", STAND_IN, _unit(job, 1, 0, 4096))
        registry.claim("r2", "x", _unit(other, 0, 0, 4096))
        rolled = make_unit(job, 0, 0, 4096, Fraction(1), 20, version_mask=0x1FFFE000, version_index=1)
        registry.claim("r3", "y", rolled)
        registry.assert_disjoint()
        self.assertEqual(len(registry), 4)

    def test_duplicate_unit_id_is_refused(self):
        registry = InFlightRegistry()
        unit = _unit(_job(), 0, 0, 4096)
        registry.claim("r0", ROUTE_MODE_A, unit)
        with self.assertRaises(SchedulerInvariantError) as caught:
            registry.claim("r1", STAND_IN, unit)
        self.assertEqual(caught.exception.reason, "duplicate unit id")


class TestScheduler(unittest.TestCase):
    def _scheduler(self, window_bits=24):
        itinerary = PythiaItinerary(window_bits=window_bits)
        dispatchers = [_mode_a(), _stand_in()]
        self.addCleanup(lambda: [d.close() for d in dispatchers])
        slots = [make_slot(f"r{i}", d, itinerary) for i, d in enumerate(dispatchers)]
        return WorkScheduler(itinerary, slots), slots

    def test_routes_with_different_unit_sizes_get_disjoint_units(self):
        scheduler, (fast, slow) = self._scheduler()
        fast.sizer.unit_size = 1 << 27
        job = _job()
        issued = []
        for slot in (fast, slow, fast, slow, slow, fast):
            spec, resumed = scheduler.take(slot, job)
            self.assertFalse(resumed)
            unit = scheduler.issue(slot, job, spec, Fraction(1))
            scheduler.registry.assert_disjoint()
            issued.append((slot.slot_id, unit.start, unit.count))
            scheduler.complete(slot, unit)
        self.assertEqual([count for _s, _st, count in issued], [1 << 27, 1 << 24, 1 << 27, 1 << 24, 1 << 24, 1 << 27])
        position = 0
        for _slot, start, count in issued:
            self.assertEqual(start, position)
            position += count

    def test_held_back_range_is_handed_to_the_next_route_first(self):
        scheduler, (r0, r1) = self._scheduler()
        job = _job()
        spec, _ = scheduler.take(r0, job)
        scheduler.put_back(UnitSpec(spec.en2_counter, spec.start + 4096, spec.count - 4096))
        scheduler.issue(r0, job, UnitSpec(spec.en2_counter, spec.start, 4096), Fraction(1))
        rest, resumed = scheduler.take(r1, job)
        self.assertTrue(resumed)
        self.assertEqual((rest.start, rest.count), (4096, (1 << 24) - 4096))
        scheduler.issue(r1, job, rest, Fraction(1))
        scheduler.registry.assert_disjoint()

    def test_a_version_mask_change_never_reissues_a_range(self):
        scheduler, (r0, r1) = self._scheduler()
        job = _job()
        spec, _ = scheduler.take(r0, job, 0)
        first = scheduler.issue(r0, job, spec, Fraction(1), 0)  # still in flight
        # The pool grants rolling: the schedule restarts in the new version space, and the
        # header of version index 0 (the job's own version) is the same header as before.
        spec, _resumed = scheduler.take(r1, job, 0x1FFFE000)
        self.assertEqual((spec.version_index, spec.start), (0, first.start + first.count))
        scheduler.issue(r1, job, spec, Fraction(1), 0x1FFFE000)
        scheduler.registry.assert_disjoint()

    def test_a_held_back_range_is_trimmed_to_the_size_of_the_route_that_takes_it(self):
        scheduler, (fast, slow) = self._scheduler()
        fast.sizer.unit_size = 1 << 27  # e.g. a GPU route next to the CPU route (1 << 24)
        job = _job()
        spec, _ = scheduler.take(fast, job)
        self.assertEqual(spec.count, 1 << 27)
        # The ceiling admits 4096 of the fast route's unit; the rest is held back.
        scheduler.put_back(UnitSpec(spec.en2_counter, spec.start + 4096, spec.count - 4096))
        first = scheduler.issue(fast, job, UnitSpec(spec.en2_counter, spec.start, 4096), Fraction(1))
        part, resumed = scheduler.take(slow, job)
        self.assertTrue(resumed)
        self.assertEqual((part.start, part.count), (4096, 1 << 24))
        second = scheduler.issue(slow, job, part, Fraction(1))
        rest, resumed = scheduler.take(fast, job)
        self.assertTrue(resumed)
        self.assertEqual((rest.start, rest.count), (4096 + (1 << 24), (1 << 27) - 4096 - (1 << 24)))
        third = scheduler.issue(fast, job, rest, Fraction(1))
        scheduler.registry.assert_disjoint()
        covered = sorted((u.start, u.start + u.count) for u in (first, second, third))
        self.assertEqual(covered, [(0, 4096), (4096, 4096 + (1 << 24)), (4096 + (1 << 24), 1 << 27)])
        following, resumed = scheduler.take(slow, job)
        self.assertFalse(resumed)
        self.assertEqual((following.start, following.count), (1 << 27, 1 << 24))

    def test_a_new_job_starts_a_new_schedule(self):
        scheduler, (r0, _r1) = self._scheduler()
        unit = scheduler.issue(r0, _job("j1"), scheduler.take(r0, _job("j1"))[0], Fraction(1))
        scheduler.complete(r0, unit)
        self.assertEqual(scheduler.registry.issued(unit_key(unit)), [(0, 1 << 24)])
        spec, _ = scheduler.take(r0, _job("j2"))
        self.assertEqual((spec.en2_counter, spec.start), (0, 0))
        # The replaced job's ranges are retired; the new job's units are new headers.
        self.assertEqual(scheduler.registry.issued(unit_key(unit)), [])

    def test_a_resent_job_id_with_a_new_header_is_scheduled_from_the_start(self):
        scheduler, (r0, r1) = self._scheduler()
        old = _job("j1")
        spec, _ = scheduler.take(r0, old)
        scheduler.complete(r0, scheduler.issue(r0, old, spec, Fraction(1)))
        # The pool re-sends job_id "j1" with a new ntime: different work under the same job_id.
        resent = replace(old, job=replace(old.job, ntime=f"{(int(old.job.ntime, 16) + 1) & 0xFFFFFFFF:08x}"))
        spec, resumed = scheduler.take(r1, resent)
        self.assertFalse(resumed)
        self.assertEqual((spec.en2_counter, spec.start), (0, 0))
        unit = scheduler.issue(r1, resent, spec, Fraction(1))
        scheduler.registry.assert_disjoint()
        self.assertEqual(scheduler.registry.issued(unit_key(unit)), [(0, 1 << 24)])
        # A clean_jobs re-send of the identical header is new work too (clean_seq is part of the key).
        scheduler.complete(r1, unit)
        again = replace(resent, clean_seq=resent.clean_seq + 1)
        spec, _ = scheduler.take(r0, again)
        self.assertEqual((spec.en2_counter, spec.start), (0, 0))


class _StandInMetal(StandInLane):
    """Stand-in for an Apple GPU lane: Mode A computing under the Metal route name (test only)."""

    def __init__(self) -> None:
        super().__init__(ROUTE_METAL)


class TestSelection(unittest.TestCase):
    def test_parse_routes(self):
        self.assertEqual(parse_routes("auto"), ("auto",))
        self.assertEqual(parse_routes("mode_a,metal,igpu"), ("igpu", "metal"))
        self.assertEqual(parse_routes("opencl,igpu"), ("opencl", "igpu"))
        for bad in ("", "igpu,cuda", "warp"):
            with self.assertRaises(ValueError):
                parse_routes(bad)

    def test_routes_auto_without_metal_degrades_to_mode_a_and_records_why(self):
        def absent():
            raise LaneUnavailable("no device")

        selection = select_routes(("auto",), mode_a_workers=1, open_metal=absent, full_window=False)
        try:
            self.assertEqual([route.executed for route, _ in selection.routes], [ROUTE_MODE_A])
            self.assertEqual(len(selection.unavailable), 1)
            entry = selection.unavailable[0]
            self.assertEqual((entry["route"], entry["backend"], entry["stage"]), (ROUTE_METAL, "metal", "detect"))
            self.assertTrue(entry["reason"].startswith("METAL_UNAVAILABLE"))
            self.assertTrue(selection.degraded_reason.startswith("METAL_UNAVAILABLE"))
            self.assertTrue(all(check.passed for check in selection.checks))
            self.assertFalse(selection.routes[0][1].always_pool)
        finally:
            selection.close()

    def test_routes_auto_with_faulty_metal_blocks(self):
        def broken():
            raise LaneFault("the Metal compiler rejected the plan kernel")

        selection = select_routes(("auto",), mode_a_workers=1, open_metal=broken, full_window=False)
        self.assertEqual(selection.routes, [])
        self.assertIn("Metal lane builds", [c.name for c in selection.checks if not c.passed])

    def test_routes_auto_with_metal_selects_both_in_prefer_order(self):
        for prefer, expected in (("ours", [ROUTE_MODE_A, ROUTE_METAL]), ("host", [ROUTE_METAL, ROUTE_MODE_A])):
            selection = select_routes(("auto",), prefer=prefer, mode_a_workers=1, open_metal=_StandInMetal,
                                      full_window=False)
            try:
                self.assertTrue(all(check.passed for check in selection.checks))
                self.assertEqual([route.executed for route, _ in selection.routes], expected)
                for route, lane in selection.routes:
                    self.assertEqual(route.executed, lane.route)
                    self.assertEqual(route.executed_backend, "igpu" if lane.route == ROUTE_MODE_A else "metal")
                    self.assertEqual(route.preference, prefer)
                mode_a = next(lane for route, lane in selection.routes if route.executed == ROUTE_MODE_A)
                self.assertTrue(mode_a.always_pool)
                self.assertEqual(selection.unavailable, [])
                self.assertIsNone(selection.degraded_reason)
            finally:
                selection.close()

    def test_strict_igpu_metal_without_metal_fails_closed(self):
        def absent():
            raise LaneUnavailable("no device")

        selection = select_routes(("igpu", "metal"), mode_a_workers=1, open_metal=absent, full_window=False)
        self.assertEqual(selection.routes, [])
        self.assertIn("Metal lane present", [c.name for c in selection.checks if not c.passed])


class TestRuntime(unittest.TestCase):
    def test_two_routes_mine_disjoint_units_of_one_itinerary(self):
        log: list = []
        units = _small_units(8)
        code, records, verified, pool = _run(
            lambda pool, box: [Recording(_mode_a(), log, box), Recording(_stand_in(), log, box)], units)
        self.assertEqual(code, EXIT_OK)
        dispatched = sorted((en2, start, count) for _r, _j, en2, start, count, _u in log)
        self.assertEqual(dispatched, sorted((u.en2_counter, u.start, u.count) for u in units))
        routes = {route for route, *_ in log}
        self.assertEqual(routes, {ROUTE_MODE_A, STAND_IN})
        work = _of(records, "work")
        by_route = {w["route"]: w for w in work}
        self.assertEqual(set(by_route), {ROUTE_MODE_A, STAND_IN})
        self.assertEqual(by_route[ROUTE_MODE_A]["slot"], "r0")
        self.assertEqual(by_route[ROUTE_MODE_A]["compute_unit"], "cpu_performance_cores")
        self.assertEqual(by_route[STAND_IN]["slot"], "r1")
        self.assertEqual(len(_of(records, "route_started")), 2)
        stopped = _of(records, "route_stopped")
        self.assertEqual(len(stopped), 2)
        self.assertEqual(sum(s["executed"] for s in stopped), 8 * 4096)
        self.assertEqual(sum(w["executed"] for w in work), 8 * 4096)
        start = _of(records, "session_start")[0]
        self.assertEqual(start["executed_routes"], [ROUTE_MODE_A, STAND_IN])
        self.assertEqual(start["executed_route"], f"{ROUTE_MODE_A}+{STAND_IN}")
        self.assertEqual(start["scheduler"]["kind"], "shared_itinerary")
        submitted = _of(records, "share_submitted")
        self.assertTrue(submitted)
        self.assertTrue(all(s["route"] in (ROUTE_MODE_A, STAND_IN) for s in submitted))
        summary = summarize(records)
        self.assertEqual(summary["shares"]["accepted"], len(pool.accepted))
        self.assertEqual(summary["route"]["executed_routes"], [ROUTE_MODE_A, STAND_IN])
        self.assertTrue(verified)

    def test_inflight_units_are_disjoint_while_both_routes_run(self):
        log: list = []
        both = {}

        async def barrier(recording, unit):
            both.setdefault("events", {}).setdefault(recording.route.executed, asyncio.Event()).set()
            other = STAND_IN if recording.route.executed == ROUTE_MODE_A else ROUTE_MODE_A
            event = both["events"].setdefault(other, asyncio.Event())
            try:
                await asyncio.wait_for(event.wait(), timeout=10)
            except asyncio.TimeoutError:
                pass

        box: dict = {}
        code, records, verified, _pool = _run(
            lambda pool, b: [Recording(_mode_a(), log, b, barrier), Recording(_stand_in(), log, b, barrier)],
            _small_units(4), box=box)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(box["peak"], 2)
        self.assertEqual(_of(records, "scheduler_invariant_violated"), [])
        self.assertTrue(verified)

    def test_fault_on_one_route_stops_every_route(self):
        log: list = []
        code, records, _verified, _pool = _run(
            lambda pool, box: [Recording(_mode_a(), log, box),
                               Recording(_stand_in(mutate=lambda u, r: replace(r, probe_words=(0,) * 8)), log, box)],
            _small_units(6))
        self.assertEqual(code, EXIT_DEVICE_FAULT)
        faults = _of(records, "device_fault")
        self.assertEqual(len(faults), 1)
        self.assertEqual(faults[0]["route"], STAND_IN)
        self.assertEqual(faults[0]["other_routes_stopped"], [ROUTE_MODE_A])
        faulty_units = {entry[5] for entry in log if entry[0] == STAND_IN}
        self.assertFalse([s for s in _of(records, "share_submitted") if s["unit_id"] in faulty_units])
        self.assertEqual(len(_of(records, "route_stopped")), 2)
        self.assertEqual(len(log), len({entry[5] for entry in log}))
        summary = summarize(records)
        self.assertEqual(summary["state"], "STOPPED")
        self.assertIsNotNone(summary["device_fault"])

    def test_lane_reporting_another_route_than_its_slot_is_a_device_fault(self):
        code, records, _verified, _pool = _run([_stand_in(route=ROUTE_METAL, slot_route=STAND_IN)], _small_units(2))
        self.assertEqual(code, EXIT_DEVICE_FAULT)
        self.assertIn("route mismatch", _of(records, "device_fault")[0]["reason"])
        self.assertFalse([w for w in _of(records, "work") if w["route"] == ROUTE_METAL])

    def test_overlapping_itinerary_fails_closed_as_a_scheduler_fault(self):
        overlapping = (UnitSpec(0, 0, 4096), UnitSpec(0, 2048, 4096))
        for two_routes in (False, True):
            log: list = []

            def build(pool, box):
                dispatchers = [Recording(_mode_a(), log, box)]
                if two_routes:
                    dispatchers.append(Recording(_stand_in(), log, box))
                return dispatchers

            with self.subTest(two_routes=two_routes):
                code, records, verified, _pool = _run(build, overlapping)
                self.assertEqual(code, EXIT_SCHEDULER_FAULT)
                violated = _of(records, "scheduler_invariant_violated")
                self.assertEqual(len(violated), 1)
                self.assertEqual((violated[0]["unit"]["start"], violated[0]["unit"]["end"]), (2048, 6144))
                self.assertEqual(violated[0]["conflict"]["start"], 0)
                self.assertEqual(len(log), 1)
                self.assertEqual(_of(records, "session_stop")[0]["exit_code"], EXIT_SCHEDULER_FAULT)
                self.assertTrue(verified)

    def test_clean_jobs_reaches_every_route(self):
        log: list = []

        async def clean_jobs_once(recording, unit):
            box = recording.box
            if box.get("fired") or recording.route.executed != ROUTE_MODE_A:
                return
            box["fired"] = True
            # Both routes hold a genesis unit before the pool replaces the job.
            await _wait_until(lambda: len(box["runtime"].scheduler.registry) == 2)
            await box["pool"].push_job("job-new", "495fab2c", clean=True)

        def build(pool, box):
            box["pool"] = pool
            # Each lane holds its genesis unit until it is aborted, so neither route can
            # finish before the clean_jobs notify is processed (no timing dependence).
            mode_a = LocalIGPUDispatcher(HoldUntilAborted(ModeALane(workers=1)), MODE_A_ROUTE)
            stand_in = LocalIGPUDispatcher(HoldUntilAborted(StandInLane()), Route("auto", STAND_IN, None))
            return [Recording(mode_a, log, box, clean_jobs_once), Recording(stand_in, log, box)]

        code, records, verified, pool = _run(build, _small_units(2, size=1 << 16))
        self.assertEqual(code, EXIT_OK)
        self.assertTrue(all(d["job_id"] == "genesis" for d in _of(records, "share_stale_dropped")))
        self.assertTrue(all(s["job_id"] == "job-new" for s in _of(records, "share_submitted")))
        self.assertFalse([p for p, _ in pool.rejected if p[1] == "genesis"])
        aborted = _of(records, "unit_aborted_stale")
        self.assertEqual(sorted(a["route"] for a in aborted), sorted([ROUTE_MODE_A, STAND_IN]))
        self.assertTrue(all(a["job_id"] == "genesis" and a["reason"] == "clean_jobs" for a in aborted))
        # The abort reached each lane before it registered the unit: the lane refused the
        # unit (stopped early, nothing executed) instead of hashing the stale job to the end.
        self.assertTrue(all((a["outcome"], a["executed_so_far"], a["device_stop"]) == ("stopped_early", 0, "signalled")
                            for a in aborted), aborted)
        new = sorted((start, start + count) for _r, job, _e, start, count, _u in log if job == "job-new")
        self.assertEqual(new, [(0, 1 << 16), (1 << 16, 2 << 16)])
        self.assertTrue(verified)

    def test_hashrate_cap_is_shared_by_both_routes(self):
        rate = 6000
        clock = FakeClock()

        class LoggingCap(HashrateCap):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.allowed = 0
                self.refunded = 0

            def allow(self, requested, now_ns=None):
                got = super().allow(requested, now_ns)
                self.allowed += got
                return got

            def refund(self, count, now_ns=None):
                self.refunded += count
                return super().refund(count, now_ns)

        cap = LoggingCap(rate, clock=clock)
        log: list = []
        times: list = []

        async def stamp(recording, unit):
            times.append((clock.now_ns, unit.count))

        gate = CapGate(sleeper=fake_sleeper(clock), monotonic_ns=clock)
        code, records, verified, _pool = _run(
            lambda pool, box: [Recording(_mode_a(), log, box, stamp), Recording(_stand_in(), log, box, stamp)],
            _small_units(4, size=8192), gate=gate, cap=cap)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual({route for route, *_ in log}, {ROUTE_MODE_A, STAND_IN})
        executed = sum(s["executed"] for s in _of(records, "route_stopped"))
        self.assertEqual(executed, 4 * 8192)
        self.assertEqual(cap.allowed - cap.refunded, executed)
        dispatched = 0
        for at_ns, count in sorted(times):
            dispatched += count
            self.assertLessEqual(dispatched, rate + rate * at_ns // 10 ** 9)
        ranges = sorted((start, start + count) for _r, _j, _e, start, count, _u in log)
        position = 0
        for start, end in ranges:
            self.assertEqual(start, position)
            position = end
        self.assertEqual(position, 4 * 8192)
        self.assertTrue(verified)

    def test_session_start_names_every_executing_backend(self):
        metal_route = BackendRoute("auto", ROUTE_METAL, None, "auto", "ours", ("igpu", "metal"), "metal")
        mode_a_route = BackendRoute("auto", ROUTE_MODE_A, None, "auto", "ours", ("igpu", "metal"), "igpu")
        code, records, verified, _pool = _run(
            lambda pool, box: [LocalIGPUDispatcher(ModeALane(workers=1), mode_a_route),
                               LocalIGPUDispatcher(_StandInMetal(), metal_route)],
            _small_units(4))
        self.assertEqual(code, EXIT_OK)
        start = _of(records, "session_start")[0]
        self.assertEqual(start["executed_route"], f"{ROUTE_MODE_A}+{ROUTE_METAL}")
        self.assertEqual(start["executed_backend"], "igpu+metal")
        self.assertEqual(start["executed_backends"], ["igpu", "metal"])
        self.assertEqual(start["detected_backends"], ["igpu", "metal"])
        self.assertEqual((start["requested_backend"], start["preference"]), ("auto", "ours"))
        summary = summarize(records)
        self.assertEqual(summary["route"]["executed_backend"], "igpu+metal")
        self.assertEqual(summary["route"]["executed_backends"], ["igpu", "metal"])
        self.assertIn("Backend      igpu+metal (requested auto, prefer ours; detected igpu, metal)",
                      render_text(summary))
        self.assertTrue(verified)

    def test_single_dispatcher_is_one_slot_and_records_are_unchanged(self):
        code, records, verified, _pool = _run([_mode_a()], _small_units(2))
        self.assertEqual(code, EXIT_OK)
        start = _of(records, "session_start")[0]
        self.assertEqual(start["executed_route"], ROUTE_MODE_A)
        self.assertEqual(start["executed_routes"], [ROUTE_MODE_A])
        self.assertEqual((start["executed_backend"], start["executed_backends"]), ("igpu", ["igpu"]))
        self.assertFalse(start["degraded"])
        self.assertEqual(len(_of(records, "route_started")), 1)
        stopped = _of(records, "route_stopped")
        self.assertEqual([(s["route"], s["state"], s["executed"]) for s in stopped], [(ROUTE_MODE_A, "exhausted", 8192)])
        self.assertEqual(_of(records, "session_stop")[0]["reason"], "itinerary complete")
        self.assertEqual(summarize(records)["route"]["label"], ROUTE_LABELS[ROUTE_MODE_A])
        self.assertTrue(verified)

    def test_degraded_selection_is_recorded_in_the_ledger(self):
        reason = "METAL_UNAVAILABLE: test"
        code, records, _verified, _pool = _run(
            [_mode_a()], _small_units(1),
            unavailable_routes=({"route": ROUTE_METAL, "backend": "metal", "reason": reason, "stage": "detect"},),
            degraded_reason=reason, requested_routes=("auto",))
        self.assertEqual(code, EXIT_OK)
        self.assertEqual([(u["route"], u["reason"]) for u in _of(records, "route_unavailable")], [(ROUTE_METAL, reason)])
        start = _of(records, "session_start")[0]
        self.assertTrue(start["degraded"])
        self.assertEqual(start["requested_routes"], ["auto"])
        summary = summarize(records)
        self.assertEqual(summary["route"]["degraded_reason"], reason)
        self.assertIn("Degraded", render_text(summary))

    def test_two_dispatchers_for_one_route_are_refused(self):
        with TempHome() as home:
            ledger = Ledger(home.layout.ledger, home.layout.ledger_lock)
            first, second = _mode_a(), _mode_a()
            try:
                with self.assertRaises(ValueError):
                    MinerRuntime(home.layout, ledger, home.store(), [first, second], "viabtc", RuntimeOptions())
                with self.assertRaises(ValueError):
                    MinerRuntime(home.layout, ledger, home.store(), [], "viabtc", RuntimeOptions())
            finally:
                first.close()
                second.close()


async def _wait_until(predicate, timeout: float = 30.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not reached in time")
        await asyncio.sleep(0.01)


if __name__ == "__main__":
    unittest.main()
