#!/usr/bin/env python3
"""Finite SU(2) gauge thread: phi -> 2I -> Poincare homology sphere -> gap.

phi -> golden icosians -> binary icosahedral group 2I -> Sigma(2,3,5)
    -> SU(2) gauge -> Casimir spectrum -> mass gap

Every stage is computed. Exact quaternion arithmetic over Q(sqrt(5)), the
group structure of 2I, the 600-cell topology, the character table from the
class algebra, and the spectrum of the Laplace operator on the group algebra.
The mass gap is read off those eigenvalues. It is never hard-coded.

Scope: this is the quantum-group Laplacian on the finite subgroup 2I of
SU(2), equivalently the 600-cell triangulation of S^3. It is not the
continuum Yang-Mills theory on R^4. ``proof_claim`` stays False; the Clay
mass-gap problem stays OPEN. Evidence class: FINITE_VOLUME_VERIFIED.

Run: python -m millennium.hyba_poincare_yangmills
"""

import math
import numpy as np

# Honest boundary. A positive eigenvalue of this finite model is not a
# continuum existence proof.
EVIDENCE_CLASS = "FINITE_VOLUME_VERIFIED"
PROOF_CLAIM = False
CONTINUUM_CLAIM = False
SCOPE = (
    "Exact spectrum of the quantum-group Laplace operator on the binary "
    "icosahedral group 2I of order 120 (the 600-cell triangulation of S^3, "
    "pi_1 of the Poincare homology sphere Sigma(2,3,5)). Finite subgroup of "
    "SU(2), not continuum Yang-Mills on R^4."
)

_CACHE = None

SQRT5 = math.sqrt(5.0)
PHI = (1.0 + SQRT5) / 2.0

# =============================================================================
# PART 0 - GOLDEN-RATIO ALGEBRAIC FAMILY (the seed of the thread, exact)
# =============================================================================


def fib_pair(n):
    """Fast-doubling: (F_n, F_{n+1}) exactly."""
    if n == 0:
        return (0, 1)
    a, b = fib_pair(n >> 1)
    c = a * ((b << 1) - a)
    d = a * a + b * b
    return (d, c + d) if (n & 1) else (c, d)


def F(n):
    return fib_pair(n)[0]


def L(n):
    if n == 0:
        return 2
    return fib_pair(n - 1)[0] + fib_pair(n + 1)[0]


def cassini(n):
    return F(n + 1) * F(n - 1) - F(n) ** 2


def zeckendorf(n):
    """Unique non-adjacent Fibonacci representation -> [(index, value)], F_2=1."""
    fibs = [(2, 1)]
    a, b = 1, 2
    idx = 3
    while b <= n:
        fibs.append((idx, b))
        a, b = b, a + b
        idx += 1
    res = []
    rem = n
    for i, f in reversed(fibs):
        if f <= rem:
            res.append((i, f))
            rem -= f
    return res


def verify_golden_family(N=200):
    checks = []
    checks.append(
        (
            "Cassini  F(n+1)F(n-1)-F(n)^2 = (-1)^n",
            all(cassini(n) == ((-1) ** n) for n in range(1, N + 1)),
        )
    )
    checks.append(
        (
            "Lucas-Cassini  L_n^2-5F_n^2 = 4(-1)^n",
            all(L(n) ** 2 - 5 * F(n) ** 2 == 4 * ((-1) ** n) for n in range(1, N + 1)),
        )
    )
    checks.append(
        ("Unimodular  |det(M^n)| = 1", all(abs(cassini(n)) == 1 for n in range(1, N + 1)))
    )
    checks.append(
        ("Trace identity  tr(M^n) = L_n", all(F(n + 1) + F(n - 1) == L(n) for n in range(1, N + 1)))
    )
    zok = True
    for n in range(1, 1000):
        z = zeckendorf(n)
        if sum(f for _, f in z) != n:
            zok = False
            break
        idxs = [i for i, _ in z]
        if any(abs(idxs[k + 1] - idxs[k]) < 2 for k in range(len(idxs) - 1)):
            zok = False
            break
    checks.append(("Zeckendorf unique non-adjacent encoding (n<1000)", zok))
    return checks


# =============================================================================
# PART 1 - EXACT ICOSIAN ARITHMETIC (Q(sqrt5); coord = (p + q*sqrt5)/4)
# =============================================================================


def _prod(x, y):
    return (x[0] * y[0] + 5 * x[1] * y[1], x[0] * y[1] + x[1] * y[0])


def _neg(x):
    return (-x[0], -x[1])


def _sumred(terms):
    P = sum(t[0] for t in terms)
    Q = sum(t[1] for t in terms)
    if P % 4 != 0 or Q % 4 != 0:
        raise ArithmeticError(f"icosian sum not divisible by 4: {(P, Q)}")
    return (P // 4, Q // 4)


def qmul(a, b):
    """Exact product of two icosian quaternions (4-tuples of (p,q) pairs)."""
    a1, a2, a3, a4 = a
    b1, b2, b3, b4 = b
    c1 = _sumred([_prod(a1, b1), _neg(_prod(a2, b2)), _neg(_prod(a3, b3)), _neg(_prod(a4, b4))])
    c2 = _sumred([_prod(a1, b2), _prod(a2, b1), _prod(a3, b4), _neg(_prod(a4, b3))])
    c3 = _sumred([_prod(a1, b3), _neg(_prod(a2, b4)), _prod(a3, b1), _prod(a4, b2)])
    c4 = _sumred([_prod(a1, b4), _prod(a2, b3), _neg(_prod(a3, b2)), _prod(a4, b1)])
    return (c1, c2, c3, c4)


def qinv(a):
    return (a[0], _neg(a[1]), _neg(a[2]), _neg(a[3]))


def qnorm2(a):
    P = sum(x[0] ** 2 + 5 * x[1] ** 2 for x in a)
    Q = sum(2 * x[0] * x[1] for x in a)
    return (P, Q)


def is_unit(a):
    P, Q = qnorm2(a)
    return P == 16 and Q == 0


def to_float4(q):
    return np.array([(p + q * SQRT5) / 4.0 for (p, q) in q])


Z = (0, 0)
ONE = (4, 0)
IDENTITY = (ONE, Z, Z, Z)

# =============================================================================
# PART 2 - CONSTRUCT 2I (binary icosahedral group, order 120) BY CLOSURE
# =============================================================================


def tetrahedral24():
    """The 24-cell / binary tetrahedral group 2T (24 unit quaternions)."""
    els = []
    for s in (1, -1):
        els.append(((s * 4, 0), Z, Z, Z))
        els.append((Z, (s * 4, 0), Z, Z))
        els.append((Z, Z, (s * 4, 0), Z))
        els.append((Z, Z, Z, (s * 4, 0)))
    for s1 in (1, -1):
        for s2 in (1, -1):
            for s3 in (1, -1):
                for s4 in (1, -1):
                    els.append(((2 * s1, 0), (2 * s2, 0), (2 * s3, 0), (2 * s4, 0)))
    return els


# golden 5-fold rotation g = (1/(2phi), 0, -phi/2, 1/2) - genuine order-5 icosian
G = ((-1, 1), (0, 0), (-1, -1), (2, 0))


def close_group(generators):
    elements = {IDENTITY}
    frontier = [IDENTITY]
    while frontier:
        g = frontier.pop()
        for h in generators:
            gh = qmul(g, h)
            if gh not in elements:
                elements.add(gh)
                frontier.append(gh)
    return elements


def build_2I():
    return close_group(tetrahedral24() + [G])


# =============================================================================
# PART 3 - GROUP STRUCTURE (conjugacy classes, computed)
# =============================================================================


def conjugacy_classes(elements):
    elist = list(elements)
    seen = set()
    classes = []
    for e in elist:
        if e in seen:
            continue
        cls = set()
        for g in elist:
            c = qmul(qmul(g, e), qinv(g))
            cls.add(c)
            seen.add(c)
        classes.append(cls)
    return classes


def element_order(e):
    o = 1
    acc = e
    while acc != IDENTITY:
        acc = qmul(acc, e)
        o += 1
        if o > 200:
            return None
    return o


# =============================================================================
# PART 4 - 600-CELL TOPOLOGY (the S^3 = SU(2) discretization, computed)
# =============================================================================


def six_hundred_cell_topology(elist, neighbors):
    V = len(elist)
    E = sum(len(nb) for nb in neighbors) // 2
    adj = [set(nb) for nb in neighbors]
    triangles = set()
    for i in range(V):
        for j in neighbors[i]:
            for l in neighbors[i]:
                if l > j and l in adj[j]:
                    triangles.add(tuple(sorted((i, j, l))))
    F = len(triangles)
    C = F // 2  # each tetrahedron has 4 faces, each face in 2 tetrahedra -> C = F/2
    euler = V - E + F - C
    return V, E, F, C, euler


# =============================================================================
# PART 5 - FULL CHARACTER TABLE OF 2I (computed from the class algebra)
# =============================================================================


def class_multiplication(elist, classes):
    """c_ijl = #{(a,b) in C_i x C_j : ab = g_l} (g_l fixed rep of C_l).
    K_i K_j = sum_l c_ijl K_l - the structure constants of the class algebra."""
    k = len(classes)
    reps = [next(iter(cls)) for cls in classes]
    class_of = {}
    for ci, cls in enumerate(classes):
        for e in cls:
            class_of[e] = ci
    c = np.zeros((k, k, k), dtype=int)
    for i in range(k):
        for j in range(k):
            for a in classes[i]:
                for b in classes[j]:
                    ab = qmul(a, b)
                    if ab == reps[class_of[ab]]:
                        c[i][j][class_of[ab]] += 1
    return c


def recognize_q5(x, tol=1e-8):
    """Recognize float x as (p + q*sqrt5)/k with small integers (p, q, k)."""
    for k in range(1, 25):
        for p in range(-40, 41):
            for q in range(-40, 41):
                if abs((p + q * SQRT5) / k - x) < tol:
                    return (p, q, k)
    return None


def q5_str(a):
    """(p, q, k) -> human string, e.g. (1,1,4) -> (1+sqrt5)/4."""
    p, q, k = a
    if q == 0:
        return str(p) if k == 1 else f"{p}/{k}"
    num = f"{p}+{q}sqrt5" if p else f"{q}sqrt5"
    return f"({num})" if k == 1 else f"({num})/{k}"


def character_table(elist, classes, sizes):
    """Compute the full character table of 2I from the class algebra.
    omega_i(rho) = |C_i| chi_rho(g_i) / d_rho are the common eigenvalues of
    the class matrices; d_rho follows from orthogonality
    sum_i |omega_i(rho)|^2 / |C_i| = |G| / d_rho^2."""
    k = len(classes)
    G = len(elist)
    c = class_multiplication(elist, classes)
    M = [
        np.array([[c[i][j][l] for j in range(k)] for l in range(k)], dtype=float) for i in range(k)
    ]
    # generic combination to split degenerate eigenspaces (same common eigenbasis);
    # any algebraically-generic weights work — a golden-ratio Weyl sequence is
    # deterministic, generic, and needs no RNG.
    _phi = (1.0 + math.sqrt(5.0)) / 2.0
    alpha = np.array([((i + 1) * _phi) % 1.0 + 0.5 for i in range(k)])
    Mgen = sum(alpha[i] * M[i] for i in range(k))
    evals, evecs = np.linalg.eig(Mgen)
    order = np.argsort(evals.real)
    omegas = np.zeros((k, k))
    for rho in range(k):
        v = evecs[:, order[rho]].real
        j = int(np.argmax(np.abs(v)))
        for i in range(k):
            omegas[i][rho] = (M[i] @ v)[j] / v[j]
    dims = []
    for rho in range(k):
        s = sum(omegas[i][rho] ** 2 / sizes[i] for i in range(k))
        dims.append(math.sqrt(G / s))
    chi = np.zeros((k, k))
    for rho in range(k):
        for i in range(k):
            chi[rho][i] = dims[rho] * omegas[i][rho] / sizes[i]
    return chi, dims, omegas


# =============================================================================
# PART 6 - QUANTUM-GROUP / YANG-MILLS LAPLACE OPERATOR
# =============================================================================


def fixed_generating_set(elist, k=12):
    """S = the 12 nearest neighbours of identity (600-cell edges, inverse-closed)."""
    vecs = np.array([to_float4(e) for e in elist])
    dots = vecs @ vecs.T
    i0 = elist.index(IDENTITY)
    d0 = dots[i0].copy()
    d0[i0] = -1.0
    return [elist[j] for j in np.argsort(-d0)[:k]]


def group_laplacian(elist, S):
    """L = I - (1/|S|) sum_{s in S} R_s on C[2I] (right-regular rep). Hermitian."""
    n = len(elist)
    index = {e: i for i, e in enumerate(elist)}
    L = np.zeros((n, n))
    for i, e in enumerate(elist):
        L[i, i] = 1.0
        for s in S:
            es = qmul(e, s)
            L[i, index[es]] -= 1.0 / len(S)
    return L


# =============================================================================
# PART 7 - RUN THE COMPLETE ENGINE
# =============================================================================


def _emit(verbose, *args):
    if verbose:
        print(*args)


def run(verbose=True):
    _emit(verbose, "=" * 78)
    _emit(verbose, "  HYBA ONE-THREAD ENGINE - COMPLETE IMPLEMENTATION")
    _emit(verbose, "  phi -> icosians -> 2I -> Sigma(2,3,5) -> SU(2) gauge -> Casimir -> gap")
    _emit(verbose, "=" * 78)

    # --- 0. golden-ratio family (the seed) ------------------------------------
    _emit(verbose, "\n[0] GOLDEN-RATIO ALGEBRAIC FAMILY (the seed, exact integer arithmetic)")
    for name, ok in verify_golden_family():
        _emit(verbose, f"    [{'PASS' if ok else 'FAIL'}]  {name}")
    if not all(ok for _, ok in verify_golden_family()):
        raise RuntimeError("golden-ratio algebraic family check failed")

    # --- 1. golden icosians ---------------------------------------------------
    _emit(verbose, "\n[1] GOLDEN ICOSIANS (exact Q(sqrt5) quaternion arithmetic)")
    _emit(verbose, f"    phi = (1+sqrt5)/2 = {PHI:.12f}")
    g = to_float4(G)
    _emit(verbose, f"    golden 5-fold rotation g = (1/(2phi), 0, -phi/2, 1/2) = {np.round(g, 6)}")
    _emit(verbose, f"    |g| = {np.linalg.norm(g):.12f}  (unit quaternion in S^3 = SU(2))")
    _emit(verbose, f"    order(g) = {element_order(G)}  (genuine 5-fold golden rotation)")
    if element_order(G) != 5:
        raise RuntimeError(f"golden icosian order is {element_order(G)}, expected 5")

    # --- 2. 2I group ----------------------------------------------------------
    _emit(verbose, "\n[2] BINARY ICOSAHEDRAL GROUP 2I")
    els = build_2I()
    elist = list(els)
    _emit(verbose, f"    |2I| = {len(els)}")
    _emit(verbose, f"    all unit quaternions : {all(is_unit(e) for e in els)}")
    _emit(verbose, f"    closed under product : {all(qmul(a, b) in els for a in els for b in els)}")
    _emit(verbose, f"    closed under inverse : {all(qinv(a) in els for a in els)}")
    if len(els) != 120:
        raise RuntimeError(f"|2I| = {len(els)}, expected 120")

    # --- 3. Poincare / conjugacy classes --------------------------------------
    _emit(verbose, "\n[3] POINCARE HOMOLOGY SPHERE Sigma(2,3,5) = S^3/2I")
    classes = conjugacy_classes(els)
    sizes = [len(c) for c in classes]  # MUST match class order (not sorted)
    _emit(verbose, f"    conjugacy classes : {len(classes)}")
    _emit(verbose, f"    class sizes       : {sorted(sizes)}")
    _emit(verbose, f"    sum|C_i| = {sum(sizes)}")
    _emit(verbose, "    pi_1(Sigma(2,3,5)) = 2I (order 120); same homology as S^3")
    if len(classes) != 9:
        raise RuntimeError(f"2I conjugacy classes = {len(classes)}, expected 9")

    # --- 4. 600-cell topology --------------------------------------------------
    _emit(verbose, "\n[4] 600-CELL TOPOLOGY (the S^3 = SU(2) discretization)")
    vecs = np.array([to_float4(e) for e in elist])
    dots = vecs @ vecs.T
    np.fill_diagonal(dots, -1.0)
    neighbors = [list(np.argsort(-dots[i])[:12]) for i in range(len(elist))]
    V, E, F, C, euler = six_hundred_cell_topology(elist, neighbors)
    _emit(verbose, f"    V = {V}   E = {E}   F = {F}   C = {C}")
    _emit(verbose, f"    Euler V-E+F-C = {euler}   (600-cell is a triangulation of S^3)")
    _emit(verbose, f"    edge dot = phi/2 = {PHI / 2:.6f}  (12 neighbours per vertex)")
    if euler != 0:
        raise RuntimeError(f"600-cell Euler characteristic {euler}, expected 0")

    # --- 5. full character table -----------------------------------------------
    _emit(verbose, "\n[5] FULL CHARACTER TABLE OF 2I (computed from the class algebra)")
    chi, dims, omegas = character_table(elist, classes, sizes)
    dims_r = [int(round(d)) for d in dims]
    _emit(verbose, f"    irrep dimensions d_rho : {dims_r}")
    _emit(verbose, f"    sum d_rho^2 = {sum(d * d for d in dims_r)}  (must equal |2I| = 120)")
    if sum(d * d for d in dims_r) != 120:
        raise RuntimeError("sum of squared irrep dimensions != |2I|")
    ortho_ok = True
    for rho in range(9):
        for sig in range(9):
            s = sum(sizes[i] * chi[rho][i] * chi[sig][i] for i in range(9))
            expected = 120 if rho == sig else 0
            if abs(s - expected) > 1e-6:
                ortho_ok = False
    _emit(verbose, f"    orthogonality sum|C_i|chi_rho chi_sigma = delta |G| : {ortho_ok}")
    if not ortho_ok:
        raise RuntimeError("2I character-table orthogonality failed")
    _emit(verbose, "    character table (rows = irreps, cols = classes):")
    for rho in range(9):
        row = "  ".join(f"{chi[rho][i]:6.3f}" for i in range(9))
        _emit(verbose, f"      d={dims_r[rho]:>2}  {row}")

    # --- 6. quantum-group / Yang-Mills Laplace operator -----------------------
    _emit(verbose, "\n[6] QUANTUM-GROUP LAPLACE OPERATOR L = I - (1/|S|) sum R_s on C[2I]")
    S = fixed_generating_set(elist, k=12)
    invclosed = all(qinv(s) in S for s in S)
    L = group_laplacian(elist, S)
    sym = np.allclose(L, L.T, atol=1e-12)
    ev = np.sort(np.linalg.eigvalsh(L))
    _emit(verbose, f"    S inverse-closed : {invclosed}   L Hermitian : {sym}")
    _emit(verbose, f"    lambda_0 = {ev[0]:.2e}  (trivial rep - the vacuum)")
    uniq, counts = np.unique(np.round(ev, 8), return_counts=True)
    _emit(verbose, f"    distinct levels : {len(uniq)}  (the 9 irreps of 2I)")
    _emit(verbose, "    level -> eigenspace dim (= d^2) -> irrep dimension d:")
    for u, c in zip(uniq, counts):
        d = round(math.sqrt(int(c)))
        _emit(verbose, f"      lambda = {u:.6f}   dim = {int(c):>2} = d^2  ->  d = {d}")

    # --- 7. exact eigenvalues from the character table ------------------------
    _emit(verbose, "\n[7] EXACT EIGENVALUES (lambda_rho = 1 - chi_rho(g)/d_rho, g a 600-cell edge)")
    reps = [next(iter(cls)) for cls in classes]
    sclass = None
    for i, r in enumerate(reps):
        if abs(to_float4(r)[0] - PHI / 2) < 1e-6:
            sclass = i
            break
    edge_rep = reps[sclass]
    edge_order = element_order(edge_rep)
    _emit(
        verbose,
        f"    generating class : {sizes[sclass]} elements of order {edge_order}, real part phi/2",
    )
    _emit(
        verbose,
        "    their images in SO(3) are 5-fold; the order-5 class has real part 1/(2 phi) and is not an edge",
    )
    exact = []
    for rho in range(9):
        d = dims_r[rho]
        val = chi[rho][sclass] / d  # = chi_rho(g)/d_rho
        lam = 1.0 - val
        rec = recognize_q5(val)
        exact.append((d, lam, rec))
    for d, lam, rec in exact:
        if rec:
            _emit(verbose, f"      d = {d:>2}   lambda = {lam:.8f}  =  1 - {q5_str(rec)}")
        else:
            _emit(verbose, f"      d = {d:>2}   lambda = {lam:.8f}")

    # --- 8. Yang-Mills gauge-invariant Hamiltonian + mass gap -----------------
    _emit(verbose, "\n[8] YANG-MILLS HAMILTONIAN ON THE GAUGE GROUP (SU(2) contains 2I)")
    _emit(verbose, "    gauge-invariant Hilbert space = class functions on 2I (dim 9)")
    _emit(verbose, "    H_YM = group Laplacian restricted to gauge-invariant states")
    gap = float(ev[ev > 1e-9][0]) - float(ev[0])
    gap_rec = recognize_q5(1.0 - gap)  # recognize chi/d = phi/2
    _emit(verbose, f"    MASS GAP Delta = lambda_1 - lambda_0 = {gap:.8f}")
    if gap_rec:
        _emit(
            verbose, f"    exact form : Delta = 1 - {q5_str(gap_rec)}  =  1 - phi/2 = 1/(2 phi^2)"
        )
    _emit(verbose, f"    Delta > 0 : {gap > 0}")
    _emit(verbose, f"    Delta * |2I| = {gap * 120:.4f}  (scale check - the gap is a genuine")
    _emit(verbose, "    eigenvalue difference of the quantum-group operator, computed)")

    # --- 9. the one thread -----------------------------------------------------
    _emit(verbose, "\n[9] THE ONE THREAD")
    _emit(verbose, "    phi -> golden icosians -> 2I (order 120) -> Sigma(2,3,5) Poincare")
    _emit(verbose, "    -> SU(2) gauge (2I in SU(2)) -> Casimir spectrum -> Delta = 1 - phi/2")
    _emit(verbose, "    Every stage implemented and computed; the gap is read off the")
    _emit(verbose, "    spectrum, never hard-coded.")

    _emit(verbose, "\n" + "=" * 78)
    _emit(verbose, f"  RESULT: positive spectral gap Delta = {gap:.6f} = 1 - phi/2 = 1/(2 phi^2)")
    _emit(verbose, "  Complete implementation: golden family -> icosians -> 2I -> Poincare")
    _emit(verbose, "  -> SU(2) gauge -> character table -> quantum-group spectrum -> gap.")
    _emit(verbose, "=" * 78)
    report = {
        "phi": PHI,
        "golden_checks": [{"name": name, "pass": bool(ok)} for name, ok in verify_golden_family()],
        "rotation_order": element_order(G),
        "edge_class_order": edge_order,
        "edge_class_size": sizes[sclass],
        "group_order": len(els),
        "all_units": all(is_unit(e) for e in els),
        "closed_product": all(qmul(a, b) in els for a in els for b in els),
        "closed_inverse": all(qinv(a) in els for a in els),
        "class_count": len(classes),
        "class_sizes": sizes,
        "topology": {"V": V, "E": E, "F": F, "C": C, "euler": euler},
        "dims": dims_r,
        "sum_squares": sum(d * d for d in dims_r),
        "orthogonality": bool(ortho_ok),
        "levels": [
            {
                "lambda": float(u),
                "multiplicity": int(c),
                "dimension": int(round(math.sqrt(int(c)))),
            }
            for u, c in zip(uniq, counts)
        ],
        "hermitian": bool(sym),
        "inverse_closed": bool(invclosed),
        "lambda0": float(ev[0]),
        "gap": gap,
        "gap_algebraic": ({"p": gap_rec[0], "q": gap_rec[1], "k": gap_rec[2]} if gap_rec else None),
        "exact": [
            {
                "dimension": d,
                "lambda": lam,
                "character_over_dim": (
                    None if rec is None else {"p": rec[0], "q": rec[1], "k": rec[2]}
                ),
            }
            for d, lam, rec in exact
        ],
        "gap_positive": bool(gap > 0),
        "evidence_class": EVIDENCE_CLASS,
        "proof_claim": PROOF_CLAIM,
        "continuum_claim": CONTINUUM_CLAIM,
        "scope": SCOPE,
    }
    return report


def cached_report(verbose=False):
    """Compute the thread once per process. TOE reads this, it does not re-derive a constant."""
    global _CACHE
    if _CACHE is None:
        _CACHE = run(verbose=verbose)
    return _CACHE


if __name__ == "__main__":
    run(verbose=True)
