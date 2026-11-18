"""Every mathematical claim in docs/papers/grover_in_o1_exact_ring_folding.{tex,md}, checked exactly."""
from __future__ import annotations

import os
from fractions import Fraction

import pytest

from chronus.geodesic.scheduler import (
    exact_fibonacci_lucas, hamming_step_histogram, lucas_pisano_geodesic_order, pisano_period_pow2,
    schedule_parameters,
)
from chronus.kernels.gl2_transform import FoldedRegisterN, hensellift_m15, invert_gl2_mod2k
from chronus.quantum.attractor_stress import mat_mul, mat_pow
from chronus.quantum.triad_grover import exact_grover_two_amplitude_trajectory

pytestmark = pytest.mark.real
I2 = ((1, 0), (0, 1))
Q = ((1, 1), (1, 0))


def chebyshev_table(m: int, x: Fraction) -> list:
    """[T_0(x), ..., T_m(x)] by T_{j+1} = 2x T_j - T_{j-1} (exact)."""
    out = [Fraction(1), x]
    while len(out) <= m:
        out.append(2 * x * out[-1] - out[-2])
    return out


@pytest.mark.parametrize("k", (8, 16, 32, 64))
def test_mk_structure(k):
    mod, mask = 1 << k, (1 << k) - 1
    M = hensellift_m15(k)
    assert M[0] == (219, 98) and M[1][0] == 98
    assert (M[0][0] * M[1][1] - 98 * 98) % mod == mod - 1                       # det = -1
    assert all((M[i][j] - I2[i][j]) % 2 == 0 for i in range(2) for j in range(2))  # Gamma(2)
    assert all((M[i][j] - I2[i][j] - 2 * Q[i][j]) % 4 == 0 for i in range(2) for j in range(2))  # I + 2Q mod 4
    tr = (M[0][0] + M[1][1]) & mask
    assert invert_gl2_mod2k(M, k) == (((M[0][0] - tr) & mask, 98), (98, (M[1][1] - tr) & mask))
    assert mat_mul(M, invert_gl2_mod2k(M, k), mask) == I2
    assert mat_pow(M, 1 << (k - 1), mask) == I2 and mat_pow(M, 1 << (k - 2), mask) != I2


def test_m15_is_q15_mod_256_and_trace_is_l15():
    assert mat_pow(Q, 15, 255) == hensellift_m15(8)
    assert (219 + 121) % 256 == exact_fibonacci_lucas(15)[1] % 256 == 84


@pytest.mark.parametrize("D", range(1, 21))
def test_pisano_period_is_order_of_q(D):
    mask = (1 << D) - 1
    pi = pisano_period_pow2(D)
    assert pi == (3 if D == 1 else 3 << (D - 1))
    assert mat_pow(Q, pi, mask) == tuple(tuple(x & mask for x in r) for r in I2)
    for p in (pi // 2, pi // 3):           # maximal proper divisors of 3 * 2^(D-1)
        if p and pi % p == 0:
            assert mat_pow(Q, p, mask) != tuple(tuple(x & mask for x in r) for r in I2)


def test_q_cubed_identity():
    assert mat_pow(Q, 3, (1 << 64) - 1) == ((3, 2), (2, 1))                      # = I + 2Q
    assert all(exact_fibonacci_lucas(3 * m + 1)[1] % 2 == 1 for m in range(2000))
    assert all(exact_fibonacci_lucas(3 * m)[1] % 2 == 0 for m in range(2000))


@pytest.mark.parametrize("D", (12, 16))
def test_schedule_bijection_and_hamming_truth(D):
    for e in range(0, 8):
        order = lucas_pisano_geodesic_order(D, epoch_step=e)
        assert sorted(order) == list(range(1 << D))
    assert schedule_parameters(D, 0)["lucas_stride_mod"] == 1
    assert hamming_step_histogram(lucas_pisano_geodesic_order(D, epoch_step=0)) == {1: (1 << D) - 1}
    assert hamming_step_histogram(lucas_pisano_geodesic_order(D, epoch_step=1)) == {1: (1 << (D - 2)) - 1, 3: 3 << (D - 2)}


@pytest.mark.parametrize("N,M,t", [(16, 1, 3), (4096, 1, 50), (65536, 1, 201), (4096, 4, 25), (65536, 4, 100)])
def test_chebyshev_closed_form_and_pi_free_stopping_rule(N, M, t):
    c = 1 - Fraction(2 * M, N)                                          # cos(2 theta)
    traj = exact_grover_two_amplitude_trajectory(N, M)
    T = chebyshev_table(2 * t + 3, c)
    assert all(P == (1 - T[2 * s + 1]) / 2 for s, _a, _b, P in traj)    # P_s = sin^2((2s+1)theta)
    assert traj[-1][0] == t == min(s for s in range(t + 1) if T[s + 1] <= 0)
    assert traj[-2][3] < traj[-1][3] and (1 - T[2 * t + 3]) / 2 < traj[-1][3]


def test_n16_peak_exact():
    t, a, b, P = exact_grover_two_amplitude_trajectory(16, 1)[-1]
    assert (t, a, b, P) == (3, Fraction(251, 64), Fraction(-13, 64), Fraction(63001, 65536))


def test_folded_register_size_and_commutation():
    reg = FoldedRegisterN.from_domain_offset((7 << 32) | 0xFFFFFF00, num_generators=12, k=32)
    frame = reg.fold_mk().to_wire_bytes()
    assert len(frame) == 16 + (18 + 8 * 13) + 4                     # header + payload + CRC-32C
    assert FoldedRegisterN.from_wire_bytes(frame) == reg.fold_mk()
    assert reg.fold_mk().collapse_generator(3, 1) == reg.collapse_generator(3, 1).fold_mk()
    assert reg.fold_mk().unfold_mk() == reg


# ---------------------------------------------------------------------------
# Remark 1.1: Lucas traces and closed geodesics of the modular surface (exact part)
# ---------------------------------------------------------------------------
def test_lucas_trace_geodesic_identity_exact():
    """tr Q^{2k} = L_{2k}; Q^{2k} in SL(2,Z); and the larger eigenvalue of Q^{2k}, i.e.
    L/2 + sqrt((L/2)^2 - 1), is exactly phi^{2k} in Z[phi].  Hence
    2 arccosh(L_{2k}/2) = 2 ln(phi^{2k}) = 4k ln(phi) with no approximation."""
    from chronus.geodesic.scheduler import exact_fibonacci_lucas
    from chronus.quantum.golden_scales import PHI, PSI, mat_pow, zphi_pow
    Q = ((1, 1), (1, 0))
    big = (1 << 2000) - 1
    for k in range(1, 201):
        F, L = exact_fibonacci_lucas(2 * k)
        (a, b), (c, d) = mat_pow(Q, 2 * k, big)
        assert a + d == L and a * d - b * c == 1                 # trace L_{2k}, det +1: hyperbolic in SL(2,Z)
        assert L * L - 4 == 5 * F * F                            # L^2 - 5F^2 = 4(-1)^{2k}
        assert zphi_pow(PHI, 2 * k) == ((L - F) // 2, F)         # (L + F sqrt5)/2 = phi^{2k}
        p, q = zphi_pow(PHI, 2 * k), zphi_pow(PSI, 2 * k)        # psi^{2k} = phi^{-2k}
        assert (p[0] + q[0], p[1] + q[1]) == (L, 0)              # L_{2k} = phi^{2k} + phi^{-2k}
        assert zphi_mul_check(p, q)
    assert exact_fibonacci_lucas(2)[1] == 3                      # k = 1: trace 3, the least |tr| > 2


def zphi_mul_check(p, q):
    from chronus.quantum.golden_scales import zphi_mul
    return zphi_mul(p, q) == (1, 0)                              # phi^{2k} * psi^{2k} = 1


# ---------------------------------------------------------------------------
# Cross-check against the authors' unified_quantum_engine.py GoldenArithmetic (exact integers).
# The file is the user's, outside this repo; it imports numpy/pandas/sklearn at top level, so the
# pure-integer classes are extracted with ast and executed alone.  Skipped if the file is absent.
# ---------------------------------------------------------------------------
UQE_PATH = os.environ.get("UNIFIED_QUANTUM_ENGINE", "/workspace/user_files/unified_quantum_engine.py")


def _load_golden_arithmetic():
    import ast
    import typing
    src = open(UQE_PATH, encoding="utf-8").read()
    tree = ast.parse(src)
    keep = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name in ("GoldenIntegrityError", "GoldenArithmetic")]
    ns = {"Optional": typing.Optional, "Sequence": typing.Sequence, "List": typing.List, "Dict": typing.Dict,
          "Any": typing.Any, "__name__": "uqe_golden"}
    exec(compile(ast.Module(body=keep, type_ignores=[]), UQE_PATH, "exec"), ns)
    return ns["GoldenArithmetic"]


@pytest.mark.skipif(not os.path.exists(UQE_PATH), reason="unified_quantum_engine.py not available")
def test_engine_golden_arithmetic_matches_chronus_exactly():
    from chronus.geodesic.scheduler import pisano_period_pow2
    from chronus.kernels.gl2_transform import hensellift_m15
    from chronus.quantum.golden_scales import mat_pow
    GA = _load_golden_arithmetic()
    Q = ((1, 1), (1, 0))
    assert GA.fold_matrix(15, 8)[0] == hensellift_m15(8)                   # the engine's Q^15 mod 256 is M15
    for bits in (8, 16, 64, 256):
        mask = (1 << bits) - 1
        assert GA.pisano_pow2(bits) == pisano_period_pow2(bits) == 3 << (bits - 1)
        for steps in (1, 15, 10 ** 9 + 7, 10 ** 76):
            M, n = GA.fold_matrix(steps, bits)
            assert n == steps % (3 << (bits - 1))
            assert M == mat_pow(Q, n, mask) == mat_pow(Q, steps, mask)       # Pisano reduction is exact
            Minv = GA.unfold_matrix(steps, bits)
            prod = tuple(tuple(sum(M[i][t] * Minv[t][j] for t in range(2)) & mask for j in range(2)) for i in range(2))
            assert prod == ((1, 0), (0, 1))
