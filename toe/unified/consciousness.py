"""Behaviour state.

Actions and corrections update a threshold and a widget ranking.
The threshold is the midpoint between the corrected class scores.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConsciousnessState:
    _actions: dict[str, dict[str, float]] = field(default_factory=dict)
    _scores: dict[str, list[tuple[float, int]]] = field(default_factory=dict)

    def observe(self, user: str, widget: str, depth: int = 1) -> None:
        weights = self._actions.setdefault(user, {})
        weights[widget] = weights.get(widget, 0.0) + float(depth)

    def correct(self, user: str, score: float, label: int) -> float:
        if label not in (0, 1):
            raise ValueError("label must be 0 or 1")
        self._scores.setdefault(user, []).append((float(score), int(label)))
        return self.threshold(user)

    def threshold(self, user: str) -> float:
        rows = self._scores.get(user) or []
        positives = [score for score, label in rows if label == 1]
        negatives = [score for score, label in rows if label == 0]
        if not positives or not negatives:
            return 0.0
        return (sum(positives) / len(positives) + sum(negatives) / len(negatives)) / 2.0

    def decide(self, user: str, score: float) -> int:
        return 1 if score > self.threshold(user) else 0

    def accuracy(self, user: str, rows: list[tuple[float, int]], *, learned: bool) -> float:
        if not rows:
            return 0.0
        limit = self.threshold(user) if learned else 0.0
        hits = sum((1 if score > limit else 0) == label for score, label in rows)
        return hits / len(rows)

    def rank(self, widgets: list[str], user: str) -> list[str]:
        weights = self._actions.get(user, {})
        return sorted(widgets, key=lambda name: (-weights.get(name, 0.0), name))
