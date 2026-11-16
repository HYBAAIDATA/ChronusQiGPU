"""Mining lanes: every lane set must equal the host reference before use."""

import hashlib
import unittest

from hyba_mine.lanes import (
    BLOCK1_HEADER,
    DIFF1_TARGET,
    GENESIS_HEADER,
    GENESIS_NONCE,
    ProcessLanes,
    calibrate,
    open_lanes,
    qualify,
    reference_scan,
    split_range,
)


def sha256d_le(header: bytes) -> int:
    return int.from_bytes(hashlib.sha256(hashlib.sha256(header).digest()).digest(), "little")


class BrokenLanes:
    name = "broken"
    lanes = 1

    def search(self, header80, start, stop, target):
        return [start]


class CapReservationTests(unittest.TestCase):
    def test_an_invalid_range_does_not_reserve_hashes(self):
        from chronus.execution.hashrate_cap import HashrateCap, override_process_cap

        lane = ProcessLanes.__new__(ProcessLanes)
        lane.lanes = 1
        cap = HashrateCap(3, clock=lambda: 0)
        with override_process_cap(cap):
            with self.assertRaises(ValueError):
                lane.search(b"short", 0, 1, 0)
            with self.assertRaises(ValueError):
                lane.search(GENESIS_HEADER, 0, (1 << 32) + 1, 0)
            self.assertEqual(cap.available(), 3)


class ReferenceTests(unittest.TestCase):
    def test_genesis_nonce_at_difficulty_one(self):
        self.assertIn(GENESIS_NONCE, reference_scan(GENESIS_HEADER, GENESIS_NONCE - 64, GENESIS_NONCE + 64, DIFF1_TARGET))

    def test_matches_a_direct_hash_on_every_nonce(self):
        target = 1 << 249
        direct = [n for n in range(1000, 1512) if sha256d_le(BLOCK1_HEADER[:76] + n.to_bytes(4, "little")) <= target]
        self.assertTrue(direct)
        self.assertEqual(reference_scan(BLOCK1_HEADER, 1000, 1512, target), direct)

    def test_rejects_bad_inputs(self):
        with self.assertRaises(ValueError):
            reference_scan(b"\x00" * 79, 0, 1, 0)
        with self.assertRaises(ValueError):
            reference_scan(GENESIS_HEADER, 5, 4, 0)
        with self.assertRaises(ValueError):
            reference_scan(GENESIS_HEADER, 0, (1 << 32) + 1, 0)

    def test_split_range_is_disjoint_and_complete(self):
        for start, stop, parts in [(0, 10, 3), (5, 6, 4), (0, 1 << 20, 7), (100, 100, 2)]:
            ranges = split_range(start, stop, parts)
            self.assertTrue(all(b > a for a, b in ranges))
            self.assertTrue(all(ranges[i][1] == ranges[i + 1][0] for i in range(len(ranges) - 1)))
            if ranges:
                self.assertEqual((ranges[0][0], ranges[-1][1]), (start, stop))
        self.assertEqual([n for a, b in split_range(0, 10, 3) for n in range(a, b)], list(range(10)))


class LaneSetTests(unittest.TestCase):
    def test_process_lanes_qualify_and_equal_the_reference(self):
        lanes = ProcessLanes(2)
        try:
            self.assertTrue(qualify(lanes)["passed"])
            target = 1 << 248
            self.assertEqual(lanes.search(BLOCK1_HEADER, 0, 3000, target), reference_scan(BLOCK1_HEADER, 0, 3000, target))
            work, elapsed = calibrate(lanes, min_elapsed_ns=50_000_000)
            self.assertGreater(work, 0)
            self.assertGreater(elapsed, 0)
        finally:
            lanes.close()

    def test_a_lane_set_that_disagrees_does_not_qualify(self):
        self.assertFalse(qualify(BrokenLanes())["passed"])

    def test_open_lanes_selects_a_qualified_set(self):
        lanes, reports = open_lanes(prefer="process", process_lanes=1)
        try:
            self.assertEqual(lanes.name, "process-lanes")
            self.assertTrue(any(r.get("selected") and r["passed"] for r in reports))
        finally:
            lanes.close()


if __name__ == "__main__":
    unittest.main()
