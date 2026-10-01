# l_hras/fold/zeckendorf.py

import hashlib
from dataclasses import dataclass
from l_hras.experimental.blueprint.fold.vector11d import Vector11D, DIM, LUCAS_TABLE
from l_hras.experimental.blueprint.substrate.phi_rotation import PHI

L15 = 1364  # Lucas number at index 15

def zeckendorf_encode(n: int) -> int:
    """Encode an integer as a non-adjacent Fibonacci mask."""
    if n == 0:
        return 0
    # Fibonacci numbers
    fibs = [1, 2]
    while fibs[-1] < n:
        fibs.append(fibs[-1] + fibs[-2])
    mask = 0
    for i in range(len(fibs) - 1, -1, -1):
        if fibs[i] <= n:
            mask |= (1 << i)
            n -= fibs[i]
    return mask

def zeckendorf_decode(mask: int) -> int:
    """Decode a non-adjacent Fibonacci mask."""
    fibs = [1, 2]
    i = 0
    while (1 << i) <= mask:
        if i >= len(fibs) - 1:
            fibs.append(fibs[-1] + fibs[-2])
        i += 1
    n = 0
    for i in range(len(fibs)):
        if mask & (1 << i):
            n += fibs[i]
    return n

# Verify: roundtrip
for n in range(1000):
    assert zeckendorf_decode(zeckendorf_encode(n)) == n
