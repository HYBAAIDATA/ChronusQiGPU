"""Adaptive φ-compression — signal-aware routing pipeline.

Doctrine: compress by folding, not by truncating.

Route logic:
  - STRUCTURED (sine, financial, φ-cascade) → φ-fold → sparsify → zlib
  - HIGH-ENTROPY (noise, dense embeddings) → float16 + zlib (no fold —
    folding noise is thermodynamically counterproductive)
  - BATCH EMBEDDING (2D) → across-batch SVD → quantize components → zlib

The fold path uses progressive pair-folding to concentrate signal energy
in a compact coarse layer, then sparsifies residuals before entropy coding.
"""

from __future__ import annotations

import zlib
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

import numpy as np

from pulvini.folding_engine.kernels_core import progressive_fold, progressive_unfold


@dataclass
class CompressResult:
    mode: str
    original_bytes: int
    compressed_bytes: int
    bits_per_sample: float
    recon_error: float
    route_reason: str
    payload: Dict[str, Any]
    compressed_blob: Optional[bytes] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d["compressed_blob"] is not None:
            d["compressed_blob"] = d["compressed_blob"].hex()[:64] + "..."
        return d


# ── signal analysis ──────────────────────────────────────────────────


def _fold_features(x: np.ndarray, depth: int = 4) -> Dict[str, float]:
    """Energy concentration features from progressive fold pyramid."""
    folded = progressive_fold(x, depth=depth)
    coarse = np.asarray(folded["coarse"], dtype=np.float64).ravel()
    residuals = [np.asarray(r, dtype=np.float64).ravel() for r in folded["residuals"]]

    # Sparsity at 5% of max residual amplitude
    all_res = np.concatenate([r for r in residuals if r.size > 0]) if residuals else np.zeros(1)
    abs_max = float(np.max(np.abs(all_res)))
    nnz_5 = int(np.count_nonzero(np.abs(all_res) > 0.05 * abs_max)) if abs_max > 1e-15 else 0
    sparsity = 1.0 - nnz_5 / all_res.size if all_res.size > 0 else 0.0

    # Coarse energy fraction — how much signal energy concentrates in the folding
    coarse_energy = float(np.sum(coarse**2))
    res_energy = float(sum(np.sum(r**2) for r in residuals))
    total = coarse_energy + res_energy
    coarse_frac = coarse_energy / total if total > 1e-15 else 0.0

    # Autocorrelation lag-1 entropy proxy
    x_flat = x.ravel()
    xc = x_flat - x_flat.mean()
    denom = float(np.dot(xc, xc))
    ac1 = float(np.dot(xc[1:], xc[:-1]) / denom) if denom > 1e-15 else 0.0
    entropy_proxy = 1.0 - abs(ac1)

    return {
        "sparsity_05": sparsity,
        "entropy_proxy": entropy_proxy,
        "coarse_energy_frac": coarse_frac,
    }


def classify_signal(x: np.ndarray) -> Dict[str, Any]:
    """Return route + diagnostics.

    Routing decision: fold only when BOTH conditions hold:
      - Fold residual sparsity > 25% (meaningful structure)
      - Entropy proxy < 0.80 (not noise-like)

    This dual gate prevents noise from slipping through on sparsity alone.
    """
    x = np.asarray(x, dtype=np.float64)
    feat = _fold_features(x.ravel() if x.ndim > 1 else x, depth=4)
    sparsity = feat["sparsity_05"]
    entropy = feat["entropy_proxy"]
    coarse_frac = feat["coarse_energy_frac"]

    # Dual gate: need BOTH sparsity AND low entropy to fold
    sparsity_ok = sparsity > 0.25
    entropy_ok = entropy < 0.80

    if sparsity_ok and entropy_ok:
        route = "fold"
        reason = f"structured: sparse={sparsity:.1%} entropy={entropy:.3f} coarse={coarse_frac:.1%}"
    elif sparsity_ok:
        # Sparse but high entropy → noise-like artifacts, don't fold
        route = "entropy_raw"
        reason = f"sparse but high entropy: sparse={sparsity:.1%} entropy={entropy:.3f}"
    else:
        route = "entropy_raw"
        reason = f"low structure: sparse={sparsity:.1%} entropy={entropy:.3f}"

    result = {"route": route, "reason": reason, **feat}
    return result


# ── codec paths ───────────────────────────────────────────────────────


def _pack_residuals(residuals: list) -> bytes:
    """Sparse-encode residual pyramid → flat bytes."""
    parts = []
    for r in residuals:
        r = np.asarray(r, dtype=np.float64).ravel()
        mask = r != 0.0
        idx = np.where(mask)[0]
        vals = r[mask]
        parts.append(np.int32(r.size).tobytes())
        parts.append(np.int32(len(idx)).tobytes())
        if len(idx) > 0:
            parts.append(idx.astype(np.int32).tobytes())
            parts.append(vals.astype(np.float16).tobytes())
    return b"".join(parts)


def _unpack_residuals(data: bytes, offset: int) -> tuple[list, int]:
    """Decode sparse residual pyramid. Returns (residuals, new_offset)."""
    residuals = []
    while offset + 8 <= len(data):
        r_size = int(np.frombuffer(data[offset : offset + 4], dtype=np.int32)[0])
        offset += 4
        n_nnz = int(np.frombuffer(data[offset : offset + 4], dtype=np.int32)[0])
        offset += 4

        r = np.zeros(r_size, dtype=np.float64)
        if n_nnz > 0:
            idx_end = offset + n_nnz * 4
            val_end = idx_end + n_nnz * 2
            if val_end > len(data):
                break
            idx = np.frombuffer(data[offset:idx_end], dtype=np.int32)
            vals = np.frombuffer(data[idx_end:val_end], dtype=np.float16).astype(np.float64)
            offset = val_end
            idx = idx[idx < r_size]
            vals = vals[: len(idx)]
            r[idx] = vals

        residuals.append(r)

        # Stop if we've read enough levels for the depth we expect
        # progressive_fold with depth=d produces d residuals.
        # We don't know depth a priori, so we read until data exhausted
        # or we encounter malformed bytes.
        if offset >= len(data):
            break

    return residuals, offset


def compress_fold(x: np.ndarray, depth: int = 4, rel_threshold: float = 0.05) -> CompressResult:
    """φ-fold path: progressive fold → sparsify → sparse-encode → zlib."""
    x = np.asarray(x, dtype=np.float64).ravel()
    n = x.size
    original_bytes = n * 8

    folded = progressive_fold(x, depth=depth)
    coarse = np.asarray(folded["coarse"], dtype=np.float64).ravel()
    residuals_raw = [np.asarray(r, dtype=np.float64).ravel() for r in folded["residuals"]]

    # Threshold relative to max residual amplitude
    all_res = np.concatenate([r for r in residuals_raw if r.size > 0]) if residuals_raw else np.zeros(1)
    abs_max = float(np.max(np.abs(all_res))) if all_res.size > 0 else 1.0
    thr = rel_threshold * abs_max

    # Sparsify: zero residuals below threshold
    residuals = []
    for r in residuals_raw:
        rc = r.copy()
        rc[np.abs(rc) < thr] = 0.0
        residuals.append(rc)

    # Pack: n(i32) + depth(i32) + coarse(f64) + residuals(sparse)
    header = np.int32(n).tobytes() + np.int32(len(residuals)).tobytes() + coarse.astype(np.float64).tobytes()
    res_body = _pack_residuals(residuals)
    compressed = zlib.compress(header + res_body, level=6)
    compressed_bytes = len(compressed)

    # Measure reconstruction error
    recon_folded = {
        "kind": "progressive_pair_fold",
        "coarse": coarse,
        "residuals": residuals,
        "n": n,
        "depth": len(residuals),
    }
    recon = progressive_unfold(recon_folded)[:n]
    err = float(np.max(np.abs(recon - x)))
    bits = compressed_bytes * 8 / max(n, 1)

    nnz_total = sum(int(np.count_nonzero(r)) for r in residuals)
    total_sz = sum(r.size for r in residuals)
    sparsity = 1.0 - nnz_total / max(total_sz, 1)

    return CompressResult(
        mode="fold",
        original_bytes=original_bytes,
        compressed_bytes=compressed_bytes,
        bits_per_sample=bits,
        recon_error=err,
        route_reason=f"φ-fold d={depth} thr={rel_threshold} sparse={sparsity:.1%}",
        payload={"n": n, "depth": depth, "rel_threshold": rel_threshold},
        compressed_blob=compressed,
    )


def decompress_fold(result: CompressResult) -> np.ndarray:
    """Decompress fold path."""
    if result.compressed_blob is None:
        raise ValueError("No compressed_blob")

    data = zlib.decompress(result.compressed_blob)
    offset = 0

    # Header
    n = int(np.frombuffer(data[offset : offset + 4], dtype=np.int32)[0])
    offset += 4
    depth = int(np.frombuffer(data[offset : offset + 4], dtype=np.int32)[0])
    offset += 4

    # Coarse layer size: ceil(n / 2^depth)
    coarse_size = max(1, (n + (1 << depth) - 1) >> depth)
    coarse = np.frombuffer(data[offset : offset + coarse_size * 8], dtype=np.float64)
    offset += coarse_size * 8

    # Residuals: read until we have depth levels or data exhausted
    all_residuals, _ = _unpack_residuals(data, offset)
    residuals = all_residuals[:depth]

    recon_folded = {
        "kind": "progressive_pair_fold",
        "coarse": coarse,
        "residuals": residuals,
        "n": n,
        "depth": min(len(residuals), depth),
    }
    return progressive_unfold(recon_folded)[:n]


def compress_entropy(x: np.ndarray) -> CompressResult:
    """float16 + zlib for high-entropy signals. No fold attempted."""
    x = np.asarray(x, dtype=np.float64).ravel()
    n = x.size
    original_bytes = n * 8

    raw = np.int32(n).tobytes() + x.astype(np.float16).tobytes()
    compressed = zlib.compress(raw, level=6)
    compressed_bytes = len(compressed)

    data = zlib.decompress(compressed)
    recon = np.frombuffer(data[4:], dtype=np.float16).astype(np.float64)[:n]
    err = float(np.max(np.abs(recon - x)))
    bits = compressed_bytes * 8 / max(n, 1)

    return CompressResult(
        mode="entropy_raw",
        original_bytes=original_bytes,
        compressed_bytes=compressed_bytes,
        bits_per_sample=bits,
        recon_error=err,
        route_reason="high entropy: float16+zlib (no fold)",
        payload={"n": n},
        compressed_blob=compressed,
    )


def decompress_entropy(result: CompressResult) -> np.ndarray:
    if result.compressed_blob is None:
        raise ValueError("No compressed_blob")
    data = zlib.decompress(result.compressed_blob)
    n = int(np.frombuffer(data[:4], dtype=np.int32)[0])
    return np.frombuffer(data[4:], dtype=np.float16).astype(np.float64)[:n]


def compress_batch(batch: np.ndarray) -> CompressResult:
    """Batch embedding: SVD fold across vectors."""
    batch = np.asarray(batch, dtype=np.float64)
    if batch.ndim != 2:
        return compress_entropy(batch.ravel())

    n_vecs, dim = batch.shape
    original_bytes = n_vecs * dim * 8

    mean_vec = batch.mean(axis=0)
    centered = batch - mean_vec

    try:
        U, S, Vt = np.linalg.svd(centered, full_matrices=False)
    except np.linalg.LinAlgError:
        return compress_entropy(batch.ravel())

    var_cumsum = np.cumsum(S**2)
    var_total = float(var_cumsum[-1]) if var_cumsum[-1] > 0 else 1.0
    k = int(np.searchsorted(var_cumsum / var_total, 0.95) + 1)
    k = max(1, min(k, min(n_vecs, dim) // 2))

    parts = [
        np.int32(n_vecs).tobytes(),
        np.int32(dim).tobytes(),
        np.int32(k).tobytes(),
        mean_vec.astype(np.float64).tobytes(),
        S[:k].astype(np.float64).tobytes(),
        U[:, :k].astype(np.float16).tobytes(),
        Vt[:k, :].astype(np.float16).tobytes(),
    ]
    compressed = zlib.compress(b"".join(parts), level=6)

    # Reconstruct for error
    data = zlib.decompress(compressed)
    off = 0
    nv_r = int(np.frombuffer(data[off:off+4], dtype=np.int32)[0]); off += 4
    dim_r = int(np.frombuffer(data[off:off+4], dtype=np.int32)[0]); off += 4
    k_r = int(np.frombuffer(data[off:off+4], dtype=np.int32)[0]); off += 4
    mean_r = np.frombuffer(data[off:off+dim_r*8], dtype=np.float64); off += dim_r*8
    S_r = np.frombuffer(data[off:off+k_r*8], dtype=np.float64); off += k_r*8
    U_r = np.frombuffer(data[off:off+nv_r*k_r*2], dtype=np.float16).reshape(nv_r, k_r).astype(np.float64)
    off += nv_r * k_r * 2
    Vt_r = np.frombuffer(data[off:off+k_r*dim_r*2], dtype=np.float16).reshape(k_r, dim_r).astype(np.float64)

    recon = mean_r + (U_r * S_r[None, :]) @ Vt_r
    err = float(np.max(np.abs(recon - batch)))
    bits = len(compressed) * 8 / max(nv_r * dim_r, 1)
    var_kept = float(var_cumsum[k_r-1] / var_total) if k_r > 0 else 0.0

    return CompressResult(
        mode="batch_fold",
        original_bytes=original_bytes,
        compressed_bytes=len(compressed),
        bits_per_sample=bits,
        recon_error=err,
        route_reason=f"batch SVD: rank {k_r}/{min(nv_r,dim_r)} ({var_kept:.1%} var)",
        payload={"k": k_r, "n_vecs": nv_r, "dim": dim_r, "variance_kept": var_kept},
        compressed_blob=compressed,
    )


def decompress_batch(result: CompressResult) -> np.ndarray:
    if result.compressed_blob is None:
        raise ValueError("No compressed_blob")
    data = zlib.decompress(result.compressed_blob)
    off = 0
    nv_r = int(np.frombuffer(data[off:off+4], dtype=np.int32)[0]); off += 4
    dim_r = int(np.frombuffer(data[off:off+4], dtype=np.int32)[0]); off += 4
    k_r = int(np.frombuffer(data[off:off+4], dtype=np.int32)[0]); off += 4
    mean_r = np.frombuffer(data[off:off+dim_r*8], dtype=np.float64); off += dim_r*8
    S_r = np.frombuffer(data[off:off+k_r*8], dtype=np.float64); off += k_r*8
    U_r = np.frombuffer(data[off:off+nv_r*k_r*2], dtype=np.float16).reshape(nv_r, k_r).astype(np.float64)
    off += nv_r * k_r * 2
    Vt_r = np.frombuffer(data[off:off+k_r*dim_r*2], dtype=np.float16).reshape(k_r, dim_r).astype(np.float64)
    return mean_r + (U_r * S_r[None, :]) @ Vt_r


# ── Adaptive compressor ───────────────────────────────────────────────


class AdaptivePhiCompressor:
    """Signal-aware φ-compression: route → fold / entropy / batch."""

    def __init__(self, depth: int = 4, rel_threshold: float = 0.05):
        self.depth = depth
        self.rel_threshold = rel_threshold

    def classify(self, x: np.ndarray) -> Dict[str, Any]:
        return classify_signal(np.asarray(x, dtype=np.float64))

    def compress(self, data: np.ndarray, *, mode: Optional[str] = None) -> CompressResult:
        x = np.asarray(data, dtype=np.float64)

        if mode:
            if mode == "fold":
                return compress_fold(x.ravel(), self.depth, self.rel_threshold)
            if mode == "entropy_raw":
                return compress_entropy(x.ravel())
            if mode == "batch_fold":
                return compress_batch(x)

        # Auto-route: 2D array → try batch first
        if x.ndim == 2 and x.shape[0] >= 4 and min(x.shape) >= 8:
            info = classify_signal(x.ravel())
            if info["route"] == "entropy_raw":
                return compress_batch(x)
            return compress_fold(x.ravel(), self.depth, self.rel_threshold)

        info = classify_signal(x.ravel())
        if info["route"] == "fold":
            return compress_fold(x.ravel(), self.depth, self.rel_threshold)
        return compress_entropy(x.ravel())

    def decompress(self, result: CompressResult) -> np.ndarray:
        if result.mode == "fold":
            return decompress_fold(result)
        if result.mode == "entropy_raw":
            return decompress_entropy(result)
        if result.mode == "batch_fold":
            return decompress_batch(result)
        raise ValueError(f"Unknown mode: {result.mode}")


# ── benchmark ──────────────────────────────────────────────────────────


def run_adaptive_benchmark() -> Dict[str, Any]:
    import time

    rng = np.random.default_rng(42)
    N = 4096
    t = np.linspace(0, 64 * np.pi, N)

    signals = {
        "financial": np.sin(t) * np.exp(-0.02 * t) + 0.05 * np.sin(7 * t),
        "phi_cascade": np.sin(t) + 0.5 * np.sin(1.618033988749895 * t),
        "gaussian": rng.normal(0.5, 0.15, N),
        "chirp": np.sin(np.linspace(0, 20 * np.pi, N) ** 1.3),
        "speech_like": np.convolve(
            rng.normal(0, 1, N + 100), np.hamming(100), mode="valid"
        )[:N],
        "noise": rng.normal(0, 1, N),
        "embedding": rng.uniform(-1, 1, N),
        "batch_embedding": rng.uniform(-0.5, 0.5, (32, 128)),
    }

    ac = AdaptivePhiCompressor(depth=4, rel_threshold=0.05)
    t0 = time.perf_counter()
    results = []

    for name, sig in signals.items():
        x = np.asarray(sig, dtype=np.float64)
        info = ac.classify(x.ravel() if x.ndim > 1 else x)
        result = ac.compress(x)

        # float16 baseline
        f16_zlib = zlib.compress(
            np.int32(x.size).tobytes() + x.ravel().astype(np.float16).tobytes(), level=6
        )
        f16_bits = len(f16_zlib) * 8 / max(x.size, 1)

        entry = {
            "signal": name,
            "n": int(x.size),
            "classification": info,
            "mode": result.mode,
            "original_bytes": result.original_bytes,
            "compressed_bytes": result.compressed_bytes,
            "bits_per_sample": result.bits_per_sample,
            "recon_error": result.recon_error,
            "float16_bits": f16_bits,
            "route_reason": result.route_reason,
        }
        results.append(entry)

    elapsed = time.perf_counter() - t0
    wins = sum(1 for r in results if r["bits_per_sample"] < r["float16_bits"])

    return {
        "title": "HYBA Data Adaptive φ-Compression Benchmark",
        "doctrine": "compress by folding, not by truncating",
        "n_samples": N,
        "results": results,
        "scoreboard": {
            "adaptive_beats_float16": f"{wins}/{len(results)}",
            "domain_strength": "structured / financial / φ-cascade / batch embeddings",
            "domain_fallback": "noise / dense vectors → float16+zlib (no fold)",
        },
        "elapsed_ms": elapsed * 1000,
        "engine": "AdaptivePhiCompressor v3.1",
        "repo_path": "python_backend/hyba_data/adaptive_compressor.py",
        "classifier": {
            "sparsity_threshold": 0.25,
            "entropy_threshold": 0.80,
            "rule": "fold only when BOTH sparsity > 0.25 AND entropy < 0.80",
        },
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_adaptive_benchmark(), indent=2, default=str))
