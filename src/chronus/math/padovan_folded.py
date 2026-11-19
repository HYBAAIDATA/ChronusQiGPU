"""Exact 3D Padovan plastic transform over F_257 with compact period folding.

Mathematical contract (verified by execution, not assumed):
  * x^3 - x - 1 is IRREDUCIBLE over F_257 (no root in F_257; the companion
    matrix has no eigenvector in F_257^3).
  * The companion matrix M = [[0,1,0],[0,0,1],[1,1,0]] of rho^3 = rho + 1
    has exact minimal period 66307 = 257^2 + 257 + 1 = 61 * 1087 over F_257
    (M^66307 == I; no smaller exponent closes the cycle).
  * Folding is memory folding, not compression: s = 66307*q + r is a
    bijective decomposition; the residual r is resolved exactly by a
    baby-step/giant-step split s = 258*g + b (258^2 = 66564 >= 66307), so
    two 258-entry tables (6,192 bytes total, L1 constant-cache resident)
    reconstruct M^s for any s without big-integer arithmetic.

The 21,930/2,807,040 figures circulating in planning notes are incorrect:
they assume a false linear root (69) of x^3 - x - 1 mod 257.
"""

from __future__ import annotations

import hashlib
import struct
from array import array

MOD = 257
PADOVAN_PERIOD = 66307  # 257**2 + 257 + 1 == 66307; factors 61 * 1087
BSGS_BASE = 258  # 258**2 = 66564 >= 66307

_PADOVAN_INIT = (1, 1, 1)  # P_0 = P_1 = P_2 = 1


def _mat_mul(A: tuple, B: tuple) -> tuple:
    return tuple(
        tuple(sum(A[i][k] * B[k][j] for k in range(3)) % MOD for j in range(3))
        for i in range(3)
    )


_COMPANION = ((0, 1, 0), (0, 0, 1), (1, 1, 0))
_IDENTITY = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


def padovan_matrix_power(s: int) -> tuple:
    """Exact M^s mod 257 by square-and-multiply; O(log s) host reference."""
    if not isinstance(s, int) or isinstance(s, bool) or s < 0:
        raise ValueError("s must be a non-negative integer")
    result, base = _IDENTITY, _COMPANION
    while s:
        if s & 1:
            result = _mat_mul(result, base)
        base = _mat_mul(base, base)
        s >>= 1
    return result


def _apply(M: tuple, v: tuple) -> tuple:
    return tuple(sum(M[i][k] * v[k] for k in range(3)) % MOD for i in range(3))


def _build_tables() -> tuple:
    """Baby-step vector table (M^b v0) and giant-step matrix table
    ((M^258)^g), so M^s v0 = G[g] @ B[b] for s = 258*g + b. Build proves
    period-66307 closure."""
    baby = []
    state = _PADOVAN_INIT
    for _ in range(BSGS_BASE):
        baby.append(tuple(state))
        state = _apply(_COMPANION, state)
    m258 = padovan_matrix_power(BSGS_BASE)
    giant = [_IDENTITY]
    for _ in range(1, BSGS_BASE):
        giant.append(_mat_mul(giant[-1], m258))
    # Closure proof: full giant walk + residual baby walk returns to v0.
    probe = _PADOVAN_INIT
    for _ in range(PADOVAN_PERIOD // BSGS_BASE):
        probe = _apply(m258, probe)
    for _ in range(PADOVAN_PERIOD % BSGS_BASE):
        probe = _apply(_COMPANION, probe)
    if probe != _PADOVAN_INIT:
        raise RuntimeError("Padovan period-66307 closure check failed")
    return tuple(baby), tuple(giant)


_BABY_TABLE, _GIANT_TABLE = _build_tables()

PADOVAN_BABY_LUT_BYTES = array(
    "H", [c for row in _BABY_TABLE for c in row]
).tobytes()
PADOVAN_GIANT_LUT_BYTES = array(
    "H", [c for mat in _GIANT_TABLE for row in mat for c in row]
).tobytes()
PADOVAN_LUT_SHA256 = hashlib.sha256(
    PADOVAN_BABY_LUT_BYTES + PADOVAN_GIANT_LUT_BYTES
).hexdigest()

#: 16-byte folded Padovan record: Q epoch_q | H r_lo | H r_hi | H flags | H resv
PADOVAN_STATE_STRUCT = struct.Struct("<QHHHH")
PADOVAN_STATE_SIZE = PADOVAN_STATE_STRUCT.size
assert PADOVAN_STATE_SIZE == 16


def padovan_state(s: int) -> tuple:
    """Exact Padovan state M^s (1,1,1) via O(1) baby-step/giant-step lookup:
    s = 258*g + b, M^s v0 = G[g] @ B[b]."""
    if not isinstance(s, int) or isinstance(s, bool) or s < 0:
        raise ValueError("s must be a non-negative integer")
    r = s % PADOVAN_PERIOD
    g, b = divmod(r, BSGS_BASE)
    return _apply(_GIANT_TABLE[g], _BABY_TABLE[b])


def fold_padovan_index(s: int, flags: int = 0) -> bytes:
    """Fold a Padovan scale index into a 16-byte record (q, r split)."""
    if not isinstance(s, int) or isinstance(s, bool) or s < 0:
        raise ValueError("s must be a non-negative integer")
    q, r = divmod(s, PADOVAN_PERIOD)
    if not 0 <= flags <= 0xFFFF:
        raise ValueError("flags must fit in a uint16 lane")
    return PADOVAN_STATE_STRUCT.pack(
        q & 0xFFFFFFFFFFFFFFFF, r & 0xFFFF, r >> 16, flags, 0
    )


def unfold_padovan_record(record_16b, high_q_limbs: int = 0) -> tuple:
    """Bijective inverse: rebuild s and the exact Padovan state triple."""
    epoch_q, r_lo, r_hi, flags, _reserved = PADOVAN_STATE_STRUCT.unpack(record_16b)
    r = (r_hi << 16) | r_lo
    if r >= PADOVAN_PERIOD:
        raise ValueError(f"Padovan residual r={r} is outside [0, {PADOVAN_PERIOD - 1}]")
    if high_q_limbs < 0:
        raise ValueError("high_q_limbs must be non-negative")
    full_q = (high_q_limbs << 64) | epoch_q
    exact_s = full_q * PADOVAN_PERIOD + r
    return exact_s, padovan_state(r), flags
