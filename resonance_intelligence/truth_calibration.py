"""Truth calibration for decision/outcome feedback loops."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass
class _SourceCalibration:
    confidences: list[float] = field(default_factory=list)
    outcomes: list[bool] = field(default_factory=list)


class TruthCalibrationEngine:
    """Track prediction calibration per source using absolute, Brier and ECE errors."""

    def __init__(self, n_bins: int = 10):
        if n_bins <= 0:
            raise ValueError("n_bins must be positive")
        self.n_bins = int(n_bins)
        self._sources: dict[str, _SourceCalibration] = {}

    def register_source(self, source_id: str) -> None:
        if not source_id:
            raise ValueError("source_id must not be empty")
        self._sources.setdefault(source_id, _SourceCalibration())

    def record_prediction(self, source_id: str, confidence: float, outcome: bool) -> None:
        value = float(confidence)
        if not 0.0 <= value <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        self.register_source(source_id)
        source = self._sources[source_id]
        source.confidences.append(value)
        source.outcomes.append(bool(outcome))

    @staticmethod
    def calibrate(confidence: float, outcome: bool) -> float:
        value = float(confidence)
        if not 0.0 <= value <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        return abs(value - float(bool(outcome)))

    def _statistics(self, source: _SourceCalibration) -> dict[str, Any]:
        n = len(source.confidences)
        if n == 0:
            return {"count": 0, "mean_confidence": 0.0, "accuracy": 0.0,
                    "mean_absolute_error": 0.0, "brier_score": 0.0, "ece": 0.0}
        confidences = source.confidences
        outcomes = [float(value) for value in source.outcomes]
        absolute = [abs(c - y) for c, y in zip(confidences, outcomes)]
        brier = [(c - y) ** 2 for c, y in zip(confidences, outcomes)]
        ece = 0.0
        for index in range(self.n_bins):
            low, high = index / self.n_bins, (index + 1) / self.n_bins
            members = [i for i, c in enumerate(confidences)
                       if low <= c < high or (index == self.n_bins - 1 and c == 1.0)]
            if members:
                avg_conf = sum(confidences[i] for i in members) / len(members)
                avg_out = sum(outcomes[i] for i in members) / len(members)
                ece += len(members) / n * abs(avg_conf - avg_out)
        return {
            "count": n,
            "mean_confidence": sum(confidences) / n,
            "accuracy": sum(outcomes) / n,
            "mean_absolute_error": sum(absolute) / n,
            "brier_score": sum(brier) / n,
            "ece": ece,
        }

    def get_source_calibration(self, source_id: str) -> dict[str, Any]:
        return self._statistics(self._sources.get(source_id, _SourceCalibration()))

    def get_global_calibration(self) -> dict[str, Any]:
        merged = _SourceCalibration()
        for source in self._sources.values():
            merged.confidences.extend(source.confidences)
            merged.outcomes.extend(source.outcomes)
        result = self._statistics(merged)
        result["sources"] = len(self._sources)
        return result

    def export_state(self) -> dict[str, Any]:
        """Durable form of every recorded (confidence, outcome) pair."""
        return {
            source_id: {
                "confidences": list(source.confidences),
                "outcomes": list(source.outcomes),
            }
            for source_id, source in self._sources.items()
        }

    def import_state(self, state: Mapping[str, Any]) -> None:
        """Restore a previously exported calibration series; replaces state."""
        self._sources = {
            source_id: _SourceCalibration(
                [float(c) for c in rows.get("confidences", [])],
                [bool(o) for o in rows.get("outcomes", [])],
            )
            for source_id, rows in dict(state or {}).items()
        }

    def reset(self) -> None:
        self._sources.clear()
