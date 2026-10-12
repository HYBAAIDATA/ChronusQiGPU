"""Exact n-step recurrence and companion powers with matched initial state.

LUCAS WIRING: integer recurrence family; roots are algebraic certificates,
not numerical bisection estimates or implicitly rounded real numbers.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


def _inputs(n: int, k: int = 0) -> None:
    if type(n) is not int or type(k) is not int:
        raise TypeError("integer order and index required")
    if n < 2 or k < 0:
        raise ValueError("order >=2 and index >=0 required")


def n_step_fib(n: int, k: int) -> int:
    _inputs(n, k)
    if k < n - 1:
        return 0
    window = deque([0] * (n - 1) + [1])
    total = 1
    for _ in range(n, k + 1):
        value = total
        total += value - window.popleft()
        window.append(value)
    return window[-1]


def companion_matrix(n: int) -> tuple[tuple[int, ...], ...]:
    _inputs(n)
    return (tuple([1] * n),) + tuple(
        tuple(int(j == i - 1) for j in range(n)) for i in range(1, n)
    )


def _multiply(a, b):
    n = len(a)
    return tuple(
        tuple(sum(a[i][r] * b[r][j] for r in range(n)) for j in range(n))
        for i in range(n)
    )


def n_step_fast_doubling(n: int, k: int) -> int:
    """Binary companion powering, not Fibonacci-specific fast doubling."""
    _inputs(n, k)
    if k < n - 1:
        return 0
    exponent = k - n + 1
    result = tuple(tuple(int(i == j) for j in range(n)) for i in range(n))
    base = companion_matrix(n)
    while exponent:
        if exponent & 1:
            result = _multiply(result, base)
        exponent >>= 1
        if exponent:
            base = _multiply(base, base)
    return result[0][0]


@dataclass(frozen=True)
class ExactPisotRoot:
    """The unique positive root in (1,2); an exact descriptor, not a scalar API.

    Descartes gives one positive root; P(1)=1-n<0 and P(2)=1>0.
    Arithmetic, ordering and general algebraic field extension are not supplied.
    """

    order: int

    def __post_init__(self) -> None:
        _inputs(self.order)

    @property
    def polynomial(self) -> tuple[int, ...]:
        return (1,) + (-1,) * self.order

    @property
    def isolating_interval(self) -> tuple[int, int]:
        return (1, 2)


def n_step_pisot_root(n: int) -> ExactPisotRoot:
    return ExactPisotRoot(n)


def tribonacci(k: int) -> int:
    return n_step_fib(3, k)


def tetranacci(k: int) -> int:
    return n_step_fib(4, k)
