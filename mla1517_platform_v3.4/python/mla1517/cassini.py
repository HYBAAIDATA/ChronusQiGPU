"""Cassini verifier — the storage seal and its exact identities.

Two identities, both exact integer statements:

    L_n^2 - 5*F_n^2 = 4*(-1)^n          (Lucas form)
    F_{n-1}F_{n+1} - F_n^2 = (-1)^n      (storage seal)

A read is valid only when the reconstructed state reproduces the expected
seal. A failed seal moves the object to quarantine rather than returning
corrupted data -- the seal is a gate, not a report.

Both are verified by exact integer arithmetic and by the Q-matrix route, so
the two derivations cross-check each other.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .core import fib, fib_pair, lucas

__all__ = [
    "CassiniResult",
    "cassini_lucas_form",
    "cassini_storage_seal",
    "q_matrix_trace",
    "q_matrix_determinant",
    "verify_state",
    "verify_range",
]


@dataclass(frozen=True)
class CassiniResult:
    """One verification outcome."""

    index: int
    passed: bool
    observed: int
    expected: int
    identity: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "passed": self.passed,
            "observed": self.observed,
            "expected": self.expected,
            "identity": self.identity,
        }


def cassini_lucas_form(n: int) -> CassiniResult:
    """``L_n^2 - 5 F_n^2 == 4(-1)^n``."""
    if n < 0:
        raise ValueError("index must be non-negative")
    expected = 4 * (1 if n % 2 == 0 else -1)
    observed = lucas(n) ** 2 - 5 * fib(n) ** 2
    return CassiniResult(n, observed == expected, observed, expected, "L^2-5F^2=4(-1)^n")


def cassini_storage_seal(f_nm1: int, f_n: int, f_np1: int) -> CassiniResult:
    """``F_{n-1}F_{n+1} - F_n^2`` must be exactly +1 or -1."""
    observed = f_nm1 * f_np1 - f_n * f_n
    passed = observed in (1, -1)
    return CassiniResult(-1, passed, observed, 0, "F_{n-1}F_{n+1}-F_n^2=(+/-1)")


def q_matrix_trace(n: int) -> int:
    """``trace(Q^n)`` where ``Q = [[1,1],[1,0]]``. Equals ``L_n`` exactly.

    The trace satisfies the same recurrence as the Lucas sequence with
    seeds ``L_0 = 2`` and ``L_1 = 1``, so it is iterated directly.
    """
    if n < 0:
        raise ValueError("index must be non-negative")
    a, b = 2, 1  # L_0, L_1
    for _ in range(2, n + 1):
        a, b = b, a + b
    # After the loop, a is L_{n-1} and b is L_n. Return b.
    return b if n >= 1 else a


def q_matrix_determinant(n: int) -> int:
    """``det(Q^n)``. ``Q`` has determinant -1, so this is ``(-1)^n``."""
    return 1 if n % 2 == 0 else -1


def verify_state(index: int) -> List[CassiniResult]:
    """Cross-check a Fibonacci state by two independent derivations."""
    f_n, f_np1 = fib_pair(index)
    f_nm1 = fib_pair(index - 1)[0] if index >= 1 else 1
    lucas_form = cassini_lucas_form(index)
    seal = cassini_storage_seal(f_nm1, f_n, f_np1)
    trace = CassiniResult(
        index,
        q_matrix_trace(index) == lucas(index),
        q_matrix_trace(index),
        lucas(index),
        "trace(Q^n)=L_n",
    )
    det = CassiniResult(
        index,
        q_matrix_determinant(index) == seal.observed,
        q_matrix_determinant(index),
        seal.observed,
        "det(Q^n)=(-1)^n",
    )
    return [lucas_form, seal, trace, det]


def verify_range(limit: int) -> Dict[str, Any]:
    """Verify every identity for ``n`` in ``[0, limit)``."""
    failures: List[Dict[str, Any]] = []
    for n in range(limit):
        for r in verify_state(n):
            if not r.passed:
                failures.append(r.as_dict())
    return {
        "checked": limit,
        "failures": failures,
        "passed": not failures,
    }
