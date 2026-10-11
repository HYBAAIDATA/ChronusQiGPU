"""Trace-substrate kernels: tr(M^n) = L_n verification and bounding.

Uses numpy for deterministic matrix power; the Lucas numbers come from the
exact integer substrate in lucas.core.
"""

from __future__ import annotations

import numpy as np

from .core import lucas


def trace_power(M: np.ndarray, n: int) -> float | complex:
    """Return tr(M^n) for a square numpy matrix."""
    if M.ndim != 2 or M.shape[0] != M.shape[1]:
        raise ValueError("M must be a square matrix")
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return M.shape[0]
    Mn = np.linalg.matrix_power(M, n)
    return np.trace(Mn)


def verify_lucas_trace(n: int) -> dict[str, object]:
    """Verify tr(Q^n) = L_n for the golden Q-matrix Q = [[1,1],[1,0]]."""
    Q = np.array([[1, 1], [1, 0]], dtype=object)
    actual = int(trace_power(Q, n))
    expected = lucas(n)
    return {
        "n": n,
        "Q_power_trace": actual,
        "L_n": expected,
        "valid": actual == expected,
    }


def verify(M: np.ndarray, n: int) -> dict[str, object]:
    """Verify tr(M^n) = L_n exactly for a given operator."""
    tr = trace_power(M, n)
    expected = lucas(n)
    return {
        "n": n,
        "trace_Mn": tr,
        "L_n": expected,
        "valid": tr == expected,
        "theorem_proven": False,
    }


def trace_kernel(M: np.ndarray, n: int) -> dict[str, object]:
    """Trace bound: the trace of M^n is compared to L_n.

    For genuine quantum operators the trace is an exact spectral sum; the
    Lucas number provides an algebraic ceiling for integer-class operators.
    """
    tr = trace_power(M, n)
    bound = lucas(n)
    return {
        "kernel": "trace_kernel",
        "n": n,
        "trace_Mn": tr,
        "lucas_bound": bound,
        "bound": bound,
        "is_lucas_bounded": abs(tr) <= bound,
        "theorem_proven": False,
    }
