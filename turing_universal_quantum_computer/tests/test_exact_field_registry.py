import unittest

from turing_universal_quantum_computer.exact_field_registry import (
    QZeta8,
    ZETA_8,
    verify_q_zeta_8_registry,
)


class ExactFieldRegistryTests(unittest.TestCase):
    def test_unified_field_registry_is_exact_and_replayable(self):
        first = verify_q_zeta_8_registry()
        second = verify_q_zeta_8_registry()
        self.assertTrue(first.verified)
        self.assertEqual(first, second)
        self.assertEqual(first.degree_over_q, 4)
        self.assertIn("T", first.exact_gate_domain)
        self.assertEqual(len(first.proof_digest), 64)
        self.assertIsInstance(ZETA_8, QZeta8)


if __name__ == "__main__":
    unittest.main()