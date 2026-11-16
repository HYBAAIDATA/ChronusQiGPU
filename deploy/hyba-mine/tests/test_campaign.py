"""Two-block campaign: block-height gating, stage end conditions and lane search."""

import asyncio
import hashlib
import types
import unittest

from chronus.fleet.capacity import CapacityLedger, HostCapacity
from hyba_mine.campaign import StageControlMixin, coinbase_height, parse_pools, pool_config
from hyba_mine.lanes import reference_scan
from hyba_mine.search import LaneSearchMixin, initial_window


def coinbase(push_hex: str) -> str:
    return "01000000" + "01" + "00" * 32 + "ffffffff" + "20" + push_hex + "00000000"


def job(height: int, job_id: str = "j1") -> dict:
    return {
        "job_id": job_id,
        "prevhash_hex": "00" * 32,
        "coinb1_hex": coinbase("03" + height.to_bytes(3, "little").hex()),
        "coinb2_hex": "",
        "merkle_branches": [],
        "version_hex": "20000000",
        "nbits_hex": "1d00ffff",
        "ntime_hex": "6731a000",
    }


class Gateway:
    def __init__(self):
        self.handled = []

    async def handle_server_push(self, message):
        self.handled.append(message.get("method"))


class Stage(StageControlMixin):
    def __init__(self, min_height=None):
        self.gateway = Gateway()
        self._init_stage("viabtc", min_height, None)


class HeightTests(unittest.TestCase):
    def test_bip34_heights(self):
        self.assertEqual(coinbase_height(coinbase("036f460d")), 869999)
        self.assertEqual(coinbase_height(coinbase("60")), 16)
        self.assertEqual(coinbase_height(coinbase("0400e1f505")), 100000000)
        self.assertIsNone(coinbase_height("01000000" + "01" + "11" * 32 + "ffffffff" + "0403a00d00"))
        self.assertIsNone(coinbase_height("zz"))
        self.assertIsNone(coinbase_height("0100"))

    def test_pools_are_validated(self):
        self.assertEqual(parse_pools("viabtc, braiins"), ["viabtc", "braiins"])
        for bad in ("", "viabtc,viabtc", "viabtc,nicehash"):
            with self.assertRaises(ValueError):
                parse_pools(bad)

    def test_pool_config_requires_every_setting(self):
        import os
        keys = {"MINING_BRAIINS_HOST": "stratum.braiins.com", "MINING_BRAIINS_PORT": "3333",
                "MINING_BRAIINS_USER": "acct.worker", "MINING_BRAIINS_PASSWORD": "x"}
        saved = {k: os.environ.get(k) for k in keys}
        try:
            os.environ.update(keys)
            self.assertEqual(pool_config("braiins"), ("stratum.braiins.com", 3333, "acct.worker", "x"))
            os.environ["MINING_BRAIINS_PORT"] = ""
            with self.assertRaises(ValueError):
                pool_config("braiins")
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


class GateTests(unittest.TestCase):
    def test_first_stage_mines_its_block_and_ends_when_the_block_moves_on(self):
        stage = Stage()
        self.assertTrue(stage._gate(job(870000)))
        self.assertEqual(stage.stage_height, 870000)
        self.assertTrue(stage._gate(job(870000, "j2")))
        self.assertFalse(stage._gate(job(870001)))
        self.assertEqual(stage.end_reason, "block_ended")
        self.assertFalse(stage._gate(job(870000)))

    def test_second_stage_cools_down_until_a_non_consecutive_block(self):
        stage = Stage(min_height=870002)
        self.assertFalse(stage._gate(job(870000)))
        self.assertFalse(stage._gate(job(870001)))
        self.assertIsNone(stage.end_reason)
        self.assertTrue(stage._gate(job(870002)))
        self.assertEqual(stage.stage_height, 870002)

    def test_unreadable_height_ends_the_stage(self):
        stage = Stage()
        bad = job(870000)
        bad["coinb1_hex"] = "00"
        self.assertFalse(stage._gate(bad))
        self.assertEqual(stage.end_reason, "block_height_unreadable")

    def test_unexpected_pool_methods_are_recorded(self):
        stage = Stage()
        for method in ("mining.notify", "client.get_version", "mining.set_difficulty"):
            asyncio.run(stage.gateway.handle_server_push({"method": method}))
        self.assertEqual(stage.push_methods["client.get_version"], 1)
        self.assertEqual(stage.gateway.handled, ["mining.notify", "client.get_version", "mining.set_difficulty"])


class ReferenceLanes:
    name = "process-lanes"
    lanes = 1

    def __init__(self, extra_false_hit=None):
        self.calls = []
        self.extra_false_hit = extra_false_hit

    def search(self, header80, start, stop, target):
        self.calls.append((start, stop))
        hits = reference_scan(header80, start, stop, target)
        if self.extra_false_hit is not None:
            hits = hits + [self.extra_false_hit]
        return hits


class Engine(LaneSearchMixin):
    def __init__(self, lanes, span=4096, shards=2):
        self.partitioner = types.SimpleNamespace(ranges=[
            types.SimpleNamespace(shard_id=i, start_nonce=i * span, end_nonce=(i + 1) * span) for i in range(shards)
        ])
        self._nonce_cursors = {}
        self._scanned_per_shard = {}
        self._next_shard = 0
        self._nonce_space_exhausted = False
        self._nonce_context = ("job", "en1", 4)
        self.hashes_computed = 0
        host = HostCapacity(logical_cpus=1, affinity_cpus=1, cgroup_cpu_quota=None, memory_bytes=None)
        ledger = CapacityLedger("SHA256D_NONCE_SEARCH", host, "process-lanes", 1, 1)
        ledger.record_calibration(1, 1_000_000_000)
        self._init_lane_search(lanes, ledger)


class SearchTests(unittest.TestCase):
    def test_initial_window_follows_the_calibrated_rate(self):
        self.assertEqual(initial_window(1), 1 << 14)
        self.assertEqual(initial_window(3_000_000), 1 << 21)
        self.assertEqual(initial_window(1 << 40), 1 << 28)

    def test_windows_cover_each_shard_and_hits_are_rechecked(self):
        lanes = ReferenceLanes()
        engine = Engine(lanes)
        engine.window = 3000
        target = 1 << 250
        root = hashlib.sha256(b"root").digest()
        first = engine._lane_search(job(870000), root, "1fffe000", target)
        self.assertIsNotNone(first)
        nonce, version_bits_hex, value = first
        self.assertEqual(version_bits_hex, "00000000")
        self.assertTrue(0 <= nonce < 3000)
        self.assertLessEqual(value, target)
        self.assertEqual(lanes.calls[0], (0, 3000))
        while engine._pending:
            self.assertIsNotNone(engine._lane_search(job(870000), root, "1fffe000", target))
        engine.window = 3000
        engine._lane_search(job(870000), root, "1fffe000", target)
        self.assertEqual(lanes.calls[1], (4096, 7096))
        self.assertEqual(engine.hashes_computed, 6000)

    def test_a_window_wraps_inside_its_shard_and_exhaustion_rolls_extranonce2(self):
        lanes = ReferenceLanes()
        engine = Engine(lanes, span=4096, shards=1)
        engine.window = 3000
        root = hashlib.sha256(b"r").digest()
        engine._lane_search(job(870000), root, "00000000", 0)
        engine.window = 3000
        engine._lane_search(job(870000), root, "00000000", 0)
        self.assertEqual(lanes.calls[1:], [(3000, 4096), (0, 1904)])
        self.assertTrue(engine._nonce_space_exhausted)
        self.assertIsNone(engine._nonce_context)

    def test_a_short_grant_advances_only_the_searched_span(self):
        class Capped(ReferenceLanes):
            def search(self, header80, start, stop, target):
                granted = min(10, stop - start)
                self.last_span = granted
                self.calls.append((start, start + granted))
                return []

        lanes = Capped()
        engine = Engine(lanes)
        engine.window = 3000
        engine._lane_search(job(870000), hashlib.sha256(b"root").digest(), "1fffe000", 0)
        self.assertEqual(lanes.calls, [(0, 10)])
        self.assertEqual(engine.hashes_computed, 10)
        self.assertEqual(engine._nonce_cursors[0], 10)
        self.assertFalse(engine._hash_throttled)

    def test_a_partial_grant_does_not_jump_the_wrap(self):
        class Partial(ReferenceLanes):
            def search(self, header80, start, stop, target):
                granted = min(100, stop - start)
                self.last_span = granted
                self.calls.append((start, start + granted))
                return []

        lanes = Partial()
        engine = Engine(lanes, span=4096, shards=1)
        engine.window = 3000
        engine._nonce_cursors[0] = 3000
        engine._lane_search(job(870000), hashlib.sha256(b"r").digest(), "00000000", 0)
        self.assertEqual(lanes.calls, [(3000, 3100)])
        self.assertEqual(engine.hashes_computed, 100)
        self.assertEqual(engine._nonce_cursors[0], 3100)
        self.assertFalse(engine._nonce_space_exhausted)

    def test_a_zero_grant_does_not_skip_unsearched_nonces(self):
        class Blocked(ReferenceLanes):
            def search(self, header80, start, stop, target):
                self.last_span = 0
                self.calls.append((start, stop))
                return []

        lanes = Blocked()
        engine = Engine(lanes)
        engine.window = 3000
        self.assertIsNone(engine._lane_search(job(870000), hashlib.sha256(b"r").digest(), "00000000", 0))
        self.assertEqual(engine.hashes_computed, 0)
        self.assertEqual(engine._nonce_cursors, {})
        self.assertTrue(engine._hash_throttled)

    def test_a_lane_hit_that_fails_the_host_recheck_is_discarded(self):
        lanes = ReferenceLanes(extra_false_hit=5)
        engine = Engine(lanes)
        engine.window = 64
        result = engine._lane_search(job(870000), hashlib.sha256(b"x").digest(), "00000000", 0)
        self.assertIsNone(result)
        self.assertEqual(engine.lane_recheck_failures, 1)


if __name__ == "__main__":
    unittest.main()
