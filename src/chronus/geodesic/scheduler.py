"""CHRONUS Lucas-Pisano geodesic scheduler (exact integer arithmetic only).

Owner's design: for an active subspace of dimension D (2^D states) the visit
order at epoch e is

    pi        = Pisano period of Fibonacci mod 2^D  (3 for D=1, else 3*2^(D-1))
    phase     = e mod pi
    idx       = 3*phase + 1           (3 does not divide idx, so L_idx is odd)
    stride    = L_idx mod 2^D         (odd => unit mod 2^D)
    phase_off = F_idx mod 2^D
    order[t]  = gray((stride*t + phase_off) mod 2^D),  t = 0..2^D-1

An affine map t -> stride*t + c with odd stride is a bijection of Z/2^D and the
reflected Gray code is a bijection of [0, 2^D), so the order is a permutation:
no state is skipped or visited twice.

Hamming-step note (docstring correction): Gray coding gives unit Hamming
distance only between Gray codes of *consecutive integers*.  Consecutive
schedule positions here are affine images differing by ``stride``; for
stride != 1 their Gray codes generally differ in more than one bit.  The
measured distribution is reported by ``hamming_step_histogram``; consecutive
steps are single-bit flips only when stride == 1 (mod 2^D).

``import math`` is used only for the integer gcd check.
"""
from __future__ import annotations

import math
from typing import Dict, List

MAX_ACTIVE_DIM = 24


def exact_fibonacci_lucas(n: int) -> tuple[int, int]:
    """(F_n, L_n) by integer fast doubling, F_0=0, F_1=1, L_0=2."""
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise ValueError("n must be a non-negative integer")

    def fd(m: int) -> tuple[int, int]:  # (F_m, F_{m+1})
        if m == 0:
            return 0, 1
        f, g = fd(m >> 1)
        c = f * (2 * g - f)
        d = f * f + g * g
        return (d, c + d) if m & 1 else (c, d)

    f, g = fd(n)
    return f, 2 * g - f


def exact_fibonacci_lucas_mod(n: int, modulus: int) -> tuple[int, int]:
    """(F_n mod m, L_n mod m) by fast doubling reduced at every step.

    Same values as ``exact_fibonacci_lucas(n)`` reduced mod m; avoids building
    multi-million-bit integers when idx is large (idx can reach ~7.5e7 at D=24).
    """
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise ValueError("n must be a non-negative integer")
    if isinstance(modulus, bool) or not isinstance(modulus, int) or modulus < 1:
        raise ValueError("modulus must be a positive integer")
    f, g = 0, 1 % modulus
    for bit in bin(n)[2:]:
        c = (f * ((2 * g - f) % modulus)) % modulus
        d = (f * f + g * g) % modulus
        f, g = (d, (c + d) % modulus) if bit == "1" else (c, d)
    return f, (2 * g - f) % modulus


def pisano_period_pow2(dim: int) -> int:
    """Pisano period of Fibonacci mod 2^dim: 3 for dim=1, 3*2^(dim-1) otherwise."""
    if isinstance(dim, bool) or not isinstance(dim, int) or dim < 1:
        raise ValueError("dim must be a positive integer")
    return 3 if dim == 1 else 3 * (1 << (dim - 1))


def gray(x: int) -> int:
    return x ^ (x >> 1)


def schedule_parameters(active_dim: int, epoch_step: int = 1) -> Dict[str, int]:
    if isinstance(active_dim, bool) or not isinstance(active_dim, int) or not 1 <= active_dim <= MAX_ACTIVE_DIM:
        raise ValueError(f"active_dim must be in 1..{MAX_ACTIVE_DIM}")
    if isinstance(epoch_step, bool) or not isinstance(epoch_step, int) or epoch_step < 0:
        raise ValueError("epoch_step must be a non-negative integer")
    size = 1 << active_dim
    mask = size - 1
    pi = pisano_period_pow2(active_dim)
    phase = epoch_step % pi
    idx = 3 * phase + 1
    f_idx, l_idx = exact_fibonacci_lucas_mod(idx, size)
    stride = l_idx & mask
    if stride % 2 == 0 or math.gcd(stride, size) != 1:
        raise ArithmeticError("Lucas stride is not a unit mod 2^D")
    return {
        "active_dim": active_dim, "pisano_period": pi, "phase": phase, "idx": idx,
        "lucas_stride_mod": stride, "fibonacci_phase_mod": f_idx & mask, "mask": mask,
    }


def lucas_pisano_geodesic_order(active_dim: int, *, epoch_step: int = 1,
                                apply_gray_geodesic: bool = True) -> List[int]:
    """Permutation of range(2^active_dim) (see module docstring)."""
    p = schedule_parameters(active_dim, epoch_step)
    stride, off, mask = p["lucas_stride_mod"], p["fibonacci_phase_mod"], p["mask"]
    out = []
    pos = off
    for _ in range(mask + 1):
        out.append(pos ^ (pos >> 1) if apply_gray_geodesic else pos)
        pos = (pos + stride) & mask
    return out


def hamming_step_histogram(order: List[int]) -> Dict[int, int]:
    """Histogram of popcount(order[t] ^ order[t+1]) over consecutive positions."""
    hist: Dict[int, int] = {}
    for a, b in zip(order, order[1:]):
        h = (a ^ b).bit_count()
        hist[h] = hist.get(h, 0) + 1
    return dict(sorted(hist.items()))
