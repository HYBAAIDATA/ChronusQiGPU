# python_backend/pythia_mining/midstate.py
# Pure-Python SHA-256 single-block compression and midstate utilities.
# Deterministic; no external deps beyond Python stdlib.

from typing import Tuple

# SHA-256 constants
K = [
    0x428A2F98,
    0x71374491,
    0xB5C0FBCF,
    0xE9B5DBA5,
    0x3956C25B,
    0x59F111F1,
    0x923F82A4,
    0xAB1C5ED5,
    0xD807AA98,
    0x12835B01,
    0x243185BE,
    0x550C7DC3,
    0x72BE5D74,
    0x80DEB1FE,
    0x9BDC06A7,
    0xC19BF174,
    0xE49B69C1,
    0xEFBE4786,
    0x0FC19DC6,
    0x240CA1CC,
    0x2DE92C6F,
    0x4A7484AA,
    0x5CB0A9DC,
    0x76F988DA,
    0x983E5152,
    0xA831C66D,
    0xB00327C8,
    0xBF597FC7,
    0xC6E00BF3,
    0xD5A79147,
    0x06CA6351,
    0x14292967,
    0x27B70A85,
    0x2E1B2138,
    0x4D2C6DFC,
    0x53380D13,
    0x650A7354,
    0x766A0ABB,
    0x81C2C92E,
    0x92722C85,
    0xA2BFE8A1,
    0xA81A664B,
    0xC24B8B70,
    0xC76C51A3,
    0xD192E819,
    0xD6990624,
    0xF40E3585,
    0x106AA070,
    0x19A4C116,
    0x1E376C08,
    0x2748774C,
    0x34B0BCB5,
    0x391C0CB3,
    0x4ED8AA4A,
    0x5B9CCA4F,
    0x682E6FF3,
    0x748F82EE,
    0x78A5636F,
    0x84C87814,
    0x8CC70208,
    0x90BEFFFA,
    0xA4506CEB,
    0xBEF9A3F7,
    0xC67178F2,
]

IV = [
    0x6A09E667,
    0xBB67AE85,
    0x3C6EF372,
    0xA54FF53A,
    0x510E527F,
    0x9B05688C,
    0x1F83D9AB,
    0x5BE0CD19,
]


def _rotr(x: int, n: int) -> int:
    return ((x >> n) | ((x << (32 - n)) & 0xFFFFFFFF)) & 0xFFFFFFFF


def _shr(x: int, n: int) -> int:
    return x >> n


def _ch(x: int, y: int, z: int) -> int:
    return (x & y) ^ (~x & z)


def _maj(x: int, y: int, z: int) -> int:
    return (x & y) ^ (x & z) ^ (y & z)


def _big_sigma0(x: int) -> int:
    return (_rotr(x, 2) ^ _rotr(x, 13) ^ _rotr(x, 22)) & 0xFFFFFFFF


def _big_sigma1(x: int) -> int:
    return (_rotr(x, 6) ^ _rotr(x, 11) ^ _rotr(x, 25)) & 0xFFFFFFFF


def _small_sigma0(x: int) -> int:
    return (_rotr(x, 7) ^ _rotr(x, 18) ^ _shr(x, 3)) & 0xFFFFFFFF


def _small_sigma1(x: int) -> int:
    return (_rotr(x, 17) ^ _rotr(x, 19) ^ _shr(x, 10)) & 0xFFFFFFFF


def _parse_block(block: bytes) -> list:
    assert len(block) == 64
    w = [0] * 64
    for i in range(16):
        w[i] = int.from_bytes(block[i * 4 : i * 4 + 4], "big")
    for i in range(16, 64):
        s0 = _small_sigma0(w[i - 15])
        s1 = _small_sigma1(w[i - 2])
        w[i] = (w[i - 16] + s0 + w[i - 7] + s1) & 0xFFFFFFFF
    return w


def sha256_compress(block: bytes, state: Tuple[int, ...] = None) -> Tuple[int, ...]:
    """Compress a single 64-byte block with given state (or IV) and return new state."""
    if state is None:
        h = IV.copy()
    else:
        h = list(state)
    w = _parse_block(block)
    a, b, c, d, e, f, g, h_var = h
    for t in range(64):
        t1 = (h_var + _big_sigma1(e) + _ch(e, f, g) + K[t] + w[t]) & 0xFFFFFFFF
        t2 = (_big_sigma0(a) + _maj(a, b, c)) & 0xFFFFFFFF
        h_var = g
        g = f
        f = e
        e = (d + t1) & 0xFFFFFFFF
        d = c
        c = b
        b = a
        a = (t1 + t2) & 0xFFFFFFFF
    # Davies-Meyer feedforward adds the round output to the supplied input
    # state (`h`, preserved from the unpack above) — NOT to the IV. Adding to
    # IV unconditionally was a bug that broke every non-IV compression.
    new_state = [
        (h[0] + a) & 0xFFFFFFFF,
        (h[1] + b) & 0xFFFFFFFF,
        (h[2] + c) & 0xFFFFFFFF,
        (h[3] + d) & 0xFFFFFFFF,
        (h[4] + e) & 0xFFFFFFFF,
        (h[5] + f) & 0xFFFFFFFF,
        (h[6] + g) & 0xFFFFFFFF,
        (h[7] + h_var) & 0xFFFFFFFF,
    ]
    return tuple(new_state)


def compute_midstate(header_prefix_64: bytes) -> Tuple[int, ...]:
    """Compute SHA-256 midstate (8 uint32 words) after compressing first 64 bytes.

    header_prefix_64 must be exactly 64 bytes.
    """
    if len(header_prefix_64) != 64:
        raise ValueError("header_prefix_64 must be 64 bytes")
    return sha256_compress(header_prefix_64, state=None)


def _state_to_bytes(state: Tuple[int, ...]) -> bytes:
    return b"".join(s.to_bytes(4, "big") for s in state)


def sha256_from_midstate(midstate: Tuple[int, ...], tail: bytes) -> bytes:
    """Continue SHA-256 from midstate over `tail` bytes and return 32-byte digest.

    This implements padding and processes blocks starting from midstate as the
    previous state (i.e., as if the first 64-byte block was already processed).
    """
    # Implement full SHA-256 message scheduling: the internal state is `midstate`.
    # We'll reimplement compression loop with starting state = midstate and process
    # the remaining tail with standard padding.

    # Create message = tail, and apply SHA-256 padding for total message length = (processed_bytes + len(tail))
    # processed_bytes = 64 (first block)
    total_len_bits = (64 + len(tail)) * 8
    # Append padding
    m = bytearray(tail)
    m.append(0x80)
    # pad zeros until length ≡ 56 mod 64 (for final 8 bytes length)
    while (len(m) + 8) % 64 != 0:
        m.append(0)
    m += total_len_bits.to_bytes(8, "big")

    state: Tuple[int, ...] = tuple(midstate)
    # process each 64-byte block in m through the shared compressor, which
    # correctly feeds back into the supplied (non-IV) state
    for i in range(0, len(m), 64):
        state = sha256_compress(bytes(m[i : i + 64]), state=state)
    # digest is big-endian concatenation of state words
    return _state_to_bytes(state)


def double_sha256_from_midstate(midstate: Tuple[int, ...], tail: bytes) -> bytes:
    """Compute double SHA-256 given midstate and tail bytes (i.e., finish block and double-hash)."""
    first = sha256_from_midstate(midstate, tail)
    import hashlib

    return hashlib.sha256(first).digest()
