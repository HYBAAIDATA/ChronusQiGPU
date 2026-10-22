"""Counterfactual: 11D geodesic vs M32 lane vs linear nonce order.

All arms iterate the SAME nonce set [0, window) on the SAME fixed header —
only traversal order differs. The 11D arm is the Poincaré–Cassini shard
order: the header folds into the 11D golden ball, face affinities rank the
32-face compass, and Cassini-certified affine permutations (stride coprime
to shard width) give complete coverage. An easy synthetic target (hit
probability ~1/TARGET_DIV per hash) makes qualifying nonces frequent enough
to count, so the comparison is measurable rather than asserted. SHA256d
digests are pseudorandom, so the expected honest result is no systematic
advantage for any ordering; this script exists to MEASURE that, not assume it.

Reports per arm: hashes attempted, qualifying hits found, stream position of
first hit, wall time, measured H/s. truth_class: measured_hardware.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mining.hash_pipeline import HashPipeline


def _target_from_divisor(divisor: int) -> bytes:
    """32-byte big-endian target with hit probability ~1/divisor."""
    return (max(1, (1 << 256) // divisor)).to_bytes(32, "big")


def _ordered_nonces(order: str, count: int, header80: bytes) -> list[int]:
    from mining.stratum_bridge import _lane_nonces

    return _lane_nonces(0, count, header80=header80, order=order)


def run_arm(pipeline: HashPipeline, header80: bytes, target_be: bytes,
            order: str, window: int, batch: int) -> dict:
    nonces = _ordered_nonces(order, window, header80)
    hits = 0
    first_hit_index = None
    t0 = time.perf_counter()
    done = 0
    for lo in range(0, window, batch):
        chunk = nonces[lo : lo + batch]
        winner, _h, n = pipeline.hasher.grind_target_batch(header80, target_be, chunk)
        done += n
        if winner is not None:
            hits += 1
            if first_hit_index is None:
                first_hit_index = chunk.index(winner) + lo
    elapsed = time.perf_counter() - t0
    return {
        "order": order,
        "hashes": done,
        "hits": hits,
        "first_hit_stream_index": first_hit_index,
        "wall_seconds": round(elapsed, 3),
        "measured_hps": round(done / elapsed, 1) if elapsed > 0 else 0.0,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--window", type=int, default=2_000_000)
    ap.add_argument("--batch", type=int, default=4096)
    ap.add_argument("--target-div", type=int, default=4096,
                    help="hit probability ~1/div per hash")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    header80 = bytes(range(80))  # fixed synthetic header; identical all arms
    target_be = _target_from_divisor(args.target_div)
    pipeline = HashPipeline()

    arms = [
        run_arm(pipeline, header80, target_be, "11d", args.window, args.batch),
        run_arm(pipeline, header80, target_be, "m32", args.window, args.batch),
        run_arm(pipeline, header80, target_be, "linear", args.window, args.batch),
    ]
    out = {
        "device": getattr(pipeline.hasher, "device", "unknown"),
        "backend": getattr(pipeline.hasher, "backend", "unknown"),
        "window": args.window,
        "batch": args.batch,
        "hit_probability_per_hash": f"~1/{args.target_div}",
        "expected_hits_per_arm": round(args.window / args.target_div, 1),
        "arms": arms,
        "truth_class": "measured_hardware",
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
