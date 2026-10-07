"""Agent B defect-class regression tests for the mining lane.

Each test pins a concrete production defect that was found and fixed:

* ``RemoteFleetHasher._slice`` split m32 windows by raw step counts, so a
  member whose ``take`` was not a whole number of 32-step lane epochs ran
  a partial epoch at a non-epoch boundary — coverage gaps, duplicate
  probes and out-of-window nonces.
* ``StratumBridge`` trusted every pool field by shape: malformed
  ``mining.notify`` / ``mining.set_difficulty`` / ``mining.subscribe``
  values surfaced later as ``ValueError`` inside ``mine_job`` or killed
  the listener outright.
* ``mine_job``'s broad ``except Exception`` fallback would have swallowed
  a proof-layer ``RuntimeError`` (device hit failing the host SHA-256d
  recheck) and silently switched traversal arms.
* A listening-mode ``_rpc`` timeout leaked its ``_pending`` entry,
  growing the table without bound.

Run: ``python -m pytest mining/tests/ -x -q``
"""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

from mining.remote_hasher import RemoteFleetHasher
from mining.stratum_bridge import (
    LiveJob,
    StratumBridge,
    _validate_notify_params,
    mine_job,
)

LANES = list(range(32))


def _fleet(members: int) -> RemoteFleetHasher:
    """Fleet shell for slicing tests — no bound agents required."""
    hasher = RemoteFleetHasher.__new__(RemoteFleetHasher)
    hasher._members = [object() for _ in range(members)]
    return hasher


def _m32_window(base: int, count: int, lanes) -> list[int]:
    """The serial m32 traversal one remote agent executes for a slice."""
    return [(base + lanes[i % 32] + 32 * (i // 32)) & 0xFFFFFFFF for i in range(count)]


def _valid_notify(job_id="job_1", clean=True):
    return {
        "method": "mining.notify",
        "params": [
            job_id,
            "00" * 32,
            "aabb",
            "ccdd",
            ["11" * 32, "22" * 32],
            "01000000",
            "1d00ffff",
            "5f3759df",
            clean,
        ],
    }


def _valid_job() -> LiveJob:
    return LiveJob(
        job_id="job_1",
        prev_hash="00" * 32,
        coinb1="aabb",
        coinb2="ccdd",
        merkle_branch=["11" * 32],
        version="01000000",
        nbits="1d00ffff",
        ntime="5f3759df",
        difficulty=1.0,
    )


class FleetM32SlicingTests(unittest.TestCase):
    """Nonce partitioning: m32 slices must be whole lane epochs."""

    def test_slices_align_to_32_step_epochs(self):
        hasher = _fleet(2)
        slices = hasher._slice("m32", 0, 96, None, LANES)
        self.assertEqual(len(slices), 2)
        self.assertEqual([s["count"] for s in slices], [64, 32])
        self.assertEqual([s["base_nonce"] for s in slices], [0, 64])
        for s in slices:
            self.assertEqual(s["count"] % 32, 0)
            self.assertEqual(s["lane_order"], LANES)

    def test_union_covers_window_exactly_once_for_any_split(self):
        # The defect case: counts whose per-member share is not a whole
        # epoch (e.g. 96 over 2 members used to give 48-step slices).
        for members, count in ((2, 96), (3, 160), (5, 64), (4, 128), (2, 32)):
            hasher = _fleet(members)
            slices = hasher._slice("m32", 7 << 24, count, None, LANES)
            produced = []
            for s in slices:
                produced += _m32_window(s["base_nonce"], s["count"], s["lane_order"])
            expected = sorted(((7 << 24) + i) & 0xFFFFFFFF for i in range(count))
            self.assertEqual(
                sorted(produced),
                expected,
                f"fleet of {members} over {count} steps broke coverage",
            )
            self.assertEqual(sum(s["count"] for s in slices), count)

    def test_partial_epoch_window_rejected(self):
        hasher = _fleet(2)
        with self.assertRaises(ValueError):
            hasher.grind_target_m32(bytes(80), b"\xff" * 32, 0, LANES, 48)

    def test_contiguous_and_batch_unchanged(self):
        hasher = _fleet(4)
        contiguous = hasher._slice("contiguous", 0, 10, None, None)
        self.assertEqual(
            [(s["base_nonce"], s["count"]) for s in contiguous],
            [(0, 3), (3, 3), (6, 2), (8, 2)],
        )
        batch = hasher._slice("batch", 0, 0, list(range(9)), None)
        self.assertEqual([len(s["nonces"]) for s in batch], [3, 2, 2, 2])


class MalformedPoolInputTests(unittest.TestCase):
    """A hostile or buggy pool must not crash or poison the bridge."""

    def test_malformed_notify_dropped_without_replacing_job(self):
        bridge = StratumBridge("127.0.0.1", 3333, "w", "x")
        bridge._handle_server_message(_valid_notify("job_a", clean=True))
        self.assertEqual(bridge.last_job.job_id, "job_a")
        self.assertEqual(bridge.clean_job_generation, 1)

        bad = _valid_notify("job_bad", clean=True)
        bad["params"][1] = "zz-not-hex"
        bridge._handle_server_message(bad)
        self.assertEqual(bridge.last_job.job_id, "job_a")
        self.assertEqual(bridge.clean_job_generation, 1)
        self.assertEqual(bridge.malformed_messages, 1)

    def test_notify_field_validation(self):
        good = _validate_notify_params(_valid_notify()["params"])
        self.assertEqual(good["job_id"], "job_1")
        for index, name in ((1, "prev_hash"), (5, "version"), (6, "nbits"), (7, "ntime")):
            params = _valid_notify()["params"]
            params[index] = "12"  # wrong-length hex
            with self.assertRaises(ValueError, msg=name):
                _validate_notify_params(params)
        for index in (2, 3):
            params = _valid_notify()["params"]
            params[index] = "abc"  # odd-length hex
            with self.assertRaises(ValueError):
                _validate_notify_params(params)
        params = _valid_notify()["params"]
        params[4] = {"not": "a list"}
        with self.assertRaises(ValueError):
            _validate_notify_params(params)
        params = _valid_notify()["params"]
        params[4] = ["ab cd"]  # whitespace is not hex
        with self.assertRaises(ValueError):
            _validate_notify_params(params)
        params = _valid_notify()["params"]
        params[0] = ""
        with self.assertRaises(ValueError):
            _validate_notify_params(params)
        params = _valid_notify()["params"]
        params[8] = "false"
        with self.assertRaises(ValueError):
            _validate_notify_params(params)

    def test_malformed_set_difficulty_ignored(self):
        bridge = StratumBridge("127.0.0.1", 3333, "w", "x")
        bridge.difficulty = 2.0
        for bad in ("garbage", [1], None, "nan", "inf", 0, -3):
            bridge._handle_server_message({"method": "mining.set_difficulty", "params": [bad]})
        self.assertEqual(bridge.difficulty, 2.0)
        self.assertEqual(bridge.malformed_messages, 7)
        bridge._handle_server_message(
            {"method": "mining.set_difficulty", "params": {"not": "a list"}}
        )
        self.assertEqual(bridge.difficulty, 2.0)
        self.assertEqual(bridge.malformed_messages, 8)
        bridge._handle_server_message({"method": "mining.set_difficulty", "params": [4096.0]})
        self.assertEqual(bridge.difficulty, 4096.0)

    def test_malformed_subscribe_fails_handshake_closed(self):
        bridge = StratumBridge("127.0.0.1", 3333, "w", "x")

        async def fake_rpc(method, params, timeout=8.0):
            return [[["mining.notify", "sub"]], "not_hex!!", 4]

        bridge._rpc = fake_rpc
        with self.assertRaises(RuntimeError):
            asyncio.run(bridge.handshake())
        self.assertEqual(bridge.extranonce1, "")

        async def fake_rpc_size(method, params, timeout=8.0):
            return [[["mining.notify", "sub"]], "abcd", "four"]

        bridge._rpc = fake_rpc_size
        with self.assertRaises(RuntimeError):
            asyncio.run(bridge.handshake())

        async def fake_rpc_range(method, params, timeout=8.0):
            return [[["mining.notify", "sub"]], "abcd", 0]

        bridge._rpc = fake_rpc_range
        with self.assertRaises(RuntimeError):
            asyncio.run(bridge.handshake())

        async def fake_rpc_shape(method, params, timeout=8.0):
            return ["too-short"]

        bridge._rpc = fake_rpc_shape
        with self.assertRaises(RuntimeError):
            asyncio.run(bridge.handshake())

        async def fake_rpc_nonstring_extranonce(method, params, timeout=8.0):
            return [[["mining.notify", "sub"]], 1234, 4]

        bridge._rpc = fake_rpc_nonstring_extranonce
        with self.assertRaises(RuntimeError):
            asyncio.run(bridge.handshake())

    def test_valid_subscribe_still_binds(self):
        bridge = StratumBridge("127.0.0.1", 3333, "w", "x")

        async def fake_rpc(method, params, timeout=8.0):
            if method == "mining.authorize":
                return True
            return [[["mining.notify", "sub"]], "abcd", 4]

        bridge._rpc = fake_rpc
        asyncio.run(bridge.handshake())
        self.assertEqual(bridge.extranonce1, "abcd")
        self.assertEqual(bridge.extranonce2_size, 4)


class ListenerOwnershipTests(unittest.TestCase):
    """Single-reader invariant: once listening is claimed, wait_for_job
    must never suspend on the shared StreamReader — a concurrent
    readline() raises RuntimeError and kills the listener."""

    def test_wait_for_job_never_reads_while_listening_claimed(self):
        class _ExplodingReader:
            async def readline(self):
                raise AssertionError("inline read while listener owns the stream")

        bridge = StratumBridge("127.0.0.1", 3333, "w", "x")
        bridge._reader = _ExplodingReader()
        # _amain claims the flag synchronously before the listener task
        # exists, so this state is exactly what wait_for_job sees then.
        bridge._listening = True
        with self.assertRaises(TimeoutError):
            asyncio.run(bridge.wait_for_job(timeout=0.3))


class PendingRpcBoundTests(unittest.TestCase):
    """Bounded queues: timed-out RPCs must not leak _pending entries."""

    def test_listening_rpc_timeout_pops_pending(self):
        bridge = StratumBridge("127.0.0.1", 3333, "w", "x")
        bridge._listening = True

        class _Writer:
            def write(self, data):
                pass

            async def drain(self):
                pass

        bridge._writer = _Writer()

        async def run():
            with self.assertRaises(asyncio.TimeoutError):
                await bridge._rpc("mining.submit", [], timeout=0.01)

        asyncio.run(run())
        self.assertEqual(bridge._pending, {})


class MineJobFallbackTests(unittest.TestCase):
    """Incorrect fallback behaviour: proof failures never switch arms."""

    class _Pipeline:
        def __init__(self, exc=None):
            self.hasher = SimpleNamespace(k_m32=object())
            self.exc = exc
            self.grind_calls = []

        def grind_m32(self, *args):
            raise self.exc

        def grind(self, header, target, nonces):
            self.grind_calls.append(list(nonces))
            return SimpleNamespace(hashes_computed=len(nonces))

    def test_runtime_error_propagates_no_arm_switch(self):
        pipeline = self._Pipeline(
            RuntimeError("device reported a hit that fails the hashlib recheck")
        )
        with self.assertRaises(RuntimeError):
            mine_job(_valid_job(), "ab", 4, pipeline=pipeline, nonce_window=64)
        self.assertEqual(pipeline.grind_calls, [])

    def test_shape_error_falls_back_preserving_window(self):
        pipeline = self._Pipeline(ValueError("m32 grind window must be a multiple of 32"))
        out = mine_job(_valid_job(), "ab", 4, pipeline=pipeline, nonce_window=64)
        self.assertEqual(len(pipeline.grind_calls), 1)
        nonces = pipeline.grind_calls[0]
        self.assertEqual(len(set(nonces)), 64)
        self.assertTrue(all(0 <= n <= 0xFFFFFFFF for n in nonces))
        self.assertEqual(out["job_id"], "job_1")

    def test_unexpected_type_error_propagates_no_arm_switch(self):
        pipeline = self._Pipeline(TypeError("backend contract bug"))
        with self.assertRaises(TypeError):
            mine_job(_valid_job(), "ab", 4, pipeline=pipeline, nonce_window=64)
        self.assertEqual(pipeline.grind_calls, [])


if __name__ == "__main__":
    unittest.main()
