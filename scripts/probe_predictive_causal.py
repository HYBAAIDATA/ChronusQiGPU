"""Search the feature-extraction space for a Lucas arm that beats random.

Diagnosis driving this: the shipped solver sets
    seed = int.from_bytes(sha256(header).digest()[:8], "big")
    nonce = seed % L_n
sha256 is a uniform mixer, so `seed % L_n` is a near-uniform residue and
carries no structure from the header. The Lucas projection is reading an
already-destroyed signal.

This tests structure-PRESERVING extractors instead: raw header words
projected onto the Lucas lattice, per-word residues, and the Binet F/K
split. Each is measured against a random baseline of identical cardinality
with a two-proportion z-test.

Reports whatever it finds. A null result is reported as a null result.
"""

import hashlib
import math
import random
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lucas.core import lucas  # noqa: E402
from lucas.ladder import FULL_LADDER  # noqa: E402
from orcle import compact_target  # noqa: E402

BITS = 0x201C3CFF
N_BLOCKS = 400
RUNGS = tuple(FULL_LADDER)


def make_header(height, timestamp, nonce):
    """Build a header with REAL, varying prevhash and merkle root.

    The first version of this probe left prevhash and merkle_root as zeros,
    which handed the extractors five constant words to read -- any deviation
    from random was then noise by construction. A real header varies in
    every field the extractors touch, so that is what is built here.
    """
    base = bytearray(80)
    # Realistic prevhash: a real block hash, chained from the height.
    prev = hashlib.sha256(f"prev-{height}".encode()).digest()
    # Realistic merkle root: varies with height, like a real coinbase.
    merkle = hashlib.sha256(f"merkle-{height}".encode()).digest()
    base[0:4] = struct.pack("<I", 0x20000000)  # version 2
    base[4:36] = prev[::-1]  # internal LE order
    base[36:68] = merkle[::-1]
    struct.pack_into("<I", base, 68, timestamp)
    struct.pack_into("<I", base, 72, BITS)
    struct.pack_into("<I", base, 76, nonce)
    return bytes(base)


def mine(height, timestamp, tries=200000):
    target = compact_target(BITS)
    for n in range(tries):
        h = make_header(height, timestamp, n)
        d = hashlib.sha256(hashlib.sha256(h).digest()).digest()
        if int.from_bytes(d, "little") <= target:
            return h
    raise RuntimeError("no nonce mined")


def wins(header, target_int, nonces):
    hits = 0
    for n in nonces:
        h = header[:76] + struct.pack("<I", n & 0xFFFFFFFF)
        d = hashlib.sha256(hashlib.sha256(h).digest()).digest()
        if int.from_bytes(d, "little") <= target_int:
            hits += 1
    return hits


# ---- structure-preserving extractors -------------------------------------


def ext_sha256_mod(header):
    """The SHIPPED extractor, kept as the control."""
    seed = int.from_bytes(hashlib.sha256(header).digest()[:8], "big")
    return [seed % lucas(r) for r in RUNGS]


def ext_word_mod(header):
    """Each 4-byte header word, reduced mod each rung. No mixing first."""
    words = struct.unpack("<20I", header)
    return [words[i] % lucas(r) for i in range(6) for r in RUNGS]


def ext_word_lane(header):
    """Word scaled into a rung, preserving relative magnitude order."""
    words = struct.unpack("<20I", header)
    return [(words[i] * lucas(r)) // 2**32 for i in range(6) for r in RUNGS]


def ext_fk_split(header):
    """Binet F/K split of the leading word against phi, then mod L_n."""
    words = struct.unpack("<20I", header)
    w = words[0]
    phi = (1 + math.sqrt(5)) / 2
    f = int(w * (phi - 1))
    k = w - f
    return [(x % lucas(r)) for x in (f, k) for r in RUNGS]


def ext_fold_residue(header):
    """Sum of words per lane band, then mod L_n. Order-sensitive, no mixing."""
    words = struct.unpack("<20I", header)
    return [sum(words[i] for i in range(0, 20, 2)) % lucas(r) for r in RUNGS]


EXTRACTORS = {
    "sha256_mod (SHIPPED control)": ext_sha256_mod,
    "word_mod (raw, no mixing)": ext_word_mod,
    "word_lane (magnitude order)": ext_word_lane,
    "fk_split (Binet F/K)": ext_fk_split,
    "fold_residue (order-sensitive)": ext_fold_residue,
}


def ext_ORACLE(header):
    """POSITIVE CONTROL: the harness must be able to see a real signal.

    This returns the true winning nonce embedded in the header. It is not a
    predictor -- it is the answer key. If the z-test does not flag THIS as
    strongly significant, the harness is broken and every null result is
    meaningless.
    """
    return [struct.unpack_from("<I", header, 76)[0]]


def z_test(x_p, x_r, n):
    if n == 0:
        return 0.0
    p_pool = (x_p + x_r) / (2 * n)
    se = (p_pool * (1 - p_pool) * (2 / n)) ** 0.5
    return (x_p / n - x_r / n) / se if se > 0 else 0.0


if __name__ == "__main__":
    target_int = compact_target(BITS)
    headers = [mine(i, 1700000000 + i * 600) for i in range(N_BLOCKS)]
    winning = [struct.unpack_from("<I", h, 76)[0] for h in headers]

    print(f"=== {N_BLOCKS} real mined blocks, target 2^252.8 ===")
    print("=== headers now carry real varying prevhash + merkle_root ===")
    print()

    # Harness validation FIRST. If this fails, every number below is void.
    ck_p = sum(1 for i, h in enumerate(headers) if wins(h, target_int, [winning[i]]))
    ck_r = sum(
        1
        for i in range(N_BLOCKS)
        if wins(headers[i], target_int, [random.Random(i).randrange(2**32)])
    )
    zc = z_test(ck_p, ck_r, N_BLOCKS)
    print("=== HARNESS VALIDATION (answer key; must be strongly positive) ===")
    print(
        f"{'ORACLE (true nonce)':30} {N_BLOCKS:>6} {ck_p:>7} {ck_r:>7} "
        f"{zc:>+7.2f}  {'SIGNIFICANT' if abs(zc) >= 1.96 else 'HARNESS BROKEN'}"
    )
    if abs(zc) < 1.96:
        print("  !! harness cannot detect a known signal -- aborting")
        raise SystemExit(1)
    print()

    print(f"{'extractor':30} {'cands':>7} {'PYTHIA':>7} {'random':>7} {'z':>7}  verdict")
    for name, fn in EXTRACTORS.items():
        tot_p = tot_r = tot_c = 0
        for i, header in enumerate(headers):
            cands = fn(header)
            tot_c += len(cands)
            tot_p += wins(header, target_int, cands)
            rng = random.Random(1000 + i)
            tot_r += wins(header, target_int, [rng.randrange(2**32) for _ in cands])
        z = z_test(tot_p, tot_r, tot_c)
        verdict = "SIGNIFICANT" if abs(z) >= 1.96 else "indistinguishable"
        print(f"{name:30} {tot_c:>7} {tot_p:>7} {tot_r:>7} {z:>+7.2f}  {verdict}")
    sys.stdout.flush()
