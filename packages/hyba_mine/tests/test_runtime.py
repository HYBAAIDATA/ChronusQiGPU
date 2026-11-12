# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""End-to-end runtime: verifying pool, Chronus iGPU Mode A, ledger and status."""

import asyncio
import unittest
from dataclasses import replace
from fractions import Fraction

import _support
from _support import GENESIS_EN2, GENESIS_NONCE, TempHome, VerifyingPool


from hyba_mine.control import block_for, request_pool_switch
from hyba_mine.dispatch import LocalIGPUDispatcher
from hyba_mine.igpu import ROUTE_MODE_A, BackendRoute, ModeALane
from hyba_mine.ledger import Ledger
from hyba_mine.plan import NoncePlan, PythiaItinerary, UnitSpec
from hyba_mine.runtime import EXIT_DEVICE_FAULT, EXIT_LOGIN_REJECTED, EXIT_OK, MinerRuntime, RuntimeOptions
from hyba_mine.status import summarize
from hyba_mine.vectors import GENESIS
from hyba_mine.work import Hit

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


async def _wait_for(ledger: Ledger, kind: str, timeout: float = 30.0) -> None:
    await _wait_until(lambda: kind in _kinds(ledger), timeout)


async def _wait_until(predicate, timeout: float = 30.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not reached in time")
        await asyncio.sleep(0.05)


if __name__ == "__main__":
    unittest.main()
