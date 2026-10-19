"""A/B/C/E multi-arm allocation probe, adjudicated by the Euclid instrument.

Four candidate orderings traverse the SAME nonce window on the SAME real
Stratum job headers, so the qualifying-nonce set is identical across arms by
construction. The discriminating statistic is the normalised STREAM POSITION
of each hit — the same instrument as ``mining.resonance_probe``.

Arms:
  A  linear            exhaustive control (nonce = base + i)
  B  m32               declared M32 lane allocation (solver ordering)
  C  11d               Poincaré–Cassini 11D shard ordering
  E  lucas76_hendrix   the deployed scaled-execution order: coprime-stride
                       permutation from HendrixStructuredSearch at Lucas
                       scale index 76 (the physical-dispatch contract)

Null hypothesis (SHA256d digests pseudorandom w.r.t. traversal order):
    hit positions ~ Uniform(0,1); mean 0.5, KS ~ small.
The 3-SE decision rule flags SIGNAL only if a pooled mean deviates from 0.5
by more than three standard errors — the same adjudication the resonance
probe applies. A null result means an ordering is coverage structure and
allocation discipline, honestly labelled — never a claim of hash advantage.

    python -m mining.euclid_multarm_probe --headers experiments/resonance_headers.json \
        --window 4000000 --target-div 1024 --decide
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Dict, List

import numpy as np

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from lucas.pisot import HendrixStructuredSearch
from mining.resonance_probe import (
    _hit_indices,
    _ks_uniform_pvalue,
    _missing_job_ids,
    _positions_stats,
    _target_from_divisor,
)
from mining.stratum_bridge import _lane_nonces

ARMS = ("A", "B", "C", "E")
_ARM_ORDER = {"A": "linear", "B": "m32", "C": "11d"}


def _euclid_stream(window: int, scale_index: int = 76) -> np.ndarray:
    """Arm E: the Hendrix Lucas-scaled coprime-stride permutation.

    This is the ordering the scaled-execution adapter physically dispatches:
    ``nonce_at(pos) = (pos * stride) mod window`` with stride coprime to the
    window, so coverage is a verified bijection.
    """
    schedule = HendrixStructuredSearch(workers=1, scale_index=scale_index).plan(window)
    if not schedule.verify():
        raise RuntimeError("Euclid schedule invariant failure")
    return np.fromiter(
        (schedule.nonce_at(pos) for pos in range(window)),
        dtype=np.uint32,
        count=window,
    )


def _arm_stream(arm: str, window: int, header80: bytes) -> np.ndarray:
    if arm == "E":
        return _euclid_stream(window)
    return np.asarray(
        _lane_nonces(0, window, header80=header80, order=_ARM_ORDER[arm]),
        dtype=np.uint32,
    )


def _arm_stats(
    arm: str, window: int, header80: bytes, hits: np.ndarray
) -> tuple[Dict[str, object], np.ndarray]:
    t0 = time.perf_counter()
    stream = _arm_stream(arm, window, header80)
    enum_s = time.perf_counter() - t0
    inv = np.empty(window, dtype=np.uint32)
    inv[stream] = np.arange(window, dtype=np.uint32)
    verified = bool(
        stream.size == window
        and np.array_equal(np.unique(stream), np.arange(window, dtype=np.uint32))
    )
    positions = inv[hits] / window if hits.size else np.empty(0)
    stats = _positions_stats(positions)
    stats["enumerate_seconds"] = round(enum_s, 3)
    stats["permutation_verified"] = verified
    return stats, positions


def probe(
    headers: List[Dict[str, str]],
    window: int,
    target_div: int,
    backend: str,
    cache_path: str = "experiments/resonance_hits.npz",
) -> Dict[str, object]:
    from mining.bitcoin_hasher import BitcoinHasher

    hasher = BitcoinHasher(backend=backend)
    target_be = _target_from_divisor(target_div)
    per_header: List[Dict[str, object]] = []
    pooled: Dict[str, List[float]] = {a: [] for a in ARMS}

    cache: Dict[str, np.ndarray] = {}
    if os.path.isfile(cache_path):
        cache = dict(np.load(cache_path, allow_pickle=False))
    cache_key_prefix = f"w{window}_d{target_div}_"

    for idx, rec in enumerate(headers):
        header80 = bytes.fromhex(rec["header80"])
        key = cache_key_prefix + rec["header80"]
        hits = (
            cache[key]
            if key in cache
            else _hit_indices(hasher, header80, target_be, window).astype(np.uint32)
        )
        cache[key] = hits
        row: Dict[str, object] = {"job_id": rec.get("job_id"), "n_hits": int(hits.size), "arms": {}}
        for arm in ARMS:
            stats, positions = _arm_stats(arm, window, header80, hits)
            row["arms"][arm] = stats
            pooled[arm].extend(positions.tolist())
        per_header.append(row)
        print(
            f"header {idx + 1}/{len(headers)} job={rec.get('job_id')} hits={hits.size} "
            + " ".join(
                f"{a}:mean={row['arms'][a].get('mean_norm_pos', float('nan')):.4f}" for a in ARMS
            ),
            file=sys.stderr,
        )

    pooled_stats: Dict[str, object] = {}
    for arm in ARMS:
        arr = np.asarray(pooled[arm], dtype=np.float64)
        stats = _positions_stats(arr)
        stats["mean_se"] = float(1.0 / np.sqrt(12.0 * max(arr.size, 1)))
        stats["ks_pvalue"] = _ks_uniform_pvalue(arr) if arr.size else None
        pooled_stats[arm] = stats

    np.savez(cache_path, **cache)

    return {
        "device": hasher.device,
        "backend": hasher.backend,
        "window": window,
        "target_div": target_div,
        "expected_hits_per_header": round(window / target_div, 1),
        "headers": len(headers),
        "total_hits": int(sum(r["n_hits"] for r in per_header)),
        "captured_job_ids": [rec.get("job_id") for rec in headers],
        "missing_job_ids": _missing_job_ids(headers),
        "arms": {
            "A": "linear exhaustive control",
            "B": "m32 declared lane allocation",
            "C": "poincare-cassini 11d shard ordering",
            "E": "lucas76 hendrix coprime-stride (deployed scaled execution)",
        },
        "null_model": "hit stream positions ~ Uniform(0,1); mean 0.5",
        "pooled": pooled_stats,
        "per_header": per_header,
        "truth_class": "measured_hardware",
        "method_notes": [
            "identical hit sets across arms by construction; only stream "
            "position discriminates orderings",
            "ordering cannot change the sha256d accept predicate — this "
            "instrument measures search-order structure, not advantage",
            "arm E is the physical-dispatch permutation used by "
            "mining.scaled_execution (Lucas index 76, gcd(stride,window)=1)",
        ],
    }


def _decide(result: Dict[str, object]) -> Dict[str, object]:
    """3-SE adjudication, identical rule to the resonance probe."""
    verdicts: Dict[str, object] = {}
    signal = False
    for arm in ARMS:
        s = result["pooled"].get(arm) or {}
        if not s.get("n_hits"):
            continue
        dev = abs(float(s["mean_norm_pos"]) - 0.5)
        thresh = 3.0 * float(s["mean_se"])
        flag = dev > thresh
        signal = signal or flag
        verdicts[arm] = {
            "mean_pos": s["mean_norm_pos"],
            "deviation_from_0.5": dev,
            "threshold_3se": thresh,
            "signal": flag,
        }
    return {
        "rule": "SIGNAL iff |mean_pos - 0.5| > 3*SE",
        "signal_detected": signal,
        "action_if_signal": "ordering earns production-default candidacy",
        "action_if_null": "ordering remains coverage structure, honestly labeled",
        "verdicts": verdicts,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--headers", default="experiments/resonance_headers.json")
    ap.add_argument("--window", type=int, default=4_000_000)
    ap.add_argument("--target-div", type=int, default=1024)
    ap.add_argument("--backend", default=os.getenv("PYTHIA_HASH_BACKEND", "auto"))
    ap.add_argument("--cache", default="experiments/resonance_hits.npz")
    ap.add_argument("--result-out", default=None)
    ap.add_argument("--decide", action="store_true")
    args = ap.parse_args()

    with open(args.headers, "r", encoding="utf-8") as fh:
        headers = json.load(fh)
    result = probe(headers, args.window, args.target_div, args.backend, cache_path=args.cache)
    if args.decide:
        result["decision"] = _decide(result)
        signal = bool(result["decision"]["signal_detected"])
        print(f"[DECIDE] signal_detected={signal}", file=sys.stderr)
    else:
        signal = False
    payload = json.dumps(result, indent=2)
    if args.result_out:
        with open(args.result_out, "w", encoding="utf-8") as fh:
            fh.write(payload)
        print(f"result -> {args.result_out}", file=sys.stderr)
    print(payload)
    return 2 if (args.decide and signal) else 0


if __name__ == "__main__":
    raise SystemExit(main())
