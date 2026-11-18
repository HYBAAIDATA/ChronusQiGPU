"""Golden / Pisot / Lucas scaling audit across scales 10^7 .. 10^76 (exact integers only).

For a scale S (a magnitude, read as N = S states for Grover, and as a PV index for
``PVScale``) this module computes, with exact integer / Z[phi] / Fraction arithmetic:

* the Lucas and Fibonacci indices nearest S (fast doubling, ``chronus.geodesic.scheduler``);
* the exact Pisot residual: psi^n = L_n - phi^n in Z[phi], |psi^n| <= 1/F_{n+1}, so
  L_n is the nearest integer to phi^n with no rounding operation;
* the Zeckendorf representation of S (``chronus.execution.structural``);
* k = ceil(log2 S); the Pisano period pi(2^k) = 3*2^(k-1) verified as the exact order of Q;
* the Hensel lift M_k (``hensellift_m15``) with det -1, order exactly 2^(k-1) and the
  Cayley-Hamilton inverse (``invert_gl2_mod2k``);
* "Lucas scales everything": L_S mod 2^k by Pisano reduction S mod pi(2^k), equal to the
  direct fast-doubling value, and PVScale(S).field_factor() in F_257[phi];
* the Grover peak t* for N = S, M = 1:
    - exact: t* is certified by two exact integer Chebyshev signs
      N^m T_m(1 - 2/N), m = t* and t* + 1 (feasible while t* log2 N is a few 10^7 bits);
    - angle certificate (all scales): t* is the unique t with
      t*theta < arctan(1) <= (t+1)*theta, theta = arctan(1/sqrt(N-1)).  Both arctans are
      enclosed by rational intervals (alternating series; integer square roots; Machin's
      identity arctan(1) = 4 arctan(1/5) - arctan(1/239)); the two strict inequalities are
      checked in Fraction arithmetic.  No numerical value of pi is used, but this is a
      rational-interval proof, not a closed form: it certifies the integer t*, not P(t*).
    - exact stepping: the integer recurrence of Theorem 6.1, feasible to t* ~ 3000 here.
"""
from __future__ import annotations

from fractions import Fraction
from time import perf_counter_ns
from typing import Dict, Optional, Tuple

from chronus.execution.structural import zeckendorf_decode, zeckendorf_encode
from chronus.geodesic.scheduler import exact_fibonacci_lucas, exact_fibonacci_lucas_mod, pisano_period_pow2
from chronus.kernels.gl2_transform import hensellift_m15, invert_gl2_mod2k

try:  # optional: GMP multiplication for the large exact Chebyshev signs
    from gmpy2 import mpz as _big  # type: ignore
except ImportError:  # pragma: no cover
    _big = int

SCALES = (7, 10, 12, 15, 18, 20, 31, 50, 76)
Q = ((1, 1), (1, 0))
I2 = ((1, 0), (0, 1))


# ------------------------------------------------------------------ Z[phi] (phi^2 = phi + 1)
def zphi_mul(x: Tuple[int, int], y: Tuple[int, int]) -> Tuple[int, int]:
    a, b = x
    c, d = y
    return (a * c + b * d, a * d + b * c + b * d)


def zphi_pow(base: Tuple[int, int], n: int) -> Tuple[int, int]:
    r = (1, 0)
    while n:
        if n & 1:
            r = zphi_mul(r, base)
        base = zphi_mul(base, base)
        n >>= 1
    return r


PHI, PSI = (0, 1), (1, -1)      # psi = 1 - phi


def mat_mul(a, b, mask):
    return (((a[0][0] * b[0][0] + a[0][1] * b[1][0]) & mask, (a[0][0] * b[0][1] + a[0][1] * b[1][1]) & mask),
            ((a[1][0] * b[0][0] + a[1][1] * b[1][0]) & mask, (a[1][0] * b[0][1] + a[1][1] * b[1][1]) & mask))


def mat_pow(m, e, mask):
    r = I2
    while e:
        if e & 1:
            r = mat_mul(r, m, mask)
        m = mat_mul(m, m, mask)
        e >>= 1
    return r


def nearest_index(S: int, lucas: bool) -> Tuple[int, int]:
    """(n, value) with the Lucas (or Fibonacci) number nearest S (ties to the lower)."""
    n = 1
    while exact_fibonacci_lucas(n + 1)[1 if lucas else 0] <= S:
        n += 1
    lo = exact_fibonacci_lucas(n)[1 if lucas else 0]
    hi = exact_fibonacci_lucas(n + 1)[1 if lucas else 0]
    return (n, lo) if S - lo <= hi - S else (n + 1, hi)


def pisot_residual(n: int) -> Dict[str, object]:
    """psi^n = L_n - phi^n exactly in Z[phi]; |psi^n| <= 1/F_{n+1} < 1/2 for n >= 2."""
    f_n, l_n = exact_fibonacci_lucas(n)
    phin, psin = zphi_pow(PHI, n), zphi_pow(PSI, n)
    f_n1 = exact_fibonacci_lucas(n + 1)[0]
    return {
        "binet_trace_exact": (phin[0] + psin[0], phin[1] + psin[1]) == (l_n, 0),
        "norm_exact": zphi_mul(phin, psin) == ((-1) ** n, 0),           # phi^n psi^n = (-1)^n (Cassini)
        "phi_n_is_F_n_phi_plus_F_n_minus_1": phin == (exact_fibonacci_lucas(n - 1)[0] if n else 1, f_n),
        "residual_bound": Fraction(1, f_n1),                            # |psi^n| <= 1/F_{n+1}
        "residual_bound_bits": f_n1.bit_length() - 1,
    }


def pisano_and_mk(k: int) -> Dict[str, object]:
    mask = (1 << k) - 1
    pi = pisano_period_pow2(k)
    eye = mat_pow(Q, 0, mask)
    q_ok = mat_pow(Q, pi, mask) == eye and mat_pow(Q, pi // 2, mask) != eye and mat_pow(Q, pi // 3, mask) != eye
    M = hensellift_m15(k)
    det_ok = (M[0][0] * M[1][1] - M[0][1] * M[1][0]) & mask == mask
    order_ok = mat_pow(M, 1 << (k - 1), mask) == eye and mat_pow(M, 1 << (k - 2), mask) != eye
    inv = invert_gl2_mod2k(M, k)
    tr = (M[0][0] + M[1][1]) & mask
    ch_ok = inv == (((M[0][0] - tr) & mask, M[0][1]), (M[1][0], (M[1][1] - tr) & mask))
    mod256 = tuple(tuple(x & 255 for x in r) for r in M) == ((219, 98), (98, 121))
    return {"pisano_period_bits": pi.bit_length(), "pisano_is_exact_order_of_Q": q_ok,
            "M_k_det_minus_1": det_ok, "M_k_order_2^(k-1)": order_ok, "cayley_hamilton_inverse": ch_ok,
            "M_k_equals_M15_mod_256": mod256}


def lucas_scales(S: int, k: int) -> Dict[str, object]:
    """L_S mod 2^k by Pisano reduction equals direct fast doubling; PVScale(S) in F_257[phi]."""
    from chronus.core.scaling import PVScale
    mod = 1 << k
    direct = exact_fibonacci_lucas_mod(S, mod)
    reduced = exact_fibonacci_lucas_mod(S % pisano_period_pow2(k), mod)
    a, b = PVScale(S).field_factor()
    ref = zphi_pow(PHI, S % 516)                       # pi(257) = 516
    return {"pisano_reduction_matches": direct == reduced, "S_mod_pi": S % pisano_period_pow2(k),
            "field_factor": (a, b), "field_factor_matches_reference": (a, b) == (ref[0] % 257, ref[1] % 257),
            "field_trace_mod_257": (2 * a + b) % 257, "lucas_S_mod_2k_hex_tail": f"{direct[1]:x}"[-16:]}


# ------------------------------------------------------------------ Grover peak, exact signs
def chebyshev_scaled(m: int, N: int) -> int:
    """N^m * T_m(1 - 2/N), an integer, by fast doubling on (U_j, U_{j+1}, N^j)."""
    N = _big(N)
    c = N - 2
    u0, u1, p = _big(1), c, _big(1)       # U_0, U_1, N^0  (U_j = N^j T_j(c/N))
    for bit in bin(m)[2:]:   # j -> 2j or 2j+1, starting from j = 0
        p2 = p * p
        u2j = 2 * u0 * u0 - p2
        u2j1 = 2 * u0 * u1 - c * p2
        if bit == "0":
            u0, u1, p = u2j, u2j1, p2
        else:
            u2j2 = 2 * u1 * u1 - p2 * N * N
            u0, u1, p = u2j1, u2j2, p2 * N
    return int(u0)


def exact_peak_certificate(N: int, t: int) -> bool:
    """True iff T_t(c) > 0 and T_{t+1}(c) <= 0 for c = 1 - 2/N, i.e. t is the exact peak."""
    return chebyshev_scaled(t, N) > 0 and chebyshev_scaled(t + 1, N) <= 0


# ------------------------------------------------------------------ Grover peak, certified bracket
def _arctan_bounds(num: int, den: int, terms: int) -> Tuple[Fraction, Fraction]:
    """Enclosure of arctan(num/den), 0 < num/den < 1, from the alternating series."""
    x = Fraction(num, den)
    s, term, x2 = Fraction(0), x, x * x
    parts = []
    for j in range(terms):
        s += term / (2 * j + 1) * (1 if j % 2 == 0 else -1)
        parts.append(s)
        term *= x2
    return (min(parts[-1], parts[-2]), max(parts[-1], parts[-2]))


def _theta_enclosure(N: int, P: int) -> Tuple[Fraction, Fraction]:
    """theta = arcsin(1/sqrt(N)) = arctan(1/sqrt(N-1)), enclosed with integer square roots
    (r/2^P <= sqrt(N-1) < (r+1)/2^P) and the alternating arctan series."""
    from math import isqrt
    r = isqrt((N - 1) << (2 * P))
    return _arctan_bounds(1 << P, r + 1, 8)[0], _arctan_bounds(1 << P, r, 8)[1]


def quarter_turn_enclosure() -> Tuple[Fraction, Fraction]:
    """arctan(1) = 4 arctan(1/5) - arctan(1/239) (Machin's identity), enclosed by partial sums."""
    a_lo, a_hi = _arctan_bounds(1, 5, 120)
    b_lo, b_hi = _arctan_bounds(1, 239, 120)
    return 4 * a_lo - b_hi, 4 * a_hi - b_lo


def pi_bounds() -> Tuple[Fraction, Fraction]:
    lo, hi = quarter_turn_enclosure()
    return 4 * lo, 4 * hi


def angle_certificate(N: int, t: int, P: Optional[int] = None) -> bool:
    """Certifies t = t*(N, 1): t*theta < arctan(1) <= (t+1)*theta, i.e. T_t(c) > 0 >= T_{t+1}(c)
    with c = 1 - 2/N (Theorem 6.2), using only rational enclosures of arctan values."""
    P = P or (2 * N.bit_length() + 128)
    th_lo, th_hi = _theta_enclosure(N, P)
    q_lo, q_hi = quarter_turn_enclosure()
    return t * th_hi < q_lo and (t + 1) * th_lo > q_hi


def certified_peak(N: int, prec_bits: Optional[int] = None) -> Dict[str, object]:
    """Candidate t* = ceil(arctan(1)/theta) - 1 from the enclosures, then ``angle_certificate``.

    N = 1 and N = 2 are exact boundary cases decided without enclosures: theta is
    exactly pi/2 resp. pi/4, so arctan(1)/theta is 1/2 resp. exactly 1 and t* = 0
    (P_0 = 1 for N = 1; P_0 = P_1 = 1/2 for N = 2, first peak at t = 0).  The
    generic path would divide by a zero lower bound (N = 1) or straddle the
    integer 1 forever (N = 2)."""
    if isinstance(N, bool) or not isinstance(N, int) or N < 1:
        raise ValueError(f"N must be a positive integer, got {N!r}")
    if N <= 2:
        return {"t_star": 0, "determined": True, "enclosure_width_bits": None}
    P = prec_bits or (2 * N.bit_length() + 128)
    th_lo, th_hi = _theta_enclosure(N, P)
    q_lo, q_hi = quarter_turn_enclosure()
    lo, hi = q_lo / th_hi, q_hi / th_lo
    c_lo = -((-lo.numerator) // lo.denominator)
    c_hi = -((-hi.numerator) // hi.denominator)
    t = c_lo - 1 if c_lo == c_hi else None
    cert = t is not None and angle_certificate(N, t, P)
    return {"t_star": t if cert else None, "determined": cert,
            "enclosure_width_bits": (hi - lo).denominator.bit_length() - (hi - lo).numerator.bit_length()}


def production_register_roundtrip(S: int, k: int, root: Optional[str] = None) -> Dict[str, object]:
    """A 16-generator window [S, S + 2^16) through the production FoldedRegisterN at ring k:
    fold by M_k, GL2 wire frame (CRC-32C), Cayley-Hamilton unfold, collapse/fold commutation,
    and (if ``root``) OVID staging + THESEUS restore."""
    import hashlib
    from chronus.kernels.gl2_transform import FoldedRegisterN
    mask = (1 << k) - 1
    reg = FoldedRegisterN.from_domain_offset(S, num_generators=16, k=k)
    folded = reg.fold_mk()
    frame = folded.to_wire_bytes()
    out = {
        "frame_bytes": len(frame), "frame_sha256": hashlib.sha256(frame).hexdigest(),
        "wire_roundtrip": FoldedRegisterN.from_wire_bytes(frame) == folded,
        "unfold_restores": folded.unfold_mk() == reg,
        "collapse_commutes": folded.collapse_generator(5, 1) == reg.collapse_generator(5, 1).fold_mk(),
        "window_values_exact": all(reg.evaluate_index(i) == ((S >> k) & mask, (S + i) & mask)
                                   for i in (0, 1, 2, 65534, 65535)),
    }
    if root is not None:
        import os
        from chronus.ovid.folded_custody import OvidAdapter, OvidFoldedAdapter, TheseusAdapter
        from chronus.ovid.transform import OvidTransformService
        from chronus.storage.durable import DurableTheseusService
        path = os.path.join(root, f"k{k}.sqlite3")
        custody = DurableTheseusService(path)
        ad = OvidFoldedAdapter(OvidAdapter(OvidTransformService()), TheseusAdapter(custody, "scale"))
        h = ad.commit_collapse_step(ad.stage_domain(f"scale/k{k}", reg), 0, 1)
        ad2 = OvidFoldedAdapter(OvidAdapter(OvidTransformService()),
                                TheseusAdapter(DurableTheseusService(path), "scale"))
        r = ad2.restore_from_theseus(f"scale/k{k}")
        out.update({"theseus_restore_exact": (r.version, r.register, r.wire_frame) == (1, h.register, h.wire_frame),
                    "theseus_chain_verified": custody.verify_journal_continuity("scale"),
                    "theseus_journal_head": custody.get_journal("scale")[-1].entry_hash})
    return out


def audit_scale(d: int, exact_bits_limit: int = 64_000_000, step_limit: int = 3000,
                custody_root: Optional[str] = None) -> Dict[str, object]:
    S = 10 ** d
    k = (S - 1).bit_length()                     # ceil(log2 S), S not a power of 2
    row: Dict[str, object] = {"scale": f"10^{d}", "k": k}
    t0 = perf_counter_ns()
    nL, L = nearest_index(S, True)
    nF, Fv = nearest_index(S, False)
    row.update({"lucas_index": nL, "fibonacci_index": nF, "lucas_value_digits": len(str(L))})
    row.update({"pisot": pisot_residual(nL)})
    z = zeckendorf_encode(S)
    row.update({"zeckendorf_terms": len(z), "zeckendorf_top_index": z[0], "zeckendorf_roundtrip": zeckendorf_decode(z) == S})
    row["ns_golden"] = perf_counter_ns() - t0
    t0 = perf_counter_ns()
    row["ring"] = pisano_and_mk(k)
    row["ns_ring"] = perf_counter_ns() - t0
    t0 = perf_counter_ns()
    row["register"] = production_register_roundtrip(S, k, custody_root)
    row["ns_register"] = perf_counter_ns() - t0
    t0 = perf_counter_ns()
    row["lucas_scales"] = lucas_scales(S, k)
    row["ns_lucas_scales"] = perf_counter_ns() - t0
    t0 = perf_counter_ns()
    cp = certified_peak(S)
    row["grover_angle_certificate"] = cp
    row["ns_angle"] = perf_counter_ns() - t0
    t = cp["t_star"]
    if t is not None and (t + 1) * S.bit_length() <= exact_bits_limit:
        t0 = perf_counter_ns()
        row["grover_chebyshev_certificate"] = exact_peak_certificate(S, t)
        row["ns_chebyshev"] = perf_counter_ns() - t0
    else:
        row["grover_chebyshev_certificate"] = None
    row["chebyshev_bits_needed"] = None if t is None else (t + 1) * S.bit_length()
    if t is not None and t <= step_limit:
        from chronus.quantum.triad_grover import exact_lucas_pisot_iterations
        t0 = perf_counter_ns()
        row["grover_exact_stepped"] = exact_lucas_pisot_iterations(S, 1)
        row["ns_stepped"] = perf_counter_ns() - t0
    else:
        row["grover_exact_stepped"] = None
    return row
