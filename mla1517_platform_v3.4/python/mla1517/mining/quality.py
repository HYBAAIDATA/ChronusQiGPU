"""Separate quality channels per search policy.

Execution, search, network, recovery and thermal quality are kept apart and
never collapsed into one scalar reward: a single score invites the policy to
trade, say, pool rejections against hash rate. An unmeasured channel reports
``None`` (unknown), never zero.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any, Deque

from .search_plan import CompletionState, ExecutionRecord, PoolOutcome


def _mean(values: Deque[float]) -> float | None:
    return sum(values) / len(values) if values else None


@dataclass
class _PolicyQuality:
    window: int
    hash_rates: Deque[float] = field(init=False)
    completion: Deque[float] = field(init=False)
    temperatures: Deque[float] = field(init=False)
    evidence: Counter = field(default_factory=Counter)
    routes: Counter = field(default_factory=Counter)
    outcomes: Counter = field(default_factory=Counter)
    early_winners: int = 0
    invalidated: int = 0
    executions: int = 0
    recovery_events: int = 0

    def __post_init__(self) -> None:
        self.hash_rates = deque(maxlen=self.window)
        self.completion = deque(maxlen=self.window)
        self.temperatures = deque(maxlen=self.window)

    def observe(self, record: ExecutionRecord) -> None:
        self.executions += 1
        if record.elapsed_seconds > 0 and record.hash_count > 0:
            self.hash_rates.append(record.hash_count / record.elapsed_seconds)
        if record.planned_window > 0:
            self.completion.append(record.actual_window / record.planned_window)
        if record.temperature_c is not None:
            self.temperatures.append(float(record.temperature_c))
        self.evidence[record.evidence_class.value] += 1
        self.routes[record.executed_route or "none"] += 1
        self.outcomes[record.pool_outcome.value] += 1
        self.early_winners += record.completion_state is CompletionState.EARLY_WINNER
        self.invalidated += record.completion_state is CompletionState.INVALIDATED
        self.recovery_events += bool(record.recovery_event)

    def snapshot(self) -> dict[str, Any]:
        resolved = (
            self.outcomes[PoolOutcome.ACCEPTED.value] + self.outcomes[PoolOutcome.REJECTED.value]
        )
        return {
            "execution": {
                "hashes_per_second_mean": _mean(self.hash_rates),
                "samples": len(self.hash_rates),
                "evidence_classes": dict(self.evidence),
                "executed_routes": dict(self.routes),
            },
            "search": {
                "completion_ratio_mean": _mean(self.completion),
                "early_winner_rate": self.early_winners / self.executions,
                "invalidated_rate": self.invalidated / self.executions,
            },
            "network": {
                "outcomes": dict(self.outcomes),
                "accept_rate": (
                    self.outcomes[PoolOutcome.ACCEPTED.value] / resolved if resolved else None
                ),
            },
            "recovery": {
                "events": self.recovery_events,
                "rate": self.recovery_events / self.executions,
            },
            "thermal": {
                "temperature_c_mean": _mean(self.temperatures),
                "samples": len(self.temperatures),
            },
        }


class QualityLedger:
    def __init__(self, *, window: int = 64) -> None:
        if window <= 0:
            raise ValueError("window must be positive")
        self._window = window
        self._policies: dict[str, _PolicyQuality] = {}

    def observe(self, record: ExecutionRecord) -> None:
        policy = self._policies.setdefault(record.policy_id, _PolicyQuality(self._window))
        policy.observe(record)

    def snapshot(self) -> dict[str, Any]:
        return {name: quality.snapshot() for name, quality in self._policies.items()}
