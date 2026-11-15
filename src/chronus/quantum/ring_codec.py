"""Bounded reversible byte encoding via exact Z[zeta_5] operations.

This illustrative format expands every nonempty input. Its checksum detects
accidental corruption, not malicious modification or authentication.
"""
import hashlib
import hmac
import struct
from chronus.quantum.geometric_polychoron import Cyclotomic5 as C

MAX_BYTES = 4096
_HEADER = struct.Struct('>4sQ32s')
_WORD = struct.Struct('>hhhh')
_MAGIC = b'RC01'


def encode(data):
    """Encode at most 4096 bytes into a header and exact ring coefficients."""
    if not isinstance(data, bytes):
        raise TypeError('input must be bytes')
    if len(data) > MAX_BYTES:
        raise ValueError('input exceeds byte limit')
    out = bytearray(_HEADER.pack(_MAGIC, len(data), hashlib.sha256(data).digest()))
    phi = C.phi()
    for value in data:
        x = C(value, 0, 0, 0)*phi
        out.extend(_WORD.pack(x.c0,x.c1,x.c2,x.c3))
    return bytes(out)


def decode(data):
    """Recover original bytes or reject a malformed or mismatched encoding."""
    if not isinstance(data, bytes):
        raise TypeError('input must be bytes')
    if len(data) < _HEADER.size:
        raise ValueError('header is truncated')
    magic, size, digest = _HEADER.unpack_from(data)
    if magic != _MAGIC or size > MAX_BYTES or len(data) != _HEADER.size+size*_WORD.size:
        raise ValueError('invalid header or length')
    recovered = bytearray()
    inv = C.phi_inv()
    for i in range(size):
        x=C(*_WORD.unpack_from(data, _HEADER.size+i*_WORD.size))*inv
        if x.c1 or x.c2 or x.c3 or not 0 <= x.c0 <= 255:
            raise ValueError('invalid ring symbol')
        recovered.append(x.c0)
    result=bytes(recovered)
    if not hmac.compare_digest(hashlib.sha256(result).digest(), digest):
        raise ValueError('digest mismatch')
    return result
