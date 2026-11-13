"""Exact mathematical supposition tests: interference, adversarial and property."""
import unittest
from hypothesis import given, settings, strategies as st
from euclid.quantum_supposition import Supposition, exact_supposition_interference


def cases(n):
    return tuple(Supposition(f"h{i}", f"proposition {i}") for i in range(1 << n))


class ExactSuppositionTests(unittest.TestCase):
    def test_one_qubit_oracle_changes_interference(self):
        c = cases(1)
        unchanged = exact_supposition_interference(c, frozenset())
        marked = exact_supposition_interference(c, frozenset({"h1"}))
        self.assertEqual(
            [x["born_probability_exact"] for x in unchanged["hypotheses"]], ["1", "0"]
        )
        self.assertEqual(
            [x["born_probability_exact"] for x in marked["hypotheses"]], ["0", "1"]
        )
        self.assertEqual(marked["oracle_evidence"], "UNVERIFIED_CALLER_ASSERTION")
        self.assertFalse(marked["authority_granted"])

    def test_global_phase_does_not_change_probabilities(self):
        for n in range(1, 5):
            c = cases(n)
            none = exact_supposition_interference(c, frozenset())
            all_marked = exact_supposition_interference(c, frozenset(x.name for x in c))
            self.assertEqual(
                [x["born_probability_exact"] for x in none["hypotheses"]],
                [x["born_probability_exact"] for x in all_marked["hypotheses"]],
            )

    @settings(max_examples=65, deadline=None)
    @given(st.integers(min_value=1, max_value=5), st.integers(min_value=0, max_value=65535))
    def test_exact_normalization_for_many_phase_oracles(self, n, mask):
        c = cases(n)
        oracle = frozenset(x.name for i, x in enumerate(c) if mask & (1 << i))
        r = exact_supposition_interference(c, oracle)
        self.assertTrue(r["normalization_exact"])
        self.assertEqual(len(r["hypotheses"]), 1 << n)
        self.assertFalse(r["quantum_advantage_claim"])

    def test_invalid_basis_rejected(self):
        with self.assertRaises(ValueError):
            exact_supposition_interference((Supposition("only", "p"),), frozenset())
        with self.assertRaises(ValueError):
            exact_supposition_interference(cases(1), frozenset({"unknown"}))
        c = cases(1)
        with self.assertRaises(ValueError):
            exact_supposition_interference((c[0], c[0]), frozenset())

    def test_deterministic_manifest_and_measure(self):
        c = cases(3)
        a = exact_supposition_interference(c, frozenset({"h2", "h4"}))
        b = exact_supposition_interference(c, frozenset({"h4", "h2"}))
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
