"""Lossless 2-byte-block transform over Z/256, self-describing.

M15 is an element of GL(2, Z/256) with det = -1 mod 256, so it is a
bijection on (Z/256)^2. M15_INV is derived from M15, not copied.
Provenance: this is the same M15 as Chronus's canonical byte-pair fold
(chronus.math.golden_core and chronus.tensor.folded_state), including the
zero pad byte for odd input; the test suite checks byte-identity over all
65,536 pairs whenever Chronus is importable.

Used by the wire layer to fold canonical JSON payloads. NOT encryption:
public, keyless, linear. Integrity lives in the frame's SHA-256 prefix.
"""

from __future__ import annotations

from dataclasses import dataclass

MODULUS = 256
M15 = ((219, 98), (98, 121))

_DET_INV = (-1) % MODULUS
_ADJ = ((M15[1][1], -M15[0][1]), (-M15[1][0], M15[0][0]))
M15_INV = tuple(tuple((_DET_INV * v) % MODULUS for v in row) for row in _ADJ)

_TABLE = None


def _table():
    """65,536-entry pair table, built on first use so import stays cheap."""
    global _TABLE
    if _TABLE is None:
        t = [b""] * 65536
        for x in range(MODULUS):
            a0 = M15[0][0] * x
            a1 = M15[1][0] * x
            for y in range(MODULUS):
                t[(x << 8) | y] = bytes(((a0 + M15[0][1] * y) % MODULUS,
                                         (a1 + M15[1][1] * y) % MODULUS))
        _TABLE = t
    return _TABLE


@dataclass(frozen=True)
class Folded:
    data: bytes
    length: int

    def __post_init__(self):
        if not isinstance(self.data, bytes):
            raise TypeError("data must be bytes")
        if self.length < 0:
            raise ValueError("length must be >= 0")
        want = self.length + (self.length & 1)
        if len(self.data) != want:
            raise ValueError(
                f"data is {len(self.data)} bytes, expected {want} "
                f"for length {self.length}")

    def __len__(self):
        return self.length


def _as_bytes(raw):
    if not isinstance(raw, (bytes, bytearray, memoryview)):
        raise TypeError("expected bytes-like")
    return bytes(raw)


def fold(raw):
    """Fold bytes. Lossless; the length is carried in the result."""
    raw = _as_bytes(raw)
    table = _table()
    pairs = [table[(raw[i] << 8) | raw[i + 1]] for i in range(0, len(raw) - 1, 2)]
    if len(raw) & 1:
        x = raw[-1]
        pairs.append(bytes(((M15[0][0] * x) % MODULUS, (M15[1][0] * x) % MODULUS)))
    return Folded(b"".join(pairs), len(raw))


def unfold(folded):
    """Exact inverse of fold."""
    if not isinstance(folded, Folded):
        raise TypeError("unfold expects a Folded")
    inv = M15_INV
    data, n = folded.data, folded.length
    out = bytearray()
    for i in range(0, n, 2):
        u, v = data[i], data[i + 1]
        out.append((inv[0][0] * u + inv[0][1] * v) % MODULUS)
        if i + 1 < n:
            out.append((inv[1][0] * u + inv[1][1] * v) % MODULUS)
    return bytes(out)


def to_wire(folded):
    return folded.length.to_bytes(4, "big") + folded.data


def from_wire(blob):
    blob = _as_bytes(blob)
    if len(blob) < 4:
        raise ValueError("wire blob shorter than its length prefix")
    return Folded(blob[4:], int.from_bytes(blob[:4], "big"))
