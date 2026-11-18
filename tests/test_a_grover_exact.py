"""Owner A — millennium/grover_exact_scale (FoldedGrover + Lucas-Pisot).

The folded Grover iterate lives on the 2D exchange-symmetric subspace:
exact complex arithmetic, O(1) memory, verified bit-for-bit against the
dense-matrix GroverSearch reference. These tests pin the Cassini witness,
the closed-form agreement, the Pisot-damped Lucas ladder rows, and the
binet_residual computation across the float64-cancellation boundary.
"""

from __future__ import annotations

import math

import pytest

from lucas import core as lucas_core
from millennium import grover_exact_scale as ges
from millennium.grover_exact_scale import (
    ITERATION_CAP,
    PSI,
    FoldedGrover,
)

# --- folded iterate vs closed form / dense reference ------------------------


def test_uniform_state_satisfies_cassini_witness():
    s = FoldedGrover.uniform(16, 1)
    assert s.cassini_witness() == pytest.approx(1.0)
    assert s.cassini_witness_exact() == 1


def test_step_preserves_cassini_witness():
    s = FoldedGrover.uniform(64, 1)
    for _ in range(6):
        s.step()
        assert s.cassini_witness() == pytest.approx(1.0, abs=1e-12)


def test_folded_matches_closed_form():
    for N, M in ((4, 1), (16, 1), (64, 1), (256, 3)):
        r = ges.run_folded(N, M)
        assert r["P_marked"] == pytest.approx(r["P_analytic_full"], abs=1e-9)
        assert r["cassini_drift"] < 1e-12


def test_folded_matches_dense_matrix_reference():
    for n_qubits in (2, 4, 6):
        r = ges.verify_against_matrix(n_qubits, [(1 << n_qubits) - 1])
        assert r["match"], r


def test_optimal_iterations_grover_bound():
    # k* = floor(pi / (4 theta)), theta = asin(sqrt(M/N)).
    assert ges.optimal_iterations(16, 1) == 3
    assert ges.optimal_iterations(4, 1) == 1
    assert ges.optimal_iterations(16, 4) == 1  # theta = pi/6 -> floor(3/2)
    assert ges.optimal_iterations(16, 16) == 0  # M >= N degenerates
    assert ges.optimal_iterations(16, 0) == 0


def test_analytical_success_classical():
    # N=4, M=1, k=1 -> sin^2(3 * pi/6) = 1 exactly.
    assert ges.analytical_success(4, 1, 1) == pytest.approx(1.0)


# --- Pisot / Lucas-Pisot layer -----------------------------------------------


def test_pisot_damp_converges_to_one():
    from kellogg.scales import ZPHI_ONE, ZPHI_ZERO
    from python_backend.exact_folded_grover import zphi_lt_rational

    vals = [ges.pisot_damp(n) for n in (10, 12, 15, 18, 20, 31, 50, 76)]
    # 0 < 1 - phi^{-n} < 1  <=>  0 < phi^{-n} < 1, n >= 1.
    assert all((v - ZPHI_ZERO).sign() > 0 and (ZPHI_ONE - v).sign() > 0 for v in vals)
    assert all((vals[i + 1] - vals[i]).sign() > 0 for i in range(len(vals) - 1))
    # pisot_damp(76) > 1 - 1e-15  <=>  phi^{-76} < 1e-15.
    assert zphi_lt_rational(ges.binet_residual(76), 1, 10**15)


def test_binet_residual_exact_small_n():
    """|phi^n - L_n| = |psi|^n exactly in Z[phi]; monotone in the real embedding."""
    from kellogg.scales import ZPHI_ONE, pisot_drift

    for n in range(10, 26):
        residual = ges.binet_residual(n)
        assert residual == (ges.PHI - ZPHI_ONE) ** n
        assert residual == (-ges.PSI) ** n
        signed = pisot_drift(n)
        # signed = phi^n - L_n = -psi^n; N(psi) = -1, so N(signed) = (-1)^n.
        assert signed.norm() == (-1) ** n
        assert (ges.binet_residual(n - 1) - residual).sign() > 0


def test_binet_residual_beyond_mantissa():
    """The residual is the exact Z[phi] element phi^{-76}, not a float64
    subtraction of phi^76 - L_76 (which used to cancel to garbage ~19)."""
    from kellogg.scales import ZPHI_ONE, pisot_drift
    from python_backend.exact_folded_grover import zphi_lt_rational

    r76 = ges.binet_residual(76)
    assert r76 == (ges.PHI - ZPHI_ONE) ** 76
    assert r76 == (-PSI) ** 76
    assert zphi_lt_rational(r76, 1, 10**15)
    d = pisot_drift(76)
    assert (d.a, d.b) == (-5527939700884757, 3416454622906707)
    assert d.norm() == 1  # norm(-psi^76) = (-1)^76


def test_convergence_bits_monotone():
    a = ges.convergence_bits(10)
    b = ges.convergence_bits(76)
    assert 0 < a < b


# --- scoreboards / pool score -----------------------------------------------


def test_decade_row_matches_analytic():
    for power in (2, 4, 6):
        r = ges.decade_row(power)
        assert r["P_measured"] == pytest.approx(r["P_analytic"], abs=1e-9)


def test_lucas_row_ladder():
    for n in (10, 15, 20):
        r = ges.lucas_row(n)
        assert r["L_n"] == lucas_core.lucas(n)
        assert r["N_eff"] == 64 * r["L_n"]
        assert r["cassini"] is True
        assert r["damp"] == ges.pisot_damp(n)
        if r["k"] <= ITERATION_CAP:
            assert r["P_marked"] > 0.99
            assert r["cassini_drift"] < 1e-9


def test_pool_kernel_score_all_bounded():
    r = ges.pool_kernel_score(4, 1)
    assert r["step_bounded"] and r["fold_bounded"] and r["amplitude_bounded"]
    assert r["is_lucas_bounded"] is True
    r2 = ges.pool_kernel_score(64 * lucas_core.lucas(15), 1)
    assert r2["is_lucas_bounded"] is True
