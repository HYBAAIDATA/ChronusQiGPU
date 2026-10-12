"""Exact Fibonacci modular clocks; candidate periods are reduced to minimality.

LUCAS WIRING: discrete clock substrate, no runtime or mining side effects.
Trial division is exact, not a claim of efficient arbitrary-size factorization.
"""

from __future__ import annotations

from math import lcm


def _integer(value: int, name: str, minimum: int) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")


def _pair(n: int, m: int) -> tuple[int, int]:
    a, b = 0, 1 % m
    for bit in bin(n)[2:]:
        c = a * (2 * b - a) % m
        d = (a * a + b * b) % m
        a, b = (c, d) if bit == "0" else (d, (c + d) % m)
    return a, b


def fib_mod(n: int, m: int) -> int:
    """F_n modulo positive m, using logarithmically many doubling stages."""
    _integer(n, "n", 0)
    _integer(m, "m", 1)
    return _pair(n, m)[0]


def pisano_is_period(m: int, period: int) -> bool:
    """Check a positive return time; multiples of the minimal period also pass."""
    _integer(m, "m", 1)
    _integer(period, "period", 1)
    return _pair(period, m) == (0, 1 % m)


def _factors(n: int) -> dict[int, int]:
    factors = {}
    p = 2
    while p * p <= n:
        while n % p == 0:
            factors[p] = factors.get(p, 0) + 1
            n //= p
        p = 3 if p == 2 else p + 2
    if n > 1:
        factors[n] = factors.get(n, 0) + 1
    return factors


def _reduce(m: int, candidate: int) -> int:
    if not pisano_is_period(m, candidate):
        raise ArithmeticError("period bound failed")
    for divisor in _factors(candidate):
        while candidate % divisor == 0 and pisano_is_period(m, candidate // divisor):
            candidate //= divisor
    return candidate


def pisano_period(m: int) -> int:
    """Minimal period, using verified prime bounds and prime-power lifting."""
    _integer(m, "m", 1)
    result = 1
    for p, exponent in _factors(m).items():
        if p == 2:
            bound = 3
        elif p == 5:
            bound = 20
        else:
            bound = p - 1 if pow(5, (p - 1) // 2, p) == 1 else 2 * (p + 1)
        prime_period = _reduce(p, bound)
        modulus = p**exponent
        period = _reduce(modulus, prime_period * p ** (exponent - 1))
        result = lcm(result, period)
    return result


def pisano_table(max_m: int) -> dict[int, int]:
    _integer(max_m, "max_m", 0)
    return {m: pisano_period(m) for m in range(1, max_m + 1)}
