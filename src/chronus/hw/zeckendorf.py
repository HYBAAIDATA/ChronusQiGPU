"""
Chronus Zeckendorf Arithmetic Reference Engine.

Zeckendorf's Theorem:
Every positive integer N can be uniquely represented as the sum of one or more
distinct, non-consecutive Fibonacci numbers F_k (k >= 2):
F = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, ...]

Invariant:
No two adjacent Fibonacci numbers are used in the representation (c_k * c_{k+1} == 0).
"""

from typing import List

# Generate Fibonacci numbers F_2 .. F_48 (covers up to 64-bit integers cleanly)
FIBONACCI_TABLE: List[int] = [1, 2]
while FIBONACCI_TABLE[-1] + FIBONACCI_TABLE[-2] < (1 << 64):
    FIBONACCI_TABLE.append(FIBONACCI_TABLE[-1] + FIBONACCI_TABLE[-2])


def fold_to_zeckendorf(n: int) -> List[int]:
    """
    Folds an integer n >= 0 into its unique Zeckendorf representation (bit pattern).
    Returns a list of 0s and 1s corresponding to FIBONACCI_TABLE indices.
    """
    if n < 0:
        raise ValueError(f"Zeckendorf representation requires non-negative integer, got {n}")
    if n == 0:
        return [0]

    # Find highest Fibonacci number <= n
    indices = []
    temp = n
    for idx in range(len(FIBONACCI_TABLE) - 1, -1, -1):
        if FIBONACCI_TABLE[idx] <= temp:
            indices.append(idx)
            temp -= FIBONACCI_TABLE[idx]

    max_idx = indices[0] if indices else 0
    bits = [0] * (max_idx + 1)
    for idx in indices:
        bits[idx] = 1

    # Verify non-adjacent invariant
    for i in range(len(bits) - 1):
        if bits[i] == 1 and bits[i + 1] == 1:
            raise ValueError(f"Zeckendorf invariant violated for {n}: consecutive 1s found.")

    return bits


def unfold(rep: List[int]) -> int:
    """
    Unfolds a Zeckendorf bit pattern back into its exact 64-bit integer sum.
    """
    total = 0
    for idx, bit in enumerate(rep):
        if bit == 1:
            if idx >= len(FIBONACCI_TABLE):
                raise ValueError(f"Fibonacci index {idx} out of bounds.")
            total += FIBONACCI_TABLE[idx]
        elif bit != 0:
            raise ValueError(f"Invalid Zeckendorf bit value {bit} at index {idx}.")
    return total


def add(a_rep: List[int], b_rep: List[int]) -> List[int]:
    """
    Adds two Zeckendorf representations and refolds the sum to maintain
    the non-adjacent Zeckendorf invariant.
    """
    val_a = unfold(a_rep)
    val_b = unfold(b_rep)
    return fold_to_zeckendorf(val_a + val_b)
