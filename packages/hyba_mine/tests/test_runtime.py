# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""End-to-end runtime: verifying pool, Chronus iGPU Mode A, ledger and status."""

import asyncio
import unittest
from dataclasses import replace
from fractions import Fraction

import _support
from _support import GENESIS_EN2, GENESIS_NONCE, FakeClock, TempHome, VerifyingPool, fake_sleeper, small_cap

from chronus.execution.hashrate_cap import override_process_cap, process_cap


from hyba_mine.control import block_for, request_pool_switch
from hyba_mine.dispatch import DispatchError, LocalIGPUDispatcher
from hyba_mine.igpu import ROUTE_MODE_A, BackendRoute, ModeALane
from hyba_mine.ledger import Ledger
from hyba_mine.plan import NoncePlan, PythiaItinerary, UnitSpec
from hyba_mine.runtime import EXIT_DEVICE_FAULT, EXIT_LOGIN_REJECTED, EXIT_OK, MinerRuntime, RuntimeOptions
from hyba_mine.status import summarize
from hyba_mine.throttle import CapGate
from hyba_mine.vectors import GENESIS
from hyba_mine.work import AbortReport, Hit, UnitAborted, roll_version

ROUTE = BackendRoute("auto", ROUTE_MODE_A, None, "auto", "ours", ("igpu",), "igpu")


def _dispatcher():
    return LocalIGPUDispatcher(ModeALane(workers=1), ROUTE)


def _records(source) -> list:
    return list(source.records()) if isinstance(source, Ledger) else list(source)


def _kinds(source) -> list:
    return [record["kind"] for record in _records(source)]


def _of(source, kind: str) -> list:
    return [record["data"] for record in _records(source) if record["kind"] == kind]


def _genesis_unit() -> UnitSpec:
    plan = NoncePlan.for_header(GENESIS.prefix)
    position = plan.position_of(GENESIS_NONCE)
    return UnitSpec(1, position - position % plan.lane_size, plan.lane_size)


def _small_units(count: int, en2: int = 0, size: int = 4096) -> tuple:
    return tuple(UnitSpec(en2, i * size, size) for i in range(count))


class Harness:
    def __init__(self, home: TempHome, pools: dict, dispatcher=None, **options) -> None:
        self.home = home
        self.ledger = Ledger(home.layout.ledger, home.layout.ledger_lock)
        endpoints = {pool_id: (pool.endpoint(),) for pool_id, pool in pools.items()}
        defaults = dict(endpoints=endpoints, backoff=(0.05,), stats_interval=0.2, control_interval=0.1,
                        submit_timeout=5.0)
        defaults.update(options)
        self.runtime = MinerRuntime(home.layout, self.ledger, home.store(), dispatcher or _dispatcher(),
                                    next(iter(pools)), RuntimeOptions(**defaults))


class TestEndToEnd(unittest.TestCase):
    def test_genesis_share_found_on_the_igpu_rechecked_and_accepted_by_a_verifying_pool(self):
        async def scenario(home):
            pool = VerifyingPool(difficulty=1)
            await pool.start()
            home.put_login("viabtc")
            itinerary = PythiaItinerary(override=(_genesis_unit(),))
            h = Harness(home, {"viabtc": pool}, itinerary=itinerary, stop_when_itinerary_ends=True)
            code = await h.runtime.run()
            await pool.stop()
            return code, h.ledger, pool

        with TempHome() as home:
            code, ledger, pool = _support.run(scenario(home))
            self.assertEqual(code, EXIT_OK)
            submitted = _of(ledger, "share_submitted")
            self.assertEqual(len(submitted), 1)
            self.assertEqual(submitted[0]["nonce"], f"{GENESIS_NONCE:08x}")
            self.assertEqual(submitted[0]["en2"], GENESIS_EN2.hex())
            self.assertEqual(submitted[0]["hash"], "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f")
            self.assertTrue(submitted[0]["block_candidate"])
            replies = _of(ledger, "pool_response")
            self.assertEqual(len(replies), 1)
            self.assertTrue(replies[0]["accepted"])
            self.assertEqual(replies[0]["reply"]["result"], True)
            self.assertEqual(len(pool.accepted), 1)
            work = _of(ledger, "work")
            self.assertEqual(sum(w["executed"] for w in work), NoncePlan.for_header(GENESIS.prefix).lane_size)
            self.assertTrue(all(w["route"] == ROUTE_MODE_A and w["device_ns"] > 0 for w in work))
            self.assertTrue(ledger.verify().ok)
            summary = summarize(ledger.records())
            self.assertEqual(summary["shares"]["accepted"], 1)
            self.assertEqual(summary["shares"]["rejected"], 0)
            self.assertEqual(summary["route"]["executed"], ROUTE_MODE_A)
            self.assertIsNone(summary["route"]["fallback_reason"])
            self.assertEqual((summary["route"]["executed_backend"], summary["route"]["preference"]), ("igpu", "ours"))
            self.assertTrue(all(w["executed_backend"] == "igpu" and w["requested_backend"] == "auto" for w in work))
            self.assertEqual(summary["state"], "STOPPED")

    def test_many_shares_counted_only_from_pool_replies(self):
        async def scenario(home):
            pool = VerifyingPool(difficulty=Fraction(1, 10 ** 7))
            await pool.start()
            home.put_login("braiins")
            itinerary = PythiaItinerary(override=_small_units(3))
            h = Harness(home, {"braiins": pool}, itinerary=itinerary, stop_when_itinerary_ends=True)
            code = await h.runtime.run()
            await pool.stop()
            return code, h.ledger, pool

        with TempHome() as home:
            code, ledger, pool = _support.run(scenario(home))
            self.assertEqual(code, EXIT_OK)
            summary = summarize(ledger.records())
            self.assertGreater(summary["shares"]["submitted"], 0)
            self.assertEqual(summary["shares"]["accepted"], len(pool.accepted))
            self.assertEqual(summary["shares"]["rejected"], len(pool.rejected))
            self.assertEqual(summary["shares"]["submitted"], len(pool.accepted) + len(pool.rejected))
            for share in _of(ledger, "share_submitted"):
                self.assertEqual(share["host_recheck"], "passed")
                self.assertLessEqual(int(share["hash"], 16), int(share["share_target"], 16))
                self.assertIsNone(share["version_bits_submitted"])
            # The default test pool has no BIP310, so submits stay at 5 params.
            self.assertTrue(all(len(params) == 5 for params, _ in pool.accepted + pool.rejected))
            self.assertEqual(summary["pool"]["version_rolling"]["active"], False)
            self.assertEqual(summary["pool"]["version_rolling"]["negotiation"], "unsupported")


class TestStaleAndSilence(unittest.TestCase):
    def test_hits_of_a_job_replaced_by_clean_jobs_are_dropped_not_submitted(self):
        class CleanJobDuringUnit:
            def __init__(self, inner, pool, runtime_box):
                self.inner, self.pool, self.box, self.route, self.fired = inner, pool, runtime_box, inner.route, False

            def describe(self):
                return self.inner.describe()

            async def run(self, unit):
                result = await self.inner.run(unit)
                if not self.fired:
                    self.fired = True
                    await self.pool.push_job("job-new", "495fab2c", clean=True)
                    session = self.box[0].session
                    for _ in range(200):
                        if session.current is not None and session.current.job_id == "job-new":
                            break
                        await asyncio.sleep(0.01)
                return result

            def close(self):
                self.inner.close()

        async def scenario(home):
            pool = VerifyingPool(difficulty=Fraction(1, 10 ** 7))
            await pool.start()
            home.put_login("viabtc")
            box = []
            dispatcher = CleanJobDuringUnit(_dispatcher(), pool, box)
            h = Harness(home, {"viabtc": pool}, dispatcher=dispatcher,
                        itinerary=PythiaItinerary(override=_small_units(1)), stop_when_itinerary_ends=True)
            box.append(h.runtime)
            code = await h.runtime.run()
            await pool.stop()
            return code, h.ledger, pool

        with TempHome() as home:
            code, ledger, pool = _support.run(scenario(home))
            self.assertEqual(code, EXIT_OK)
            dropped = _of(ledger, "share_stale_dropped")
            self.assertGreater(len(dropped), 0)
            self.assertTrue(all(d["job_id"] == "genesis" for d in dropped))
            submitted = _of(ledger, "share_submitted")
            self.assertTrue(all(s["job_id"] == "job-new" for s in submitted))
            self.assertFalse([p for p, _ in pool.rejected if p[1] == "genesis"])

    def test_a_share_without_a_pool_reply_is_never_counted_as_accepted(self):
        async def scenario(home):
            pool = VerifyingPool(difficulty=Fraction(1, 10 ** 7), reply_to_submits=False)
            await pool.start()
            home.put_login("viabtc")
            h = Harness(home, {"viabtc": pool}, submit_timeout=0.3,
                        itinerary=PythiaItinerary(override=_small_units(1)), stop_when_itinerary_ends=True)
            code = await h.runtime.run()
            await pool.stop()
            return code, h.ledger

        with TempHome() as home:
            code, ledger = _support.run(scenario(home))
            summary = summarize(ledger.records())
            self.assertGreater(summary["shares"]["submitted"], 0)
            self.assertEqual(summary["shares"]["accepted"], 0)
            self.assertEqual(summary["shares"]["rejected"], 0)
            self.assertEqual(summary["shares"]["awaiting_or_unacknowledged"], summary["shares"]["submitted"])
            self.assertEqual(len(_of(ledger, "share_unacknowledged")), summary["shares"]["submitted"])


class TestFailClosed(unittest.TestCase):
    def _faulty(self, mutate):
        inner = _dispatcher()

        class Faulty:
            route = inner.route

            def describe(self):
                return inner.describe()

            async def run(self, unit):
                return mutate(unit, await inner.run(unit))

            def close(self):
                inner.close()

        return Faulty()

    def _run_with(self, dispatcher, difficulty=Fraction(1, 10 ** 7)):
        async def scenario(home):
            pool = VerifyingPool(difficulty=difficulty)
            await pool.start()
            home.put_login("viabtc")
            h = Harness(home, {"viabtc": pool}, dispatcher=dispatcher,
                        itinerary=PythiaItinerary(override=_small_units(2)), stop_when_itinerary_ends=True)
            code = await h.runtime.run()
            await pool.stop()
            return code, list(h.ledger.records()), pool

        with TempHome() as home:
            return _support.run(scenario(home))

    def test_wrong_probe_digest_stops_mining_as_a_device_fault(self):
        code, ledger, pool = self._run_with(self._faulty(lambda u, r: replace(r, probe_words=(0,) * 8)))
        self.assertEqual(code, EXIT_DEVICE_FAULT)
        self.assertIn("device_fault", _kinds(ledger))
        self.assertEqual(_of(ledger, "share_submitted"), [])
        self.assertEqual(pool.accepted + pool.rejected, [])

    def test_device_hit_that_fails_the_host_recheck_is_never_submitted(self):
        def forge(unit, result):
            offset = next(o for o in range(unit.count) if all(h.offset != o for h in result.hits))
            fake = Hit(offset, unit.plan.nonce_at(unit.start + offset))
            return replace(result, hits=(fake,))

        code, ledger, pool = self._run_with(self._faulty(forge), difficulty=1)
        self.assertEqual(code, EXIT_DEVICE_FAULT)
        self.assertIn("host SHA-256d recheck rejected", _of(ledger, "device_fault")[0]["reason"])
        self.assertEqual(_of(ledger, "share_submitted"), [])
        self.assertEqual(pool.accepted + pool.rejected, [])

    def test_no_job_means_no_hashing(self):
        async def scenario(home):
            pool = VerifyingPool(send_notify=False)
            await pool.start()
            home.put_login("viabtc")
            h = Harness(home, {"viabtc": pool}, max_seconds=1.0)
            code = await h.runtime.run()
            await pool.stop()
            return code, h.ledger

        with TempHome() as home:
            code, ledger = _support.run(scenario(home))
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(_of(ledger, "work"), [])
            self.assertIsNone(summarize(ledger.records())["hashrate"]["hashrate_hs"])

    def test_rejected_login_stops_and_blocks_the_pool(self):
        async def scenario(home):
            pool = VerifyingPool(password="the-pool-expects-this")
            await pool.start()
            home.put_login("viabtc")
            h = Harness(home, {"viabtc": pool})
            code = await h.runtime.run()
            await pool.stop()
            return code, h.ledger, pool

        with TempHome() as home:
            code, ledger, pool = _support.run(scenario(home))
            self.assertEqual(code, EXIT_LOGIN_REJECTED)
            self.assertIsNotNone(block_for(home.layout, "viabtc"))
            self.assertEqual(_of(ledger, "work"), [])
            self.assertEqual(_kinds(ledger).count("pool_auth_rejected"), 1)


class TestLivePoolSwitch(unittest.TestCase):
    def test_switch_pool_from_the_console_while_mining(self):
        async def scenario(home):
            first, second = VerifyingPool(difficulty=Fraction(1, 10 ** 7)), VerifyingPool(difficulty=Fraction(1, 10 ** 7))
            await first.start()
            await second.start()
            home.put_login("viabtc")
            home.put_login("braiins")
            h = Harness(home, {"viabtc": first, "braiins": second},
                        itinerary=PythiaItinerary(override=_small_units(1)))
            task = asyncio.create_task(h.runtime.run())
            await _wait_for(h.ledger, "work")
            refused = request_pool_switch(home.layout, "nicehash")
            await _wait_for(h.ledger, "pool_switch_refused")
            request = request_pool_switch(home.layout, "braiins")
            await _wait_for(h.ledger, "pool_switch_applied")
            await _wait_until(lambda: len(second.accepted) > 0)
            h.runtime.request_stop("test complete")
            code = await task
            await first.stop()
            await second.stop()
            return code, h.ledger, refused, request, first, second

        with TempHome() as home:
            code, ledger, refused, request, first, second = _support.run(scenario(home), timeout=120)
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(_of(ledger, "pool_switch_refused")[0]["request_id"], refused["request_id"])
            applied = _of(ledger, "pool_switch_applied")[0]
            self.assertEqual((applied["from"], applied["to"], applied["request_id"]), ("viabtc", "braiins", request["request_id"]))
            pools = [d["pool"] for d in _of(ledger, "pool_connected")]
            self.assertEqual(pools[:2], ["viabtc", "braiins"])
            summary = summarize(ledger.records())
            self.assertEqual(summary["pool"]["pool_id"], "braiins")
            self.assertEqual(summary["shares"]["accepted"], len(first.accepted) + len(second.accepted))
            share_ids = [s["share_id"] for s in _of(ledger, "share_submitted")]
            self.assertEqual(len(share_ids), len(set(share_ids)))


class TestRefusedPoolSwitch(unittest.TestCase):
    def test_a_refused_switch_never_interrupts_the_unit_in_flight(self):
        class HoldFirstUnit:
            def __init__(self, inner):
                self.inner, self.route = inner, inner.route
                self.started = asyncio.Event()
                self.release = asyncio.Event()
                self.units = 0

            def describe(self):
                return self.inner.describe()

            async def run(self, unit):
                self.units += 1
                if self.units == 1:
                    self.started.set()
                    await self.release.wait()
                return await self.inner.run(unit)

            async def abort(self, unit_id, grace):
                self.release.set()
                return await self.inner.abort(unit_id, grace)

            def close(self):
                self.inner.close()

        async def scenario(home):
            pool = VerifyingPool(difficulty=Fraction(1, 10 ** 7))
            await pool.start()
            home.put_login("viabtc")
            held = HoldFirstUnit(_dispatcher())
            h = Harness(home, {"viabtc": pool}, dispatcher=held, itinerary=PythiaItinerary(override=_small_units(1)),
                        stop_when_itinerary_ends=True)
            task = asyncio.create_task(h.runtime.run())
            await asyncio.wait_for(held.started.wait(), 30)
            refused = request_pool_switch(home.layout, "nicehash")  # no stored login
            await _wait_for(h.ledger, "pool_switch_refused")
            held.release.set()
            code = await task
            await pool.stop()
            _snapshot(h)
            return code, h, refused

        with TempHome() as home:
            code, h, refused = _support.run(scenario(home), timeout=120)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(_of(h.records, "pool_switch_refused")[0]["request_id"], refused["request_id"])
        self.assertEqual(_of(h.records, "unit_aborted_stale"), [])
        self.assertEqual(sum(w["executed"] for w in _of(h.records, "work")), 4096)
        self.assertEqual(_of(h.records, "pool_switch_applied"), [])


def _snapshot(h) -> None:
    """Read the ledger before the temporary home is removed."""
    h.records = list(h.ledger.records())
    h.verified = h.ledger.verify().ok


class _Counting:
    """Records every unit the runtime dispatches (fake time, en2, start, count)."""

    def __init__(self, inner, clock, before=None, after=None):
        self.inner, self.clock, self.route = inner, clock, inner.route
        self.before, self.after = before, after
        self.units: list = []

    def describe(self):
        return self.inner.describe()

    async def run(self, unit):
        self.units.append((self.clock.now_ns, unit.en2.hex(), unit.start, unit.count))
        if self.before is not None:
            await self.before(unit, len(self.units))
        result = await self.inner.run(unit)
        if self.after is not None:
            result = await self.after(unit, result, len(self.units))
        return result

    def close(self):
        self.inner.close()


class TestHashrateCap(unittest.TestCase):
    RATE = 6000

    def _run(self, dispatcher_for, *, rate=None, units=None, setup=None, waits=None, **options):
        rate = rate or self.RATE
        clock = FakeClock()
        test_cap = small_cap(rate, clock)

        async def scenario(home):
            pool = VerifyingPool(difficulty=Fraction(1, 10 ** 7))
            await pool.start()
            home.put_login("viabtc")
            if setup is not None:
                setup(home)
            dispatcher = dispatcher_for(clock, pool)
            h = Harness(home, {"viabtc": pool}, dispatcher=dispatcher,
                        itinerary=PythiaItinerary(override=units or _small_units(2, size=8192)),
                        stop_when_itinerary_ends=True, **options)
            h.runtime.gate = CapGate(sleeper=fake_sleeper(clock, waits), monotonic_ns=clock)
            code = await h.runtime.run()
            await pool.stop()
            return code, h, dispatcher, pool

        with TempHome() as home, override_process_cap(test_cap):
            code, h, dispatcher, pool = _support.run(scenario(home))
            _snapshot(h)
            return code, h, dispatcher, pool, test_cap, clock

    def test_units_are_clamped_and_coverage_stays_exact(self):
        code, h, dispatcher, _pool, _cap, _clock = self._run(lambda clock, pool: _Counting(_dispatcher(), clock))
        self.assertEqual(code, EXIT_OK)
        self.assertTrue(all(count <= self.RATE for _t, _en2, _s, count in dispatcher.units))
        self.assertGreater(len(dispatcher.units), 2)
        ranges = sorted((start, start + count) for _t, en2, start, count in dispatcher.units)
        self.assertTrue(all(en2 == dispatcher.units[0][1] for _t, en2, _s, _c in dispatcher.units))
        position = 0
        for start, end in ranges:
            self.assertEqual(start, position)
            position = end
        self.assertEqual(position, 16384)
        self.assertEqual(sum(w["executed"] for w in _of(h.records, "work")), 16384)
        self.assertTrue(h.verified)

    def test_runtime_waits_instead_of_exceeding_the_ceiling(self):
        waits: list = []
        code, _h, dispatcher, _pool, _cap, clock = self._run(lambda clock, pool: _Counting(_dispatcher(), clock),
                                                             waits=waits)
        self.assertEqual(code, EXIT_OK)
        self.assertGreater(len(waits), 0)
        self.assertGreaterEqual(clock.now_ns, (16384 - self.RATE) * 10 ** 9 // self.RATE)
        dispatched = 0
        for at_ns, _en2, _start, count in dispatcher.units:
            dispatched += count
            self.assertLessEqual(dispatched, self.RATE + self.RATE * at_ns // 10 ** 9)

    def test_ledger_records_ceiling_not_achieved_rate(self):
        code, h, _units, _pool, _cap, _clock = self._run(lambda clock, pool: _Counting(_dispatcher(), clock))
        self.assertEqual(code, EXIT_OK)
        start = _of(h.records, "session_start")[0]["hashrate_cap"]
        self.assertEqual(start["cap_h_s"], self.RATE)
        self.assertIn("not a measured rate", start["basis"])
        windows = _of(h.records, "hashrate_cap_window")
        self.assertTrue(windows)
        self.assertGreaterEqual(sum(w["clamped_units"] for w in windows), 1)
        # Windows are recorded only when the ceiling held work back, so they need not cover every grant.
        self.assertLessEqual(sum(w["granted_hashes"] for w in windows), 16384)
        self.assertTrue(all(w["cap_h_s"] == self.RATE and "not a device hashrate" in w["basis"] for w in windows))
        self.assertEqual(_of(h.records, "session_stop")[0]["hashrate_cap_h_s"], self.RATE)
        summary = summarize(h.records)
        work = _of(h.records, "work")
        measured = sum(w["executed"] for w in work) / (sum(w["device_ns"] for w in work) / 1e9)
        self.assertAlmostEqual(summary["hashrate"]["hashrate_hs"], measured)
        self.assertEqual(summary["hashrate_cap"]["cap_h_s"], self.RATE)
        self.assertEqual(summary["hashrate_cap"]["kind"], "ceiling")
        self.assertTrue(summary["hashrate_cap"]["bound_in_window"])

    def test_device_fault_does_not_refund_unknown_execution(self):
        class Broken(_Counting):
            async def run(self, unit):
                self.units.append((self.clock.now_ns, unit.en2.hex(), unit.start, unit.count))
                raise DispatchError("lane lost")

        code, h, _units, _pool, test_cap, _clock = self._run(lambda clock, pool: Broken(_dispatcher(), clock))
        self.assertEqual(code, EXIT_DEVICE_FAULT)
        self.assertEqual(test_cap.available(), 0)
        windows = _of(h.records, "hashrate_cap_window")
        self.assertEqual(sum(w["unsettled_hashes"] for w in windows), self.RATE)
        self.assertEqual(sum(w["granted_hashes"] for w in windows), self.RATE)
        self.assertEqual(sum(w["refunded_hashes"] for w in windows), 0)

    def test_short_result_refunds_unexecuted_hashes(self):
        async def short(unit, result, n):
            return replace(result, executed=result.executed - 100)

        code, h, _units, _pool, test_cap, _clock = self._run(
            lambda clock, pool: _Counting(_dispatcher(), clock, after=short))
        self.assertEqual(code, EXIT_DEVICE_FAULT)
        self.assertEqual(test_cap.available(), 100)
        self.assertEqual(sum(w["refunded_hashes"] for w in _of(h.records, "hashrate_cap_window")), 100)

    def test_aborted_unit_returns_the_hashes_it_did_not_run(self):
        class StopsOnAbort(_Counting):
            def __init__(self, inner, clock, pool):
                super().__init__(inner, clock)
                self.pool, self.released = pool, asyncio.Event()

            async def run(self, unit):
                self.units.append((self.clock.now_ns, unit.en2.hex(), unit.start, unit.count))
                if len(self.units) > 1:
                    return await self.inner.run(unit)
                await self.pool.push_job("job-new", "495fab2c", clean=True)
                await self.released.wait()
                raise UnitAborted(unit.unit_id, 1000, 1, ROUTE_MODE_A, "test-node")

            async def abort(self, unit_id, grace):
                self.released.set()
                return AbortReport(unit_id, True, "stopped_early", None, None, None, ROUTE_MODE_A, "test-node", 0)

        code, h, dispatcher, _pool, test_cap, _clock = self._run(
            lambda clock, pool: StopsOnAbort(_dispatcher(), clock, pool), units=_small_units(1, size=4096))
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(len(_of(h.records, "unit_aborted_stale")), 1)
        self.assertEqual([c for _t, _e, _s, c in dispatcher.units], [4096, 4096])
        windows = _of(h.records, "hashrate_cap_window")
        self.assertEqual(sum(w["refunded_hashes"] for w in windows), 4096 - 1000)
        self.assertEqual(test_cap.available(), self.RATE - 4096 + (4096 - 1000) - 4096)

    def test_genesis_known_answer_still_found_under_a_clamping_cap(self):
        lane = NoncePlan.for_header(GENESIS.prefix).lane_size
        clock = FakeClock()
        test_cap = small_cap(lane // 3, clock)

        async def scenario(home):
            pool = VerifyingPool(difficulty=1)
            await pool.start()
            home.put_login("viabtc")
            dispatcher = _Counting(_dispatcher(), clock)
            h = Harness(home, {"viabtc": pool}, dispatcher=dispatcher,
                        itinerary=PythiaItinerary(override=(_genesis_unit(),)), stop_when_itinerary_ends=True)
            h.runtime.gate = CapGate(sleeper=fake_sleeper(clock), monotonic_ns=clock)
            code = await h.runtime.run()
            await pool.stop()
            return code, h, dispatcher, pool

        with TempHome() as home, override_process_cap(test_cap):
            code, h, dispatcher, pool = _support.run(scenario(home))
            _snapshot(h)
        self.assertEqual(code, EXIT_OK)
        self.assertGreater(len(dispatcher.units), 1)
        self.assertTrue(all(count <= lane // 3 for _t, _e, _s, count in dispatcher.units))
        self.assertEqual(sum(count for _t, _e, _s, count in dispatcher.units), lane)
        submitted = _of(h.records, "share_submitted")
        self.assertEqual([s["nonce"] for s in submitted], [f"{GENESIS_NONCE:08x}"])
        self.assertEqual(len(pool.accepted), 1)

    def test_published_limit_before_start_is_adopted(self):
        def publish(home):
            home.cap_limit_file.write_text("0.000000000000002\n", encoding="ascii")

        code, h, dispatcher, _pool, test_cap, _clock = self._run(
            lambda clock, pool: _Counting(_dispatcher(), clock), setup=publish)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(test_cap.cap_h_s, 2000)
        self.assertEqual(_of(h.records, "session_start")[0]["hashrate_cap"]["cap_h_s"], 2000)
        self.assertTrue(all(count <= 2000 for _t, _e, _s, count in dispatcher.units))
        self.assertEqual(sum(count for _t, _e, _s, count in dispatcher.units), 16384)

    def test_published_limit_change_mid_run_is_recorded(self):
        box = {}

        def remember(home):
            box["home"] = home

        def make(clock, pool):
            async def lower_after_first(unit, result, n):
                if n == 1:
                    box["home"].cap_limit_file.write_text("0.000000000000002\n", encoding="ascii")
                    await _wait_until(lambda: box["runtime"]._cap_seen == 2000, timeout=10)
                    box["changed_at"] = n
                return result

            dispatcher = _Counting(_dispatcher(), clock, after=lower_after_first)
            box["dispatcher"] = dispatcher
            return dispatcher

        rate = self.RATE
        clock = FakeClock()
        test_cap = small_cap(rate, clock)

        async def scenario(home):
            pool = VerifyingPool(difficulty=Fraction(1, 10 ** 7))
            await pool.start()
            home.put_login("viabtc")
            remember(home)
            dispatcher = make(clock, pool)
            h = Harness(home, {"viabtc": pool}, dispatcher=dispatcher,
                        itinerary=PythiaItinerary(override=_small_units(2, size=8192)), stop_when_itinerary_ends=True)
            box["runtime"] = h.runtime
            h.runtime.gate = CapGate(sleeper=fake_sleeper(clock), monotonic_ns=clock)
            code = await h.runtime.run()
            await pool.stop()
            return code, h

        with TempHome() as home, override_process_cap(test_cap):
            code, h = _support.run(scenario(home))
            _snapshot(h)
        self.assertEqual(code, EXIT_OK)
        changed = _of(h.records, "hashrate_cap_changed")
        self.assertEqual([(c["from_h_s"], c["to_h_s"]) for c in changed], [(rate, 2000)])
        self.assertIn("not a measured rate", changed[0]["basis"])
        units = box["dispatcher"].units
        self.assertEqual(units[0][3], rate)
        self.assertTrue(all(count <= 2000 for _t, _e, _s, count in units[1:]))
        self.assertEqual(sum(count for _t, _e, _s, count in units), 16384)
        self.assertEqual(summarize(h.records)["hashrate_cap"]["cap_h_s"], 2000)

    def test_invalid_published_limit_is_ignored(self):
        def publish(home):
            home.cap_limit_file.write_text("5\n", encoding="ascii")

        code, h, dispatcher, _pool, test_cap, _clock = self._run(
            lambda clock, pool: _Counting(_dispatcher(), clock), setup=publish)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(test_cap.cap_h_s, self.RATE)
        self.assertEqual(_of(h.records, "hashrate_cap_changed"), [])
        self.assertEqual(_of(h.records, "session_start")[0]["hashrate_cap"]["cap_h_s"], self.RATE)

    def test_the_real_ceiling_never_holds_back_this_hardware(self):
        async def scenario(home):
            pool = VerifyingPool(difficulty=Fraction(1, 10 ** 7))
            await pool.start()
            home.put_login("viabtc")
            h = Harness(home, {"viabtc": pool}, itinerary=PythiaItinerary(override=_small_units(2)),
                        stop_when_itinerary_ends=True)
            code = await h.runtime.run()
            await pool.stop()
            return code, h

        with TempHome() as home:
            code, h = _support.run(scenario(home))
            _snapshot(h)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(_of(h.records, "hashrate_cap_window"), [])
        cap = _of(h.records, "session_start")[0]["hashrate_cap"]
        self.assertEqual(cap["cap_h_s"], process_cap().cap_h_s)
        self.assertEqual(cap["source"], "chronus.execution.hashrate_cap.process_cap")


async def _wait_for(ledger: Ledger, kind: str, timeout: float = 30.0) -> None:
    await _wait_until(lambda: kind in _kinds(ledger), timeout)


async def _wait_until(predicate, timeout: float = 30.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not reached in time")
        await asyncio.sleep(0.05)


class _ChangeMaskAfterUnit:
    """Runs the first unit on the lane, then has the pool push mining.set_version_mask.

    ``mode`` sets what the "device" does afterwards: "poll" returns once the
    session holds the new mask; "hang" keeps the unit running until it is
    cancelled (no device stop); "release" keeps it running until ``abort`` is
    called and then hands back the whole result (completed before the stop).
    """

    def __init__(self, inner, pool, box, mode, new_mask="0000e000"):
        self.inner, self.pool, self.box, self.route = inner, pool, box, inner.route
        self.mode, self.new_mask = mode, new_mask
        self.released = asyncio.Event()
        self.units: list = []
        if mode == "release":
            self.abort = self._abort

    def describe(self):
        return self.inner.describe()

    async def run(self, unit):
        self.units.append(unit)
        result = await self.inner.run(unit)
        if len(self.units) == 1:
            await self.pool.push_version_mask(self.new_mask)
            if self.mode == "poll":
                session = self.box[0].session
                for _ in range(200):
                    if session.version_mask == int(self.new_mask, 16):
                        break
                    await asyncio.sleep(0.01)
            elif self.mode == "hang":
                await asyncio.Event().wait()
            else:
                await self.released.wait()
        return result

    async def _abort(self, unit_id, grace):
        self.released.set()
        return AbortReport(unit_id, True, "completed_before_stop", None, None, None, ROUTE_MODE_A, "test-node", 0)

    def close(self):
        self.inner.close()


class TestVersionRollingEndToEnd(unittest.TestCase):
    def _run(self, units, *, pool_kwargs, dispatcher_for=None):
        async def scenario(home):
            pool = VerifyingPool(**pool_kwargs)
            await pool.start()
            home.put_login("viabtc")
            box = []
            dispatcher = dispatcher_for(pool, box) if dispatcher_for is not None else None
            h = Harness(home, {"viabtc": pool}, dispatcher=dispatcher,
                        itinerary=PythiaItinerary(override=units), stop_when_itinerary_ends=True)
            box.append(h.runtime)
            code = await h.runtime.run()
            await pool.stop()
            _snapshot(h)
            return code, h, pool

        with TempHome() as home:
            return _support.run(scenario(home))

    def test_rolled_shares_are_rechecked_submitted_with_six_params_and_accepted(self):
        units = tuple(UnitSpec(0, i * 4096, 4096, version_index=3) for i in range(3))
        code, h, pool = self._run(units, pool_kwargs={"difficulty": Fraction(1, 10 ** 7), "version_rolling": "1fffe000"})
        self.assertEqual(code, EXIT_OK)
        bits = f"{roll_version(int(pool.version, 16), 0x1FFFE000, 3)[1]:08x}"
        submitted = _of(h.records, "share_submitted")
        self.assertGreater(len(submitted), 0)
        for share in submitted:
            self.assertEqual(share["version_bits"], bits)
            self.assertEqual(share["version_bits_submitted"], bits)
            self.assertEqual(share["version_mask"], "1fffe000")
            self.assertEqual(share["host_recheck"], "passed")
        self.assertTrue(pool.accepted)
        self.assertTrue(all(len(params) == 6 and params[5] == bits for params, _ in pool.accepted))
        self.assertEqual(pool.rejected, [])
        summary = summarize(h.records)
        self.assertEqual(summary["shares"]["accepted"], len(pool.accepted))
        self.assertEqual(summary["pool"]["version_rolling"]["active"], True)
        self.assertEqual(summary["pool"]["version_rolling"]["mask"], "1fffe000")
        self.assertEqual(summary["pool"]["version_rolling"]["negotiation"], "granted")
        self.assertEqual(_of(h.records, "device_fault"), [])
        # Rolling widens the search space only: work is still the executed candidates.
        self.assertEqual(sum(w["executed"] for w in _of(h.records, "work")), 3 * 4096)
        self.assertTrue(h.verified)

    def test_genesis_known_answer_is_unchanged_when_rolling_is_granted(self):
        code, h, pool = self._run((_genesis_unit(),), pool_kwargs={"difficulty": 1, "version_rolling": "1fffe000"})
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(len(pool.accepted), 1)
        params, block_hash = pool.accepted[0]
        self.assertEqual(len(params), 6)
        self.assertEqual(params[5], "00000000")
        submitted = _of(h.records, "share_submitted")
        self.assertEqual(submitted[0]["hash"], "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f")
        self.assertEqual(submitted[0]["version_bits_submitted"], "00000000")

    def test_shares_are_rechecked_and_accepted_under_a_pool_mask_wider_than_the_rolled_mask(self):
        # The pool answers mining.configure with ffffffff: HYBA Mine rolls 1fffe000 only, but
        # the pool rebuilds nVersion with ffffffff, so the job's own bit 0 must be submitted.
        reply = {"version-rolling": True, "version-rolling.mask": "ffffffff"}
        units = (_genesis_unit(), UnitSpec(0, 0, 4096, version_index=3))
        code, h, pool = self._run(units, pool_kwargs={"difficulty": Fraction(1, 10 ** 7), "configure_reply": reply})
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(_of(h.records, "device_fault"), [])
        self.assertEqual(pool.rejected, [])
        submitted = _of(h.records, "share_submitted")
        genesis = [s for s in submitted if s["nonce"] == f"{GENESIS_NONCE:08x}"]
        self.assertEqual(len(genesis), 1)
        self.assertEqual(genesis[0]["version_bits_submitted"], "00000001")
        self.assertEqual(genesis[0]["hash"], "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f")
        rolled_version = roll_version(int(pool.version, 16), 0x1FFFE000, 3)[0]
        rolled = [s for s in submitted if s["version"] == f"{rolled_version:08x}"]
        self.assertTrue(rolled)
        self.assertTrue(all(s["version_bits_submitted"] == f"{rolled_version:08x}" for s in rolled))
        self.assertEqual(len(pool.accepted), len(submitted))
        connected = _of(h.records, "pool_connected")[0]
        self.assertEqual((connected["version_mask"], connected["pool_version_mask"]), ("1fffe000", "ffffffff"))

    def test_unit_in_flight_when_the_mask_withdraws_its_bits_is_aborted(self):
        units = (UnitSpec(0, 0, 4096, version_index=16),)
        code, h, pool = self._run(
            units, pool_kwargs={"difficulty": Fraction(1, 10 ** 7), "version_rolling": "1fffe000"},
            dispatcher_for=lambda pool, box: _ChangeMaskAfterUnit(_dispatcher(), pool, box, "hang"))
        self.assertEqual(code, EXIT_OK)
        aborted = _of(h.records, "unit_aborted_stale")
        self.assertEqual(len(aborted), 1)
        self.assertEqual(aborted[0]["reason"], "version_mask_changed")
        self.assertEqual(aborted[0]["version_bits"], "00020000")
        self.assertEqual(aborted[0]["current_version_mask"], "0000e000")
        self.assertEqual(_of(h.records, "device_fault"), [])
        self.assertEqual(_of(h.records, "share_submitted"), [])
        self.assertFalse([p for p, _ in pool.accepted + pool.rejected if len(p) == 6 and p[5] == "00020000"])
        self.assertEqual(summarize(h.records)["pool"]["version_rolling"]["mask"], "0000e000")

    def test_hits_rolled_under_a_withdrawn_mask_are_dropped_not_submitted(self):
        units = (UnitSpec(0, 0, 4096, version_index=16),)
        code, h, pool = self._run(
            units, pool_kwargs={"difficulty": Fraction(1, 10 ** 7), "version_rolling": "1fffe000"},
            dispatcher_for=lambda pool, box: _ChangeMaskAfterUnit(_dispatcher(), pool, box, "release"))
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(len(_of(h.records, "unit_aborted_stale")), 1)
        dropped = _of(h.records, "share_stale_dropped")
        self.assertGreater(len(dropped), 0)
        self.assertTrue(all("version mask" in d["reason"] and d["version_bits"] == "00020000" for d in dropped))
        self.assertTrue(all(d["current_mask"] == "0000e000" for d in dropped))
        self.assertEqual(_of(h.records, "device_fault"), [])
        self.assertEqual(_of(h.records, "share_submitted"), [])
        self.assertFalse([p for p, _ in pool.accepted + pool.rejected if len(p) == 6 and p[5] == "00020000"])

    def test_a_mask_change_that_keeps_the_rolled_bits_does_not_stop_the_unit(self):
        # Index 3 rolls bits 13 and 14, which the narrower mask 0001e000 still allows.
        units = (UnitSpec(0, 0, 4096, version_index=3),)
        code, h, pool = self._run(
            units, pool_kwargs={"difficulty": Fraction(1, 10 ** 7), "version_rolling": "1fffe000"},
            dispatcher_for=lambda pool, box: _ChangeMaskAfterUnit(_dispatcher(), pool, box, "poll", new_mask="0001e000"))
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(_of(h.records, "unit_aborted_stale"), [])
        self.assertGreater(len(pool.accepted), 0)
        self.assertTrue(all(params[5] == "00006000" for params, _ in pool.accepted))
        self.assertEqual(pool.rejected, [])

    def test_a_rolled_unit_is_skipped_when_the_pool_grants_no_rolling(self):
        units = (UnitSpec(0, 0, 4096, version_index=3), UnitSpec(0, 4096, 4096))
        code, h, pool = self._run(units, pool_kwargs={"difficulty": Fraction(1, 10 ** 7)})
        self.assertEqual(code, EXIT_OK)
        skipped = _of(h.records, "unit_skipped")
        self.assertEqual([(s["version_index"], s["version_mask"]) for s in skipped], [(3, "00000000")])
        self.assertEqual(sum(w["executed"] for w in _of(h.records, "work")), 4096)
        self.assertTrue(pool.accepted)
        self.assertTrue(all(len(params) == 5 for params, _ in pool.accepted))

    def test_version_rolling_off_sends_no_configure(self):
        async def scenario(home):
            pool = VerifyingPool(difficulty=Fraction(1, 10 ** 7), version_rolling="1fffe000")
            await pool.start()
            home.put_login("viabtc")
            h = Harness(home, {"viabtc": pool}, itinerary=PythiaItinerary(override=_small_units(1)),
                        stop_when_itinerary_ends=True, version_rolling=False)
            code = await h.runtime.run()
            await pool.stop()
            _snapshot(h)
            return code, h, pool

        with TempHome() as home:
            code, h, pool = _support.run(scenario(home))
        self.assertEqual(code, EXIT_OK)
        self.assertNotIn("mining.configure", pool.methods)
        self.assertTrue(pool.accepted)
        self.assertTrue(all(len(params) == 5 for params, _ in pool.accepted))
        rolling = summarize(h.records)["pool"]["version_rolling"]
        self.assertEqual((rolling["active"], rolling["negotiation"]), (False, "disabled"))


if __name__ == "__main__":
    unittest.main()
