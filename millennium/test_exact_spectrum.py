#!/usr/bin/env python3
"""Exact 2I Laplace spectrum recomputed from the class algebra.

Floats may only conjecture; exact arithmetic decides.  Every level
lambda_rho = 1 - chi_rho(g_edge)/d_rho reported by
``hyba_poincare_yangmills.exact_spectrum`` is a Q(sqrt 5) value verified
against the integer class algebra, column orthogonality, the measured
eigvalsh spectrum (multiplicities d^2), and the proof-carrying level
table of ``millennium.exact_gap``.  The gap identities

    Delta = (3 - sqrt5)/4 = 1 - phi/2 = 1/(2 phi^2)

and the conjugate partner (3 + sqrt5)/4 are asserted exactly.
"""

from __future__ import annotations

import math
import unittest
from fractions import Fraction

import numpy as np

from kellogg.substrate import QPhi
from millennium import hyba_poincare_yangmills as hpy
from millennium.exact_gap import exact_gap_from_class_algebra

SQRT5 = math.sqrt(5.0)


def _pqk_float(pqk):
    p, q, k = pqk
    return (p + q * SQRT5) / k


class ExactSpectrumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.elist = list(hpy.build_2I())
        cls.classes = hpy.conjugacy_classes(cls.elist)
        cls.sizes = [len(c) for c in cls.classes]
        cls.c = hpy.class_multiplication(cls.elist, cls.classes)
        cls.sclass = hpy.edge_class_index(cls.classes)
        cls.spectrum = hpy.exact_spectrum(cls.elist, cls.classes, cls.sizes, cls.sclass)

    def test_edge_class_is_exact_not_a_float_tolerance(self) -> None:
        self.assertTrue(all(e[0] == (1, 1) for e in self.classes[self.sclass]))
        self.assertEqual(self.sizes[self.sclass], 12)

    def test_conjectures_reproduce_the_computed_float_table(self) -> None:
        chi_f, dims_f, _ = hpy.character_table(self.elist, self.classes, self.sizes)
        for rho in range(9):
            for i in range(9):
                v = self.spectrum["chi"][rho][i]
                self.assertAlmostEqual(v.a + v.b * hpy.PHI, float(chi_f[rho][i]), places=6)
        self.assertEqual(self.spectrum["dims"], [int(round(d)) for d in dims_f])

    def test_character_table_satisfies_exact_column_orthogonality(self) -> None:
        chi = self.spectrum["chi"]
        for rho in range(9):
            for sig in range(9):
                s = sum((self.sizes[i] * chi[rho][i] * chi[sig][i] for i in range(9)), QPhi(0, 0))
                want = QPhi(120, 0) if rho == sig else QPhi(0, 0)
                self.assertEqual(s, want, f"rho={rho} sig={sig}")

    def test_class_algebra_omega_identity_holds_exactly(self) -> None:
        chi = self.spectrum["chi"]
        dims = self.spectrum["dims"]
        k = len(self.classes)
        omega = [[self.sizes[i] * chi[rho][i] / dims[rho] for i in range(k)] for rho in range(k)]
        for rho in range(k):
            for i in range(k):
                for j in range(k):
                    rhs = QPhi(0, 0)
                    for l in range(k):
                        n = int(self.c[i][j][l])
                        if n:
                            rhs = rhs + n * omega[rho][l]
                    self.assertEqual(omega[rho][i] * omega[rho][j], rhs, f"rho={rho} i={i} j={j}")

    def test_levels_match_measured_spectrum_with_multiplicity_d_squared(self) -> None:
        S = hpy.fixed_generating_set(self.elist)
        L = hpy.group_laplacian(self.elist, S)
        ev = np.sort(np.linalg.eigvalsh(L))
        used = np.zeros(len(ev), dtype=bool)
        for lv in self.spectrum["levels"]:
            target = _pqk_float(lv["eigenvalue"])
            hits = np.where(np.abs(ev - target) < 1e-9)[0]
            self.assertEqual(len(hits), lv["multiplicity"], f"level {lv}")
            self.assertFalse(bool(used[hits].any()), f"overlapping level {lv}")
            used[hits] = True
        self.assertTrue(bool(used.all()))
        self.assertEqual(sum(lv["multiplicity"] for lv in self.spectrum["levels"]), 120)

    def test_gap_is_exactly_three_minus_root5_over_four(self) -> None:
        positive = [lv for lv in self.spectrum["levels"] if lv["lambda_qphi"].sign() > 0]
        gap_level = min(positive, key=lambda lv: lv["lambda_qphi"])
        gap_q = gap_level["lambda_qphi"]
        self.assertEqual(gap_level["dimension"], 2)
        self.assertEqual(gap_level["multiplicity"], 4)
        self.assertEqual(gap_q, QPhi(1, 0) - QPhi(0, Fraction(1, 2)))  # 1 - phi/2
        self.assertAlmostEqual(gap_q.a + gap_q.b * hpy.PHI, (3.0 - SQRT5) / 4.0, places=12)
        self.assertEqual(gap_level["eigenvalue"], (3, -1, 4))
        self.assertEqual(gap_q, QPhi(2, 2).inverse())  # 1/(2 phi^2)
        self.assertEqual(gap_level["character_over_dim"], (1, 1, 4))  # chi/d = phi/2

    def test_conjugate_partner_level_is_exact(self) -> None:
        two = [lv for lv in self.spectrum["levels"] if lv["dimension"] == 2]
        self.assertEqual(len(two), 2)
        gap_q = min(lv["lambda_qphi"] for lv in two)
        partner = max(lv["lambda_qphi"] for lv in two)
        self.assertEqual(partner, gap_q.conjugate())
        self.assertEqual(partner, QPhi(Fraction(1, 2), Fraction(1, 2)))  # (3 + sqrt5)/4
        self.assertAlmostEqual(partner.a + partner.b * hpy.PHI, (3.0 + SQRT5) / 4.0, places=12)
        self.assertEqual(gap_q + partner, QPhi(Fraction(3, 2), 0))
        self.assertEqual(gap_q * partner, QPhi(Fraction(1, 4), 0))

    def test_levels_cross_check_the_proof_carrying_gap_table(self) -> None:
        from_exact_gap = {
            (lvl.dimension, lvl.eigenvalue_exact) for lvl in exact_gap_from_class_algebra().levels
        }
        from_spectrum = {(lv["dimension"], lv["eigenvalue"]) for lv in self.spectrum["levels"]}
        self.assertEqual(from_exact_gap, from_spectrum)

    def test_run_report_carries_the_exact_derivation(self) -> None:
        report = hpy.cached_report(verbose=False)
        self.assertEqual(report["gap_algebraic"], {"p": 1, "q": 1, "k": 4})
        derived = sorted(
            (lv["dimension"], lv["character_over_dim"]) for lv in self.spectrum["levels"]
        )
        reported = sorted(
            (
                lv["dimension"],
                (
                    lv["character_over_dim"]["p"],
                    lv["character_over_dim"]["q"],
                    lv["character_over_dim"]["k"],
                ),
            )
            for lv in report["exact"]
        )
        self.assertEqual(reported, derived)


if __name__ == "__main__":
    unittest.main()
