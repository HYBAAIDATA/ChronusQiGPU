"""Controlled φ/Lucas/Pisot/manifold experiments against neutral baselines."""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from .phi_schedule import neutral_order, phi_order


@dataclass(frozen=True)
class PairedResult:
    seed: int
    neutral_score: float
    mathematical_score: float
    neutral_cost: float
    mathematical_cost: float

    @property
    def score_delta(self) -> float:
        return self.mathematical_score - self.neutral_score

    @property
    def cost_delta(self) -> float:
        return self.mathematical_cost - self.neutral_cost


def paired_ordering_experiment(
    size: int,
    evaluator: Callable[[Sequence[int], int], tuple[float, float]],
    *,
    seeds: Sequence[int] = tuple(range(10)),
) -> dict[str, Any]:
    """Compare φ ordering with identity using identical seeds and workloads."""
    if size <= 1:
        raise ValueError("size must exceed one")
    rows = []
    for seed in seeds:
        neutral_score, neutral_cost = evaluator(neutral_order(size), int(seed))
        mathematical_score, mathematical_cost = evaluator(phi_order(size), int(seed))
        rows.append(PairedResult(
            int(seed), float(neutral_score), float(mathematical_score),
            float(neutral_cost), float(mathematical_cost),
        ))
    deltas = [row.score_delta for row in rows]
    costs = [row.cost_delta for row in rows]
    mean = statistics.fmean(deltas)
    variation = statistics.stdev(deltas) if len(deltas) > 1 else 0.0
    return {
        "schema": "euclid.math-ordering-experiment/1",
        "hypothesis": (
            "φ low-discrepancy ordering improves measured task score or cost "
            "relative to neutral identity ordering"
        ),
        "evidence_class": "controlled-internal-experiment",
        "paired_runs": [
            {
                "seed": row.seed,
                "neutral_score": row.neutral_score,
                "mathematical_score": row.mathematical_score,
                "neutral_cost": row.neutral_cost,
                "mathematical_cost": row.mathematical_cost,
                "score_delta": row.score_delta,
                "cost_delta": row.cost_delta,
            }
            for row in rows
        ],
        "mean_score_delta": mean,
        "score_delta_stddev": variation,
        "mean_cost_delta": statistics.fmean(costs),
        "supported": mean > 0.0,
        "falsification": "mean score delta <= 0 or cost increase erases score gain",
        "external_superiority_established": False,
    }


__all__ = ["PairedResult", "paired_ordering_experiment"]