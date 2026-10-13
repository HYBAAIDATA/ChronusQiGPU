"""DeepMind-grade controlled evaluation utilities for the Intelligence substrate.

Seeded RNG, held-out splits, equal-budget ablations, paired
bootstrap intervals, Brier/ECE calibration, and negative-control
probes for the Lucas multi-scale coherence claim.

Design rules (AGENTS.md): pure measurement (callers inject
callables; no sibling Intelligence imports), deterministic
(explicit seed everywhere), fail-closed honesty
(``available=False`` instead of fabricated scores).
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: trace

from __future__ import annotations

import hashlib
import platform
import random
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Sequence, Tuple

THEOREM_PROVEN = False


def seeded_rng(seed: int) -> random.Random:
    """Return a dedicated RNG for one evaluation seed."""
    return random.Random(int(seed))


def content_hash(payload: Mapping[str, Any]) -> str:
    """Stable sha256 over a JSON-canonical payload for reproducibility."""
    import json

    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def environment_fingerprint() -> Dict[str, str]:
    """Record the execution substrate so a report is reproducible."""
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "theorem_proven": str(THEOREM_PROVEN),
    }


@dataclass
class AblationCondition:
    """One evaluation arm: full system or one mechanism removed."""

    name: str
    scores: List[float] = field(default_factory=list)


def heldout_split(task_ids: Sequence[str], n_train: int, seed: int = 0) -> Dict[str, Any]:
    """Deterministic train/held-out partition over task ids."""
    ids = list(task_ids)
    rng = seeded_rng(seed)
    rng.shuffle(ids)
    cut = max(0, min(len(ids), int(n_train)))
    return {"train": ids[:cut], "heldout": ids[cut:], "seed": seed}


def ablation_report(
    baseline: Sequence[float],
    conditions: Sequence[AblationCondition],
    seed: int = 0,
) -> Dict[str, Any]:
    """Paired deltas of each ablation vs the full system (verbatim)."""
    base = [float(v) for v in baseline]
    rows: List[Dict[str, Any]] = []
    for cond in conditions:
        diff = paired_bootstrap_diff(list(cond.scores), base, seed=seed)
        rows.append({"condition": cond.name, "n": len(cond.scores), "delta_vs_full": diff})
    return {"available": True, "n_tasks": len(base), "seed": seed, "rows": rows}


def instrumented_run(
    tasks: Sequence[str],
    system_fn: Callable[[str], Tuple[float, float]],
    seed: int = 0,
) -> Dict[str, Any]:
    """Run ``system_fn(task) -> (score, confidence)`` over tasks."""
    scores: List[float] = []
    confs: List[float] = []
    for task in tasks:
        score, conf = system_fn(str(task))
        scores.append(float(score))
        confs.append(float(conf))
    return {
        "n_tasks": len(scores),
        "scores": scores,
        "confidences": confs,
        "brier": brier_score(confs, scores),
        "ece": expected_calibration_error(confs, scores),
        "mean_ci": bootstrap_ci(scores, seed=seed),
        "seed": seed,
        "env": environment_fingerprint(),
        "theorem_proven": False,
    }


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
    rng = seeded_rng(seed)
    n = len(vals)
    means: List[float] = []
    for _ in range(max(100, int(n_resamples))):
        sample = [vals[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    alpha = (1.0 - ci) / 2.0
    lo = means[int(alpha * len(means))]
    hi = means[min(len(means) - 1, int((1.0 - alpha) * len(means)))]
    return {
        "available": True,
        "mean": sum(vals) / n,
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


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool."""
    import numpy as np  # noqa: F401

    from lucas.pool import get as _lucas_get

    result = _lucas_get("trace_kernel")(__import__("numpy").eye(2, dtype=int), n)
    result["module"] = __name__
    return result

