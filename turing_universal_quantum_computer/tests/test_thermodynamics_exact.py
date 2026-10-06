import unittest
from fractions import Fraction

from turing_universal_quantum_computer.thermodynamics_exact import (
    LandauerExpression,
    thermodynamic_boundary_report,
)


class ThermodynamicsExactTests(unittest.TestCase):
    def test_landauer_expression_remains_exact_and_symbolic(self):
        expression = LandauerExpression(256, Fraction(3, 100))
        self.assertEqual(
            expression.coefficient_of_kb_ln2_joules,
            Fraction(192, 25),
        )
        self.assertFalse(expression.as_dict()["numerical_value_asserted"])

    def test_truth_boundary_rejects_false_reversible_mining_claim(self):
        report = thermodynamic_boundary_report()
        self.assertTrue(report.sha256d_output_many_to_one)
        self.assertTrue(report.reversible_embedding_possible)
        self.assertTrue(report.end_to_end_reset_obligations_remain)
        self.assertFalse(report.pure_math_energy_claim)
        self.assertEqual(len(report.proof_digest), 64)


if __name__ == "__main__":
    unittest.main()