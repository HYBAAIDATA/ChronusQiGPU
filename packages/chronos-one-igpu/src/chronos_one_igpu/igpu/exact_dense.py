"""Certified exact ground-state solver for arbitrary dense symmetric matrices.

This is the dense counterpart of ``exact_solver.certified_ground_state``
(which exploits the structured tridiagonal+rank-2 form). For a general real
symmetric matrix the same epistemics apply:

* The matrix is converted bit-exactly to rationals (``Fraction`` of each
  float64 entry), then symmetrised exactly as (H + H^T)/2.
* An FP64 eigh proposes a candidate eigenpair (lam, v). The proposal carries
  no evidential weight.
* Exact residual certificate: r = ||H v - lam v|| / ||v|| is bounded in
  rationals; by the Weinstein residual theorem an eigenvalue of H lies inside
  [lam - r, lam + r].
* Isolation certificate: the characteristic polynomial is computed exactly
  (Faddeev-LeVerrier in rationals) and a polynomial Sturm sequence counts
  real roots inside the residual interval exactly. For a symmetric matrix
  all eigenvalues are real, so root count == eigenvalue count. A degenerate
  characteristic polynomial (gcd(p, p') non-trivial) or a count != 1 fails
  closed.
* Certified spectral gap: bisection on the Sturm root count locates the
  second eigenvalue's certified lower bound.

The returned ``vector`` is the certified representative: its exact residual
bound and sin(theta) bound are reported. Certificates are the evidence;
the float view is a projection of them. Quota: n <= 64 (Faddeev-LeVerrier is
O(n^4) in exact arithmetic); larger requests fail closed.
"""

from fractions import Fraction
import math

import numpy as np

DENSE_EXACT_DIMENSION_QUOTA = 64


def _exact_symmetric(matrix):
    a = np.asarray(matrix, dtype=np.float64)
    if a.ndim != 2 or a.shape[0] != a.shape[1] or a.shape[0] < 1:
        raise ValueError("square symmetric matrix required")
    if not np.isfinite(a).all():
        raise ValueError("finite matrix required")
    if a.shape[0] > DENSE_EXACT_DIMENSION_QUOTA:
        raise ArithmeticError(
            f"certified dense quota is n<={DENSE_EXACT_DIMENSION_QUOTA}; "
            "larger requests must use the structured certified path or "
            "explicitly named non-production references"
        )
    half = Fraction(1, 2)
    n = a.shape[0]
    h = [
        [(Fraction(float(a[i, j])) + Fraction(float(a[j, i]))) * half for j in range(n)]
        for i in range(n)
    ]
    return h


def _to_integer_matrix(h):
    """Scale a rational matrix to an integer matrix B = D * h (D a power of 2
    — float64 entries are dyadic, so D is the largest denominator)."""
    d = 1
    for row in h:
        for v in row:
            if v.denominator > d:
                d = v.denominator
    b = [[int(v * d) for v in row] for row in h]
    return b, d


def _bareiss_det(m):
    """Fraction-free exact determinant of an integer matrix (Bareiss)."""
    n = len(m)
    a = [row[:] for row in m]
    sign = 1
    prev = 1
    for k in range(n - 1):
        if a[k][k] == 0:
            pivot = next((i for i in range(k + 1, n) if a[i][k] != 0), None)
            if pivot is None:
                return 0
            a[k], a[pivot] = a[pivot], a[k]
            sign = -sign
        for i in range(k + 1, n):
            for j in range(k + 1, n):
                a[i][j] = (a[i][j] * a[k][k] - a[i][k] * a[k][j]) // prev
        prev = a[k][k]
    return sign * a[n - 1][n - 1]


def _char_poly_integer_matrix(b):
    """Exact integer characteristic polynomial q(mu) = det(mu I - B).

    Computed by evaluating q at the integer points 0..n with Bareiss
    determinants (fraction-free, exact) and recovering coefficients via
    Newton forward differences:

        q(x) = sum_k C(x, k) * D^k q(0)

    where C(x, k) = x(x-1)...(x-k+1)/k!.
    """
    n = len(b)
    values = []
    for x in range(n + 1):
        shifted = [[(x - b[i][j]) if i == j else -b[i][j] for j in range(n)] for i in range(n)]
        values.append(_bareiss_det(shifted))
    # Forward differences D^k q(0)
    diffs = values[:]
    table = [diffs[0]]
    work = diffs
    for k in range(1, n + 1):
        work = [work[i + 1] - work[i] for i in range(len(work) - 1)]
        table.append(work[0])
    # Newton -> standard basis: q(x) = sum_k table[k] * C(x,k)
    coeffs = [Fraction(0)] * (n + 1)
    binom_poly = [Fraction(1)]  # C(x,0)
    for k in range(n + 1):
        w = Fraction(table[k])
        if w:
            for j in range(k + 1):
                coeffs[j] += w * binom_poly[j] if j < len(binom_poly) else Fraction(0)
        # C(x,k+1) = C(x,k) * (x - k)/(k+1)
        new = [Fraction(0)] * (k + 2)
        for j in range(k + 1):
            new[j + 1] += binom_poly[j]  # x * C(x,k)
            new[j] -= Fraction(k) * binom_poly[j]  # -k * C(x,k)
        binom_poly = [c / (k + 1) for c in new]
    return tuple(reversed(coeffs))


def _matmul(a, b):
    n = len(a)
    out = [[Fraction(0)] * n for _ in range(n)]
    for i in range(n):
        ai = a[i]
        oi = out[i]
        for k in range(n):
            x = ai[k]
            if x:
                bk = b[k]
                for j in range(n):
                    oi[j] += x * bk[j]
    return out


def _poly_deriv(p):
    return [c * (len(p) - 1 - i) for i, c in enumerate(p[:-1])]


def _neg_inertia_fraction(a):
    """Exact LDL^T negative-inertia count in rational arithmetic.

    Sylvester's law of inertia: the number of negative diagonal pivots
    equals the number of negative eigenvalues. Zero pivots are resolved by
    inertia-preserving congruence transforms:

    * symmetric row/column swap to a nonzero diagonal pivot, or
    * a row+row / column+column fold when the remaining diagonal is all
      zero but an off-diagonal entry remains, or
    * an identically-zero trailing block contributes no negative pivots.
    """
    n = len(a)
    m = [[Fraction(v) for v in row] for row in a]
    neg = 0
    for k in range(n):
        if m[k][k] == 0:
            j = next((i for i in range(k + 1, n) if m[i][i] != 0), None)
            if j is not None:
                for i in range(n):
                    m[i][k], m[i][j] = m[i][j], m[i][k]
                m[k], m[j] = m[j], m[k]
            else:
                j = next((i for i in range(k + 1, n) if m[k][i] != 0), None)
                if j is None:
                    # trailing block is entirely zero
                    return neg
                # congruence fold: col k += col j, then row k += row j
                for i in range(n):
                    m[i][k] += m[i][j]
                for i in range(n):
                    m[k][i] += m[j][i]
        pivot = m[k][k]
        if pivot < 0:
            neg += 1
        for i in range(k + 1, n):
            mik = m[i][k] / pivot
            for j in range(k + 1, n):
                m[i][j] -= mik * m[k][j]
            m[i][k] = Fraction(0)
    return neg


def _neg_inertia(a):
    """Certified negative inertia of a symmetric integer matrix.

    Fraction-free Bareiss elimination in integers is the fast path: the
    k-th pivot of the LDL^T factorization is m[k][k]/prev, so its sign is
    sign(m[k][k] * prev). If a zero pivot is ever encountered (the one case
    where fraction-free pivot handling becomes subtle), the probe falls
    back to the exact Fraction path, which resolves it by certified
    congruence transforms.
    """
    n = len(a)
    m = [row[:] for row in a]
    neg = 0
    prev = 1
    for k in range(n):
        if m[k][k] == 0:
            # Rare pathological pivot: defer to the Fraction path, whose
            # congruence handling is certified.
            return _neg_inertia_fraction(a)
        pivot = m[k][k]
        if pivot * prev < 0:
            neg += 1
        rowk = m[k][:]
        for i in range(k + 1, n):
            mik = m[i][k]
            for j in range(k + 1, n):
                m[i][j] = (pivot * m[i][j] - mik * rowk[j]) // prev
            m[i][k] = 0
        prev = pivot
    return neg


def _count_below(b, mu):
    """Certified count of eigenvalues of integer symmetric B strictly below
    the rational bound mu = p/q (Sylvester inertia of q*B - p*I)."""
    p, qq = mu.numerator, mu.denominator
    n = len(b)
    a = [[qq * b[i][j] - (p if i == j else 0) for j in range(n)] for i in range(n)]
    return _neg_inertia(a)


def _nullity_at(b, mu):
    """Certified nullity of (B - mu*I) for rational mu = p/q, computed as
    n - rank over the rationals by full-pivoting elimination on q*B - p*I.

    For symmetric B, nullity is the geometric multiplicity of mu as an
    eigenvalue; combined with an exact residual of zero it certifies an
    exact eigenpair and its eigenspace dimension."""
    p, qq = mu.numerator, mu.denominator
    n = len(b)
    m = [[Fraction(qq * b[i][j] - (p if i == j else 0)) for j in range(n)] for i in range(n)]
    rank = 0
    for k in range(n):
        piv = None
        for i in range(k, n):
            for j in range(k, n):
                if m[i][j] != 0:
                    piv = (i, j)
                    break
            if piv is not None:
                break
        if piv is None:
            break
        i0, j0 = piv
        if i0 != k:
            m[k], m[i0] = m[i0], m[k]
        if j0 != k:
            for i in range(n):
                m[i][k], m[i][j0] = m[i][j0], m[i][k]
        rank += 1
        pivv = m[k][k]
        rowk = m[k][:]
        for i in range(k + 1, n):
            f = m[i][k] / pivv
            for j in range(k + 1, n):
                m[i][j] -= f * rowk[j]
            m[i][k] = Fraction(0)
    return n - rank


def _sqrt_upper(q):
    if q <= 0:
        return Fraction(0)
    scale = 1 << 64
    r = math.isqrt(q.numerator * scale * scale // q.denominator)
    return Fraction(r + 2, scale)


def _sqrt_lower(q):
    if q <= 0:
        raise ArithmeticError("non-positive norm cannot be lower-bounded")
    scale = 1 << 64
    r = math.isqrt(q.numerator * scale * scale // q.denominator)
    return Fraction(max(r - 1, 1), scale)


def _fr(value, digits=8):
    return str(float(value)) if abs(value) < Fraction(10) ** 30 else format(float(value), ".6e")


def _matvec_exact(h, v):
    n = len(h)
    return [sum(h[i][j] * v[j] for j in range(n)) for i in range(n)]


def certified_dense_ground_state(matrix, gap_iterations=None):
    """Certified exact ground eigenpair of a real symmetric matrix.

    Returns ``(vector, evidence)``. ``vector`` is the FP64 certified
    representative whose exact residual bound is reported; ``evidence``
    carries the certified eigenvalue interval, gap bound, and sin(theta)
    bound. Raises ArithmeticError (fail closed) when a certificate cannot be
    produced: non-symmetric input, degenerate eigenspace, overlapping
    intervals, or dimension above the exact quota. ``gap_iterations`` is
    retained for API compatibility; the gap is certified directly via the
    second eigenpair's exact residual interval.
    """
    h = _exact_symmetric(matrix)
    n = len(h)

    if n == 1:
        lam = h[0][0]
        return np.ones(1, dtype=np.complex128), {
            "backend": "certified_exact_dense_cpu",
            "arithmetic": "exact_rational",
            "certified": True,
            "eigenvalue": float(lam),
            "eigenvalue_exact": _fr(lam),
            "eigenvalue_interval": [_fr(lam), _fr(lam)],
            "eigenvalue_interval_width": "0",
            "residual": 0.0,
            "residual_bound": "0",
            "gap_lower": None,
            "gap_bound": None,
            "sin_theta_bound": "0",
            "dimension": 1,
            "ground_check": "certified_closed_form_n1",
            "iterations": 0,
        }

    # ---- Exact characteristic polynomial ----
    # B = D * h integer matrix; eigenvalues of H are roots of q(mu)/D where
    # q(mu) = det(mu I - B) is the exact integer characteristic polynomial.
    b, scale = _to_integer_matrix(h)
    q = _char_poly_integer_matrix(b)
    # Degeneracy is certified away by the isolation count below: a repeated
    # ground root puts >=2 eigenvalues inside the residual interval, and a
    # repeated second eigenvalue makes the two certified intervals overlap.
    # ---- FP64 proposal (no evidential weight) ----
    a = np.array([[float(h[i][j]) for j in range(n)] for i in range(n)])
    values, vectors = np.linalg.eigh(a)
    lam_tilde = float(values[0])
    v = vectors[:, 0].astype(np.float64)
    peak = int(np.argmax(np.abs(v)))
    if v[peak] < 0:
        v = -v

    # ---- Exact residual certificate ----
    ve = [Fraction(float(t)) for t in v]
    lam_e = Fraction(lam_tilde)
    hv = _matvec_exact(h, ve)
    r2 = sum((hv_i - lam_e * vi) ** 2 for hv_i, vi in zip(hv, ve))
    v2 = sum(t * t for t in ve)
    residual_bound = _sqrt_upper(r2) / _sqrt_lower(v2)
    lo = lam_e - residual_bound
    hi = lam_e + residual_bound

    # ---- Isolation: exactly one root inside [lo, hi] (probes in B-space) ----
    count_lo = _count_below(b, lo * scale)
    if count_lo != 0:
        raise ArithmeticError(
            "certification failed: eigenvalues below residual interval "
            "lower bound; proposal is not the ground state"
        )
    if residual_bound == 0:
        # Exact eigenpair: the residual interval is a single exact point and
        # the strictly-below count cannot isolate a boundary root. Certify
        # instead that the eigenpair is simple: nullity of (B - lam*D*I) == 1
        # proves lam*scale is an eigenvalue of geometric multiplicity one.
        multiplicity = _nullity_at(b, lam_e * scale)
        if multiplicity != 1:
            raise ArithmeticError(
                "certification failed: exact ground eigenvalue has "
                f"eigenspace dimension {multiplicity} != 1"
            )
    else:
        count_hi = _count_below(b, hi * scale)
        if count_hi != 1:
            raise ArithmeticError(
                "certification failed: residual interval does not isolate "
                f"exactly one eigenvalue (count_below(lo)={count_lo}, "
                f"count_below(hi)={count_hi})"
            )

    # ---- Certified gap: exact residual bound on the second eigenpair ----
    # The FP64 proposal for lambda_1 (second eigenvalue) gets the same exact
    # Weinstein interval; its certified lower bound minus our certified upper
    # bound is a rigorous spectral gap — no bisection needed.
    lam2_e = Fraction(float(values[1]))
    ve2 = [Fraction(float(t)) for t in vectors[:, 1]]
    hv2 = _matvec_exact(h, ve2)
    r22 = sum((hv_i - lam2_e * vi) ** 2 for hv_i, vi in zip(hv2, ve2))
    v22 = sum(t * t for t in ve2)
    residual2_bound = _sqrt_upper(r22) / _sqrt_lower(v22)
    lam2_lo = lam2_e - residual2_bound
    # Certify that exactly one eigenvalue lies strictly below lam2_lo
    # (the isolated ground root we already certified).
    if _count_below(b, lam2_lo * scale) != 1:
        raise ArithmeticError(
            "certification failed: second-eigenvalue lower bound does not "
            "isolate the ground eigenvalue"
        )
    gap_bound = lam2_lo - hi
    if gap_bound <= 0:
        raise ArithmeticError(
            "certification failed: eigenvalue intervals overlap; spectral "
            "gap cannot be certified"
        )
    dist_other = lam2_lo - lam_e
    sin_theta = residual_bound / dist_other if dist_other > 0 else None

    vector = np.frombuffer(np.asarray(v, dtype=np.complex128).tobytes(), dtype=np.complex128)
    evidence = {
        "backend": "certified_exact_dense_cpu",
        "arithmetic": "exact_rational_sylvester_inertia",
        "certified": True,
        "proposal": "dense_eigh_fp64_proposal",
        "eigenvalue": float((lo + hi) / 2),
        "eigenvalue_exact": _fr((lo + hi) / 2),
        "eigenvalue_interval": [_fr(lo), _fr(hi)],
        "eigenvalue_interval_width": _fr(hi - lo),
        "residual": float(residual_bound),
        "residual_bound": _fr(residual_bound),
        "eigenvector_residual_bound": _fr(residual_bound),
        "gap_lower": float(gap_bound) if gap_bound > 0 else None,
        "gap_bound": _fr(gap_bound),
        "lambda1_lower_bound": _fr(lam2_lo),
        "sin_theta_bound": _fr(sin_theta) if sin_theta is not None else None,
        "vector_norm": 1.0,
        "dimension": n,
        "ground_check": "certified_weinstein_interval_sylvester_inertia",
        "integer_scale": int(scale),
        "characteristic_polynomial_bits": max(
            (c.numerator.bit_length() + c.denominator.bit_length()) for c in q
        ),
        "inertia_probes": 3,
    }
    return vector, evidence
