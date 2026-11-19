"""Golden members (Binet, Cassini, Lucas, Pisano, Pisot, Zeckendorf) and the 10^7..10^76
scale sweep, exact integer arithmetic only.  Production FoldedRegisterN is run at every k."""
from fractions import Fraction

import pytest

from chronus.execution.structural import fold_pair, unfold_pair, zeckendorf_decode, zeckendorf_encode
from chronus.geodesic.scheduler import exact_fibonacci_lucas
from chronus.kernels.gl2_transform import FoldedRegisterN, hensellift_m15, invert_gl2_mod2k
from chronus.quantum import golden_scales as gs
from chronus.quantum.triad_grover import exact_lucas_pisot_iterations

pytestmark = pytest.mark.real


def FL(n):
    return exact_fibonacci_lucas(n)


def matpow(m, e, mod):
    return gs.mat_pow(m, e, mod - 1)


# ---- Binet in Z[phi]: phi^n = F_{n-1} + F_n phi, i.e. (L_n + F_n sqrt5)/2
@pytest.mark.parametrize("n", [1, 2, 15, 33, 100, 364])
def test_binet_in_zphi(n):
    F, L = FL(n)
    Fm1, _ = FL(n - 1)
    assert gs.zphi_pow(gs.PHI, n) == (Fm1, F)
    # (L + F sqrt5)/2 with sqrt5 = 2 phi - 1  ->  (L - F)/2 + F phi
    assert ((L - F) // 2, F) == (Fm1, F) and (L - F) % 2 == 0
    p, q = gs.zphi_pow(gs.PHI, n), gs.zphi_pow(gs.PSI, n)
    assert (p[0] + q[0], p[1] + q[1]) == (L, 0)        # L_n = phi^n + psi^n (Pisot trace)


def test_m15_is_q15_mod_256_and_lucas_trace():
    m15 = gs.mat_pow(gs.Q, 15, 255)
    assert m15 == ((219, 98), (98, 121)) == hensellift_m15(8)
    L15 = FL(15)[1]
    assert L15 == 1364                                    # Lucas L_15
    assert (m15[0][0] + m15[1][1]) % 256 == L15 % 256 == 84


@pytest.mark.parametrize("n", [1, 2, 3, 15, 64, 253])
def test_cassini_and_trace_of_qn(n):
    (a, b), (c, d) = gs.mat_pow(gs.Q, n, (1 << 300) - 1)
    F, L = FL(n)
    assert (a, b, d) == (FL(n + 1)[0], F, FL(n - 1)[0])
    assert a * d - b * c == (-1) ** n                     # Cassini
    assert a + d == L                                     # tr Q^n = L_n


def test_lucas_stride_odd_and_even_iff_3_divides():
    assert all((FL(3 * m + 1)[1] % 2) == 1 for m in range(60))
    assert all((FL(n)[1] % 2 == 0) == (n % 3 == 0) for n in range(1, 200))


def test_ovid_unfold_is_m15_minus_84i():
    inv = invert_gl2_mod2k(hensellift_m15(8), 8)
    assert inv == ((219 - 84, 98), (98, 121 - 84)) == ((135, 98), (98, 37))
    assert all(unfold_pair(*fold_pair(x, y)) == (x, y) for x in range(0, 256, 7) for y in range(0, 256, 11))


def test_zeckendorf_roundtrip_at_scales():
    for d in gs.SCALES:
        z = zeckendorf_encode(10 ** d)
        assert zeckendorf_decode(z) == 10 ** d


@pytest.mark.parametrize("n", [33, 96, 364])
def test_pisot_residual_exact(n):
    r = gs.pisot_residual(n)
    assert r["binet_trace_exact"] and r["norm_exact"] and r["phi_n_is_F_n_phi_plus_F_n_minus_1"]
    assert Fraction(r["residual_bound"]) == Fraction(1, FL(n + 1)[0])


# ---- Production FoldedRegisterN at any k in [8, 255]
@pytest.mark.parametrize("k", [8, 12, 24, 67, 103, 167, 253, 255])
def test_register_any_k(k):
    S = (1 << k) - 3                       # window wraps the ring
    reg = FoldedRegisterN.from_domain_offset(S, num_generators=min(16, k), k=k)
    f = reg.fold_mk()
    assert f.unfold_mk() == reg
    frame = f.to_wire_bytes()
    assert FoldedRegisterN.from_wire_bytes(frame) == f
    assert f.collapse_generator(3, 1) == reg.collapse_generator(3, 1).fold_mk()


def test_register_k253_ring_facts():
    k, mod = 253, 1 << 253
    M = hensellift_m15(k)
    (a, b), (c, d) = M
    assert (a * d - b * c) % mod == mod - 1                       # det M_k = -1
    tr = (a + d) % mod
    assert invert_gl2_mod2k(M, k) == (((a - tr) % mod, b), (c, (d - tr) % mod))   # M - tr I
    assert gs.mat_pow(M, 1 << 252, mod - 1) == ((1, 0), (0, 1))
    assert gs.mat_pow(M, 1 << 251, mod - 1) != ((1, 0), (0, 1))   # order exactly 2^252
    assert gs.mat_pow(M, 1, 255) == hensellift_m15(8)
    r = gs.pisano_and_mk(k)
    assert all(v for v in r.values() if isinstance(v, bool))


@pytest.mark.parametrize("k", [7, 256, True, 16.0])
def test_register_rejects_bad_k(k):
    with pytest.raises(ValueError):
        FoldedRegisterN.from_domain_offset(0, num_generators=4, k=k)


def test_wire_width_ceil_k_over_8():
    for k in (12, 253):
        reg = FoldedRegisterN.from_domain_offset((1 << k) - 1, num_generators=1, k=k)
        assert FoldedRegisterN.from_wire_bytes(reg.to_wire_bytes()).base == reg.base


# ---- Grover peak certificates
@pytest.mark.parametrize("N", [4, 16, 100, 4096, 12345, 65536, 10 ** 5])
def test_angle_certificate_matches_exact_stepping(N):
    t = exact_lucas_pisot_iterations(N, 1)
    assert gs.certified_peak(N)["t_star"] == t
    assert gs.angle_certificate(N, t)
    assert not gs.angle_certificate(N, t - 1) and not gs.angle_certificate(N, t + 1)
    assert gs.exact_peak_certificate(N, t)



@pytest.mark.parametrize("N", [1, 2])
def test_certified_peak_boundary_cases_match_exact_stepping(N):
    # N=1: theta = pi/2 (zero lower enclosure); N=2: arctan(1)/theta is exactly 1.
    res = gs.certified_peak(N)
    assert res["determined"] is True
    assert res["t_star"] == 0 == exact_lucas_pisot_iterations(N, 1)


@pytest.mark.parametrize("N", [0, -3, True, 2.0])
def test_certified_peak_rejects_non_positive_or_non_int(N):
    with pytest.raises(ValueError):
        gs.certified_peak(N)


def test_chebyshev_scaled_against_fractions():
    N = 37
    c = Fraction(N - 2, N)
    T0, T1 = Fraction(1), c
    for m in range(2, 30):
        T0, T1 = T1, 2 * c * T1 - T0
        assert gs.chebyshev_scaled(m, N) == T1 * N ** m


def test_exact_chebyshev_certificate_at_1e10():
    assert gs.exact_peak_certificate(10 ** 10, 78539)


def test_angle_certificate_all_scales():
    expected = {7: 2483, 10: 78539, 12: 785398, 15: 24836470, 18: 785398163, 20: 7853981633,
                31: 2483647066449025, 50: 7853981633974483096156608,
                76: 78539816339744830961566084581987572104}
    for d, t in expected.items():
        assert gs.angle_certificate(10 ** d, t)
        assert not gs.angle_certificate(10 ** d, t - 1)


def test_audit_scale_10e7_small_bits():
    r = gs.audit_scale(7, step_limit=0)
    assert r["k"] == 24 and r["grover_chebyshev_certificate"] is True
    assert all(v for v in r["register"].values() if isinstance(v, bool))
    assert all(v for v in r["ring"].values() if isinstance(v, bool))


# ---- One recurrence, two regimes: Dickson traces x_{n+1} = t x_n - d x_{n-1}
def _grover_matrix(N, M):
    U = N - M
    return ((Fraction(N - 2 * M, N), Fraction(2 * U, N)), (Fraction(-2 * M, N), Fraction(2 * U - N, N)))


def _fmatmul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(2)) for j in range(2)) for i in range(2))


@pytest.mark.parametrize("N,M", [(16, 1), (4096, 1), (100, 7)])
def test_grover_iterate_is_det1_trace_2c_and_traces_are_chebyshev(N, M):
    G = _grover_matrix(N, M)
    c = Fraction(N - 2 * M, N)
    assert G[0][0] + G[1][1] == 2 * c and G[0][0] * G[1][1] - G[0][1] * G[1][0] == 1
    # G reproduces the recurrence of triad_grover.py:36 on (alpha, beta)
    a, b = Fraction(1), Fraction(1)
    mu = ((N - M) * b - M * a) / N
    assert (G[0][0] * a + G[0][1] * b, G[1][0] * a + G[1][1] * b) == (2 * mu + a, 2 * mu - b)
    P, T0, T1 = G, Fraction(1), c
    for n in range(1, 40):
        assert P[0][0] + P[1][1] == 2 * T1                      # tr G^n = 2 T_n(c)
        P, T0, T1 = _fmatmul(P, G), T1, 2 * c * T1 - T0


def test_lucas_and_m15_traces_follow_dickson_with_det_minus_1():
    x0, x1 = 2, 1                                               # D_n(1, -1) = L_n
    for n in range(1, 120):
        assert FL(n)[1] == x1
        x0, x1 = x1, x1 + x0
    M8 = hensellift_m15(8)
    for n in range(1, 64):
        P = gs.mat_pow(M8, n, 255)
        assert (P[0][0] + P[1][1]) % 256 == FL(15 * n)[1] % 256   # tr M15^n = L_{15n} mod 256


# ---- Golden constants in storage and PV scaling
def test_phyllotaxis_constants_exact():
    from chronus.storage.phyllotaxis import (GOLDEN_RATIO_CONJUGATE_64, fibonacci_cassini_witness,
                                             metallic_conjugate_64)
    assert metallic_conjugate_64(1) == GOLDEN_RATIO_CONJUGATE_64 == 0x9E3779B97F4A7C15
    assert [fibonacci_cassini_witness(n) for n in (1, 2, 3, 64)] == [-1, 1, -1, 1]
    F64, F65, F66 = FL(64)[0], FL(65)[0], FL(66)[0]
    assert F64 * F66 - F65 ** 2 == -1                           # Cassini for the convergent F_64/F_66


def test_pvscale_field_period_516():
    from chronus.core.scaling import PVScale
    assert 257 % 5 == 2                                         # x^2 - x - 1 irreducible over F_257
    assert PVScale(258).field_factor() == (256, 0)              # phi^(p+1) = N(phi) = -1
    assert PVScale(516).field_factor() == (1, 0)
    for d in gs.SCALES:
        S = 10 ** d
        assert PVScale(S).field_factor() == PVScale(S % 516).field_factor()
        assert PVScale(S).cassini_parity() == 1


@pytest.mark.parametrize("exponent", [-1, -2])
def test_power_helpers_reject_negative_exponents(exponent):
    with pytest.raises(ValueError, match="nonnegative"):
        gs.zphi_pow(gs.PHI, exponent)
    with pytest.raises(ValueError, match="nonnegative"):
        gs.mat_pow(gs.Q, exponent, 255)


def test_power_helpers_zero_is_identity():
    assert gs.zphi_pow(gs.PHI, 0) == (1, 0)
    assert gs.mat_pow(gs.Q, 0, 255) == gs.I2


@pytest.mark.parametrize("S,expected", [(1, (1, 1)), (2, (0, 2)), (3, (2, 3)), (5, (3, 4))])
def test_nearest_lucas_includes_zero_and_ties_to_lower(S, expected):
    assert gs.nearest_index(S, True) == expected


def test_exact_certificate_rejects_later_crossing():
    # For N=4, T_6(1/2)=1 and T_7(1/2)=1/2, followed by T_8(1/2)=-1/2.
    assert gs.chebyshev_scaled(7, 4) > 0
    assert gs.chebyshev_scaled(8, 4) < 0
    assert not gs.exact_peak_certificate(4, 7)
    assert gs.exact_peak_certificate(4, 1)


def test_angle_certificate_exact_two_state_tie():
    assert gs.angle_certificate(2, 0)
    assert gs.exact_peak_certificate(2, 0)
    assert not gs.angle_certificate(2, -1)
    assert not gs.angle_certificate(2, 1)


@pytest.mark.parametrize("d", gs.SCALES)
def test_production_register_at_every_scale(d):
    S = 10 ** d
    k = (S - 1).bit_length()
    result = gs.production_register_roundtrip(S, k)
    assert result["wire_roundtrip"]
    assert result["window_values_exact"]
    assert result["unfold_restores"]
    assert result["collapse_commutes"]


def test_register_custody_distinguishes_windows_and_reuses_retry(tmp_path):
    root = str(tmp_path)
    first = gs.production_register_roundtrip(10 ** 7, 24, root)
    second = gs.production_register_roundtrip(10 ** 7 + 1, 24, root)
    retry = gs.production_register_roundtrip(10 ** 7, 24, root)
    for result in (first, second, retry):
        assert result["theseus_restore_exact"]
        assert result["theseus_chain_verified"]
    assert first["frame_sha256"] != second["frame_sha256"]
    assert first["frame_sha256"] == retry["frame_sha256"]
    assert second["theseus_journal_head"] == retry["theseus_journal_head"]
