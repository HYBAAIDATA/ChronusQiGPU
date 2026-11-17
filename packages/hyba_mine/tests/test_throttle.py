# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""The hashrate ceiling gate, on an injected small-rate bucket and a fake clock."""

import asyncio
import unittest

import _support  # noqa: F401  (import paths)
from _support import FakeClock, fake_sleeper, small_cap

from chronus.execution import hashrate_cap as hc
from chronus.execution.hashrate_cap import override_process_cap

from hyba_mine.throttle import CapConfigError, CapGate, eh_s_text


def _gate(cap) -> CapGate:
    return CapGate(cap_source=lambda: cap)


class TestCapGate(unittest.TestCase):
    def test_full_grant_under_ceiling(self):
        clock = FakeClock()
        cap = small_cap(1 << 20, clock)
        admission = _gate(cap).admit(4096)
        self.assertEqual((admission.positions, admission.charged, admission.wait_seconds), (4096, 4096, 0.0))
        self.assertFalse(admission.clamped)
        self.assertEqual(cap.available(), (1 << 20) - 4096)

    def test_partial_grant_is_clamped_to_available_tokens(self):
        cap = small_cap(10_000, FakeClock())
        admission = _gate(cap).admit(16384, floor=4096)
        self.assertEqual(admission.positions, 10_000)
        self.assertTrue(admission.clamped)
        self.assertEqual(cap.available(), 0)

    def test_below_floor_refunds_and_reports_wait(self):
        cap = small_cap(10_000, FakeClock())
        self.assertEqual(cap.allow(8000), 8000)
        gate = _gate(cap)
        admission = gate.admit(16384, floor=4096)
        self.assertEqual((admission.positions, admission.charged), (0, 0))
        self.assertFalse(admission.clamped)
        self.assertEqual(cap.available(), 2000)
        expected = min(0.25, -(-(4096 - 2000) * 10 ** 9 // 10_000) / 1e9)
        self.assertAlmostEqual(admission.wait_seconds, expected)
        self.assertGreater(admission.wait_seconds, 0)

    def test_floor_never_exceeds_burst(self):
        cap = small_cap(1000, FakeClock())
        admission = _gate(cap).admit(4096, floor=4096)
        self.assertEqual(admission.positions, 1000)
        self.assertTrue(admission.clamped)

    def test_settle_refunds_unexecuted_positions(self):
        cap = small_cap(1 << 20, FakeClock())
        gate = _gate(cap)
        admission = gate.admit(4096)
        before = cap.available()
        self.assertEqual(gate.settle(admission, 1000), 3096)
        self.assertEqual(cap.available(), before + 3096)
        second = gate.admit(4096)
        self.assertEqual(gate.settle(second, 5000), 0)
        third = gate.admit(4096)
        self.assertEqual(gate.settle(third, -7), 4096)
        self.assertEqual(gate.drain()["refunded_hashes"], 3096 + 4096)

    def test_settle_with_unknown_execution_refunds_nothing(self):
        cap = small_cap(1 << 20, FakeClock())
        gate = _gate(cap)
        admission = gate.admit(4096)
        before = cap.available()
        self.assertEqual(gate.settle(admission, None), 0)
        self.assertEqual(cap.available(), before)
        self.assertEqual(gate.drain()["unsettled_hashes"], admission.charged)

    def test_hashes_per_position_multiplies_charge(self):
        cap = small_cap(10_000, FakeClock())
        gate = _gate(cap)
        admission = gate.admit(4096, hashes_per_position=4)
        self.assertEqual((admission.positions, admission.charged), (2500, 10_000))
        self.assertEqual(cap.available(), 0)
        with self.assertRaises(CapConfigError):
            gate.admit(1, hashes_per_position=10_001)
        for bad in (0, -1, 1.5, True):
            with self.assertRaises(ValueError):
                gate.admit(bad)

    def test_whole_positions_only_and_remainder_refunded(self):
        cap = small_cap(10_000, FakeClock())
        cap.allow(10_000 - 4099)
        admission = _gate(cap).admit(4096, hashes_per_position=4)
        self.assertEqual((admission.positions, admission.charged), (1024, 4096))
        self.assertEqual(cap.available(), 3)

    def test_uses_process_singleton_and_respects_override(self):
        real = hc.process_cap()
        self.assertIs(CapGate().cap(), real)
        test_cap = small_cap(5000, FakeClock())
        with override_process_cap(test_cap):
            gate = CapGate()
            self.assertIs(gate.cap(), test_cap)
            gate.admit(1000)
            self.assertEqual(test_cap.available(), 4000)
        self.assertIs(CapGate().cap(), hc.process_cap())
        self.assertIs(hc.process_cap(), real)

    def test_refill_over_fake_time_bounds_total_grant(self):
        clock = FakeClock()
        cap = small_cap(5000, clock)
        gate = CapGate(cap_source=lambda: cap, sleeper=fake_sleeper(clock), monotonic_ns=clock)
        stop = asyncio.Event()
        total = 0

        async def drive():
            nonlocal total
            while clock.now_ns < 10 * 10 ** 9:
                admission = gate.admit(4096, floor=1)
                if admission.positions == 0:
                    await gate.pause(admission, stop)
                else:
                    total += admission.charged
                    self.assertLessEqual(total, 5000 + 5000 * clock.now_ns // 10 ** 9 + 5000)

        asyncio.run(drive())
        self.assertLessEqual(total, 5000 * (10 + 1))
        self.assertGreater(total, 5000 * 9)

    def test_drain_reports_ceiling_not_rate(self):
        clock = FakeClock()
        cap = small_cap(6000, clock)
        gate = CapGate(cap_source=lambda: cap, sleeper=fake_sleeper(clock), monotonic_ns=clock)
        self.assertTrue(gate.admit(8192, floor=4096).clamped)
        waiting = gate.admit(4096, floor=4096)
        self.assertEqual(waiting.positions, 0)
        asyncio.run(gate.pause(waiting, asyncio.Event()))
        window = gate.drain()
        self.assertEqual(window["cap_h_s"], 6000)
        self.assertGreaterEqual(window["throttle_waits"], 1)
        self.assertGreaterEqual(window["clamped_units"], 1)
        self.assertEqual(window["throttled_ns"], int(waiting.wait_seconds * 1e9))
        self.assertIn("not a device hashrate", window["basis"])
        self.assertIsNone(gate.drain())

    def test_describe_reports_exact_ceiling(self):
        self.assertEqual(hc.HASHRATE_CAP_H_S, 10 ** 18)
        self.assertEqual(eh_s_text(10 ** 18), "1")
        self.assertEqual(eh_s_text(4096), "0.000000000000004096")
        described = CapGate().describe()
        self.assertEqual(described["cap_h_s"], hc.process_cap().cap_h_s)
        self.assertEqual(described["cap_eh_s"], eh_s_text(hc.process_cap().cap_h_s))
        self.assertIn("not a measured rate", described["basis"])
        self.assertIn("this hyba-mine process", described["scope"])
        with override_process_cap(hc.HashrateCap()):
            self.assertEqual(CapGate().describe()["cap_eh_s"], "1")


if __name__ == "__main__":
    unittest.main()
