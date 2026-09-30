"""Deterministic CPU references for every core GPU-blueprint operation.

These functions are correctness oracles, not performance claims. Hardware
backends must agree with them and separately attest which device executed the
work and how long it took.
"""

from __future__ import annotations

import hashlib
import math
import struct
from dataclasses import dataclass
from typing import Any, Iterable, Sequence


@dataclass(frozen=True)
class ScanResult:
    nonce: int | None
    digest: bytes | None
    hashes_computed: int


def _bounded_non_negative(value: int, name: str, maximum: int = 1_000_000) -> int:
    value = int(value)
    if value < 0 or value > maximum:
        raise ValueError(f"{name} must be between 0 and {maximum}")
    return value


def fibonacci(index: int) -> int:
    """Return F(index) using exact fast doubling."""
    index = _bounded_non_negative(index, "index")

    def pair(n: int) -> tuple[int, int]:
        if n == 0:
            return 0, 1
        a, b = pair(n // 2)
        c = a * ((b << 1) - a)
        d = a * a + b * b
        return (d, c + d) if n & 1 else (c, d)

    return pair(index)[0]


def lucas_wind(index: int) -> int:
    """Return the exact Lucas number L(index)."""
    index = _bounded_non_negative(index, "index")
    if index == 0:
        return 2
    return 2 * fibonacci(index + 1) - fibonacci(index)


def cassini_step(index: int, modulus: int, stride: int, origin: int = 0) -> int:
    """One coverage-preserving affine step in a finite nonce window."""
    index = _bounded_non_negative(index, "index", 0xFFFFFFFF)
    modulus = int(modulus)
    stride = int(stride)
    origin = int(origin)
    if modulus <= 0 or modulus > 0x100000000:
        raise ValueError("modulus must be in the uint32 nonce range")
    if math.gcd(stride, modulus) != 1:
        raise ValueError("stride must be coprime to modulus")
    return (origin + index * stride) % modulus


def pisot_wind(size: int, seed: int = 0) -> list[int]:
    """Return a deterministic complete Lucas-derived permutation."""
    size = _bounded_non_negative(size, "size")
    if size == 0:
        return []
    stride = max(1, lucas_wind(abs(int(seed)) % 31 + 1) % size)
    while math.gcd(stride, size) != 1:
        stride = (stride + 1) % size or 1
    origin = int(seed) % size
    return [cassini_step(index, size, stride, origin) for index in range(size)]


def morton_step(x: int, y: int, bits: int = 16) -> int:
    """Interleave unsigned x/y bits into a two-dimensional Morton code."""
    bits = _bounded_non_negative(bits, "bits", 32)
    maximum = (1 << bits) - 1
    x = _bounded_non_negative(x, "x", maximum)
    y = _bounded_non_negative(y, "y", maximum)
    result = 0
    for bit in range(bits):
        result |= ((x >> bit) & 1) << (2 * bit)
        result |= ((y >> bit) & 1) << (2 * bit + 1)
    return result


def korobov_point(
    index: int,
    modulus: int,
    multipliers: Sequence[int],
) -> tuple[float, ...]:
    """Return one deterministic Korobov lattice point."""
    index = _bounded_non_negative(index, "index", 0xFFFFFFFF)
    modulus = int(modulus)
    if modulus <= 1:
        raise ValueError("modulus must be > 1")
    if not multipliers:
        raise ValueError("multipliers must not be empty")
    return tuple(
        ((index * int(multiplier)) % modulus) / modulus
        for multiplier in multipliers
    )


def _matrix_shape(matrix: Sequence[Sequence[Any]], name: str) -> tuple[int, int]:
    rows = len(matrix)
    cols = len(matrix[0]) if rows else 0
    if any(len(row) != cols for row in matrix):
        raise ValueError(f"{name} must be rectangular")
    return rows, cols


def matmul_f4(a: Sequence[Sequence[Any]], b: Sequence[Sequence[Any]]) -> list[list[Any]]:
    """Exact/generic matrix product; scalars retain their own F4 arithmetic."""
    a_rows, a_cols = _matrix_shape(a, "a")
    b_rows, b_cols = _matrix_shape(b, "b")
    if a_cols != b_rows:
        raise ValueError(
            f"incompatible matrix shapes ({a_rows}, {a_cols}) "
            f"and ({b_rows}, {b_cols})"
        )
    if not a_rows or not b_cols:
        return [[] for _ in range(a_rows)]
    return [
        [sum((a[i][k] * b[k][j] for k in range(a_cols)), start=0) for j in range(b_cols)]
        for i in range(a_rows)
    ]


def matvec_f4(matrix: Sequence[Sequence[Any]], vector: Sequence[Any]) -> list[Any]:
    """Exact/generic matrix-vector product."""
    rows, cols = _matrix_shape(matrix, "matrix")
    if cols != len(vector):
        raise ValueError(f"matrix width {cols} does not match vector length {len(vector)}")
    return [sum((matrix[i][j] * vector[j] for j in range(cols)), start=0) for i in range(rows)]


def _inner(left: Sequence[complex], right: Sequence[complex]) -> complex:
    if len(left) != len(right):
        raise ValueError("vectors must have equal length")
    return sum((complex(a).conjugate() * complex(b) for a, b in zip(left, right)), 0j)


def qfi_pure(state: Sequence[complex], derivative: Sequence[complex]) -> float:
    """Pure-state quantum Fisher information for one parameter derivative."""
    norm = _inner(state, state).real
    if not math.isfinite(norm) or norm <= 0:
        raise ValueError("state must have finite, non-zero norm")
    psi = [complex(value) / math.sqrt(norm) for value in state]
    dpsi = [complex(value) / math.sqrt(norm) for value in derivative]
    value = 4.0 * (_inner(dpsi, dpsi).real - abs(_inner(psi, dpsi)) ** 2)
    return max(0.0, float(value))


def grover_iterate(state: Sequence[complex], marked: Iterable[int]) -> list[complex]:
    """Apply one phase-oracle and diffusion iteration to an amplitude vector."""
    amplitudes = [complex(value) for value in state]
    if not amplitudes:
        raise ValueError("state must not be empty")
    marked_set = {int(index) for index in marked}
    if any(index < 0 or index >= len(amplitudes) for index in marked_set):
        raise ValueError("marked index outside state")
    oracle = [(-value if i in marked_set else value) for i, value in enumerate(amplitudes)]
    mean = sum(oracle, 0j) / len(oracle)
    return [2.0 * mean - value for value in oracle]


def grover_hendrix_iterate(
    state: Sequence[complex], marked: Iterable[int], order: Sequence[int]
) -> list[complex]:
    """Run Grover in a declared permutation and restore canonical ordering."""
    n = len(state)
    permutation = [int(index) for index in order]
    if sorted(permutation) != list(range(n)):
        raise ValueError("order must be a complete permutation of the state")
    inverse = {canonical: position for position, canonical in enumerate(permutation)}
    ordered_state = [state[index] for index in permutation]
    ordered_marked = [inverse[int(index)] for index in marked]
    evolved = grover_iterate(ordered_state, ordered_marked)
    restored = [0j] * n
    for position, canonical in enumerate(permutation):
        restored[canonical] = evolved[position]
    return restored


def sha256d(payload: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(bytes(payload)).digest()).digest()


def sha256d_verify(payload: bytes, claimed: bytes) -> bool:
    return len(claimed) == 32 and sha256d(payload) == bytes(claimed)


def sha256d_merkle(left: bytes, right: bytes) -> bytes:
    if len(left) != 32 or len(right) != 32:
        raise ValueError("Merkle children must each be 32 bytes")
    return sha256d(bytes(left) + bytes(right))


_SHA256_INITIAL = (
    0x6A09E667,
    0xBB67AE85,
    0x3C6EF372,
    0xA54FF53A,
    0x510E527F,
    0x9B05688C,
    0x1F83D9AB,
    0x5BE0CD19,
)
_SHA256_K = (
    0x428A2F98, 0x71374491, 0xB5C0FBCF, 0xE9B5DBA5, 0x3956C25B, 0x59F111F1,
    0x923F82A4, 0xAB1C5ED5, 0xD807AA98, 0x12835B01, 0x243185BE, 0x550C7DC3,
    0x72BE5D74, 0x80DEB1FE, 0x9BDC06A7, 0xC19BF174, 0xE49B69C1, 0xEFBE4786,
    0x0FC19DC6, 0x240CA1CC, 0x2DE92C6F, 0x4A7484AA, 0x5CB0A9DC, 0x76F988DA,
    0x983E5152, 0xA831C66D, 0xB00327C8, 0xBF597FC7, 0xC6E00BF3, 0xD5A79147,
    0x06CA6351, 0x14292967, 0x27B70A85, 0x2E1B2138, 0x4D2C6DFC, 0x53380D13,
    0x650A7354, 0x766A0ABB, 0x81C2C92E, 0x92722C85, 0xA2BFE8A1, 0xA81A664B,
    0xC24B8B70, 0xC76C51A3, 0xD192E819, 0xD6990624, 0xF40E3585, 0x106AA070,
    0x19A4C116, 0x1E376C08, 0x2748774C, 0x34B0BCB5, 0x391C0CB3, 0x4ED8AA4A,
    0x5B9CCA4F, 0x682E6FF3, 0x748F82EE, 0x78A5636F, 0x84C87814, 0x8CC70208,
    0x90BEFFFA, 0xA4506CEB, 0xBEF9A3F7, 0xC67178F2,
)


def _ror(value: int, shift: int) -> int:
    return ((value >> shift) | (value << (32 - shift))) & 0xFFFFFFFF


def sha256_midstate(block64: bytes) -> bytes:
    """Return the SHA-256 compression state after exactly one 64-byte block."""
    if len(block64) != 64:
        raise ValueError("midstate input must be exactly 64 bytes")
    words = list(struct.unpack(">16I", block64)) + [0] * 48
    for index in range(16, 64):
        s0 = _ror(words[index - 15], 7) ^ _ror(words[index - 15], 18) ^ (words[index - 15] >> 3)
        s1 = _ror(words[index - 2], 17) ^ _ror(words[index - 2], 19) ^ (words[index - 2] >> 10)
        words[index] = (words[index - 16] + s0 + words[index - 7] + s1) & 0xFFFFFFFF
    a, b, c, d, e, f, g, h = _SHA256_INITIAL
    for index in range(64):
        upper = _ror(e, 6) ^ _ror(e, 11) ^ _ror(e, 25)
        choice = (e & f) ^ ((~e) & g)
        temp1 = (h + upper + choice + _SHA256_K[index] + words[index]) & 0xFFFFFFFF
        lower = _ror(a, 2) ^ _ror(a, 13) ^ _ror(a, 22)
        majority = (a & b) ^ (a & c) ^ (b & c)
        temp2 = (lower + majority) & 0xFFFFFFFF
        h, g, f, e, d, c, b, a = (
            g,
            f,
            e,
            (d + temp1) & 0xFFFFFFFF,
            c,
            b,
            a,
            (temp1 + temp2) & 0xFFFFFFFF,
        )
    working = (a, b, c, d, e, f, g, h)
    state = tuple(
        (initial + value) & 0xFFFFFFFF
        for initial, value in zip(_SHA256_INITIAL, working)
    )
    return struct.pack(">8I", *state)


def sha256d_scan(
    header80: bytes,
    target: bytes,
    *,
    base_nonce: int = 0,
    count: int = 1,
) -> ScanResult:
    """Exhaustively scan a bounded nonce window with real SHA-256d."""
    if len(header80) != 80:
        raise ValueError("header80 must be exactly 80 bytes")
    if len(target) != 32:
        raise ValueError("target must be exactly 32 bytes")
    if not 0 <= base_nonce <= 0xFFFFFFFF or not 0 <= count <= 0x100000000:
        raise ValueError("nonce window outside uint32 range")
    if base_nonce + count > 0x100000000:
        raise ValueError("nonce window must not wrap uint32")
    target_int = int.from_bytes(target, "big")
    prefix = bytes(header80[:76])
    attempted = 0
    for offset in range(count):
        nonce = (base_nonce + offset) & 0xFFFFFFFF
        digest = sha256d(prefix + nonce.to_bytes(4, "little"))
        attempted += 1
        if int.from_bytes(digest, "big") <= target_int:
            return ScanResult(nonce, digest, attempted)
    return ScanResult(None, None, attempted)
