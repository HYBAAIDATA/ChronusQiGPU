"""First-principles verification for the Kellogg tensor package.

These tests prove the *mathematics* directly: field axioms over Q(zeta_8),
gate identities, exact Born weights, entanglement structure (Schmidt rank,
reduced density matrices), the exact QFT, and the documented boundary
between the exact plane (F4 fractions) and the finite-precision plane
(IEEE-754 complex).
"""

import random
import unittest
from fractions import Fraction

import kellogg
import kellogg.exact_tensor as kt
import kellogg.quantum_tensor
import kellogg.tensor_ml
from kellogg.exact_tensor import (
    F4,
    GATES,
    I_UNIT,
    ONE,
    ZERO,
    ZETA8,
    ExactStateVector,
    ExactTOETensor,
    Qsqrt2,
    density_is_pure,
    density_purity,
    density_trace,
)
from kellogg.quantum_tensor import QuantumState


class FieldAxiomTests(unittest.TestCase):
    """F4 = Q(zeta_8) is a field: closure, inverses, conjugation, norm."""

    def test_ring_axioms(self):
        a, b, c = F4(1, 2, 3, 4), F4(Fraction(1, 3), 0, -1, 2), F4(0, 1, 0, -1)
        self.assertEqual(a + b, b + a)
        self.assertEqual(a * b, b * a)
        self.assertEqual((a + b) * c, a * c + b * c)
        self.assertEqual((a * b) * c, a * (b * c))
        self.assertEqual(a + ZERO, a)
        self.assertEqual(a * ONE, a)

    def test_inverse_and_norm(self):
        z = F4(3, -1, 2, 1)
        self.assertEqual(z * z.inverse(), ONE)
        n = z.norm2()
        self.assertEqual(n, z.real * z.real + z.imag * z.imag)
        self.assertGreater(n.sign(), 0)

    def test_zeta8_powers_close_under_field(self):
        z = ZETA8
        acc = ONE
        for _ in range(8):
            acc = acc * z
        self.assertEqual(acc, ONE)  # zeta_8^8 = 1 exactly

    def test_ordered_field_sign(self):
        self.assertEqual(Qsqrt2(1, -1).sign(), -1)  # 1 - sqrt(2) < 0
        self.assertEqual(Qsqrt2(3, -2).sign(), 1)  # 3 - 2*sqrt(2) > 0
        self.assertEqual(Qsqrt2(-3, 2).sign(), -1)  # -3 + 2*sqrt(2) < 0


class GateIdentityTests(unittest.TestCase):
    """Clifford+T identities proved on exact amplitudes, not floats."""

    def test_T_squared_is_S(self):
        s = ExactStateVector.basis(1, 1)
        self.assertEqual(
            s.apply_single(0, GATES["T"]).apply_single(0, GATES["T"]).amplitudes,
            s.apply_single(0, GATES["S"]).amplitudes,
        )

    def test_S_squared_is_Z(self):
        s = ExactStateVector.basis(1, 1)
        self.assertEqual(
            s.apply_single(0, GATES["S"]).apply_single(0, GATES["S"]).amplitudes,
            s.apply_single(0, GATES["Z"]).amplitudes,
        )

    def test_adjoints_invert(self):
        s = ExactStateVector.basis(1, 0).apply_single(0, GATES["H"])
        self.assertEqual(
            s.apply_single(0, GATES["T"]).apply_single(0, GATES["Tdg"]).amplitudes,
            s.amplitudes,
        )
        self.assertEqual(
            s.apply_single(0, GATES["S"]).apply_single(0, GATES["Sdg"]).amplitudes,
            s.amplitudes,
        )

    def test_HZH_equals_X(self):
        s = ExactStateVector.basis(1, 0)
        hzh = (
            s.apply_single(0, GATES["H"])
            .apply_single(0, GATES["Z"])
            .apply_single(0, GATES["H"])
        )
        self.assertEqual(hzh.amplitudes, s.apply_single(0, GATES["X"]).amplitudes)

    def test_every_declared_gate_is_exactly_unitary(self):
        for name, gate in GATES.items():
            with self.subTest(gate=name):
                kt._validate_gate(gate)  # raises unless U†U == I exactly

    def test_cnot_truth_table(self):
        # |10> (control=q0 set) -> |11>; |01> -> |01>; |00> -> |00>
        s = ExactStateVector.basis(2, 0).apply_single(0, GATES["X"])
        out = s.apply_cnot(0, 1)
        self.assertEqual(out.amplitudes[3], ONE)
        untouched = ExactStateVector.basis(2, 2).apply_cnot(0, 1)
        self.assertEqual(untouched.amplitudes[2], ONE)

    def test_toffoli_and_swap_and_cz(self):
        # Toffoli: controls q0,q1 set (index 0b011 = 3), target q2 -> |111>
        s = ExactStateVector.basis(3, 3)
        self.assertEqual(s.apply_toffoli(0, 1, 2).amplitudes[7], ONE)
        # target already set -> maps back: |111> -> |011>
        s7 = ExactStateVector.basis(3, 7)
        self.assertEqual(s7.apply_toffoli(0, 1, 2).amplitudes[3], ONE)
        # SWAP: |10> -> |01>
        s2 = ExactStateVector.basis(2, 1)
        self.assertEqual(s2.apply_swap(0, 1).amplitudes[2], ONE)
        # CZ on |11> -> -|11>
        s3 = ExactStateVector.basis(2, 3)
        self.assertEqual(s3.apply_cz(0, 1).amplitudes[3], -ONE)


class ExactQuantumTests(unittest.TestCase):
    """Born rule, entanglement structure, partial trace, QFT — all exact."""

    def test_bell_state_entanglement(self):
        bell = (
            ExactStateVector.basis(2, 0)
            .apply_single(0, GATES["H"])
            .apply_cnot(0, 1)
        )
        self.assertTrue(bell.normalized_exact())
        self.assertEqual(bell.schmidt_rank([0]), 2)
        rho = bell.reduced_density([0])
        self.assertEqual(rho[0][0], F4(Fraction(1, 2)))
        self.assertEqual(rho[1][1], F4(Fraction(1, 2)))
        self.assertEqual(rho[0][1], ZERO)
        self.assertEqual(density_trace(rho), ONE)
        self.assertFalse(density_is_pure(rho))
        self.assertEqual(density_purity(rho), F4(Fraction(1, 2)))

    def test_product_state_separates(self):
        prod = (
            ExactStateVector.basis(2, 0)
            .apply_single(0, GATES["H"])
            .apply_single(1, GATES["H"])
        )
        self.assertEqual(prod.schmidt_rank([0]), 1)
        self.assertTrue(density_is_pure(prod.reduced_density([0])))

    def test_born_weights_exact_and_measurements(self):
        s = ExactStateVector.basis(2, 0).apply_single(0, GATES["H"])
        weights = s.probabilities_exact()
        self.assertEqual(sum(weights, Qsqrt2()), Qsqrt2(1))
        self.assertEqual(s.measure_deterministic(), 0)  # tie -> lowest index
        # Born sampling is exact-CDF driven; degenerate state always same cell
        self.assertEqual(ExactStateVector.basis(2, 3).sample_born(random.Random(0)), 3)
        rng = random.Random(1234)
        counts = [0] * 4
        for _ in range(4000):
            counts[s.sample_born(rng)] += 1
        # |+> on qubit 0: outcomes {00, 01} each with weight exactly 1/2
        self.assertEqual(counts[2], 0)
        self.assertEqual(counts[3], 0)
        self.assertGreater(counts[0], 1500)
        self.assertGreater(counts[1], 1500)

    def test_pauli_expectations(self):
        plus = ExactStateVector.basis(1, 0).apply_single(0, GATES["H"])
        self.assertEqual(plus.expectation_pauli(0, "X"), Qsqrt2(1))
        self.assertEqual(plus.expectation_pauli(0, "Z"), Qsqrt2())
        self.assertEqual(ExactStateVector.basis(1, 1).expectation_pauli(0, "Z"), Qsqrt2(-1))

    def test_z_eighths_phases(self):
        s = ExactStateVector.basis(1, 1)
        self.assertEqual(s.z_eighths(2).amplitudes[1], I_UNIT)  # pi/2 = i
        self.assertEqual(s.z_eighths(4).amplitudes[1], -ONE)  # pi = -1
        self.assertEqual(s.z_eighths(8).amplitudes[1], ONE)  # full turn

    def test_qft_exact(self):
        # n=1: QFT|1> = |-> = (|0> - |1>)/sqrt(2)
        q1 = ExactStateVector.basis(1, 1).qft()
        self.assertEqual(q1.amplitudes[0], F4(0, Fraction(1, 2)))
        self.assertEqual(q1.amplitudes[1], F4(0, -Fraction(1, 2)))
        # n=3: inverse round-trip is exact
        s3 = ExactStateVector.basis(3, 5)
        self.assertEqual(s3.qft().qft(inverse=True).amplitudes, s3.amplitudes)
        # n=4 fails closed: zeta_16 is outside F4
        with self.assertRaises(NotImplementedError):
            ExactStateVector.basis(4, 0).qft()

    def test_fidelity_squared_exact(self):
        a = ExactStateVector.basis(1, 0)
        b = ExactStateVector.basis(1, 0).apply_single(0, GATES["H"])
        # |<0|+>|^2 = 1/2 exactly (a=1/2, b=0 — not sqrt(2)/2)
        self.assertEqual(a.fidelity_squared(b), Qsqrt2(Fraction(1, 2)))
        self.assertEqual(a.fidelity_squared(a), Qsqrt2(1))

    def test_toe_witness_determinism(self):
        tensor = ExactTOETensor()
        first = tensor.evaluate({"job": "abc"}, quarter_turns=1)
        second = tensor.evaluate({"job": "abc"}, quarter_turns=1)
        self.assertEqual(first["state_commitment"], second["state_commitment"])
        self.assertTrue(first["normalized_exact"])
        self.assertFalse(first["theorem_proven"])


class PlaneBoundaryTests(unittest.TestCase):
    """The exact->float boundary is explicit, one-way, and documented."""

    def test_exact_state_embeds_into_float_substrate(self):
        plus = ExactStateVector.basis(1, 0).apply_single(0, GATES["H"])
        projected = QuantumState.from_exact_state(plus)
        probs = projected.probabilities()
        self.assertAlmostEqual(probs[0], 0.5, places=15)
        self.assertAlmostEqual(probs[1], 0.5, places=15)

    def test_float_born_sampling_is_seeded(self):
        state = QuantumState.from_basis(4, 0)
        out1, _, post1 = state.measure_born(random.Random(7))
        out2, _, post2 = state.measure_born(random.Random(7))
        self.assertEqual(out1, out2)
        self.assertEqual(post1.probabilities()[out1], 1.0)

    def test_complex_dunder_algebra(self):
        from kellogg.quantum_tensor import Complex

        z = Complex(1.0, 2.0) * Complex(3.0, -1.0)
        self.assertEqual(z, Complex(5.0, 5.0))
        self.assertEqual(Complex(1.0, 0.0) + 2.0, Complex(3.0, 0.0))
        self.assertEqual(abs(Complex(3.0, 4.0)), 5.0)

    def test_retired_toe_paths_do_not_resolve(self):
        import importlib
        import sys as _sys

        # The tensor implementation lives in kellogg/ only — no toe.* alias
        # modules survive the consolidation.
        for retired in ("toe.exact_tensor", "toe.quantum_tensor", "toe.tensor_ml"):
            with self.subTest(module=retired):
                _sys.modules.pop(retired, None)
                with self.assertRaises(ModuleNotFoundError):
                    importlib.import_module(retired)


class TensorDataPlaneTests(unittest.TestCase):
    """tensor_ml: real partial trace, CV index integrity, plane guards."""

    def test_partial_trace_is_true_kronecker_trace(self):
        from kellogg.tensor_ml import TensorState, joint, partial_trace

        left = TensorState.from_values([[1, 2]])
        right = TensorState.from_values([[3, 4]])
        j = joint(left, right)
        # J = L ⊗ R = [[3,4,6,8]]; Tr_R(J) = Tr(R) * L = 3 * [1,2] = [3,6]
        traced = partial_trace(j, (0,))
        self.assertEqual(
            _diag(traced.rows[0][0]), 3.0
        )  # wait: diag of R over min(rR,cR)=1 -> R[0][0] = 3
        self.assertEqual(traced.shape, (1, 2))
        traced_r = partial_trace(j, (1,))
        # Tr_L(J) = Tr(L) * R = 1 * [3,4]
        self.assertEqual(traced_r.shape, (1, 2))
        self.assertEqual(_diag(traced_r.rows[0][0]), 3.0)
        self.assertEqual(_diag(traced_r.rows[0][1]), 4.0)

    def test_cv_folds_carry_indices_no_leakage(self):
        import numpy as np

        from kellogg.tensor_ml import TensorState, joint_for_cv

        # duplicate rows must not corrupt the split
        X = np.array([[1.0, 1.0], [1.0, 1.0], [2.0, 2.0], [3.0, 3.0]])
        state = TensorState.from_values(X)
        seen_test = set()
        for fold in joint_for_cv(state, 2):
            self.assertFalse(set(fold.train_indices) & set(fold.test_indices))
            self.assertEqual(
                sorted(fold.train_indices + fold.test_indices), list(range(4))
            )
            seen_test.update(fold.test_indices)
        self.assertEqual(seen_test, set(range(4)))

    def test_median_rejects_complex_channel(self):
        from kellogg.tensor_ml import PlaneViolation, median_f

        with self.assertRaises(PlaneViolation):
            median_f([F4(0, 0, 1, 0), F4(1)])

    def test_package_surface(self):
        self.assertEqual(kellogg.F4(1) + kellogg.F4(0, 1), F4(1, 1))
        self.assertTrue(callable(kellogg.exact_linear))


def _diag(value: F4) -> float:
    return float(value.a) + float(value.b) * (2.0**0.5)


if __name__ == "__main__":
    unittest.main()
