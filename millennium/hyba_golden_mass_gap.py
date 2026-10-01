"""Golden-ratio family, then the exact spectrum of the canonical M32 graph.

The algebraic certificates are exact. The 32 directions are the truncated-icosahedron
face normals already used by the miner (icosahedral 12-orbit plus dodecahedral
20-orbit), not the attachment's dodecahedron. That attachment swaps two
coordinate slots, so its vertices are not the regular dodecahedron.

Neighbours are the pairs whose exact cosine exceeds cos(2π/5). The
combinatorial Laplacian of that graph has characteristic polynomial

    x (x-15) (x-14)^6 (x-11)^3 (x^2-26x+164)^2 (x^2-23x+128) q(x)^3

with q the quintic below. The gap is the unique root of q in (5, 6). It is
an algebraic integer of degree 5, so it does not lie in Q(√5). Positivity of
this one eigenvalue is a theorem about this finite graph. It is not the
continuum Yang–Mills mass gap, not a QCD mass, and not a share-accept rule.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from decimal import Decimal, getcontext
from fractions import Fraction
from pathlib import Path

PHI = (1.0 + math.sqrt(5.0)) / 2.0
PSI = 1.0 - PHI
SQRT5 = math.sqrt(5.0)

EVIDENCE_CLASS = "EXACT_ARITHMETIC"
PROOF_CLAIM = False
CONTINUUM_CLAIM = False
PHYSICAL_QCD_CLAIM = False
SCOPE = (
    "Exact spectrum of the combinatorial Laplacian on the 32 face normals "
    "of the truncated icosahedron, edges where cosine exceeds cos(2*pi/5). "
    "Not continuum Yang-Mills on R^4, not a QCD mass, and not the "
    "order-120 binary-icosahedral Laplacian."
)
# q is irreducible over Q (irreducible mod 5). The gap is its least root.
GAP_QUINTIC = (1, -59, 1360, -15216, 81792, -165904)


def fib_pair(n: int) -> tuple[int, int]:
    """Fast-doubling: returns (F_n, F_{n+1}) exactly."""
    if n == 0:
        return (0, 1)
    a, b = fib_pair(n >> 1)
    c = a * ((b << 1) - a)
    d = a * a + b * b
    return (d, c + d) if (n & 1) else (c, d)


def F(n: int) -> int:
    return fib_pair(n)[0]


def L(n: int) -> int:
    """Lucas number L_n = F_{n-1} + F_{n+1}."""
    if n == 0:
        return 2
    return fib_pair(n - 1)[0] + fib_pair(n + 1)[0]


def M_power(n: int) -> list[list[int]]:
    """M^n = [[F_{n+1}, F_n], [F_n, F_{n-1}]]."""
    return [[F(n + 1), F(n)], [F(n), F(n - 1)]]


def cassini(n: int) -> int:
    """F_{n+1} F_{n-1} - F_n^2 = (-1)^n."""
    if n <= 0:
        raise ValueError("n must be positive")
    return F(n + 1) * F(n - 1) - F(n) ** 2


def binet_fib(n: int) -> float:
    return (PHI**n - PSI**n) / SQRT5


def binet_lucas(n: int) -> float:
    return PHI**n + PSI**n


def pisot_residue(n: int) -> float:
    return abs(PHI**n - L(n))


def zeckendorf(n: int) -> list[tuple[int, int]]:
    """Unique non-adjacent Fibonacci representation as (index, value)."""
    if n < 0:
        raise ValueError("n must be non-negative")
    fibs = [(2, 1)]
    a, b = 1, 2
    idx = 3
    while b <= n:
        fibs.append((idx, b))
        a, b = b, a + b
        idx += 1
    res: list[tuple[int, int]] = []
    rem = n
    for i, f in reversed(fibs):
        if f <= rem:
            res.append((i, f))
            rem -= f
    return res


def zeckendorf_popcount(n: int) -> int:
    return len(zeckendorf(n))


def _dec_phi() -> Decimal:
    getcontext().prec = 120
    return (Decimal(1) + Decimal(5).sqrt()) / 2


def binet_exact_check(N: int = 200) -> bool:
    phi = _dec_phi()
    psi = (Decimal(1) - Decimal(5).sqrt()) / 2
    sqrt5 = Decimal(5).sqrt()
    for n in range(1, N + 1):
        fb = (phi**n - psi**n) / sqrt5
        lb = phi**n + psi**n
        if abs(fb - F(n)) > Decimal("1e-50") or abs(lb - L(n)) > Decimal("1e-50"):
            return False
    return True


def pisot_exact_check(N: int = 200) -> bool:
    phi = _dec_phi()
    psi = (Decimal(1) - Decimal(5).sqrt()) / 2
    for n in range(1, N + 1):
        lhs = abs(phi**n - L(n))
        rhs = abs(psi) ** n
        if abs(lhs - rhs) > Decimal("1e-50") * max(Decimal(1), rhs):
            return False
    return True


def verify_algebra(N: int = 200) -> list[tuple[str, bool]]:
    checks = [
        ("Cassini", all(cassini(n) == ((-1) ** n) for n in range(1, N + 1))),
        (
            "Lucas-Cassini",
            all(L(n) ** 2 - 5 * F(n) ** 2 == 4 * ((-1) ** n) for n in range(1, N + 1)),
        ),
        ("Unimodular", all(abs(cassini(n)) == 1 for n in range(1, N + 1))),
        (
            "Matrix power",
            all(
                M_power(n)[0][0] == F(n + 1) and M_power(n)[1][1] == F(n - 1)
                for n in range(1, N + 1)
            ),
        ),
        ("Binet exact", binet_exact_check(N)),
        ("Pisot exact", pisot_exact_check(N)),
        (
            "Binet float64 n<30",
            all(abs(binet_fib(n) - F(n)) < 1e-9 for n in range(1, 30)),
        ),
        (
            "Trace",
            all(M_power(n)[0][0] + M_power(n)[1][1] == L(n) for n in range(1, N + 1)),
        ),
    ]
    zok = True
    for n in range(1, 1000):
        encoded = zeckendorf(n)
        if sum(f for _, f in encoded) != n:
            zok = False
            break
        idxs = [i for i, _ in encoded]
        if any(abs(idxs[k + 1] - idxs[k]) < 2 for k in range(len(idxs) - 1)):
            zok = False
            break
    checks.append(("Zeckendorf", zok))
    return checks


def _geometry():
    """Load the miner's exact frame without importing the mining package."""
    path = Path(__file__).resolve().parents[1] / "chronus/mla1517/mining/geometry.py"
    name = "pythia_m32_geometry"
    module = sys.modules.get(name)
    if module is None:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return module


def _bareiss_det(matrix: list[list[int]]) -> int:
    size = len(matrix)
    work = [row[:] for row in matrix]
    sign = 1
    previous = 1
    for k in range(size - 1):
        if work[k][k] == 0:
            for swap in range(k + 1, size):
                if work[swap][k] != 0:
                    work[k], work[swap] = work[swap], work[k]
                    sign = -sign
                    break
            else:
                return 0
        for i in range(k + 1, size):
            for j in range(k + 1, size):
                work[i][j] = (work[i][j] * work[k][k] - work[i][k] * work[k][j]) // previous
        previous = work[k][k]
    return sign * work[-1][-1]


def _horner(coeffs: tuple[int, ...], value: int) -> int:
    total = 0
    for coeff in coeffs:
        total = total * value + coeff
    return total


def _claimed_charpoly(value: int) -> int:
    """Evaluate the factored characteristic polynomial at an integer."""
    quadratic_golden = value * value - 26 * value + 164
    quadratic_other = value * value - 23 * value + 128
    quintic = _horner(GAP_QUINTIC, value)
    return (
        value
        * (value - 15)
        * (value - 14) ** 6
        * (value - 11) ** 3
        * quadratic_golden**2
        * quadratic_other
        * quintic**3
    )


def _sturm_variations(value: int) -> int:
    """Sign variations of a positive-primitive Sturm chain of the quintic."""
    chain = (
        GAP_QUINTIC,
        (5, -236, 4080, -30432, 81792),
        (81, -3120, 39912, -169532),
        (1218, -31089, 198124),
        (87189, -1134188),
        (1,),
    )
    signs = []
    for coeffs in chain:
        ev = _horner(coeffs, value)
        if ev > 0:
            signs.append(1)
        elif ev < 0:
            signs.append(-1)
    return sum(left != right for left, right in zip(signs, signs[1:]))


def canonical_laplacian() -> tuple[list[list[int]], int]:
    """Integer Laplacian of cosine > cos(2π/5) on the canonical 32-frame.

    Returns (L, edge_count). Comparison is exact in Q(√5).
    """
    geom = _geometry()
    frame = geom.truncated_icosahedron_frame()
    q5 = geom._Q5
    norm_a = geom._PHI + q5(2)
    norm_b = q5(3)
    cut = q5(Fraction(-1, 4), Fraction(1, 4))  # (√5 - 1) / 4
    norms = [geom._dot(point, point) for point in frame]
    if any(norm != norm_a and norm != norm_b for norm in norms):
        raise RuntimeError("frame left the icosahedral and dodecahedral orbits")
    cross = norm_a * norm_b
    size = len(frame)
    laplacian = [[0] * size for _ in range(size)]
    edges = 0
    for i in range(size):
        for j in range(i + 1, size):
            inner = geom._dot(frame[i], frame[j])
            if norms[i] == norms[j]:
                above = ((inner / norms[i]) - cut)._cmp_int(0) > 0
            elif inner._cmp_int(0) <= 0:
                above = False
            else:
                above = ((inner * inner) - (cut * cut) * cross)._cmp_int(0) > 0
            if above:
                laplacian[i][j] = laplacian[j][i] = -1
                laplacian[i][i] += 1
                laplacian[j][j] += 1
                edges += 1
    return laplacian, edges


def characteristic_polynomial_matches() -> bool:
    """det(tI - L) equals the factored polynomial at 33 points, hence identically."""
    laplacian, _edges = canonical_laplacian()
    size = len(laplacian)
    for value in range(size + 1):
        shifted = [
            [(value if i == j else 0) - laplacian[i][j] for j in range(size)] for i in range(size)
        ]
        if _bareiss_det(shifted) != _claimed_charpoly(value):
            return False
    return True


def gap_root_in_open_unit_interval() -> tuple[Fraction, Fraction]:
    """Isolate the unique root of q in (5, 6) by exact bisection."""
    if _sturm_variations(0) - _sturm_variations(6) != 1:
        raise RuntimeError("the quintic does not have exactly one root in (0, 6)")
    if _horner(GAP_QUINTIC, 5) >= 0 or _horner(GAP_QUINTIC, 6) <= 0:
        raise RuntimeError("the gap root is not inside (5, 6)")
    lo, hi = Fraction(5), Fraction(6)
    for _ in range(40):
        mid = (lo + hi) / 2
        den = mid.denominator
        num = mid.numerator
        # Numerator of den^5 q(num/den). Sign matches q.
        scaled = GAP_QUINTIC[0]
        den_pow = 1
        for coeff in GAP_QUINTIC[1:]:
            den_pow *= den
            scaled = scaled * num + coeff * den_pow
        if scaled < 0:
            lo = mid
        else:
            hi = mid
    return lo, hi


def quintic_irreducible_mod_5() -> bool:
    """No root and no quadratic factor of q modulo 5, so q is irreducible over Q."""
    coeffs = [c % 5 for c in GAP_QUINTIC]

    def ev(a: int) -> int:
        total = 0
        for coeff in coeffs:
            total = (total * a + coeff) % 5
        return total

    if any(ev(a) == 0 for a in range(5)):
        return False
    # monic quadratic divisors x^2 + b x + c
    for b in range(5):
        for c in range(5):
            # polynomial division of q by x^2 + b x + c
            out = coeffs[:]
            for i in range(4):
                lead = out[i]
                out[i + 1] = (out[i + 1] - lead * b) % 5
                out[i + 2] = (out[i + 2] - lead * c) % 5
            if out[4] == 0 and out[5] == 0:
                return False
    return True


def run(algebra_n: int = 200) -> dict:
    """Exact finite spectrum. The continuum problem stays open."""
    checks = verify_algebra(algebra_n)
    if not all(ok for _, ok in checks):
        failed = [name for name, ok in checks if not ok]
        raise RuntimeError(f"golden-ratio certificates failed: {failed}")
    laplacian, edges = canonical_laplacian()
    if edges != 192:
        raise RuntimeError(f"canonical cut produced {edges} edges, not 192")
    degrees = [laplacian[i][i] for i in range(32)]
    if sum(degrees) != 2 * edges:
        raise RuntimeError("Laplacian degrees do not match the edge count")
    if not characteristic_polynomial_matches():
        raise RuntimeError("characteristic polynomial does not match the factorization")
    if not quintic_irreducible_mod_5():
        raise RuntimeError("gap quintic factored modulo 5")
    lower, upper = gap_root_in_open_unit_interval()
    # 13 - sqrt(5) > 6 because 7^2 > 5. That quadratic root is the next golden eigenvalue.
    golden_root_above_6 = (7 * 7) > 5
    return {
        "phi": PHI,
        "algebra": {name: ok for name, ok in checks},
        "sites": 32,
        "geometry": "truncated_icosahedron_32f",
        "mining_truncated_icosahedron": True,
        "attachment_dodecahedron": "two coordinate slots swapped; rejected",
        "binary_icosahedral_2i": False,
        "cut": "cosine > cos(2*pi/5)",
        "edges": edges,
        "degree_mean": sum(degrees) / len(degrees),
        "connected": True,
        "kernel_multiplicity": 1,
        "gap_polynomial": GAP_QUINTIC,
        "gap_degree": 5,
        "gap_in_golden_field": False,
        "gap_lower": lower,
        "gap_upper": upper,
        "golden_eigenvalues": "13 ± sqrt(5)",
        "golden_partner_above_gap": golden_root_above_6,
        "cassini_certifies_gap": False,
        "index_potential_is_geometric": False,
        "evidence_class": EVIDENCE_CLASS,
        "proof_claim": PROOF_CLAIM,
        "continuum_claim": CONTINUUM_CLAIM,
        "physical_qcd_claim": PHYSICAL_QCD_CLAIM,
        "share_acceptance": False,
        "scope": SCOPE,
        "rungs": (
            "golden-family identities",
            "canonical 32-face frame",
            "exact cosine cut",
            "characteristic polynomial",
            "degree-5 gap, not in Q(sqrt(5))",
            "continuum Yang-Mills: open",
        ),
    }


_CACHE: dict | None = None


def cached_report() -> dict:
    global _CACHE
    if _CACHE is None:
        _CACHE = run()
    return _CACHE
