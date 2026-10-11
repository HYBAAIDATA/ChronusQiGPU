"""Exact T_phi byte fold shared by both Turing entrypoints; standard library only."""

from __future__ import annotations

M15: tuple[tuple[int, int], tuple[int, int]] = ((219, 98), (98, 121))
M15_INV: tuple[tuple[int, int], tuple[int, int]] = ((135, 98), (98, 37))
FOLD_MODULUS: int = 256


def t_phi_fold(raw: bytes) -> bytes:
    """Fold raw bytes through the Cassini-protected T_phi bijection.

    Byte pairs are multiplied by M15 mod 256 — exact, invertible,
    same-length (a trailing odd byte pads with zero on the fold axis).
    """
    out = bytearray(len(raw) + (len(raw) & 1))
    n_pairs = len(raw) // 2
    for i in range(n_pairs):
        x, y = raw[2 * i], raw[2 * i + 1]
        out[2 * i] = (M15[0][0] * x + M15[0][1] * y) % FOLD_MODULUS
        out[2 * i + 1] = (M15[1][0] * x + M15[1][1] * y) % FOLD_MODULUS
    if len(raw) & 1:
        x = raw[-1]
        out[-2] = (M15[0][0] * x) % FOLD_MODULUS
        out[-1] = (M15[1][0] * x) % FOLD_MODULUS
    return bytes(out)


def t_phi_unfold(folded: bytes, original_len: int) -> bytes:
    """Exact inverse of t_phi_fold over Z/256Z."""
    out = bytearray()
    for i in range(0, len(folded) - 1, 2):
        u, v = folded[i], folded[i + 1]
        out.append((M15_INV[0][0] * u + M15_INV[0][1] * v) % FOLD_MODULUS)
        if len(out) < original_len:
            out.append((M15_INV[1][0] * u + M15_INV[1][1] * v) % FOLD_MODULUS)
    return bytes(out[:original_len])


def iter_original_u8(folded: bytes, original_len: int):
    """Stream the original bytes out of folded state — inverse fused into
    the read, no raw buffer materialised."""
    emitted = 0
    for i in range(0, len(folded) - 1, 2):
        u, v = folded[i], folded[i + 1]
        if emitted < original_len:
            yield (M15_INV[0][0] * u + M15_INV[0][1] * v) % FOLD_MODULUS
            emitted += 1
        if emitted < original_len:
            yield (M15_INV[1][0] * u + M15_INV[1][1] * v) % FOLD_MODULUS
            emitted += 1


def folded_modular_dot(folded: bytes, original_len: int, weights: list[int]) -> int:
    """q^T x (mod 256) computed directly on folded bytes as (M^-T q)^T y —
    the query is compiled into the fold; the data never leaves it."""
    total = 0
    for pair, i in enumerate(range(0, len(folded) - 1, 2)):
        q0 = int(weights[2 * pair]) if 2 * pair < original_len else 0
        q1 = int(weights[2 * pair + 1]) if 2 * pair + 1 < original_len else 0
        qu = (M15_INV[0][0] * q0 + M15_INV[1][0] * q1) % FOLD_MODULUS
        qv = (M15_INV[0][1] * q0 + M15_INV[1][1] * q1) % FOLD_MODULUS
        total = (total + qu * folded[i] + qv * folded[i + 1]) % FOLD_MODULUS
    return total
