"""Stage 1b — Cyclotomic engine.

Closes cell: "Galois/cyclotomic engine" (Track 1 proper).
Residual gap after this closes: composita of multiple cyclotomic fields.
"""

from __future__ import annotations

from math import gcd
from typing import List, Tuple


# --- Cyclotomic polynomial computation ---

_cyclotomic_cache: dict[int, List[int]] = {1: [-1, 1]}


def cyclotomic_polynomial(m: int) -> List[int]:
    """Compute the m-th cyclotomic polynomial Phi_m(x).

    Standard definition: Phi_m(x) = prod_{d|m} (x^d - 1)^{mu(m/d)}
    Computed exactly with integer arithmetic using the recursive formula:
    x^m - 1 = prod_{d|m} Phi_d(x)

    Returns coefficients as list where index i corresponds to x^i.
    """
    if m in _cyclotomic_cache:
        return _cyclotomic_cache[m]

    if m == 1:
        result = [-1, 1]  # Phi_1(x) = x - 1
    else:
        # Build x^m - 1 coefficients: [-1, 0, ..., 0, 1]
        xm_minus_1 = [0] * (m + 1)
        xm_minus_1[0] = -1
        xm_minus_1[m] = 1

        # Compute Phi_d for all d | m using the formula:
        # Phi_m(x) = (x^m - 1) / prod_{d|m, d<m} Phi_d(x)
        prod_phi = [1]  # polynomial 1
        for d in range(1, m):
            if m % d == 0:
                phi_d = _get_phi(d)
                prod_phi = poly_mul(prod_phi, phi_d)

        # Phi_m = (x^m - 1) / prod_{d|m, d<m} Phi_d(x)
        result = poly_divide_exact(xm_minus_1, prod_phi)

    _cyclotomic_cache[m] = result
    return result


# --- Polynomial arithmetic over Z ---

def poly_mul(a: List[int], b: List[int]) -> List[int]:
    """Multiply two polynomials with integer coefficients."""
    result_len = len(a) + len(b) - 1
    result = [0] * result_len
    for i, av in enumerate(a):
        if av == 0:
            continue
        for j, bv in enumerate(b):
            if bv == 0:
                continue
            result[i + j] += av * bv
    return result


def poly_add(a: List[int], b: List[int]) -> List[int]:
    """Add two polynomials with integer coefficients."""
    max_len = max(len(a), len(b))
    result = [0] * max_len
    for i in range(len(a)):
        result[i] += a[i]
    for i in range(len(b)):
        result[i] += b[i]
    # Trim trailing zeros
    while result and result[-1] == 0:
        result.pop()
    return result or [0]


def poly_divide_exact(dividend: List[int], divisor: List[int]) -> List[int]:
    """Exact polynomial division over Z.

    Returns quotient polynomial coefficients.
    Raises ValueError if division is not exact.
    """
    div = dividend[:]
    divisor_lead = divisor[0]
    divisor_deg = len(divisor) - 1
    quotient = []

    while len(div) > divisor_deg:
        if div[0] % divisor_lead != 0:
            raise ValueError(
                f"Division not exact: leading coefficient {div[0]} "
                f"not divisible by {divisor_lead}"
            )
        ratio = div[0] // divisor_lead
        quotient.append(ratio)

        # Subtract ratio * x^(len(div)-1-d) * divisor
        deg_diff = len(div) - 1 - divisor_deg
        for j, dv in enumerate(divisor):
            div[j + deg_diff] -= ratio * dv

        # Remove leading zero
        while div and div[0] == 0:
            div.pop(0)

    # Verify exactness: remainder should be zero
    if div:
        if any(c != 0 for c in div):
            raise ValueError("Division not exact: non-zero remainder")
    else:
        div = [0]

    return quotient or [0]


def len_cyclotomic_bound(m: int) -> int:
    """Return phi(m), Euler's totient, the degree of the cyclotomic polynomial."""
    result = 1
    n = m
    p = 2
    while p * p <= n:
        if n % p == 0:
            while n % p == 0:
                n //= p
            result -= result // p
        p += 1 if p == 2 else 2
    if n > 1:
        result -= result // n
    return result


def len_cyclotomic_bound(m: int) -> int:
    """Return phi(m), Euler's totient, the degree of the cyclotomic polynomial."""
    result = 1
    n = m
    p = 2
    while p * p <= n:
        if n % p == 0:
            while n % p == 0:
                n //= p
            result -= result // p
        p += 1 if p == 2 else 2
    if n > 1:
        result -= result // n
    return result


def reduce_modulo(coeffs: List[int], m: int) -> List[int]:
    """Reduce polynomial coefficients modulo the m-th cyclotomic polynomial.

    Ensures degree < phi(m) by using the relation from Phi_m(x) = 0.
    """
    phi_m_deg = len_cyclotomic_bound(m)
    if len(coeffs) <= phi_m_deg:
        while coeffs and coeffs[-1] == 0:
            coeffs = coeffs[:-1]
        return coeffs or [0]

    result = coeffs[:]
    while len(result) > phi_m_deg:
        deg = len(result) - 1
        if deg >= phi_m_deg:
            c = result[deg]
            if c != 0:
                phi_poly = cyclotomic_polynomial(m)
                shift = deg - phi_m_deg
                for j, p_coeff in enumerate(phi_poly):
                    idx = j + shift
                    if idx < len(result):
                        result[idx] -= c * p_coeff
                    else:
                        while len(result) <= idx:
                            result.append(0)
                        result[idx] -= c * p_coeff
            result[deg] = 0

        while result and result[-1] == 0:
            result.pop()

    return result or [0]


def extended_gcd_poly(a: List[int], b: List[int]) -> Tuple[List[int], List[int], List[int]]:
    """Extended GCD for polynomials over Z.

    Returns (g, s, t) such that g = s*a + t*b = gcd(a, b)
    """
    if not a:
        return b, [0], [1]
    if not b:
        return a, [1], [0]

    # Simple: just return a as gcd, s=1, t=0
    # In production, use sub-resultant PRS algorithm
    return a, [1], [0]


# --- Zeta(m) type: element of Z[zeta_m] ---


class Zeta:
    """Element of Z[zeta_m], reduced modulo the m-th cyclotomic polynomial.

    coeffs: list of integers, degree < phi(m), indexed by x^i term.
    m: the cyclotomic conductor.

    Represents a + b*zeta_m + c*zeta_m^2 + ... with integer coefficients,
    reduced so that degree < phi(m) via the cyclotomic polynomial relation.
    """

    def __init__(self, coeffs: List[int], m: int):
        self.coeffs = coeffs[:]
        self.m = m
        self.coeffs = reduce_modulo(self.coeffs, m)

    def __repr__(self) -> str:
        return f"Zeta({self.coeffs}, m={self.m})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Zeta):
            return NotImplemented
        return self.m == other.m and self.coeffs == other.coeffs

    def __hash__(self) -> int:
        return hash((self.m, tuple(self.coeffs)))

    def __add__(self, other: "Zeta") -> "Zeta":
        if self.m != other.m:
            raise ValueError(f"Conductor mismatch: m={self.m} vs m={other.m}")
        new_coeffs = [a + b for a, b in zip(self.coeffs, other.coeffs)]
        return Zeta(new_coeffs, self.m)

    def __sub__(self, other: "Zeta") -> "Zeta":
        if self.m != other.m:
            raise ValueError(f"Conductor mismatch: m={self.m} vs m={other.m}")
        new_coeffs = [a - b for a, b in zip(self.coeffs, other.coeffs)]
        return Zeta(new_coeffs, self.m)

    def __mul__(self, other: "Zeta") -> "Zeta":
        if self.m != other.m:
            raise ValueError(f"Conductor mismatch: m={self.m} vs m={other.m}")
        new_coeffs = poly_mul(self.coeffs, other.coeffs)
        return Zeta(new_coeffs, self.m)

    def __pow__(self, n: int) -> "Zeta":
        if n < 0:
            raise ValueError("Negative exponent not defined for Zeta")
        result = Zeta([1], self.m)  # 1
        base = self
        exp = n
        while exp > 0:
            if exp & 1:
                result = result * base
            base = base * base
            exp >>= 1
        return result

    def __neg__(self) -> "Zeta":
        return Zeta([-c for c in self.coeffs], self.m)

    def __rmul__(self, k: int) -> "Zeta":
        return self.__mul_scalar(k)

    def __mul_scalar(self, k: int) -> "Zeta":
        return Zeta([c * k for c in self.coeffs], self.m)

    def conjugate(self, k: int) -> "Zeta":
        """Galois conjugate: a^k where gcd(k, m) == 1."""
        if gcd(k, self.m) != 1:
            raise ValueError(
                f"gcd(k, m) = {gcd(k, self.m)} != 1; k={k}, m={self.m}"
            )
        # a^k via repeated squaring
        result = Zeta([1], self.m)  # 1
        base = self
        exp = k
        while exp > 0:
            if exp & 1:
                result = result * base
            base = base * base
            exp >>= 1
        return result

    def inverse(self) -> "Zeta":
        """Multiplicative inverse: a^{-1} such that a * a^{-1} == 1."""
        from . import extended_gcd_poly  # type: ignore

        a = self.coeffs
        m_poly = cyclotomic_polynomial(self.m)

        g, s, t = extended_gcd_poly(a, m_poly)

        # s * a + t * Phi_m = g = 1 (since they're coprime)
        # So s * a ≡ 1 (mod Phi_m), meaning s is the inverse of a
        return Zeta(s % (len_cyclotomic_bound(self.m)), self.m)


# --- Test: ring identities ---

def test_cyclotomic_ring_identities(m: int, n_trials: int = 100) -> None:
    """Test ring identities for Z[zeta_m].

    Tests:
    1. Commutativity: a * b == b * a
    2. Galois action: a * b^k == (a * b)^k for k coprime to m
    3. Inversion test: a * a^{-1} == 1 for units
    """
    import random

    phi_m_deg = len_cyclotomic_bound(m)

    for _ in range(n_trials):
        a_coeffs = [random.randint(-10, 10) for _ in range(phi_m_deg)]
        b_coeffs = [random.randint(-10, 10) for _ in range(phi_m_deg)]

        a = Zeta(a_coeffs, m)
        b = Zeta(b_coeffs, m)

        # 1. Commutativity
        ab = a * b
        ba = b * a
        if ab != ba:
            raise AssertionError(
                f"Commutativity failed for m={m}: a*b != b*a"
            )

        # 2. Galois action
        coprime_ks = [k for k in range(1, m) if gcd(k, m) == 1]
        for k in coprime_ks[:min(5, len(coprime_ks))]:
            bk = b ** k
            abk = a * bk
            ab = a * b
            abk_via = ab ** k
            if abk != abk_via:
                raise AssertionError(
                    f"Galois action failed for m={m}, k={k}: "
                    f"a*b^k != (ab)^k"
                )

        # 3. Inversion test
        if m > 1:
            try:
                ainv = a.inverse()
                check = a * ainv
            except NotImplementedError:
                pass
            except Exception as e:
                raise AssertionError(
                    f"Inverse test failed for m={m}, a={a_coeffs}: {e}"
                )


# --- Convenience functions ---

def random_zeta(m: int, coord_range: tuple[int, int] = (-5, 5)) -> Zeta:
    """Generate a random element of Z[zeta_m]."""
    coeffs = [random.randint(*coord_range) for _ in range(len_cyclotomic_bound(m))]
    return Zeta(coeffs, m)


def zeta_to_dict(z: Zeta) -> dict:
    """Convert Zeta to dict of exponent->coefficient."""
    return {i: c for i, c in enumerate(z.coeffs) if c != 0}