"""Equal-budget multi-scale coherence probes with negative controls."""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: trace

from __future__ import annotations

import random
from typing import Any, Dict, List, Sequence


def _rng(seed: int) -> random.Random:
    return random.Random(int(seed))


def _autocorr_lag1(xs: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    mean = sum(xs) / len(xs)
    den = sum((x - mean) ** 2 for x in xs)
    if den <= 0:
        return 0.0
    num = sum((xs[i] - mean) * (xs[i + 1] - mean) for i in range(len(xs) - 1))
    return float(num / den)


def equal_block_coherence(
    signal: Sequence[float],
    block_sizes: Sequence[int],
    blocks_per_scale: int = 8,
    seed: int = 0,
) -> Dict[str, Any]:
    """Coherence at each scale with EQUAL block counts (seeded windows)."""
    xs = [float(v) for v in signal]
    if not block_sizes or len(xs) < max(int(b) for b in block_sizes) * 2:
        return {"available": False, "reason": "signal shorter than 2x max block"}
    rng = _rng(seed)
    per_scale: Dict[str, Any] = {}
    coherences: List[float] = []
    for block in block_sizes:
        block = max(1, int(block))
        if block > len(xs):
            continue
        windows: List[float] = []
        for _ in range(max(2, int(blocks_per_scale))):
            start = rng.randrange(0, len(xs) - block + 1)
            chunk = xs[start : start + block]
            windows.append(sum(chunk) / len(chunk))
        ac1 = _autocorr_lag1(windows)
        per_scale[str(block)] = {"block": block, "autocorr_lag1": ac1, "n_blocks": len(windows)}
        coherences.append(ac1)
    if not coherences:
        return {"available": False, "reason": "no scale produced windows"}
    mean_c = sum(coherences) / len(coherences)
    var_c = sum((c - mean_c) ** 2 for c in coherences) / len(coherences)
    return {
        "available": True,
        "mean_coherence": float(mean_c),
        "coherence_variance": float(var_c),
        "scale_invariant": bool(var_c < 0.01 and mean_c > 0.3),
        "per_scale": per_scale,
        "n_scales": len(coherences),
        "seed": seed,
    }


def negative_control_shuffle(signal: Sequence[float], seed: int = 0) -> List[float]:
    """Seeded permutation: destroys temporal structure, keeps marginals."""
    xs = [float(v) for v in signal]
    rng = _rng(seed)
    rng.shuffle(xs)
    return xs


def negative_control_iid(n: int, seed: int = 0) -> List[float]:
    """Seeded iid Gaussian: the null a real signal must beat."""
    rng = _rng(seed)
    return [rng.gauss(0.0, 1.0) for _ in range(max(0, int(n)))]


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool."""
    import numpy as np  # noqa: F401

    from lucas.pool import get as _lucas_get

    result = _lucas_get("trace_kernel")(__import__("numpy").eye(2, dtype=int), n)
    result["module"] = __name__
    return result
