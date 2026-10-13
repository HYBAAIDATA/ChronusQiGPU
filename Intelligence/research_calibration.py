"""Brier/ECE calibration plus seeded bootstrap intervals."""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: trace

from __future__ import annotations

import random
from typing import Any, Dict, List, Sequence, Tuple


def _rng(seed: int) -> random.Random:
    return random.Random(int(seed))


def brier_score(predicted: Sequence[float], outcome: Sequence[float]) -> Dict[str, Any]:
    """Mean squared error between forecast probabilities and outcomes."""
    pred = [max(0.0, min(1.0, float(p))) for p in predicted]
    obs = [max(0.0, min(1.0, float(o))) for o in outcome]
    if len(pred) != len(obs) or len(pred) < 3:
        return {"available": False, "reason": "need >=3 paired samples", "n": len(pred)}
    mse = sum((p - o) ** 2 for p, o in zip(pred, obs)) / len(pred)
    return {"available": True, "brier": float(mse), "n": len(pred)}


def expected_calibration_error(
    predicted: Sequence[float], outcome: Sequence[float], n_bins: int = 10
) -> Dict[str, Any]:
    """Bin-wise |accuracy - confidence| weighted by bin mass."""
    pred = [max(0.0, min(1.0, float(p))) for p in predicted]
    obs = [max(0.0, min(1.0, float(o))) for o in outcome]
    if len(pred) != len(obs) or len(pred) < n_bins:
        return {"available": False, "reason": "need >=n_bins paired samples", "n": len(pred)}
    bins: List[List[Tuple[float, float]]] = [[] for _ in range(n_bins)]
    for p, o in zip(pred, obs):
        idx = min(n_bins - 1, int(p * n_bins))
        bins[idx].append((p, o))
    ece = 0.0
    for b in bins:
        if not b:
            continue
        acc = sum(o for _, o in b) / len(b)
        conf = sum(p for p, _ in b) / len(b)
        ece += abs(acc - conf) * (len(b) / len(pred))
    return {"available": True, "ece": float(ece), "n": len(pred), "n_bins": n_bins}


def bootstrap_ci(
    values: Sequence[float], n_resamples: int = 2000, seed: int = 0, ci: float = 0.95
) -> Dict[str, Any]:
    """Percentile bootstrap CI for the mean. Seeded, deterministic."""
    vals = [float(v) for v in values]
    if len(vals) < 2:
        return {"available": False, "reason": "need >=2 samples", "n": len(vals)}
    rng = _rng(seed)
    n = len(vals)
    means: List[float] = []
    for _ in range(max(100, int(n_resamples))):
        sample = [vals[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    alpha = (1.0 - ci) / 2.0
    lo = means[int(alpha * len(means))]
    hi = means[min(len(means) - 1, int((1.0 - alpha) * len(means)))]
    mean = sum(vals) / n
    return {
        "available": True,
        "mean": mean,
        "lo": float(lo),
        "hi": float(hi),
        "ci": ci,
        "n": n,
        "seed": seed,
    }


def paired_bootstrap_diff(
    a: Sequence[float],
    b: Sequence[float],
    n_resamples: int = 2000,
    seed: int = 0,
    ci: float = 0.95,
) -> Dict[str, Any]:
    """CI for mean(a - b) with paired resampling. Reports zero-exclusion."""
    xa = [float(v) for v in a]
    xb = [float(v) for v in b]
    if len(xa) != len(xb) or len(xa) < 2:
        return {"available": False, "reason": "need >=2 paired samples"}
    diffs = [x - y for x, y in zip(xa, xb)]
    base = bootstrap_ci(diffs, n_resamples=n_resamples, seed=seed, ci=ci)
    if not base.get("available"):
        return base
    base["excludes_zero"] = bool(base["lo"] > 0 or base["hi"] < 0)
    return base
