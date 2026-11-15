"""Deterministic, lossless prime-symbol reference codec.

Each source octet selects the corresponding prime in the ordered sequence of
primes beginning at 2. The prime is serialized as an unsigned 16-bit big-endian
word. The separate metadata header records format version, source length, and
SHA-256 digest. This reference representation is reversible; it is not a
compression method and makes no capacity or performance claim.
"""

from __future__ import annotations

import hashlib
import hmac
import struct
from math import isqrt

_HEADER = struct.Struct(">4sBQ32s")
_MAGIC = b"CPRM"
_VERSION = 1
_SYMBOL_COUNT = 256
_SYMBOL_WIDTH = 2


class PrimeCodecError(ValueError):
    """Base class for malformed or invalid prime-codec data."""


class PrimeCodecIntegrityError(PrimeCodecError):
    """Raised when decoded source bytes do not match the metadata digest."""


def _is_prime(candidate: int) -> bool:
    if candidate < 2:
        return False
    for divisor in range(2, isqrt(candidate) + 1):
        if candidate % divisor == 0:
            return False
    return True


def _first_primes(count: int) -> tuple[int, ...]:
    primes: list[int] = []
    candidate = 2
    while len(primes) < count:
        if _is_prime(candidate):
            primes.append(candidate)
        candidate += 1
    return tuple(primes)


_SYMBOL_PRIMES = _first_primes(_SYMBOL_COUNT)
_PRIME_TO_SYMBOL = {prime: symbol for symbol, prime in enumerate(_SYMBOL_PRIMES)}


def _as_bytes(value: bytes | bytearray | memoryview, name: str) -> bytes:
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise TypeError(f"{name} must be bytes-like")
    return bytes(value)


def encode(data: bytes | bytearray | memoryview) -> tuple[bytes, bytes]:
    """Encode bytes into prime words and a versioned integrity header.

    Returns ``(payload, metadata)``. Metadata is a fixed-width binary header;
    it is deliberately separate from the encoded payload.
    """
    source = _as_bytes(data, "data")
    if len(source) >= 1 << 64:
        raise ValueError("data length does not fit the format header")

    payload = bytearray(len(source) * _SYMBOL_WIDTH)
    for index, symbol in enumerate(source):
        struct.pack_into(">H", payload, index * _SYMBOL_WIDTH, _SYMBOL_PRIMES[symbol])

    metadata = _HEADER.pack(
        _MAGIC,
        _VERSION,
        len(source),
        hashlib.sha256(source).digest(),
    )
    return bytes(payload), metadata


def decode(
    payload: bytes | bytearray | memoryview,
    metadata: bytes | bytearray | memoryview,
) -> bytes:
    """Decode a prime-word payload and verify its source SHA-256 digest.

    Raises :class:`PrimeCodecError` for malformed headers or symbols and
    :class:`PrimeCodecIntegrityError` when the reconstructed bytes fail the
    digest check. Partial output is never returned.
    """
    encoded = _as_bytes(payload, "payload")
    header = _as_bytes(metadata, "metadata")
    if len(header) != _HEADER.size:
        raise PrimeCodecError("metadata header has an invalid length")

    magic, version, source_length, expected_digest = _HEADER.unpack(header)
    if magic != _MAGIC:
        raise PrimeCodecError("metadata magic does not match")
    if version != _VERSION:
        raise PrimeCodecError(f"unsupported prime codec version: {version}")
    if len(encoded) != source_length * _SYMBOL_WIDTH:
        raise PrimeCodecError("payload length does not match metadata")

    decoded = bytearray(source_length)
    for index in range(source_length):
        prime = struct.unpack_from(">H", encoded, index * _SYMBOL_WIDTH)[0]
        symbol = _PRIME_TO_SYMBOL.get(prime)
        if symbol is None:
            raise PrimeCodecError(f"invalid prime symbol at offset {index}")
        decoded[index] = symbol

    result = bytes(decoded)
    if not hmac.compare_digest(hashlib.sha256(result).digest(), expected_digest):
        raise PrimeCodecIntegrityError("decoded data does not match metadata digest")
    return result


__all__ = ["PrimeCodecError", "PrimeCodecIntegrityError", "decode", "encode"]
