from __future__ import annotations

import math
import unittest

from Intelligence.agentic_controller import AgenticController
from Intelligence.search_crystal import (
    PoincareCassiniSearchEngine,
    build_search_crystal,
    cassini_permutation,
    partition_interval,
)


class TestSearchCrystal(unittest.TestCase):
    def test_search_crystal_is_the_complete_dual_face_set(self) -> None:
        crystal = build_search_crystal()

        self.assertEqual(len(crystal), 32)
        self.assertEqual(sum(face.solid == "dodecahedron" for face in crystal), 12)
        self.assertEqual(sum(face.solid == "icosahedron" for face in crystal), 20)
        self.assertEqual(len({face.face_id for face in crystal}), 32)
        self.assertEqual(
            len({tuple(round(x, 12) for x in face.normal_3d) for face in crystal}), 32
        )

        for face in crystal:
            self.assertTrue(
                math.isclose(sum(x * x for x in face.normal_3d), 1.0, abs_tol=1e-12)
            )
            self.assertEqual(len(face.direction_11d), 11)
            self.assertLess(face.poincare_norm_sq, 1.0)
            self.assertIn(face.cassini_determinant, (-1, 1))

    def test_partition_interval_is_disjoint_and_complete(self) -> None:
        for size in [1, 2, 31, 32, 33, 1031]:
            with self.subTest(size=size):
                parts = partition_interval(start=17, size=size, partitions=32)
                flattened = [value for part in parts for value in range(part.start, part.stop)]

                self.assertEqual(flattened, list(range(17, 17 + size)))
                self.assertEqual(sum(part.size for part in parts), size)
                self.assertTrue(all(parts[i].stop == parts[i + 1].start for i in range(31)))

    def test_cassini_permutation_covers_each_shard_once(self) -> None:
        for width in [1, 2, 7, 16, 31, 32, 97]:
            with self.subTest(width=width):
                schedule = cassini_permutation(width=width, face_id=11, seed=29)
                offsets = list(schedule)

                self.assertEqual(len(schedule), width)
                self.assertEqual(sorted(offsets), list(range(width)))
                self.assertIn(schedule.cassini_determinant, (-1, 1))
                self.assertEqual(math.gcd(schedule.stride, width), 1)

    def test_full_uint32_schedule_is_lazy_and_constant_space(self) -> None:
        schedule = cassini_permutation(width=2**32, face_id=31, seed=7)

        self.assertEqual(len(schedule), 2**32)
        self.assertEqual(math.gcd(schedule.stride, 2**32), 1)
        self.assertEqual(len({schedule.offset_at(i) for i in range(64)}), 64)

    def test_search_is_consensus_verified_and_coverage_complete(self) -> None:
        engine = PoincareCassiniSearchEngine(total_nonce_space=64)
        header = bytes(80)

        miss = engine.search(header=header, target=bytes(32))
        self.assertIsNone(miss.winner_nonce)
        self.assertEqual(miss.hashes_checked, 64)
        self.assertTrue(miss.coverage_complete)
        self.assertEqual(miss.coverage_fraction, 1.0)
        self.assertEqual(miss.truth_class, "computational")

        hit = engine.search(header=header, target=b"\xff" * 32)
        self.assertIsNotNone(hit.winner_nonce)
        self.assertIsNotNone(hit.winner_hash)
        self.assertLess(
            int.from_bytes(hit.winner_hash, "little"), int.from_bytes(b"\xff" * 32, "big")
        )
        self.assertEqual(hit.hashes_checked, 1)

    def test_budgeted_search_reports_partial_coverage_without_false_pruning(self) -> None:
        engine = PoincareCassiniSearchEngine(total_nonce_space=96)
        result = engine.search(header=bytes(76), target=bytes(32), max_hashes=17)

        self.assertIsNone(result.winner_nonce)
        self.assertEqual(result.hashes_checked, 17)
        self.assertFalse(result.coverage_complete)
        self.assertAlmostEqual(result.coverage_fraction, 17 / 96)
        self.assertLess(result.faces_exhausted, 32)

    def test_consensus_target_boundary_is_strict_and_little_endian(self) -> None:
        engine = PoincareCassiniSearchEngine(total_nonce_space=1)
        header = bytes(76)
        candidate_hash = engine.search(header, b"\xff" * 32).winner_hash
        self.assertIsNotNone(candidate_hash)
        hash_value = int.from_bytes(candidate_hash, "little")

        equal_target = hash_value.to_bytes(32, "big")
        rejected = engine.search(header, equal_target)
        self.assertIsNone(rejected.winner_nonce)
        self.assertTrue(rejected.coverage_complete)

        accepted = engine.search(header, (hash_value + 1).to_bytes(32, "big"))
        self.assertEqual(accepted.winner_nonce, 0)

    def test_agentic_entrypoint_delegates_to_verified_search_crystal(self) -> None:
        controller = AgenticController(total_nonce_space=64, max_qubits=4, max_threads=1)
        result = controller.search(bytes(80), bytes(32), max_faces=32)

        self.assertEqual(result["search_engine"], "poincare_cassini_32_face")
        self.assertEqual(result["total_hashes"], 64)
        self.assertTrue(result["coverage_complete"])
        self.assertIsNone(result["winner_nonce"])
        self.assertEqual(result["truth_class"], "computational")

    def test_invalid_contracts_fail_closed(self) -> None:
        engine = PoincareCassiniSearchEngine(total_nonce_space=8)
        with self.assertRaisesRegex(ValueError, "76 or 80"):
            engine.search(header=b"short", target=bytes(32))
        with self.assertRaisesRegex(ValueError, "32 bytes"):
            engine.search(header=bytes(80), target=b"short")


if __name__ == "__main__":
    unittest.main()
