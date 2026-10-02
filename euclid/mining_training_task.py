"""Bounded mining-shaped HOLD/REDUCE/RESTORE training task.

A deterministic, dependency-free dataset generator for the governed training
pipeline.  States are coarse banded summaries of a mining transport snapshot;
the oracle reward maps degraded transport health to ``reduce``, healthy high
hashrate to ``restore`` and everything else to ``hold``.  The canonical state
family is deliberately small and shared across partitions — the same
operating envelope — while every case still owns distinct
lineage/session/seed metadata, so partitions stay whole-lineage.
"""
from __future__ import annotations

from typing import Any

from .training_pipeline import TrainingCase

RECOVERY_MODES = ("normal", "degraded")

CANONICAL_BREADTH_STATES: tuple[dict[str, Any], ...] = (
    {
        "accepted_band": 3, "rejected_band": 0, "stale_band": 0,
        "rtt_band": 1, "hashrate_band": 3, "recovery": "normal",
    },
    {
        "accepted_band": 3, "rejected_band": 0, "stale_band": 0,
        "rtt_band": 0, "hashrate_band": 1, "recovery": "normal",
    },
    {
        "accepted_band": 2, "rejected_band": 1, "stale_band": 0,
        "rtt_band": 1, "hashrate_band": 0, "recovery": "normal",
    },
    {
        "accepted_band": 1, "rejected_band": 1, "stale_band": 1,
        "rtt_band": 1, "hashrate_band": 2, "recovery": "normal",
    },
    {
        "accepted_band": 1, "rejected_band": 0, "stale_band": 0,
        "rtt_band": 2, "hashrate_band": 0, "recovery": "normal",
    },
    {
        "accepted_band": 1, "rejected_band": 1, "stale_band": 0,
        "rtt_band": 0, "hashrate_band": 1, "recovery": "normal",
    },
    {
        "accepted_band": 0, "rejected_band": 3, "stale_band": 1,
        "rtt_band": 2, "hashrate_band": 1, "recovery": "normal",
    },
    {
        "accepted_band": 2, "rejected_band": 0, "stale_band": 3,
        "rtt_band": 3, "hashrate_band": 2, "recovery": "normal",
    },
    {
        "accepted_band": 3, "rejected_band": 0, "stale_band": 0,
        "rtt_band": 1, "hashrate_band": 3, "recovery": "degraded",
    },
)


def breadth_reward(case: TrainingCase, action: str) -> float:
    """Bounded reward in [-1, 1] derived only from the declared banded state."""
    state = dict(case.state)
    degraded = (
        int(state.get("rejected_band", 0)) >= 2
        or int(state.get("stale_band", 0)) >= 2
        or str(state.get("recovery", "normal")) != "normal"
    )
    healthy = (
        int(state.get("accepted_band", 0)) >= 2
        and int(state.get("hashrate_band", 0)) >= 1
    )
    optimal = "reduce" if degraded else "restore" if healthy else "hold"
    return 1.0 if action == optimal else -1.0


def make_breadth_cases(
    *,
    count: int,
    session_id: str,
    seed: int,
    lineage_prefix: str | None = None,
) -> list[TrainingCase]:
    """Emit ``count`` deterministic cases owned by one session/seed.

    Cases cycle the canonical operating states so the bounded state family is
    covered by every partition; identity (case_id/lineage/session/seed) is
    unique per partition.
    """
    if count <= 0:
        raise ValueError("case count must be positive")
    if not str(session_id).strip():
        raise ValueError("a session_id is required for lineage accounting")
    prefix = lineage_prefix or f"{session_id}-lineage"
    family = CANONICAL_BREADTH_STATES
    return [
        TrainingCase(
            case_id=f"{session_id}-{index}",
            state=dict(family[index % len(family)]),
            lineage_id=f"{prefix}-{index}",
            session_id=session_id,
            seed=seed,
        )
        for index in range(count)
    ]


def make_partitioned_dataset(
    *,
    per_partition: int,
    train_seed: int = 1103,
    validation_seed: int = 2213,
    final_test_seed: int = 3313,
) -> dict[str, list[TrainingCase]]:
    """Whole-lineage partitions: each partition owns disjoint sessions/seeds."""
    return {
        "train": make_breadth_cases(
            count=per_partition, session_id="sess-train", seed=train_seed
        ),
        "validation": make_breadth_cases(
            count=per_partition,
            session_id="sess-validation",
            seed=validation_seed,
        ),
        "final_test": make_breadth_cases(
            count=per_partition,
            session_id="sess-final-test",
            seed=final_test_seed,
        ),
    }


__all__ = [
    "CANONICAL_BREADTH_STATES",
    "RECOVERY_MODES",
    "breadth_reward",
    "make_breadth_cases",
    "make_partitioned_dataset",
]
