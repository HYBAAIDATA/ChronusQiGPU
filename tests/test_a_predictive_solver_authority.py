from __future__ import annotations

import hashlib
import struct
import unittest

from Intelligence.predictive_solver import PredictiveSolver


HEADER = bytes(range(80))


def _sha256d(nonce: int) -> bytes:
    payload = HEADER[:76] + struct.pack("<I", nonce)
    return hashlib.sha256(hashlib.sha256(payload).digest()).digest()


def _force_candidate(solver: PredictiveSolver, nonce: int) -> None:
    solver._generate_candidates = lambda _header, _features: [
        (nonce, 1.0, "forced")
    ]


class PredictiveSolverAuthorityTests(unittest.TestCase):
    def test_solve_rejects_noncanonical_header_lengths(self) -> None:
        for length in (0, 76, 79, 81):
            with self.subTest(length=length):
                with self.assertRaisesRegex(ValueError, "header must be 80 bytes"):
                    PredictiveSolver().solve(bytes(length), bytes(32))

    def test_solve_rejects_noncanonical_target_lengths(self) -> None:
        for length in (0, 31, 33):
            with self.subTest(length=length):
                with self.assertRaisesRegex(ValueError, "target must be 32 bytes"):
                    PredictiveSolver().solve(HEADER, bytes(length))

    def test_predicted_nonce_is_accepted_only_after_sha256d_target_check(self) -> None:
        solver = PredictiveSolver()
        nonce = 7
        digest = _sha256d(nonce)
        _force_candidate(solver, nonce)

        result = solver.solve(HEADER, digest[::-1])

        self.assertTrue(result.winning)
        self.assertTrue(result.verified)
        self.assertEqual(result.predicted_nonce, nonce)
        self.assertEqual(result.hash_hex, digest.hex())

    def test_fabricated_fallback_nonce_is_not_accepted(self) -> None:
        solver = PredictiveSolver()
        _force_candidate(solver, 1)

        result = solver.solve(
            HEADER,
            bytes(32),
            fallback_search=lambda _header, _target: (0, 1),
        )

        self.assertFalse(result.winning)
        self.assertFalse(result.fallback_found)
        self.assertIsNone(result.fallback_nonce)

    def test_valid_fallback_nonce_is_independently_rechecked(self) -> None:
        first = _sha256d(11)
        second = _sha256d(12)
        fallback_nonce, miss_nonce = (
            (11, 12)
            if int.from_bytes(first, "little") < int.from_bytes(second, "little")
            else (12, 11)
        )
        solver = PredictiveSolver()
        _force_candidate(solver, miss_nonce)

        result = solver.solve(
            HEADER,
            _sha256d(fallback_nonce)[::-1],
            fallback_search=lambda _header, _target: (fallback_nonce, 2),
        )

        self.assertFalse(result.winning)
        self.assertTrue(result.fallback_found)
        self.assertEqual(result.fallback_nonce, fallback_nonce)
        self.assertEqual(result.fallback_hashes, 2)


if __name__ == "__main__":
    unittest.main()
