"""phi-winner resonance hypothesis test + local PoW verifier.

Every winner nonce must be PoW-verified locally: rebuild the 80-byte header,
double-SHA256, compare to the compact-bits target (verify_block). Baseline is
a uniform uint32 Monte-Carlo draw scored with the SAME scorer. R_phi is
ordering telemetry, never a hit-probability predictor.
"""

from __future__ import annotations

import hashlib
import math
import random
import struct

from python_backend.phi_grover_v4 import phi_resonance, cheap_resonance  # noqa: E402

THRESHOLD = 0.5
SWEEP_THRESHOLDS = [0.5, 0.55, 0.6, 0.65, 0.7]


def _norm_bits(bits) -> int:
    return int(bits, 16) if isinstance(bits, str) else int(bits)


def compact_target(bits) -> int:
    nb = _norm_bits(bits)
    exp = nb >> 24
    mant = nb & 0xFFFFFF
    if mant == 0:
        raise ValueError(f"zero mantissa bits {nb:#010x}")
    if exp <= 3:
        return mant >> (8 * (3 - exp))
    return mant << (8 * (exp - 3))


def pow_hit(digest_le_int: int, bits) -> bool:
    return digest_le_int <= compact_target(bits)


def build_header_variants(blk: dict):
    ver = blk["version"]
    prev = bytes.fromhex(blk["previousblockhash"])
    mrk = bytes.fromhex(blk["merkle_root"])
    ts = blk["timestamp"]
    nb = _norm_bits(blk["bits"]) & 0xFFFFFFFF
    nonce = blk["nonce"]
    out = []
    for rev_prev in (True, False):
        p = prev[::-1] if rev_prev else prev
        for rev_mrk in (True, False):
            m = mrk[::-1] if rev_mrk else mrk
            out.append(
                struct.pack("<I", ver & 0xFFFFFFFF)
                + p
                + m
                + struct.pack("<III", ts & 0xFFFFFFFF, nb, nonce & 0xFFFFFFFF)
            )
    return out


def verify_block(blk: dict):
    """(ok, nonce, meta) iff header rebuilds to the block id AND meets target."""
    variants = build_header_variants(blk)
    matches = []
    for hdr in variants:
        d = hashlib.sha256(hashlib.sha256(hdr).digest()).digest()
        if d[::-1].hex() == blk["id"]:
            matches.append((d, hdr))
    if len(matches) != 1:
        return False, None, {"error": f"id-match count={len(matches)}"}
    digest, hdr = matches[0]
    le = int.from_bytes(digest, "little")
    hit = pow_hit(le, blk["bits"])
    return (
        hit,
        blk["nonce"],
        {
            "height": blk["height"],
            "id": blk["id"],
            "bits": f"{_norm_bits(blk['bits']):08x}",
            "header": hdr.hex(),
            "digest_le": str(le),
        },
    )


def score(nonce_val: int):
    return phi_resonance(int(nonce_val))


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    lo = max(0.0, (c - m) / d)
    hi = min(1.0, (c + m) / d)
    return (p, lo, hi)


def two_proportion_zt(k1, n1, k2, n2):
    p1, p2 = k1 / n1, k2 / n2
    pp = (k1 + k2) / (n1 + n2)
    se = math.sqrt(pp * (1 - pp) * (1 / n1 + 1 / n2))
    if se == 0:
        return 0.0, 1.0
    z = (p1 - p2) / se
    p = math.erfc(abs(z) / math.sqrt(2))
    return z, p


def baseline(samples: int):
    rng = random.Random(0x9E3779B9)
    seen = set()
    hits_full = hits_cheap = 0
    vals = []
    while len(seen) < samples:
        seen.add(rng.getrandbits(32))
    for n in seen:
        r = phi_resonance(n)
        vals.append(r)
        if r >= THRESHOLD:
            hits_full += 1
        if cheap_resonance(n) >= THRESHOLD:
            hits_cheap += 1
    vals.sort()

    def q(f):
        return vals[min(len(vals) - 1, int(f * len(vals)))]

    return {
        "samples": len(seen),
        "rate_full_ge_threshold": hits_full / len(seen),
        "rate_cheap_ge_threshold": hits_cheap / len(seen),
        "mean_resonance": sum(vals) / len(vals),
        "quantiles": {str(x): round(q(x), 4) for x in (0.1, 0.25, 0.5, 0.75, 0.9)},
    }


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", type=int, default=60000)
    args = ap.parse_args()
    print("baseline:", baseline(args.baseline))
