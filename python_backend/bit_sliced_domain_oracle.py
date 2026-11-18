"""Bit-sliced SHA-256d domain oracle (Python big-int bit planes).

Design
------
* Midstate = SHA-256 compress of header[0:64] (chunk 1), computed once.
* Chunk-2 rounds 0-2 are cached (W[3] = nonce first enters at round 3).
* 128-lane big-int bit planes, one bit per nonce in a batch.
* H2 early-abort is adaptive in the target's leading-zero bits
  (``derive_early_abort_constraints``):
    - byte-aligned low-bit congruence
      e61 == -IV7 (mod 2**(8*floor(z/8))) after 61 rounds (rounds 0..60),
      because digest word 7 = IV7 + e61 (= IV7 + h after 64 rounds);
    - if z < 8, finish rounds 61-63 bit-sliced and test bits 7..(8-z)
      of H2 word 7;
    - if z >= 64, also test word 6.  Word 6 = IV6 + g_64 = IV6 + e after
      62 rounds (round indices 0..61).  This is *not* f at the post-61
      state (that f is e after only 60 rounds).
* Every survivor is confirmed with scalar hashlib.sha256d.
* phase_mask is an exact int, bit i set iff nonces[i] meets the target.
* Accounting is honest per-lane rounds / 64, never "1 per bit-sliced pass".
"""
from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from python_backend.pythia_mining.midstate import (
    IV,
    K,
    _big_sigma0,
    _big_sigma1,
    _ch,
    _maj as _maj_scalar,
    _small_sigma0,
    _small_sigma1,
    compute_midstate,
)

LANE_WIDTH = 128
MASK32 = 0xFFFFFFFF

# SHA-256 IV word 6 and 7, and their additive inverses mod 2^32.
IV6 = IV[6]
IV7 = IV[7]
NEG_IV6 = (-IV6) & MASK32
NEG_IV7 = (-IV7) & MASK32


def target_from_bits(bits: int) -> int:
    return (bits & 0xFFFFFF) << (8 * ((bits >> 24) - 3))


def derive_early_abort_constraints(target: int) -> Tuple[int, int]:
    """Return (h7_zero_bits, h6_zero_bits) implied by hash_le <= target.

    Leading zeros of a 256-bit Bitcoin hash (int.from_bytes(..., 'little'))
    are the low bits of SHA-256 digest word 7, then the low bits of word 6.
    """
    if target <= 0:
        return 32, 32
    if target >= (1 << 256):
        return 0, 0
    leading = 256 - int(target).bit_length()
    h7 = min(32, leading)
    h6 = min(32, max(0, leading - 32))
    return h7, h6


def sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def hash_meets_target(digest: bytes, target: int) -> bool:
    return int.from_bytes(digest, "little") <= target


# ---------------------------------------------------------------------------
# Bit-plane helpers.  A word is a list of 32 Python ints (LSB = plane 0);
# bit k of plane i is bit i of lane k's word.  Loop indices are never
# named a/b/c, so they cannot shadow Maj/Ch parameters.
# ---------------------------------------------------------------------------


def _mask(n: int) -> int:
    return (1 << n) - 1 if n else 0


def splat(value: int, n: int) -> List[int]:
    m = _mask(n)
    v = value & MASK32
    return [m if (v >> i) & 1 else 0 for i in range(32)]


def pack_words(values: Sequence[int], n: int) -> List[int]:
    planes = [0] * 32
    for k, raw in enumerate(values):
        v = raw & MASK32
        if not v:
            continue
        bit = 1 << k
        for i in range(32):
            if (v >> i) & 1:
                planes[i] |= bit
    return planes


def _andnot(n: int, x: int) -> int:
    return _mask(n) ^ x


def rot_r(word: List[int], r: int) -> List[int]:
    r &= 31
    return word[r:] + word[:r]


def shr(word: List[int], r: int) -> List[int]:
    if r <= 0:
        return list(word)
    if r >= 32:
        return [0] * 32
    return word[r:] + [0] * r


def xor_words(*words: List[int]) -> List[int]:
    out = list(words[0])
    for w in words[1:]:
        for i in range(32):
            out[i] ^= w[i]
    return out


def and_words(x: List[int], y: List[int]) -> List[int]:
    return [x[i] & y[i] for i in range(32)]


def add32(*words: List[int]) -> List[int]:
    acc = words[0]
    for w in words[1:]:
        acc = _add2(acc, w)
    return acc


def _add2(x: List[int], y: List[int]) -> List[int]:
    out = [0] * 32
    carry = 0
    for i in range(32):
        xi, yi = x[i], y[i]
        out[i] = xi ^ yi ^ carry
        carry = (xi & yi) | (xi & carry) | (yi & carry)
    return out


def _ch_planes(x: List[int], y: List[int], z: List[int], n: int) -> List[int]:
    # Ch(x,y,z) = (x & y) ^ (~x & z)
    return [(x[i] & y[i]) ^ (_andnot(n, x[i]) & z[i]) for i in range(32)]


def _maj_planes(x: List[int], y: List[int], z: List[int]) -> List[int]:
    # Maj(x,y,z) = (x & y) ^ (x & z) ^ (y & z).  Parameters are x,y,z so a
    # loop index cannot shadow them (the original _maj(a,b,c) + ``for b in
    # range(32)`` bug).
    return [(x[i] & y[i]) ^ (x[i] & z[i]) ^ (y[i] & z[i]) for i in range(32)]


def _bs0(x: List[int]) -> List[int]:
    return xor_words(rot_r(x, 2), rot_r(x, 13), rot_r(x, 22))


def _bs1(x: List[int]) -> List[int]:
    return xor_words(rot_r(x, 6), rot_r(x, 11), rot_r(x, 25))


def _ss0(x: List[int]) -> List[int]:
    return xor_words(rot_r(x, 7), rot_r(x, 18), shr(x, 3))


def _ss1(x: List[int]) -> List[int]:
    return xor_words(rot_r(x, 17), rot_r(x, 19), shr(x, 10))


def eq_mod_mask(word: List[int], scalar: int, mod_bits: int, n: int) -> int:
    """Lanes where word ≡ scalar (mod 2**mod_bits).  mod_bits<=0 => all lanes."""
    all_lanes = _mask(n)
    if mod_bits <= 0:
        return all_lanes
    bits = 32 if mod_bits >= 32 else mod_bits
    acc = all_lanes
    s = scalar & MASK32
    for i in range(bits):
        plane = word[i]
        acc &= plane if (s >> i) & 1 else _andnot(n, plane)
    return acc


def bits_zero_mask(word: List[int], lo: int, hi: int, n: int) -> int:
    """Lanes where word bits lo..hi inclusive are clear."""
    acc = _mask(n)
    for i in range(lo, hi + 1):
        acc &= _andnot(n, word[i])
    return acc


def _sha256_round_planes(a, b, c, d, e, f, g, h, w, k_word, n: int):
    t1 = add32(h, _bs1(e), _ch_planes(e, f, g, n), k_word, w)
    t2 = add32(_bs0(a), _maj_planes(a, b, c))
    return add32(t1, t2), a, b, c, add32(d, t1), e, f, g


def _expand_w(w: List[Optional[List[int]]], t: int) -> List[int]:
    # W[t] = σ1(W[t-2]) + W[t-7] + σ0(W[t-15]) + W[t-16]
    return add32(_ss1(w[t - 2]), w[t - 7], _ss0(w[t - 15]), w[t - 16])


def _scalar_prefix_rounds(state: Sequence[int], w0: int, w1: int, w2: int):
    """Run chunk-2 rounds 0-2 (nonce-independent) from midstate working vars."""
    a, b, c, d, e, f, g, h = state
    for t, wt in enumerate((w0, w1, w2)):
        t1 = (h + _big_sigma1(e) + _ch(e, f, g) + K[t] + wt) & MASK32
        t2 = (_big_sigma0(a) + _maj_scalar(a, b, c)) & MASK32
        h, g, f, e, d, c, b, a = g, f, e, (d + t1) & MASK32, c, b, a, (t1 + t2) & MASK32
    return (a, b, c, d, e, f, g, h)


@dataclass
class OracleTelemetry:
    midstate: Tuple[int, ...]
    cached_rounds_0_2: Tuple[int, ...]
    h7_zero_bits: int
    h6_zero_bits: int
    batches: int = 0
    lanes: int = 0
    h1_rounds: int = 0
    h2_rounds: int = 0
    hashlib_confirms: int = 0
    early_abort_lanes: int = 0
    hashlib_hits: int = 0

    @property
    def bitsliced_lane_rounds(self) -> int:
        return self.h1_rounds + self.h2_rounds

    @property
    def hashlib_lane_rounds(self) -> int:
        # each hashlib.sha256d confirm is three full compressions (chunk1+chunk2+H2)
        return 3 * 64 * self.hashlib_confirms

    @property
    def lane_rounds(self) -> int:
        return self.bitsliced_lane_rounds + self.hashlib_lane_rounds

    @property
    def lane_compressions(self) -> float:
        return self.lane_rounds / 64.0

    @property
    def bitsliced_lane_compressions(self) -> float:
        return self.bitsliced_lane_rounds / 64.0


class BitSlicedDomainOracle:
    """Exact SHA-256d phase-mask oracle for a header and a compact target."""

    def __init__(self, header80: bytes, target: int):
        if len(header80) < 76:
            raise ValueError("header must have at least 76 bytes")
        self.prefix = bytes(header80[:76])
        self.target = int(target)
        self.midstate = compute_midstate(self.prefix[:64])
        tail = self.prefix[64:76]  # 12 bytes: merkle tail, ntime, nbits
        self.w0 = int.from_bytes(tail[0:4], "big")
        self.w1 = int.from_bytes(tail[4:8], "big")
        self.w2 = int.from_bytes(tail[8:12], "big")
        # W[4]=0x80000000, W[5..14]=0, W[15]=640 (80-byte message)
        self.cached_rounds_0_2 = _scalar_prefix_rounds(self.midstate, self.w0, self.w1, self.w2)
        self.h7_zero_bits, self.h6_zero_bits = derive_early_abort_constraints(self.target)
        self.telemetry = OracleTelemetry(
            midstate=self.midstate,
            cached_rounds_0_2=self.cached_rounds_0_2,
            h7_zero_bits=self.h7_zero_bits,
            h6_zero_bits=self.h6_zero_bits,
        )

    def reset_telemetry(self) -> None:
        t = self.telemetry
        t.batches = t.lanes = t.h1_rounds = t.h2_rounds = 0
        t.hashlib_confirms = t.early_abort_lanes = t.hashlib_hits = 0

    def phase_mask(self, nonces: Sequence[int]) -> int:
        """Exact integer mask: bit i is set iff SHA256d(prefix|nonces[i]) <= target."""
        mask = 0
        for start in range(0, len(nonces), LANE_WIDTH):
            batch = list(nonces[start:start + LANE_WIDTH])
            batch_mask = self._phase_mask_batch(batch)
            mask |= batch_mask << start
        return mask

    def marked_indices(self, nonces: Sequence[int]) -> List[int]:
        m = self.phase_mask(nonces)
        return [i for i in range(len(nonces)) if (m >> i) & 1]

    def _phase_mask_batch(self, nonces: List[int]) -> int:
        n = len(nonces)
        tel = self.telemetry
        tel.batches += 1
        tel.lanes += n

        # ---- H1 chunk 2, starting after cached rounds 0-2 ----
        w3_vals = [int.from_bytes(struct.pack("<I", nonce & MASK32), "big") for nonce in nonces]
        w3 = pack_words(w3_vals, n)
        w: List[Optional[List[int]]] = [None] * 64
        w[0], w[1], w[2], w[3] = splat(self.w0, n), splat(self.w1, n), splat(self.w2, n), w3
        w[4] = splat(0x80000000, n)
        zero = splat(0, n)
        for i in range(5, 15):
            w[i] = zero
        w[15] = splat(640, n)

        a, b, c, d, e, f, g, h = (splat(x, n) for x in self.cached_rounds_0_2)
        ksplat = [splat(K[t], n) for t in range(64)]

        # rounds 3..63 (61 rounds); expand W on demand
        for t in range(3, 64):
            if w[t] is None:
                if t >= 16:
                    w[t] = _expand_w(w, t)
                else:
                    raise RuntimeError(f"missing W[{t}]")
            a, b, c, d, e, f, g, h = _sha256_round_planes(a, b, c, d, e, f, g, h, w[t], ksplat[t], n)
        tel.h1_rounds += n * 61

        # H1 digest = midstate + working vars
        h1 = [add32(splat(self.midstate[i], n), v) for i, v in enumerate((a, b, c, d, e, f, g, h))]

        # ---- H2: SHA-256 of the 32-byte H1 digest, starting from IV ----
        w2s: List[Optional[List[int]]] = [None] * 64
        for i in range(8):
            w2s[i] = h1[i]
        w2s[8] = splat(0x80000000, n)
        for i in range(9, 15):
            w2s[i] = zero
        w2s[15] = splat(256, n)

        a, b, c, d, e, f, g, h = (splat(x, n) for x in IV)
        for t in range(16):
            if w2s[t] is None:
                raise RuntimeError("H2 W missing")
        # rounds 0..60 inclusive = 61 rounds; e is then e61
        for t in range(61):
            if w2s[t] is None:
                w2s[t] = _expand_w(w2s, t)
            a, b, c, d, e, f, g, h = _sha256_round_planes(a, b, c, d, e, f, g, h, w2s[t], ksplat[t], n)
        tel.h2_rounds += n * 61

        z7, z6 = self.h7_zero_bits, self.h6_zero_bits
        live = _mask(n)

        # Word-7 check uses e after 61 rounds (rounds 0..60).
        if z7 >= 8:
            mod_bits = 8 * (z7 // 8)
            live &= eq_mod_mask(e, NEG_IV7, mod_bits, n)
        elif z7 > 0:
            # z<8: finish rounds 61-63 and test bits 7..(8-z) of H2 word 7.
            for t in range(61, 64):
                if w2s[t] is None:
                    w2s[t] = _expand_w(w2s, t)
                a, b, c, d, e, f, g, h = _sha256_round_planes(a, b, c, d, e, f, g, h, w2s[t], ksplat[t], n)
            tel.h2_rounds += n * 3
            word7 = add32(splat(IV7, n), h)  # h_64 = e61, already in h after 64 rounds
            live &= bits_zero_mask(word7, 8 - z7, 7, n)
            # leftover low bits of the target are decided by hashlib confirm

        # Word-6 check: need e after 62 rounds (round indices 0..61).
        # Skip if everyone already died, or if we already finished 64 rounds (z7<8)
        # and z6>0 — then g_64 is in g and we can form word6 without more rounds.
        if z6 > 0 and live:
            if z7 < 8:
                # H2 already finished; word6 = IV6 + g_64
                word6 = add32(splat(IV6, n), g)
                mod_bits = 8 * (z6 // 8) if z6 >= 8 else 0
                if mod_bits:
                    live &= eq_mod_mask(word6, 0, mod_bits, n)
                # if z6 < 8, rely on hashlib for the few bits
            else:
                # currently at after 61 rounds; run round index 61 once
                t = 61
                if w2s[t] is None:
                    w2s[t] = _expand_w(w2s, t)
                a, b, c, d, e, f, g, h = _sha256_round_planes(a, b, c, d, e, f, g, h, w2s[t], ksplat[t], n)
                tel.h2_rounds += n * 1
                # new e is e after 62 rounds = g_64
                mod_bits = 8 * (z6 // 8) if z6 >= 8 else 0
                if mod_bits:
                    live &= eq_mod_mask(e, NEG_IV6, mod_bits, n)

        dead = _mask(n) ^ live
        tel.early_abort_lanes += dead.bit_count()

        # Scalar hashlib confirm on every survivor — the mask bit is set only
        # when hashlib agrees.  This is the zero-false-negative / zero-false-
        # positive contract (early abort must never drop a real hit).
        out = 0
        for k, nonce in enumerate(nonces):
            if not ((live >> k) & 1):
                continue
            tel.hashlib_confirms += 1
            hdr = self.prefix + struct.pack("<I", nonce & MASK32)
            if hash_meets_target(sha256d(hdr), self.target):
                out |= 1 << k
                tel.hashlib_hits += 1
        return out


def linear_scan_compressions(
    header80: bytes,
    target: int,
    nonces: Sequence[int],
    *,
    stop_at_first_hit: bool = False,
) -> Tuple[Optional[int], float, int]:
    """Fair scalar baseline: same midstate, cached rounds 0-2, and H2 early abort.

    Returns (hit_nonce or None, lane_compressions, lanes_evaluated).
    Round counts match the bit-sliced path (61 H1 rounds after the cache,
    61 H2 rounds, +1 if word6 is checked, +3 if z<8 finishes H2).  A
    surviving scalar candidate is finished and compared without hashlib.
    """
    oracle = BitSlicedDomainOracle(header80, target)
    z7, z6 = oracle.h7_zero_bits, oracle.h6_zero_bits
    h1_r = h2_r = 0
    evaluated = 0
    hit = None
    # Precompute scalar W0-2 and cached state already on the oracle.
    ms = oracle.midstate
    cache = oracle.cached_rounds_0_2

    def first_hash_complete(nonce: int) -> Tuple[int, ...]:
        # Continue rounds 3..63 from cache with this nonce, add midstate.
        w3 = int.from_bytes(struct.pack("<I", nonce & MASK32), "big")
        w = [0] * 64
        w[0], w[1], w[2], w[3] = oracle.w0, oracle.w1, oracle.w2, w3
        w[4] = 0x80000000
        w[15] = 640
        for t in range(16, 64):
            s0 = _small_sigma0(w[t - 15])
            s1 = _small_sigma1(w[t - 2])
            w[t] = (w[t - 16] + s0 + w[t - 7] + s1) & MASK32
        a, b, c, d, e, f, g, h = cache
        for t in range(3, 64):
            t1 = (h + _big_sigma1(e) + _ch(e, f, g) + K[t] + w[t]) & MASK32
            t2 = (_big_sigma0(a) + _maj_scalar(a, b, c)) & MASK32
            h, g, f, e, d, c, b, a = g, f, e, (d + t1) & MASK32, c, b, a, (t1 + t2) & MASK32
        return (
            (ms[0] + a) & MASK32,
            (ms[1] + b) & MASK32,
            (ms[2] + c) & MASK32,
            (ms[3] + d) & MASK32,
            (ms[4] + e) & MASK32,
            (ms[5] + f) & MASK32,
            (ms[6] + g) & MASK32,
            (ms[7] + h) & MASK32,
        )

    def h2_schedule(h1: Tuple[int, ...]) -> List[int]:
        w = [0] * 64
        for i in range(8):
            w[i] = h1[i]
        w[8] = 0x80000000
        w[15] = 256
        for t in range(16, 64):
            s0 = _small_sigma0(w[t - 15])
            s1 = _small_sigma1(w[t - 2])
            w[t] = (w[t - 16] + s0 + w[t - 7] + s1) & MASK32
        return w

    def run_h2(w: List[int], nrounds: int):
        a, b, c, d, e, f, g, h = IV
        for t in range(nrounds):
            t1 = (h + _big_sigma1(e) + _ch(e, f, g) + K[t] + w[t]) & MASK32
            t2 = (_big_sigma0(a) + _maj_scalar(a, b, c)) & MASK32
            h, g, f, e, d, c, b, a = g, f, e, (d + t1) & MASK32, c, b, a, (t1 + t2) & MASK32
        return a, b, c, d, e, f, g, h

    for nonce in nonces:
        evaluated += 1
        h1 = first_hash_complete(nonce)
        h1_r += 61
        w = h2_schedule(h1)
        st = run_h2(w, 61)
        h2_r += 61
        e61 = st[4]
        survive = True
        if z7 >= 8:
            mod_bits = 8 * (z7 // 8)
            survive = ((e61 - NEG_IV7) & ((1 << mod_bits) - 1)) == 0 if mod_bits < 32 else e61 == NEG_IV7
        elif z7 > 0:
            st = run_h2(w, 64)
            h2_r += 3
            word7 = (IV7 + st[7]) & MASK32
            lo = 8 - z7
            check = (word7 >> lo) & ((1 << (7 - lo + 1)) - 1)
            survive = check == 0
        if survive and z6 > 0:
            if z7 < 8:
                word6 = (IV6 + st[6]) & MASK32
            else:
                st62 = run_h2(w, 62)
                h2_r += 1
                word6 = (IV6 + st62[4]) & MASK32  # e after 62 rounds
            mod_bits = 8 * (z6 // 8) if z6 >= 8 else 0
            if mod_bits:
                survive = (word6 & ((1 << mod_bits) - 1)) == 0
        if not survive:
            continue
        # finish and compare the full digest (scalar, no hashlib)
        st64 = run_h2(w, 64)
        # only count extra H2 rounds not already run
        already = 64 if z7 < 8 else (62 if z6 > 0 else 61)
        h2_r += 64 - already
        digest = b"".join(((ms_i := (IV[i] + st64[i]) & MASK32).to_bytes(4, "big") for i in range(8)))
        # typo check: H2 feedforward is IV + working, yes.  (ms_i is a bad name)
        if hash_meets_target(digest, target):
            hit = nonce
            if stop_at_first_hit:
                break

    return hit, (h1_r + h2_r) / 64.0, evaluated
