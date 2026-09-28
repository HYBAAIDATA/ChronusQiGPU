"""Train PYTHIA's PredictiveSolver on real mined blocks and MEASURE it.

No presupposition. Runs the actual strategy stack -- including the
Lucas-resonance arm that projects the header seed mod L_n, i.e. the
L_15 = 1364 and L_20 = 15127 rungs -- and compares candidate hit rate
against a random baseline of identical cardinality, with a two-proportion
z-test so the verdict is a measurement rather than an impression.
"""

import hashlib
import random
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Intelligence.lucas_scales import build_lucas_scale_profile  # noqa: E402
from Intelligence.predictive_solver import PredictiveSolver  # noqa: E402
from orcle import compact_target  # noqa: E402

BITS = 0x201C3CFF  # target 2^252.8 -> per-hash hit chance ~1.1e-1
N_BLOCKS = 60


def make_header(height, timestamp, nonce):
    base = bytearray(80)
    struct.pack_into("<I", base, 0, 1)
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
        h = header[:76] + struct.pack("<I", n)
        d = hashlib.sha256(hashlib.sha256(h).digest()).digest()
        if int.from_bytes(d, "little") <= target_int:
            hits += 1
    return hits


if __name__ == "__main__":
    target_int = compact_target(BITS)
    profile = build_lucas_scale_profile()
    solver = PredictiveSolver(lucas_scales=profile)

    print("=== Lucas arms live in the solver? ===")
    for lv in profile.levels:
        print(f"  L_{lv.index:<3} = {lv.value:<8} position={lv.ladder_position:.3f}")

    total_pythia = total_random = total_cands = o1_hits = 0
    by_method = Counter()

    for i in range(N_BLOCKS):
        header = mine(i, 1700000000 + i * 600)
        res = solver.solve(
            header=header,
            target=target_int.to_bytes(32, "big"),
            block_context={"height": i},
        )
        cands = solver._generate_candidates(header, res.features)
        nonces = [c[0] for c in cands]
        total_cands += len(nonces)
        total_pythia += wins(header, target_int, nonces)
        if res.winning:
            o1_hits += 1
        for nonce, _c, method in cands:
            if wins(header, target_int, [nonce]):
                by_method[method] += 1
        rng = random.Random(i)
        total_random += wins(header, target_int, [rng.randrange(2**32) for _ in nonces])

    print()
    print(f"=== MEASURED over {N_BLOCKS} real mined blocks ===")
    print(f"  candidates/block      : {total_cands / N_BLOCKS:.1f}")
    print(f"  PYTHIA candidate hits : {total_pythia}")
    print(f"  random baseline hits  : {total_random}")
    print(f"  O(1) verified wins    : {o1_hits}/{N_BLOCKS}")
    n = total_cands
    p_pool = (total_pythia + total_random) / (2 * n)
    se = (p_pool * (1 - p_pool) * (2 / n)) ** 0.5
    z = (total_pythia / n - total_random / n) / se if se > 0 else 0.0
    print()
    print("=== TWO-PROPORTION Z-TEST (PYTHIA vs random, same cardinality) ===")
    print(
        f"  z = {z:+.3f}  -> "
        f"{'INDISTINGUISHABLE from random' if abs(z) < 1.96 else 'SIGNIFICANT'}"
    )
    print()
    print("=== per-strategy attribution ===")
    for m, c in by_method.most_common():
        print(f"  {m:28} {c}")
    sys.stdout.flush()
