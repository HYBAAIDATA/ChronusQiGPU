"""
Fibonacci and Lucas Polynomials — continuous-space embedding.

Fibonacci polynomials:
    F_0(x) = 0,  F_1(x) = 1,  F_n(x) = x*F_{n-1}(x) + F_{n-2}(x)

Lucas polynomials:
    L_0(x) = 2,  L_1(x) = x,  L_n(x) = x*L_{n-1}(x) + L_{n-2}(x)

Key properties:
    - F_n(1) = F_n  (standard Fibonacci)
    - L_n(1) = L_n  (standard Lucas)
    - L_n(x) = F_{n-1}(x) + F_{n+1}(x)

Represented as coefficient lists [a_0, a_1, ..., a_d] where the polynomial is
sum(a_i * x^i). This gives exact arithmetic with no float drift.
"""

from typing import List


def _poly_add(a: list[int], b: list[int]) -> list[int]:
    """Add two polynomials represented as coefficient lists."""
    n = max(len(a), len(b))
    result = [0] * n
    for i, c in enumerate(a):
        result[i] += c
    for i, c in enumerate(b):
        result[i] += c
    return result


def _poly_scale_shift(a: list[int], power: int) -> list[int]:
    """Multiply polynomial by x^power (shifts coefficients)."""
    return [0] * power + a


def fib_poly_coeffs(n: int) -> list[int]:
    """Compute Fibonacci polynomial F_n(x) as coefficient list.

    F_0(x) = 0,  F_1(x) = 1,  F_n(x) = x*F_{n-1}(x) + F_{n-2}(x)

    Iterative O(n) — no recursion.
    """
    if n == 0:
        return [0]
    if n == 1:
        return [1]
    # F_{n-2} and F_{n-1}
    fm2 = [0]   # F_0
    fm1 = [1]   # F_1
    for _ in range(2, n + 1):
        # F_n = x * F_{n-1} + F_{n-2}
        fn = _poly_add(_poly_scale_shift(fm1, 1), fm2)
        fm2 = fm1
        fm1 = fn
    return fm1


def lucas_poly_coeffs(n: int) -> list[int]:
    """Compute Lucas polynomial L_n(x) as coefficient list.

    L_0(x) = 2,  L_1(x) = x,  L_n(x) = x*L_{n-1}(x) + L_{n-2}(x)

    Iterative O(n) — no recursion.
    """
    if n == 0:
        return [2]
    if n == 1:
        return [0, 1]
    lm2 = [2]      # L_0
    lm1 = [0, 1]   # L_1
    for _ in range(2, n + 1):
        ln = _poly_add(_poly_scale_shift(lm1, 1), lm2)
        lm2 = lm1
        lm1 = ln
    return lm1


def fib_poly_eval(n: int, x: int | float) -> int | float:
    """Evaluate F_n(x) using Horner's method on coefficient list."""
    coeffs = fib_poly_coeffs(n)
    result = 0
    for c in reversed(coeffs):
        result = result * x + c
    return result


def lucas_poly_eval(n: int, x: int | float) -> int | float:
    """Evaluate L_n(x) using Horner's method on coefficient list."""
    coeffs = lucas_poly_coeffs(n)
    result = 0
    for c in reversed(coeffs):
        result = result * x + c
    return result


def fib_poly_specialization(n: int) -> bool:
    """Verify F_n(1) == F_n (standard Fibonacci number)."""
    from ..sequences import fibonacci
    return fib_poly_eval(n, 1) == fibonacci(n)


def lucas_poly_specialization(n: int) -> bool:
    """Verify L_n(1) == L_n (standard Lucas number)."""
    from ..sequences import lucas
    return lucas_poly_eval(n, 1) == lucas(n)


def lucas_fib_relation(n: int) -> bool:
    """Verify L_n(x) == F_{n-1}(x) + F_{n+1}(x).

    This is the polynomial generalization of the identity L_n = F_{n-1} + F_{n+1}.
    """
    if n < 1:
        return True  # Trivially true for n=0 (no F_{-1} polynomial)
    l_coeffs = lucas_poly_coeffs(n)
    f_prev = fib_poly_coeffs(n - 1)
    f_next = fib_poly_coeffs(n + 1)
    combined = _poly_add(f_prev, f_next)
    return l_coeffs == combined
