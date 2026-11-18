# Lossless 2-byte-block transform over GL(2, Z/256Z), formally elevated.

# Algebraic Contract:
#   - M15 = M^15 in Gamma(2) <= GL(2, Z/256Z), det(M15) === -1 (mod 256),
#     order 128, with Hensel lifts M_k in GL(2, Z/2^k Z) for any k >= 8 via
#     c_k = (98^2 - 1) * 219^-1 (mod 2^k).
#   - Cayley-Hamilton O(1) inversion: M_k^-1 === M_k - tr(M_k)*I_2 (mod 2^k).
#   - Strict lossless contract only: we fold, we never truncate.
#   - Exact 256-to-1 quotient fiber enumeration via `trunc_fiber(u)` ISOLATED for tests.

# Wire Framing:
#   - v2 (`Folded.to_wire()` / `Folded.from_wire()`):
#       `GL2\x01` (4 B) | flags (1 B) | reserved (3 B) | orig_len (8 B BE)
#       | payload (orig_len + (orig_len & 1) B) | CRC-32C (4 B BE)
#   - v1 legacy (`to_wire_v1()` / `from_wire_v1()`): 4-byte length prefix + payload.
#   - Zero-copy bounded-buffer streaming via `FoldStream` and `UnfoldStream`.

# NOTE: `fold_truncated`, `trunc_fiber`, `FLAG_TRUNCATED`, and `gl2_fold_truncated_pairs`
# are ISOLATED in `tests/quotient_geometry_audit.py` only; they are NOT exported from
# the production `gl2_transform` namespace. This enforces the project's no-truncation contract.

from __future__ import annotations

import ctypes
import os
import struct
from dataclasses import dataclass
from typing import TypeAlias

try:
    import numpy as np  # type: ignore

    _HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore
    _HAS_NUMPY = False

MODULUS: int = 256
MASK: int = 0xFF
WIRE_HEADER_SIZE_V1: int = 4
MAX_WIRE_LENGTH_V1: int = 0xFFFF_FFFF

WIRE_MAGIC_V2: bytes = b"GL2\x01"
WIRE_HEADER_STRUCT_V2 = struct.Struct(">4sB3sQ")  # 16 bytes: magic, flags, reserved, orig_len
WIRE_CRC_STRUCT_V2 = struct.Struct(">I")          # 4 bytes: big-endian CRC-32C
WIRE_HEADER_SIZE_V2: int = WIRE_HEADER_STRUCT_V2.size
WIRE_FOOTER_SIZE_V2: int = WIRE_CRC_STRUCT_V2.size
FLAG_LOSSLESS: int = 0x00
FLAG_TRUNCATED: int = 0x01  # ISOLATED: only used in tests/quotient_geometry_audit.py

Matrix2x2: TypeAlias = tuple[tuple[int, int], tuple[int, int]]
BytesLike: TypeAlias = bytes | bytearray | memoryview


# ---------------------------------------------------------------------------
# 1. Algebraic Core: GL(2, Z/2^k Z), Hensel Lifting & Cayley-Hamilton
# ---------------------------------------------------------------------------

def hensellift_m15(k: int = 8) -> Matrix2x2:
    """Hensel-lift M15 = ((219, 98), (98, 121)) to GL(2, Z/2^k Z) for k >= 8.

    Guarantees M_k === M15 (mod 256), M_k === I_2 (mod 2), det(M_k) === -1 (mod 2^k),
    and maximal 2-group multiplicative order 2^(k-1).
    """
    if isinstance(k, bool) or not isinstance(k, int) or k < 8:
        raise ValueError(f"k must be an integer >= 8, got {k!r}")
    mod = 1 << k
    a, b = 219, 98
    c = ((b * b - 1) * pow(a, -1, mod)) % mod
    return ((a, b), (b, c))


def invert_gl2_mod2k(m: Matrix2x2, k: int = 8) -> Matrix2x2:
    """Compute M^-1 in GL(2, Z/2^k Z) and verify M * M^-1 === I_2 (mod 2^k).

    Uses Cayley-Hamilton reduction M^-1 = M - tr(M)*I_2 when det(M) === -1 (mod 2^k),
    and general adjugate inversion det(M)^-1 * adj(M) for arbitrary units.
    """
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError(f"k must be an integer >= 1, got {k!r}")
    mod = 1 << k
    mask = mod - 1
    det = (m[0][0] * m[1][1] - m[0][1] * m[1][0]) & mask
    if (det & 1) == 0:
        raise ValueError(f"Matrix is singular mod 2^{k} (even determinant {det})")

    if det == mask:
        tr = (m[0][0] + m[1][1]) & mask
        inv: Matrix2x2 = (
            ((m[0][0] - tr) & mask, m[0][1] & mask),
            (m[1][0] & mask, (m[1][1] - tr) & mask),
        )
    else:
        det_inv = pow(det, -1, mod)
        inv = (
            ((det_inv * m[1][1]) & mask, (det_inv * (-m[0][1])) & mask),
            ((det_inv * (-m[1][0])) & mask, (det_inv * m[0][0]) & mask),
        )

    i00 = (m[0][0] * inv[0][0] + m[0][1] * inv[1][0]) & mask
    i01 = (m[0][0] * inv[0][1] + m[0][1] * inv[1][1]) & mask
    i10 = (m[1][0] * inv[0][0] + m[1][1] * inv[1][0]) & mask
    i11 = (m[1][0] * inv[0][1] + m[1][1] * inv[1][1]) & mask
    if (i00, i01, i10, i11) != (1, 0, 0, 1):
        raise ValueError(f"Matrix failed GL(2, Z/2^{k}Z) inverse verification")
    return inv


M15: Matrix2x2 = hensellift_m15(8)
M15_INV: Matrix2x2 = invert_gl2_mod2k(M15, 8)
_INV_219_MOD256: int = pow(219, -1, MODULUS)  # 59


def trunc_fiber(u: int) -> 'Iterator[tuple[int, int]]':
    """Yield the exact 256-element affine fiber {(x, y) : (219x + 98y) mod 256 == u}.

    NOTE: This function ISOLATED for test/fixture use only; does not appear in
    production __all__ to enforce the no-truncation contract.
    """
    if isinstance(u, bool) or not isinstance(u, int) or not (0 <= u < MODULUS):
        raise ValueError(f"u must be an integer in [0, 255], got {u!r}")
    x0 = (u * _INV_219_MOD256) & MASK
    for t in range(MODULUS):
        yield ((x0 - 98 * t) & MASK, (219 * t) & MASK)