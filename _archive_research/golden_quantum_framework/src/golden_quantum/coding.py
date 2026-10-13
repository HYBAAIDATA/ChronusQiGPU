"""
Zeckendorf representation and Fibonacci coding.

Zeckendorf's theorem: every positive integer has a unique representation
as a sum of non-consecutive Fibonacci numbers (using F(2)=1, F(3)=2, ...).

Fibonacci coding: a prefix-free, self-delimiting code for positive integers
based on Zeckendorf representation, terminated by '11'.
"""

from .sequences import fibonacci


def zeckendorf(n: int) -> list[int]:
    """Zeckendorf representation of n as a list of Fibonacci indices.

    Uses F(2)=1, F(3)=2, F(4)=3, F(5)=5, ...
    Returns indices k such that sum(F(k)) = n, with no two consecutive.

    Examples:
        zeckendorf(0)  → []
        zeckendorf(1)  → [2]       # F(2)=1
        zeckendorf(4)  → [4, 2]    # F(4)+F(2) = 3+1 = 4
        zeckendorf(10) → [6, 3]    # F(6)+F(3) = 8+2 = 10
        zeckendorf(100) → [11, 6, 4]  # F(11)+F(6)+F(4) = 89+8+3 = 100
    """
    if n <= 0:
        return []
    # Find the largest k such that F(k) <= n
    k = 2
    while fibonacci(k + 1) <= n:
        k += 1
    indices = []
    remaining = n
    while remaining > 0:
        while k >= 2 and fibonacci(k) > remaining:
            k -= 1
        if k >= 2:
            indices.append(k)
            remaining -= fibonacci(k)
            k -= 2  # Skip next index (non-consecutive)
    return indices


def fib_encode(n: int) -> str:
    """Encode n as a Fibonacci codeword (prefix-free, self-delimiting).

    Standard Fibonacci coding for n ≥ 1:
    - Compute Zeckendorf representation
    - Build bit string with '1' at each Fibonacci index position (LSB = F(2))
    - Append '1' terminator → codeword ends with '11'

    The codeword ends with '11' because the highest Fibonacci index
    always has a '1' bit, followed by the terminator '1'.

    Example:
        fib_encode(1)  → '11'      # F(2)=1, terminator
        fib_encode(2)  → '011'     # F(3)=2, terminator
        fib_encode(4)  → '1011'    # F(4)+F(2)=3+1, terminator
        fib_encode(10) → '0010011' # F(6)+F(3)=8+2, terminator
    """
    if n < 1:
        raise ValueError("Fibonacci coding requires n >= 1")
    indices = zeckendorf(n)
    if not indices:
        return "11"
    max_idx = max(indices)
    bits = ['0'] * (max_idx - 1)
    for idx in indices:
        bits[idx - 2] = '1'
    bits.append('1')  # terminator
    return ''.join(bits)


def fib_decode(code: str) -> int:
    """Decode a Fibonacci codeword to its integer value.

    The codeword consists of data bits (F(2), F(3), ...) followed by
    a '1' terminator. The codeword must end with '11' (since the
    highest data bit is always 1) and the data portion must not
    contain consecutive '1's.

    Raises ValueError for invalid codes.
    """
    if not code or len(code) < 2:
        raise ValueError(f"Invalid Fibonacci code (too short): {code!r}")
    if code[-1] != '1':
        raise ValueError(f"Invalid Fibonacci code (must end with '1'): {code!r}")
    if code[-2] != '1':
        raise ValueError(f"Invalid Fibonacci code (must end with '11'): {code!r}")

    # Strip the terminator (last '1')
    data = code[:-1]

    # Validate: no consecutive 1s in data portion
    for i in range(len(data) - 1):
        if data[i] == '1' and data[i + 1] == '1':
            raise ValueError(
                f"Invalid Fibonacci code (consecutive 1s in data): {code!r}"
            )

    # Decode: bit at position i (0-indexed) corresponds to F(i+2)
    total = 0
    for i, bit in enumerate(data):
        if bit == '1':
            total += fibonacci(i + 2)
    if total == 0:
        raise ValueError(f"Invalid Fibonacci code (encodes 0): {code!r}")
    return total


def is_valid_fib_code(code: str) -> bool:
    """Check whether a string is a valid Fibonacci codeword."""
    try:
        fib_decode(code)
        return True
    except (ValueError, IndexError):
        return False
