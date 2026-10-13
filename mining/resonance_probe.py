"""Resonance probe — does the 11D manifold ordering rank winning nonces early?

Every ordering arm iterates the SAME nonce window [0, window): the set of
qualifying nonces is identical by construction, so hit COUNT cannot
discriminate orderings. The discriminating statistic is the STREAM POSITION
of each qualifying nonce inside a given ordering.

Null hypothesis (SHA256d digests pseudorandom w.r.t. traversal order):
    hit positions ~ Uniform(0, window)  →  mean normalized position = 0.5
Resonance hypothesis (manifold ordering tracks real digest structure):
    the 11d arm systematically places hits early  →  mean position < 0.5

The linear arm doubles as a harness sanity check: its stream position IS the
nonce offset, so non-uniformity there would indicate nonce-space clustering
(or a broken probe) rather than ordering resonance.

Headers are REAL pool jobs captured over Stratum V1 (``--capture``), built
through the same ``build_job_header`` wire path the production miner uses.
Targets are synthetic (``--target-div``) purely to collect enough hits for
statistics — structure in the digest space would appear at any threshold.

    python -m mining.resonance_probe --capture 10 --out headers.json
    python -m mining.resonance_probe --headers headers.json --window 4000000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from typing import Dict, List

import numpy as np

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mining.bitcoin_hasher import BitcoinHasher, MAX_BATCH
from mining.production_miner import (
    StratumV1Client,
    build_job_header,
    parse_endpoint,
)
from mining.stratum_bridge import _lane_nonces

ORDERS = ("11d", "m32", "linear")


def _face_affinity_stats(header80: bytes, hits: np.ndarray, window: int) -> Dict[str, object]:
    """Does the header-affinity ranking predict WHERE hits live?

    The 32 faces partition [0, window) into near-equal shards; _rank_faces
    orders them by golden-metric affinity to the header's folded 11D
    direction.  Under the null each shard holds ~hits/32 qualifying nonces.
    Resonance predicts enrichment on the top-ranked faces.

    Reports: per-face hit counts in affinity order, the enrichment ratio of
    the top-8 faces vs their 25% share expectation, and a Spearman
    correlation between affinity rank and hit density.
    """
    from Intelligence.search_crystal import PoincareCassiniSearchEngine

    engine = PoincareCassiniSearchEngine(total_nonce_space=window, nonce_start=0)
    ranked = engine._rank_faces(header80[:76])
    counts = np.zeros(32, dtype=np.int64)
    for face in ranked:
        iv = engine.partitions[face.face_id]
        counts[face.face_id] = int(
            np.count_nonzero((hits >= iv.start) & (hits < iv.stop))
        )
    ranked_counts = np.array([counts[f.face_id] for f in ranked], dtype=np.float64)
    total = float(ranked_counts.sum())
    top8_share = float(ranked_counts[:8].sum() / total) if total else None
    widths = np.array(
        [engine.partitions[f.face_id].size for f in ranked], dtype=np.float64
    )
    density = ranked_counts / np.maximum(widths, 1.0)
    ranks = np.arange(32, dtype=np.float64)
    rho = None
    if total and float(density.std()) > 0:
        order_by_density = np.argsort(np.argsort(-density))
        order_by_rank = np.argsort(np.argsort(ranks))
        rho = float(np.corrcoef(order_by_rank, order_by_density)[0, 1])
    return {
        "hits_per_face_affinity_order": ranked_counts.astype(int).tolist(),
        "top8_hit_share": top8_share,
        "top8_expected_share": 0.25,
        "spearman_rank_vs_density": rho,
        "null_model": "hits uniform across near-equal face shards",
    }


def _target_from_divisor(divisor: int) -> bytes:
    return (max(1, (1 << 256) // divisor)).to_bytes(32, "big")


def _load_env_file() -> None:
    """Populate os.environ from .env.braiins/.env for capture mode only.

    Values are never logged; existing environment variables win."""
    for name in (".env.braiins", ".env"):
        path = os.path.join(_PROJECT_ROOT, name)
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                if key and key not in os.environ:
                    os.environ[key] = value.strip().strip('"').strip("'")


async def _capture(n: int, seconds: float, out_path: str) -> None:
    _load_env_file()
    endpoint = parse_endpoint(os.environ["PYTHIA_STRATUM_ENDPOINT"])
    client = StratumV1Client(
        endpoint,
        os.environ["PYTHIA_STRATUM_WORKER"],
        os.environ["PYTHIA_STRATUM_PASSWORD"],
    )
    await client.connect_and_authorize()
    extranonce2 = "00" * client.extranonce2_size
    headers: List[Dict[str, str]] = []
    seen: set = set()
    deadline = time.monotonic() + seconds
    try:
        while len(headers) < n and time.monotonic() < deadline:
            gen = client.generation
            while client.generation == gen and time.monotonic() < deadline:
                await asyncio.sleep(0.2)
            job = client.job
            if job is None or job.job_id in seen:
                continue
            seen.add(job.job_id)
            header80 = build_job_header(job, client.extranonce1, extranonce2)
            headers.append({
                "job_id": job.job_id,
                "header80": header80.hex(),
                "nbits": job.nbits,
            })
            print(f"captured job={job.job_id} ({len(headers)}/{n})", file=sys.stderr)
    finally:
        await client.close()
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(headers, fh, indent=2)
    print(f"wrote {len(headers)} headers -> {out_path}", file=sys.stderr)


def _hit_indices(hasher: BitcoinHasher, header80: bytes, target_be: bytes,
                 window: int) -> np.ndarray:
    """All nonce offsets in [0, window) whose sha256d digest meets target."""
    tgt = np.frombuffer(target_be, np.uint8)
    hits: List[np.ndarray] = []
    for lo in range(0, window, MAX_BATCH):
        hi = min(lo + MAX_BATCH, window)
        nonces = np.arange(lo, hi, dtype=np.uint32)
        digests = hasher.hash_batch(header80, nonces)
        # Consensus order: digest byte-reversed, lexicographic <= target.
        arr = np.frombuffer(b"".join(digests), np.uint8).reshape(-1, 32)[:, ::-1]
        neq = arr != tgt
        has_diff = neq.any(axis=1)
        first = neq.argmax(axis=1)
        rows = np.arange(arr.shape[0])
        lt = has_diff & (arr[rows, first] < tgt[first])
        eq = ~has_diff
        hit_flags = lt | eq
        hits.append(np.nonzero(hit_flags)[0] + lo)
    return np.concatenate(hits) if hits else np.empty(0, dtype=np.int64)


def _position_map(order: str, window: int, header80: bytes) -> np.ndarray:
    """Inverse map: nonce offset -> stream position under `order`."""
    stream = np.asarray(
        _lane_nonces(0, window, header80=header80, order=order), dtype=np.uint32
    )
    inv = np.empty(window, dtype=np.uint32)
    inv[stream] = np.arange(window, dtype=np.uint32)
    return inv


def _verify_permutation(order: str, window: int, header80: bytes) -> bool:
    """Measured coverage check: `order` enumerates a true bijection on
    [0, window). Asserted per header — coverage is verified, not assumed."""
    stream = np.asarray(
        _lane_nonces(0, window, header80=header80, order=order), dtype=np.uint32
    )
    if stream.size != window:
        return False
    return bool(np.array_equal(np.unique(stream), np.arange(window, dtype=np.uint32)))


def _missing_job_ids(headers: List[Dict[str, str]]) -> List[str]:
    """Disclosure: hex job ids captured vs expected contiguous range."""
    try:
        ids = sorted(int(rec["job_id"], 16) for rec in headers)
    except (KeyError, ValueError):
        return []
    return [f"{x:02x}" for x in range(ids[0], ids[-1] + 1) if x not in ids]


def _positions_stats(norm_positions: np.ndarray) -> Dict[str, float]:
    n = int(norm_positions.size)
    if n == 0:
        return {"n_hits": 0}
    ordered = np.sort(norm_positions)
    ecdf = np.arange(1, n + 1) / n
    ks = float(
        max(np.max(np.abs(ecdf - ordered)), np.max(np.abs(ordered - (ecdf - 1.0 / n))))
    )
    return {
        "n_hits": n,
        "mean_norm_pos": float(norm_positions.mean()),
        "median_norm_pos": float(np.median(norm_positions)),
        "first_norm_pos": float(norm_positions.min()),
        "ks_vs_uniform": ks,
    }


def probe(headers: List[Dict[str, str]], window: int, target_div: int,
          backend: str, cache_path: str = "experiments/resonance_hits.npz") -> Dict[str, object]:
    hasher = BitcoinHasher(backend=backend)
    target_be = _target_from_divisor(target_div)
    per_header: List[Dict[str, object]] = []
    pooled: Dict[str, List[float]] = {o: [] for o in ORDERS}
    face_rows: List[Dict[str, object]] = []

    cache: Dict[str, np.ndarray] = {}
    if os.path.isfile(cache_path):
        cache = dict(np.load(cache_path, allow_pickle=False))
    cache_key_prefix = f"w{window}_d{target_div}_"

    for idx, rec in enumerate(headers):
        header80 = bytes.fromhex(rec["header80"])
        key = cache_key_prefix + rec["header80"]
        if key in cache:
            hits = cache[key]
        else:
            hits = _hit_indices(hasher, header80, target_be, window)
            cache[key] = hits.astype(np.uint32)
        row: Dict[str, object] = {
            "job_id": rec.get("job_id"), "n_hits": int(hits.size), "arms": {}
        }
        face_stats = _face_affinity_stats(header80, hits, window)
        row["face_affinity"] = face_stats
        face_rows.append(face_stats)
        for order in ORDERS:
            t0 = time.perf_counter()
            inv = _position_map(order, window, header80)
            enum_s = time.perf_counter() - t0
            stats = _positions_stats(inv[hits] / window if hits.size else np.empty(0))
            stats["enumerate_seconds"] = round(enum_s, 3)
            stats["permutation_verified"] = _verify_permutation(order, window, header80)
            row["arms"][order] = stats
            pooled[order].extend((inv[hits] / window).tolist())
        per_header.append(row)
        print(
            f"header {idx + 1}/{len(headers)} job={rec.get('job_id')} "
            f"hits={hits.size} "
            + " ".join(
                f"{o}:mean={row['arms'][o].get('mean_norm_pos', float('nan')):.4f}"
                for o in ORDERS
            ),
            file=sys.stderr,
        )

    pooled_stats: Dict[str, object] = {}
    n_hits_total = int(sum(r["n_hits"] for r in per_header))
    for order in ORDERS:
        arr = np.asarray(pooled[order], dtype=np.float64)
        stats = _positions_stats(arr)
        stats["mean_se"] = float(1.0 / np.sqrt(12.0 * max(arr.size, 1)))
        stats["ks_pvalue"] = _ks_uniform_pvalue(arr) if arr.size else None
        pooled_stats[order] = stats

    np.savez(cache_path, **cache)

    top8 = np.array(
        [f["top8_hit_share"] for f in face_rows if f["top8_hit_share"] is not None],
        dtype=np.float64,
    )
    rhos = np.array(
        [f["spearman_rank_vs_density"] for f in face_rows
         if f["spearman_rank_vs_density"] is not None],
        dtype=np.float64,
    )
    face_pooled = {
        "top8_hit_share_mean": float(top8.mean()) if top8.size else None,
        "top8_hit_share_se": float(top8.std(ddof=1) / np.sqrt(top8.size))
        if top8.size > 1 else None,
        "top8_expected_share": 0.25,
        "spearman_mean": float(rhos.mean()) if rhos.size else None,
        "spearman_se": float(rhos.std(ddof=1) / np.sqrt(rhos.size))
        if rhos.size > 1 else None,
        "null_model": "hits uniform across faces; top8 share 0.25; rho ~ 0",
    }

    return {
        "device": hasher.device,
        "backend": hasher.backend,
        "window": window,
        "target_div": target_div,
        "expected_hits_per_header": round(window / target_div, 1),
        "headers": len(headers),
        "total_hits": n_hits_total,
        "captured_job_ids": [rec.get("job_id") for rec in headers],
        "missing_job_ids": _missing_job_ids(headers),
        "null_model": "hit stream positions ~ Uniform(0,1); mean 0.5",
        "pooled": pooled_stats,
        "face_affinity_pooled": face_pooled,
        "per_header": per_header,
        "truth_class": "measured_hardware",
        "method_notes": [
            "headers are stratum job templates (coinbase/merkle-derived), "
            "not bare chain headers",
            "m32 and linear arms are near-degenerate at this window "
            "(same shard stride; they are not independent instruments)",
            "stream-position measures face_id-order enumeration; affinity "
            "rank ordering enters only via the face-affinity instrument",
            "hit sets are identical across arms by construction — the "
            "permutation_verified flags are the measured coverage assertion",
        ],
    }


def _ks_uniform_pvalue(arr: np.ndarray) -> float:
    """One-sample KS test against U(0,1), NumPy-only.

    D = max|F_emp - x|; p-value via the Kolmogorov limiting distribution
    Q(lambda) = 2 * sum_{k>=1} (-1)^(k-1) exp(-2 k^2 lambda^2) with the
    Stephens lambda correction (sqrt(n) + 0.12 + 0.11/sqrt(n)) * D.
    Matches scipy.stats.kstest(arr, 'uniform') to ~1e-3 at these n.
    """
    n = int(arr.size)
    if n == 0:
        return 1.0
    xs = np.sort(np.asarray(arr, dtype=np.float64))
    i = np.arange(1, n + 1, dtype=np.float64)
    d = float(max(np.max(i / n - xs), np.max(xs - (i - 1.0) / n)))
    lam = (np.sqrt(n) + 0.12 + 0.11 / np.sqrt(n)) * d
    # Kolmogorov series; converges fast, k=100 is overkill
    k = np.arange(1, 101, dtype=np.float64)
    terms = ((-1.0) ** (k - 1)) * np.exp(-2.0 * k * k * lam * lam)
    p = float(2.0 * np.sum(terms))
    return min(max(p, 0.0), 1.0)


def _decide(result: Dict[str, object]) -> Dict[str, object]:
    """The 3-SE decision rule for the resonance claim — real code, not prose.

    SIGNAL (ordering should become production default) iff either:
      * any arm's pooled mean hit position deviates from 0.5 by > 3 SE, or
      * the pooled top-8 face hit share deviates from 0.25 by > 3 SE.
    """
    verdicts: Dict[str, object] = {}
    signal = False
    for order in ORDERS:
        s = result["pooled"].get(order) or {}
        if not s.get("n_hits"):
            continue
        dev = abs(float(s["mean_norm_pos"]) - 0.5)
        thresh = 3.0 * float(s["mean_se"])
        flag = dev > thresh
        signal = signal or flag
        verdicts[order] = {
            "mean_pos": s["mean_norm_pos"],
            "deviation_from_0.5": dev,
            "threshold_3se": thresh,
            "signal": flag,
        }
    fa = result.get("face_affinity_pooled") or {}
    if fa.get("top8_hit_share_mean") is not None and fa.get("top8_hit_share_se"):
        dev = abs(float(fa["top8_hit_share_mean"]) - float(fa["top8_expected_share"]))
        thresh = 3.0 * float(fa["top8_hit_share_se"])
        flag = dev > thresh
        signal = signal or flag
        verdicts["face_top8_share"] = {
            "share": fa["top8_hit_share_mean"],
            "deviation_from_expected": dev,
            "threshold_3se": thresh,
            "signal": flag,
        }
    return {
        "rule": "SIGNAL iff |mean_pos - 0.5| > 3*SE or |top8_share - 0.25| > 3*SE",
        "signal_detected": signal,
        "action_if_signal": "ordering earns production-default candidacy",
        "action_if_null": "ordering remains coverage structure, honestly labeled",
        "verdicts": verdicts,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--capture", type=int, default=0,
                    help="capture N live headers from the pool, then exit")
    ap.add_argument("--seconds", type=float, default=300.0,
                    help="capture deadline")
    ap.add_argument("--headers", default="experiments/resonance_headers.json")
    ap.add_argument("--out", default="experiments/resonance_headers.json")
    ap.add_argument("--window", type=int, default=4_000_000)
    ap.add_argument("--target-div", type=int, default=1024)
    ap.add_argument("--backend", default=os.getenv("PYTHIA_HASH_BACKEND", "auto"))
    ap.add_argument("--result-out", default=None,
                    help="write result JSON to this file (stdout prints it too)")
    ap.add_argument("--decide", action="store_true",
                    help="apply the 3-SE decision rule; exit 2 on SIGNAL")
    ap.add_argument("--cache", default="experiments/resonance_hits.npz",
                    help="hit-set cache path (keyed by window/div/full header)")
    args = ap.parse_args()

    if args.capture:
        asyncio.run(_capture(args.capture, args.seconds, args.out))
        return 0

    with open(args.headers, "r", encoding="utf-8") as fh:
        headers = json.load(fh)
    result = probe(headers, args.window, args.target_div, args.backend,
                   cache_path=args.cache)
    if args.decide:
        result["decision"] = _decide(result)
        signal = bool(result["decision"]["signal_detected"])
        print(
            f"[DECIDE] signal_detected={signal} "
            f"({result['decision']['rule']})",
            file=sys.stderr,
        )
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
