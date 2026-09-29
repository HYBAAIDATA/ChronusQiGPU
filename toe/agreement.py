"""Agreement between genuinely distinct evaluators.

A model-agreement score is evidence only when the evaluators are different
configurations looking at the same question. Scoring one evaluator against
copies of itself returns 1.0 by construction and says nothing. So:

- evaluators that share a configuration identifier count once;
- fewer than two distinct evaluators is ``available=False`` with
  ``agreement=None``, never 1.0;
- the score for a pair of prediction vectors p, q is
  ``1 - ||p - q|| / (||p|| + ||q||)``: 1 when they are identical, 0 when
  they point in opposite directions with equal norm (two zero vectors
  agree perfectly);
- the reported agreement is the mean over distinct pairs, with the minimum
  pair beside it.
"""

from __future__ import annotations

import itertools
import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

AGREEMENT_METRIC = "mean pairwise 1 - ||p_i - p_j|| / (||p_i|| + ||p_j||) over distinct evaluators"

Prediction = Union[float, Sequence[float]]


def _vector(prediction: Prediction) -> List[float]:
    values = [prediction] if isinstance(prediction, (int, float)) else list(prediction)
    out = []
    for value in values:
        if value is None or isinstance(value, bool):
            raise ValueError("prediction contains a missing or boolean entry")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("prediction contains a non-finite entry")
        out.append(number)
    if not out:
        raise ValueError("empty prediction")
    return out


def pair_agreement(p: Sequence[float], q: Sequence[float]) -> float:
    """``1 - ||p - q|| / (||p|| + ||q||)`` for equal-length vectors."""
    if len(p) != len(q):
        raise ValueError("predictions have different lengths")
    distance = math.sqrt(math.fsum((a - b) ** 2 for a, b in zip(p, q)))
    scale = math.sqrt(math.fsum(a * a for a in p)) + math.sqrt(math.fsum(b * b for b in q))
    if scale == 0.0:
        return 1.0
    return max(0.0, 1.0 - distance / scale)


def evaluator_agreement(
    predictions: Mapping[str, Prediction],
    *,
    evaluator_ids: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Agreement between the predictions of distinct evaluators.

    ``predictions`` maps an evaluator name to its prediction (a number or a
    vector). ``evaluator_ids`` optionally maps each name to a configuration
    identifier; names sharing an identifier are the same evaluator and are
    counted once (the first name in sorted order is kept).
    """
    ids = dict(evaluator_ids or {})
    kept: Dict[str, List[float]] = {}
    seen_ids: Dict[str, str] = {}
    duplicates: List[str] = []
    try:
        for name in sorted(predictions):
            identity = ids.get(name, name)
            if identity in seen_ids:
                duplicates.append(name)
                continue
            seen_ids[identity] = name
            kept[name] = _vector(predictions[name])
    except ValueError as exc:
        return {
            "available": False,
            "agreement": None,
            "reason": str(exc),
            "metric": AGREEMENT_METRIC,
        }
    base = {
        "metric": AGREEMENT_METRIC,
        "evaluators": sorted(kept),
        "duplicates_merged": duplicates,
        "n_distinct": len(kept),
    }
    if len(kept) < 2:
        return {
            **base,
            "available": False,
            "agreement": None,
            "reason": "fewer than two distinct evaluators; agreement is undefined",
        }
    try:
        pairs = {
            f"{a}|{b}": pair_agreement(kept[a], kept[b])
            for a, b in itertools.combinations(sorted(kept), 2)
        }
    except ValueError as exc:
        return {**base, "available": False, "agreement": None, "reason": str(exc)}
    return {
        **base,
        "available": True,
        "agreement": math.fsum(pairs.values()) / len(pairs),
        "min_pair_agreement": min(pairs.values()),
        "pairwise": pairs,
        "reason": None,
    }


__all__ = ["AGREEMENT_METRIC", "evaluator_agreement", "pair_agreement"]
