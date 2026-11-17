# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Canonical search: PYTHIA itinerary, Hendrix traversal, golden-stride bijection."""

import hashlib
import subprocess
import sys
import unittest

import _support  # noqa: F401  (import paths)

from chronus.execution.elevation import GOLDEN_STRIDE
from chronus.hendrix import GF257

from hyba_mine.plan import (
    LANES_PER_WINDOW,
    MASK32,
    NONCE_SPACE,
    STRIDE_INVERSE,
    NoncePlan,
    PythiaItinerary,
    RouteSizer,
    UnitSpec,
    hendrix_lane_table,
    hendrix_slot_of_lane,
    plan_seed,
)
from hyba_mine.vectors import GENESIS, REAL_HEADERS


def _det_values(seed: bytes, count: int, modulus: int) -> list:
    """Deterministic pseudo-random sample (SHA-256 counter mode); no global state."""
    out = []
    for i in range(count):
        digest = hashlib.sha256(seed + i.to_bytes(8, "little")).digest()
        out.append(int.from_bytes(digest[:8], "little") % modulus)
    return out


class TestInvariants(unittest.TestCase):
    def test_golden_stride_is_the_chronus_constant_and_invertible(self):
        self.assertEqual(GOLDEN_STRIDE, 0x9E3779B9)
        self.assertEqual((GOLDEN_STRIDE * STRIDE_INVERSE) & MASK32, 1)

    def test_every_hendrix_lane_table_is_a_bijection_on_256_lanes(self):
        for rotation in range(LANES_PER_WINDOW):
            table = hendrix_lane_table(rotation)
            self.assertEqual(sorted(table), list(range(LANES_PER_WINDOW)))
            for slot, lane in enumerate(table):
                self.assertEqual(hendrix_slot_of_lane(lane, rotation), slot)

    def test_lane_table_follows_the_f257_generator_cycle(self):
        table = hendrix_lane_table(0)
        self.assertEqual(table[0], 0)  # 3**0 - 1
        self.assertEqual(table[1], 2)  # 3**1 - 1
        for slot in range(LANES_PER_WINDOW):
            self.assertEqual(table[slot], pow(GF257.generator, slot, 257) - 1)


class TestProperty(unittest.TestCase):
    def test_position_nonce_round_trip_on_real_headers(self):
        for vector in REAL_HEADERS:
            for window_bits in (8, 12, 20, 30):
                plan = NoncePlan.for_header(vector.prefix, window_bits)
                for value in _det_values(vector.prefix, 200, NONCE_SPACE):
                    self.assertEqual(plan.nonce_at(plan.position_of(value)), value)
                    self.assertEqual(plan.position_of(plan.nonce_at(value)), value)

    def test_full_window_is_covered_once_zero_repeats_zero_gaps(self):
        plan = NoncePlan.for_header(GENESIS.prefix, 16)
        for window in (0, 1, plan.window_count - 1):
            base = window * plan.window_size
            indices = [plan.index_at(base + gid) for gid in range(plan.window_size)]
            self.assertEqual(len(set(indices)), plan.window_size)
            self.assertEqual(set(indices), set(range(base, base + plan.window_size)))
            nonces = {plan.nonce_at(base + gid) for gid in range(plan.window_size)}
            self.assertEqual(len(nonces), plan.window_size)

    def test_random_scheduling_control_leaves_about_one_in_e_gaps(self):
        size = 1 << 16
        drawn = _det_values(b"random-control", size, size)
        gaps = size - len(set(drawn))
        self.assertGreater(gaps / size, 0.35)
        self.assertLess(gaps / size, 0.39)

    def test_segments_cover_a_range_exactly_and_follow_the_stride(self):
        plan = NoncePlan.for_header(GENESIS.prefix, 12)
        start, count = plan.lane_size * 3 + 17, plan.window_size + 100
        seen = []
        for first, nonce, length in plan.segments(start, count):
            for k in range(length):
                self.assertEqual(plan.nonce_at(first + k), (nonce + k * GOLDEN_STRIDE) & MASK32)
                seen.append(first + k)
        self.assertEqual(seen, list(range(start, start + count)))


class TestAdversarial(unittest.TestCase):
    def test_planted_even_stride_is_not_a_bijection(self):
        plan = NoncePlan.for_header(GENESIS.prefix, 16)
        broken = NoncePlan(plan.header_prefix, plan.window_bits, plan.offset, plan.rotation, plan.lane_table, stride=2)
        nonces = {broken.nonce_at(p) for p in range(1 << 16)} | {broken.nonce_at((1 << 31) + p) for p in range(1 << 16)}
        self.assertLess(len(nonces), 1 << 17)

    def test_planted_duplicate_lane_is_detected_as_repeats_and_gaps(self):
        plan = NoncePlan.for_header(GENESIS.prefix, 12)
        table = list(plan.lane_table)
        table[5] = table[4]
        broken = NoncePlan(plan.header_prefix, plan.window_bits, plan.offset, plan.rotation, tuple(table))
        indices = [broken.index_at(gid) for gid in range(broken.window_size)]
        self.assertLess(len(set(indices)), broken.window_size)

    def test_rejects_out_of_range_inputs(self):
        plan = NoncePlan.for_header(GENESIS.prefix)
        for bad in (-1, NONCE_SPACE):
            with self.assertRaises(ValueError):
                plan.nonce_at(bad)
            with self.assertRaises(ValueError):
                plan.position_of(bad)
        with self.assertRaises(ValueError):
            NoncePlan.for_header(GENESIS.prefix[:75])
        for bits in (7, 31):
            with self.assertRaises(ValueError):
                NoncePlan.for_header(GENESIS.prefix, bits)
        with self.assertRaises(ValueError):
            hendrix_lane_table(256)
        with self.assertRaises(ValueError):
            list(plan.segments(NONCE_SPACE - 1, 2))


class TestEdge(unittest.TestCase):
    def test_last_position_and_window_edges(self):
        plan = NoncePlan.for_header(GENESIS.prefix)
        for position in (0, plan.lane_size - 1, plan.lane_size, plan.window_size - 1, plan.window_size, MASK32):
            self.assertEqual(plan.position_of(plan.nonce_at(position)), position)
        self.assertEqual(plan.nonce_at(0), (plan.offset + plan.lane_table[0] * plan.lane_size * GOLDEN_STRIDE) & MASK32)


class TestUnit(unittest.TestCase):
    def test_plan_is_bound_to_the_job(self):
        a = NoncePlan.for_header(REAL_HEADERS[0].prefix)
        b = NoncePlan.for_header(REAL_HEADERS[1].prefix)
        self.assertNotEqual((a.offset, a.rotation), (b.offset, b.rotation))
        seed = plan_seed(REAL_HEADERS[0].prefix)
        self.assertEqual(a.offset, int.from_bytes(seed[:4], "little"))
        self.assertEqual(a.rotation, seed[4])

    def test_itinerary_units_are_disjoint_ordered_and_advance_extranonce2(self):
        itinerary = PythiaItinerary(window_bits=30, windows_per_unit=1)
        units = []
        for unit in itinerary.units(en2_limit=3):
            units.append(unit)
            if len(units) == 9:
                break
        self.assertEqual([u.en2_counter for u in units], [0, 0, 0, 0, 1, 1, 1, 1, 2])
        self.assertEqual([u.start for u in units[:4]], [0, 1 << 30, 2 << 30, 3 << 30])
        self.assertTrue(all(u.count == 1 << 30 for u in units))

    def test_resized_units_still_cover_the_nonce_space_exactly(self):
        itinerary = PythiaItinerary(window_bits=24, windows_per_unit=1)
        timings = [0.01, 0.01, 0.01, 5.0, 5.0, 0.4, 0.01, 5.0]
        end, sizes = 0, []
        for index, unit in enumerate(itinerary.units(en2_limit=1)):
            self.assertEqual(unit.start, end)
            self.assertEqual(unit.count % itinerary.window_size, 0)
            end = unit.start + unit.count
            sizes.append(unit.count)
            itinerary.resize(timings[index % len(timings)], target_seconds=0.5)
        self.assertEqual(end, 1 << 32)
        self.assertGreater(max(sizes), 1 << 24)
        self.assertGreaterEqual(min(sizes), 1 << 24)
        itinerary.unit_size = 1 << 30
        itinerary.resize(0.001, 0.5)
        self.assertEqual(itinerary.unit_size, 1 << 30)

    def test_itinerary_override_is_used_once(self):
        spec = (UnitSpec(1, 4096, 4096),)
        self.assertEqual(list(PythiaItinerary(override=spec).units(2)), list(spec))
        with self.assertRaises(ValueError):
            list(PythiaItinerary(override=(UnitSpec(5, 0, 1),)).units(2))


class TestItineraryCursor(unittest.TestCase):
    def test_cursor_take_is_window_aligned_contiguous_and_rolls_extranonce2(self):
        itinerary = PythiaItinerary(window_bits=24)
        window = itinerary.window_size
        cursor = itinerary.cursor(en2_limit=2)
        sizes = [1, 3 << 24, 1 << 30, 5 << 24, (1 << 24) + 7]
        taken, index = [], 0
        while True:
            spec = cursor.take(sizes[index % len(sizes)])
            index += 1
            if spec is None:
                break
            taken.append(spec)
        self.assertTrue(cursor.exhausted)
        self.assertIsNone(cursor.take(window))
        for en2 in (0, 1):
            specs = [s for s in taken if s.en2_counter == en2]
            self.assertEqual(specs[0].start, 0)
            end = 0
            for spec in specs:
                self.assertEqual(spec.start, end)
                self.assertEqual(spec.count % window, 0)
                self.assertGreaterEqual(spec.count, window)
                end = spec.start + spec.count
            self.assertEqual(end, NONCE_SPACE)
        self.assertEqual([s.en2_counter for s in taken], sorted(s.en2_counter for s in taken))
        with self.assertRaises(ValueError):
            cursor.take(0)

    def test_two_routes_interleaved_takes_cover_the_space_exactly_once(self):
        cursor = PythiaItinerary(window_bits=24).cursor(en2_limit=1)
        choices = _det_values(b"interleave", 4096, 2)
        sizes = {0: 1 << 24, 1: 1 << 27}
        received = {0: [], 1: []}
        index = 0
        while True:
            route = choices[index % len(choices)]
            index += 1
            spec = cursor.take(sizes[route])
            if spec is None:
                break
            received[route].append((spec.start, spec.start + spec.count))
        self.assertTrue(received[0] and received[1])
        intervals = sorted(received[0] + received[1])
        position = 0
        for start, end in intervals:
            self.assertEqual(start, position)
            position = end
        self.assertEqual(position, NONCE_SPACE)

    def test_cursor_rolls_versions_inside_each_extranonce2(self):
        cursor = PythiaItinerary(window_bits=30).cursor(en2_limit=2, version_count=2)
        order = []
        while (spec := cursor.take(1 << 31)) is not None:
            order.append((spec.en2_counter, spec.version_index, spec.start))
        self.assertEqual(order, [(0, 0, 0), (0, 0, 1 << 31), (0, 1, 0), (0, 1, 1 << 31),
                                 (1, 0, 0), (1, 0, 1 << 31), (1, 1, 0), (1, 1, 1 << 31)])

    def test_units_wrapper_is_unchanged_by_the_cursor(self):
        units = list(PythiaItinerary(window_bits=30).units(3))[:9]
        expected = [UnitSpec(en2, i << 30, 1 << 30) for en2 in range(3) for i in range(4)][:9]
        self.assertEqual(units, expected)

    def test_override_cursor_yields_each_spec_once_and_ignores_size(self):
        specs = (UnitSpec(1, 4096, 4096), UnitSpec(0, 0, 12288))
        cursor = PythiaItinerary(override=specs).cursor(en2_limit=2)
        self.assertEqual([cursor.take(1), cursor.take(1 << 30)], list(specs))
        self.assertIsNone(cursor.take(4096))
        with self.assertRaises(ValueError):
            PythiaItinerary(override=(UnitSpec(5, 0, 1),)).cursor(en2_limit=2)

    def test_route_sizer_resizes_per_route_only(self):
        window = 1 << 20
        fast, slow = RouteSizer(4 * window, window, max_size=8 * window), RouteSizer(4 * window, window)
        fixed = RouteSizer(4 * window, window, fixed=True)
        for _ in range(5):
            fast.resize(0.01, 0.5)
            slow.resize(5.0, 0.5)
            fixed.resize(0.01, 0.5)
        self.assertEqual(fast.unit_size, 8 * window)
        self.assertEqual(slow.unit_size, window)
        self.assertEqual(fixed.unit_size, 4 * window)


class TestIntegration(unittest.TestCase):
    def test_plan_replays_identically_in_a_fresh_process(self):
        code = (
            "import sys, json\n"
            "from hyba_mine.plan import NoncePlan\n"
            "from hyba_mine.vectors import GENESIS\n"
            "p = NoncePlan.for_header(GENESIS.prefix)\n"
            "print(json.dumps([p.describe(), [p.nonce_at(i) for i in range(16)]]))\n"
        )
        done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120,
                              env=_support_env())
        self.assertEqual(done.returncode, 0, done.stderr)
        plan = NoncePlan.for_header(GENESIS.prefix)
        import json

        self.assertEqual(json.loads(done.stdout), [plan.describe(), [plan.nonce_at(i) for i in range(16)]])


class TestEndToEnd(unittest.TestCase):
    def test_real_block_nonce_is_located_by_the_inverse_map(self):
        for vector in REAL_HEADERS:
            plan = NoncePlan.for_header(vector.prefix)
            position = plan.position_of(vector.nonce)
            header = vector.prefix + plan.nonce_at(position).to_bytes(4, "little")
            self.assertEqual(header, vector.header)


def _support_env():
    import os

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
    return env


if __name__ == "__main__":
    unittest.main()
