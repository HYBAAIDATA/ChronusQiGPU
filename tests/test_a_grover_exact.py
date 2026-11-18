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
    vals = [ges.pisot_damp(n) for n in (10, 12, 15, 18, 20, 31, 50, 76)]
    assert all(0 < v < 1 for v in vals)
    assert vals == sorted(vals)
    assert ges.pisot_damp(76) > 1 - 1e-15


def _decimal_phi(prec: int = 60):
    """60-digit phi/psi — enough headroom to evaluate the Z[phi] drift
    element past the cancellation that breaks float64 at n > ~22."""
    from decimal import Decimal, getcontext

    getcontext().prec = prec
    root5 = Decimal(5).sqrt()
    return (1 + root5) / 2, (1 - root5) / 2


def test_binet_residual_exact_small_n():
    """|phi^n - L_n| = |psi|^n exactly — monotone decay, and the value
    matches 60-digit Decimal evaluation of the exact drift element."""
    from decimal import Decimal
    from kellogg.scales import pisot_drift

    phi_d, _ = _decimal_phi()
    for n in range(10, 26):
        assert ges.binet_residual(n) == pytest.approx(abs(PSI) ** n, rel=1e-12)
        d = pisot_drift(n)
        exact = Decimal(d.a) + Decimal(d.b) * phi_d  # = phi^n - L_n, ~60 digits
        assert ges.binet_residual(n) == pytest.approx(abs(float(exact)), rel=1e-9)
        assert ges.binet_residual(n) < ges.binet_residual(n - 1)


def test_binet_residual_beyond_mantissa():
    """Regression: phi^76 ~ 7.6e15 outgrows the float64 mantissa, so the
    raw subtraction returned ~19.0 (garbage) — the residual must be the
    Binet-identical |psi|^76 ~ 1.3e-16, computed without cancellation."""
    r76 = ges.binet_residual(76)
    assert r76 == pytest.approx(abs(PSI) ** 76, rel=1e-9)
    assert r76 < 1e-15
    # Independent verification: the exact Z[phi] drift element evaluated
    # in 60-digit Decimal arithmetic recovers the same value.
    from decimal import Decimal
    from kellogg.scales import pisot_drift

    phi_d, _ = _decimal_phi()
    d = pisot_drift(76)
    assert (d.a, d.b) == (-5527939700884757, 3416454622906707)
    assert d.norm() == 1  # norm(-psi^76) = (phi*psi)^76 = (-1)^76
    exact = Decimal(d.a) + Decimal(d.b) * phi_d
    assert r76 == pytest.approx(abs(float(exact)), rel=1e-9)


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
