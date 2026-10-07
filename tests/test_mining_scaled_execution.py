"""Mining owns the scaled execution plane: the LucasScaledAethelExecutionAdapter
that certifies a work window, orders it by the Hendrix schedule, round-trips the
tensor fold and grinds sha256d. It consumes TURING; it is not part of it."""

import unittest

from mining.scaled_execution import LucasScaledAethelExecutionAdapter
from toe.strict_quantum import certify_work_window, verify_certificate


class StrictWorkWindowTests(unittest.TestCase):
    def test_strict_quantum_certificate(self):
        cert = certify_work_window(bytes(range(76)), nonce_start=0, nonce_count=256)
        self.assertTrue(verify_certificate(cert))
        self.assertFalse(cert["consensus_authority"])
        self.assertFalse(cert["theorem_proven"])


class ScaledExecutionTests(unittest.TestCase):
    def test_execution_certifies_window(self):
        adapter = LucasScaledAethelExecutionAdapter(scale_index=76)
        header = bytes(range(76)) + (0).to_bytes(4, "little")
        # No nonce can meet a zero target: the whole window is hashed and a
        # window without a winner completes (the ordinary case in mining).
        result = adapter.execute(header, target=0, base_nonce=0, count=256)
        self.assertEqual(result.hashes, 256)
        self.assertIsNone(result.winner)
        self.assertTrue(result.metadata["fold_roundtrip_lossless"])
        self.assertTrue(result.metadata["cassini_holds"])
        self.assertTrue(result.metadata["toe"]["provenance_verified"])

    def test_execution_stops_at_the_schedules_first_winner(self):
        adapter = LucasScaledAethelExecutionAdapter(scale_index=76)
        header = bytes(range(76)) + (0).to_bytes(4, "little")
        # Every nonce meets the maximal target: the first scheduled one wins.
        result = adapter.execute(header, target=(1 << 256) - 1, base_nonce=0, count=256)
        self.assertEqual(result.hashes, 1)
        self.assertIsNotNone(result.winner)
        self.assertTrue(result.metadata["chronus"]["recheck_bit_exact"])

    def test_adapter_accepts_any_width(self):
        a = LucasScaledAethelExecutionAdapter(n_qubits=23, scale_index=76)
        self.assertEqual(a.n_qubits, 23)
        a2 = LucasScaledAethelExecutionAdapter(n_qubits=10_000, scale_index=76)
        self.assertEqual(a2.n_qubits, 10_000)
        with self.assertRaises(ValueError):
            LucasScaledAethelExecutionAdapter(n_qubits=0)


if __name__ == "__main__":
    unittest.main()
