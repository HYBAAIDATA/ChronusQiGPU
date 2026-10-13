"""
Honsberger's Identity — context composition rule.

Honsberger's Identity:
    F_{n-1} * F_k + F_n * F_{k+1} = F_{n+k}

This allows merging two split context blocks (at indices n and k) into a
single composed block at index n+k, with exact integer fidelity and zero
overlap.
"""

from ..sequences import fibonacci


def honsberger_identity(n: int, k: int) -> bool:
    """Verify Honsberger's identity for indices n, k.

    F_{n-1} * F_k + F_n * F_{k+1} == F_{n+k}

    Uses exact Python integers.
    """
    if n < 1:
        # F_{n-1} requires n >= 1 for standard Fibonacci
        # For n=0, F_{-1}=1 via the extension F_{-1}=1
        from .docagne import fib_signed
        F_nm1 = fib_signed(n - 1)
    else:
        F_nm1 = fibonacci(n - 1)

    F_n = fibonacci(n)
    F_k = fibonacci(k)
    F_k1 = fibonacci(k + 1)
    F_nk = fibonacci(n + k)

    lhs = F_nm1 * F_k + F_n * F_k1

    return lhs == F_nk


def honsberger_compose(n: int, k: int) -> tuple[int, int, int]:
    """Compose two context blocks at indices n and k.

    Returns (n+k, F_{n+k}, F_{n+k+1}) derived from Honsberger's identity:
        F_{n+k} = F_{n-1} * F_k + F_n * F_{k+1}

    Also computes F_{n+k+1} via:
        F_{n+k+1} = F_n * F_k + F_{n+1} * F_{k+1}
    (which is Honsberger with n+1, k)
    """
    if n < 1:
        from .docagne import fib_signed
        F_nm1 = fib_signed(n - 1)
    else:
        F_nm1 = fibonacci(n - 1)

    F_n = fibonacci(n)
    F_n1 = fibonacci(n + 1)
    F_k = fibonacci(k)
    F_k1 = fibonacci(k + 1)

    F_nk = F_nm1 * F_k + F_n * F_k1
    F_nk1 = F_n * F_k + F_n1 * F_k1

    return (n + k, F_nk, F_nk1)
