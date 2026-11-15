"""Exact Fibonacci, Lucas and Zeckendorf arithmetic (integers only).

Used by the AL HARAS kernel self-test and by the notes' "Pisot-Lucas" and
"Zeckendorf ALU" claims. What is implemented and checked:

* F_n and L_n by fast doubling (O(log n) multiplications on integers);
* phi^n + psi^n = L_n checked exactly in Z[phi] (phi^2 = phi + 1, psi = 1 - phi);
* Zeckendorf decomposition with an exact non-adjacency and sum check;
* storage sizes: the size of the index n versus the size of L_n itself.

The descriptor (n) grows like log n, and materialising L_n needs about
0.694 n bits; no constant-size representation of large values is claimed.
"""

from typing import Any, Dict, List, Tuple


def fib_pair(n: int) -> Tuple[int, int]:
    """(F_n, F_{n+1}) by fast doubling."""
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return 0, 1
    a, b = fib_pair(n >> 1)
    c = a * (2 * b - a)
    d = a * a + b * b
    return (d, c + d) if n & 1 else (c, d)


def fibonacci(n: int) -> int:
    return fib_pair(n)[0]


def lucas(n: int) -> int:
    f_n, f_n1 = fib_pair(n)
    return 2 * f_n1 - f_n  # L_n = F_{n-1} + F_{n+1} = 2 F_{n+1} - F_n


def _zphi_mul(x: Tuple[int, int], y: Tuple[int, int]) -> Tuple[int, int]:
    """(a + b phi)(c + d phi) with phi^2 = phi + 1."""
    a, b = x
    c, d = y
    return (a * c + b * d, a * d + b * c + b * d)


def _zphi_pow(base: Tuple[int, int], n: int) -> Tuple[int, int]:
    result = (1, 0)
    while n:
        if n & 1:
            result = _zphi_mul(result, base)
        base = _zphi_mul(base, base)
        n >>= 1
    return result


def binet_lucas_identity(n: int) -> bool:
    """phi^n + psi^n == L_n, evaluated exactly in Z[phi]."""
    phi_n = _zphi_pow((0, 1), n)
    psi_n = _zphi_pow((1, -1), n)
    total = (phi_n[0] + psi_n[0], phi_n[1] + psi_n[1])
    return total == (lucas(n), 0)


def zeckendorf(n: int) -> List[int]:
    """Indices i (F_i with F_2 = 1, F_3 = 2, ...) of the Zeckendorf representation."""
    if n < 0:
        raise ValueError("n must be non-negative")
    fibs = [1, 2]
    while fibs[-1] <= n:
        fibs.append(fibs[-1] + fibs[-2])
    indices: List[int] = []
    remaining = n
    for i in range(len(fibs) - 1, -1, -1):
        if fibs[i] <= remaining:
            indices.append(i + 2)
            remaining -= fibs[i]
    return indices


def verify_zeckendorf(n: int) -> Dict[str, Any]:
    idx = zeckendorf(n)
    total = sum(fibonacci(i) for i in idx)
    non_adjacent = all(idx[j] - idx[j + 1] >= 2 for j in range(len(idx) - 1))
    return {"n": n, "indices": idx, "sum_matches": total == n, "non_adjacent": non_adjacent}


def storage_profile(n: int) -> Dict[str, Any]:
    value = lucas(n)
    return {
        "n": n,
        "lucas_digits": len(str(value)),
        "index_bytes": max(1, (n.bit_length() + 7) // 8),
        "value_bytes": (value.bit_length() + 7) // 8,
        "binet_identity_exact": binet_lucas_identity(n),
    }
