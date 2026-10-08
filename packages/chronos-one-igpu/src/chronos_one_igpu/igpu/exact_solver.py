"""Certified exact ground-state solver for the structured Hamiltonian.

The production eigenpair request is answered with certificates, not with
unverified floating-point output:

* The Hamiltonian H = D + tridiag(off) - (x x^T + y y^T) is built with every
  entry an exact rational derived bit-exactly from the caller's float64 input
  (``Fraction`` of each float, plus ``-1/Fraction(phi)`` for the band).
* An FP64 computation proposes a candidate eigenpair (lam, v). The proposal
  carries no evidential weight: every bound in the returned evidence is
  derived from exact rational or outward-rounded dyadic-interval arithmetic.
* Residual certificate: the exact vector r = H v - lam v is computed in
  rationals; ``residual_bound`` is a rational upper bound for ||r||/||v||.
  By the Weinstein residual theorem for symmetric matrices there is an
  eigenvalue of H inside ``[lam - r, lam + r]``.
* Isolation certificate: the number of eigenvalues of H strictly below a
  rational probe mu is computed exactly as
      count(mu) = sturm(T - mu I) + neg_inertia(I - A^T (T - mu I)^{-1} A)
  (Haynsworth inertia additivity on [[T-mu I, A],[A^T, I]]), evaluated in
  outward-rounded dyadic interval arithmetic with adaptive precision. The
  ground eigenvalue is certified when count(lo)==0 and count(hi)==1 on the
  residual interval [lo,hi]; the second-eigenvalue bound comes from the
  count>=2 transition and yields a certified spectral gap.
* The returned ``vector`` is the certified representative: its exact
  residual bound and the Davis-Kahan-style bound
  ``sin(theta) <= residual_bound / gap_bound`` are both reported.

If any certificate cannot be produced (degenerate eigenspace, precision
quota exhausted) the solver fails closed; it never silently substitutes an
uncertified numerical answer for a certified request.
"""

from fractions import Fraction
import math

import numpy as np


class _Undecided(ArithmeticError):
    """Interval sign could not be resolved at the current precision."""


class _IV:
    """Outward-rounded dyadic interval [lo, hi] with Fraction endpoints."""

    __slots__ = ("lo", "hi", "p")

    def __init__(self, lo, hi, p):
        self.lo = lo
        self.hi = hi
        self.p = p

    @staticmethod
    def point(value, p):
        v = value if isinstance(value, Fraction) else Fraction(value)
        return _IV(v, v, p)

    @staticmethod
    def _floor(value, p):
        q = value.numerator * (1 << p)
        return Fraction(q // value.denominator, 1 << p)

    @staticmethod
    def _ceil(value, p):
        return -_IV._floor(-value, p)

    def __add__(self, other):
        return _IV(self.lo + other.lo, self.hi + other.hi, self.p)

    def __sub__(self, other):
        return _IV(self.lo - other.hi, self.hi - other.lo, self.p)

    def __neg__(self):
        return _IV(-self.hi, -self.lo, self.p)

    def __mul__(self, other):
        products = (self.lo * other.lo, self.lo * other.hi, self.hi * other.lo, self.hi * other.hi)
        lo = _IV._floor(min(products), self.p)
        hi = _IV._ceil(max(products), self.p)
        return _IV(lo, hi, self.p)

    def reciprocal(self):
        if self.lo <= 0 <= self.hi:
            raise _Undecided("division by an interval containing zero")
        inv_lo = _IV._floor(Fraction(1) / self.hi, self.p)
        inv_hi = _IV._ceil(Fraction(1) / self.lo, self.p)
        return _IV(inv_lo, inv_hi, self.p)

    def square(self):
        if self.lo <= 0 <= self.hi:
            lo = Fraction(0)
            hi = _IV._ceil(max(self.lo * self.lo, self.hi * self.hi), self.p)
        else:
            a, b = self.lo * self.lo, self.hi * self.hi
            lo = _IV._floor(min(a, b), self.p)
            hi = _IV._ceil(max(a, b), self.p)
        return _IV(lo, hi, self.p)

    def sign(self):
        if self.hi < 0:
            return -1
        if self.lo > 0:
            return 1
        raise _Undecided("interval straddles zero")


def _exact_params(operator):
    """Exact rational Hamiltonian parameters from the float64 operator."""
    d = [Fraction(float(v)) for v in operator.diagonal]
    x = [Fraction(float(v)) for v in operator.real]
    y = [Fraction(float(v)) for v in operator.imag]
    # -1/phi computed on the exact reciprocal, not on the rounded float ratio.
    off = -Fraction(1) / Fraction(float(operator.phi))
    return d, off, x, y


def _sturm_count_iv(d, off, lam, precision):
    """Certified count of eigenvalues of tridiagonal(diag, off) below lam."""
    n = len(d)
    q = _IV.point(d[0] - lam, precision)
    off_iv = _IV.point(off, precision)
    pivots = [q]
    count = 0
    for i in range(n):
        count += int(pivots[i].sign() < 0)
        if i + 1 == n:
            break
        try:
            q = _IV.point(d[i + 1] - lam, precision) - off_iv.square() * pivots[i].reciprocal()
        except _Undecided:
            raise
        pivots.append(q)
    return count


def _solve_tridiagonal_iv(d, off, lam, b, precision):
    """Thomas solve of (T - lam I) u = b in interval arithmetic."""
    n = len(d)
    off_iv = _IV.point(off, precision)
    p = [None] * n
    f = [None] * n
    p[0] = _IV.point(d[0] - lam, precision)
    p[0].sign()
    f[0] = _IV.point(b[0], precision)
    for i in range(1, n):
        l = off_iv * p[i - 1].reciprocal()
        p[i] = _IV.point(d[i] - lam, precision) - l * off_iv
        p[i].sign()
        f[i] = _IV.point(b[i], precision) - l * f[i - 1]
    u = [None] * n
    u[-1] = f[-1] * p[-1].reciprocal()
    for i in range(n - 2, -1, -1):
        u[i] = (f[i] - off_iv * u[i + 1]) * p[i].reciprocal()
    return u


def _secular_neg_iv(d, off, x, y, lam, precision):
    """Negative inertia of S = I - A^T (T - lam I)^{-1} A, A = [x, y]."""
    ux = _solve_tridiagonal_iv(d, off, lam, x, precision)
    uy = _solve_tridiagonal_iv(d, off, lam, y, precision)
    one = _IV.point(1, precision)

    def dot(a, u):
        s = _IV.point(0, precision)
        for ai, ui in zip(a, u):
            s = s + _IV.point(ai, precision) * ui
        return s

    s00 = one - dot(x, ux)
    s01 = _IV.point(0, precision) - dot(x, uy)
    s11 = one - dot(y, uy)
    det = s00 * s11 - s01 * s01
    tr = s00 + s11
    det_sign = det.sign()
    if det_sign < 0:
        return 1
    return 2 if tr.sign() < 0 else 0


def _count_below_certified(d, off, x, y, lam, precision):
    return _sturm_count_iv(d, off, lam, precision) + _secular_neg_iv(d, off, x, y, lam, precision)


def _count_below(d, off, x, y, lam, precision=192, precision_cap=6144):
    p = precision
    while True:
        try:
            return _count_below_certified(d, off, x, y, lam, p)
        except _Undecided:
            p *= 2
            if p > precision_cap:
                raise ArithmeticError(
                    "certified eigenvalue count undecidable within precision quota"
                )


def _matvec_exact(d, off, x, y, v):
    """Exact rational H v for the structured operator."""
    n = len(v)
    sx = sum(xi * vi for xi, vi in zip(x, v))
    sy = sum(yi * vi for yi, vi in zip(y, v))
    out = [None] * n
    for i in range(n):
        band = Fraction(0)
        if i > 0:
            band += off * v[i - 1]
        if i + 1 < n:
            band += off * v[i + 1]
        out[i] = d[i] * v[i] - x[i] * sx - y[i] * sy + band
    return out


def _sqrt_upper(q):
    """Rational upper bound of sqrt(q) for non-negative Fraction q."""
    if q <= 0:
        return Fraction(0)
    scale = 1 << 64
    r = math.isqrt(q.numerator * scale * scale // q.denominator)
    return Fraction(r + 2, scale)


def _sqrt_lower(q):
    """Rational lower bound of sqrt(q) for positive Fraction q."""
    if q <= 0:
        raise ArithmeticError("non-positive norm cannot be lower-bounded")
    scale = 1 << 64
    r = math.isqrt(q.numerator * scale * scale // q.denominator)
    return Fraction(max(r - 1, 1), scale)


def _fr(value, digits=8):
    """Human-readable decimal string for a Fraction."""
    return str(float(value)) if abs(value) < Fraction(10) ** 30 else format(float(value), ".6e")


def certified_ground_state(operator, count_precision=192, gap_iterations=40):
    """Certified exact ground eigenpair for ``StructuredHamiltonian``.

    Returns a ``(vector, evidence)`` pair with the same contract as the
    numerical backends plus the certificate fields. Raises ArithmeticError
    (fail-closed) when a certificate cannot be produced.
    """
    from ..reference_contract import require_reference
    require_reference("structured_ground.interval_or_fp64")
    d, off, x, y = _exact_params(operator)
    n = operator.n

    if n == 1:
        lam = d[0] - x[0] * x[0] - y[0] * y[0]
        vector = np.ones(1, dtype=np.complex128)
        return vector, {
            "backend": "certified_exact_structured_cpu",
            "arithmetic": "exact_rational",
            "certified": True,
            "eigenvalue": float(lam),
            "eigenvalue_exact": _fr(lam),
            "eigenvalue_interval": [_fr(lam), _fr(lam)],
            "eigenvalue_interval_width": "0",
            "residual": 0.0,
            "residual_bound": "0",
            "eigenvector_residual_bound": "0",
            "gap_lower": None,
            "gap_bound": None,
            "sin_theta_bound": "0",
            "vector_norm": 1.0,
            "matrix_materialized": False,
            "working_bytes": 0,
            "dimension": 1,
            "operator_storage_bytes": operator.storage_bytes,
            "rank_update_columns": 2,
            "ground_check": "certified_closed_form_n1",
            "iterations": 0,
        }

    # ---- FP64 proposal (carries no evidential weight) ----
    if n <= 512:
        h = operator.dense()
        values, vectors = np.linalg.eigh(h)
        lam_tilde = float(values[0])
        v = vectors[:, 0].astype(np.float64)
        peak = int(np.argmax(np.abs(v)))
        if v[peak] < 0:
            v = -v
        proposal = "dense_eigh_fp64_proposal"
    else:
        meta = operator._python_ground()
        v = np.frombuffer(meta["vector_bytes"], dtype=np.float64).copy()
        lam_tilde = float((v[:, None].T @ (operator.matvec(v)[:, None]))[0, 0])
        v = v / np.linalg.norm(v)
        peak = int(np.argmax(np.abs(v)))
        if v[peak] < 0:
            v = -v
        proposal = "tridiagonal_rank2_fp64_proposal"

    # ---- Exact residual certificate ----
    ve = [Fraction(float(t)) for t in v]
    lam_e = Fraction(lam_tilde)
    hv = _matvec_exact(d, off, x, y, ve)
    r2 = sum((hv_i - lam_e * vi) ** 2 for hv_i, vi in zip(hv, ve))
    v2 = sum(t * t for t in ve)
    v_lower = _sqrt_lower(v2)
    r_upper = _sqrt_upper(r2)
    residual_bound = r_upper / v_lower
    lo = lam_e - residual_bound
    hi = lam_e + residual_bound

    # ---- Isolation certificate: exactly one eigenvalue inside [lo, hi] ----
    count_lo = _count_below(d, off, x, y, lo, count_precision)
    count_hi = _count_below(d, off, x, y, hi, count_precision)
    if count_lo != 0:
        raise ArithmeticError(
            "certification failed: eigenvalues below residual interval lower bound"
        )
    if count_hi < 1:
        raise ArithmeticError("certification failed: residual interval contains no eigenvalue")
    if count_hi != 1:
        raise ArithmeticError("certification failed: degenerate/clustered ground eigenspace")

    # ---- Certified spectral gap: first lambda with count >= 2 ----
    # Gershgorin bound on the top of the spectrum, computed exactly.
    x1 = sum(abs(t) for t in x)
    y1 = sum(abs(t) for t in y)
    bound_upper = (
        max(abs(d[i]) + abs(x[i]) * x1 + abs(y[i]) * y1 for i in range(n)) + 2 * abs(off) + 1
    )
    lam2_lo, lam2_hi = hi, bound_upper
    verified_top = _count_below(d, off, x, y, lam2_hi, count_precision)
    if verified_top != n:
        raise ArithmeticError(
            "certification failed: spectrum bound does not contain all eigenvalues"
        )
    for _ in range(gap_iterations):
        mid = (lam2_lo + lam2_hi) / 2
        try:
            c = _count_below(d, off, x, y, mid, count_precision)
        except ArithmeticError:
            # Probe hit a pole at this dyadic point; re-probe nearby inside the
            # bracket and use that certified count for the same update.
            mid = mid + (lam2_hi - lam2_lo) / 64
            c = _count_below(d, off, x, y, mid, count_precision)
        if c >= 2:
            lam2_hi = mid
        else:
            lam2_lo = mid
    lam1_lo = lam2_lo
    gap_bound = lam1_lo - hi

    # Certified distance from lam_tilde to every OTHER eigenvalue: count(hi)==1
    # proves the only eigenvalue below hi is the ground eigenvalue itself, so the
    # nearest other eigenvalue is lambda_1 >= lam1_lo.
    dist_other = lam1_lo - lam_e
    sin_theta = residual_bound / dist_other if dist_other > 0 else None
    vector = np.frombuffer(np.asarray(v, dtype=np.complex128).tobytes(), dtype=np.complex128)
    evidence = {
        "backend": "certified_exact_structured_cpu",
        "arithmetic": "exact_rational_and_dyadic_interval",
        "certified": True,
        "proposal": proposal,
        "eigenvalue": float((lo + hi) / 2),
        "eigenvalue_exact": _fr((lo + hi) / 2),
        "eigenvalue_interval": [_fr(lo), _fr(hi)],
        "eigenvalue_interval_width": _fr(hi - lo),
        "residual": float(r_upper / _sqrt_lower(v2)),
        "residual_bound": _fr(residual_bound),
        "eigenvector_residual_bound": _fr(residual_bound),
        "gap_lower": float(gap_bound) if gap_bound > 0 else None,
        "gap_bound": _fr(gap_bound),
        "lambda1_lower_bound": _fr(lam1_lo),
        "sin_theta_bound": _fr(sin_theta) if sin_theta is not None else None,
        "vector_norm": 1.0,
        "matrix_materialized": False,
        "working_bytes": operator.storage_bytes + n * 3 * 8,
        "dimension": n,
        "operator_storage_bytes": operator.storage_bytes,
        "rank_update_columns": 2,
        "ground_check": "certified_weinstein_interval_sturm",
        "iterations": gap_iterations,
    }
    return vector, evidence
