"""Decision-level causal attribution by leave-one-module-out intervention."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class ModuleContribution:
    module_id: str
    contribution_score: float
    direction: str
    baseline_utility: float
    counterfactual_utility: float


@dataclass(frozen=True)
class AttributionReport:
    contributions: dict[str, ModuleContribution]
    total_attribution: float

    def get_top_contributors(self, n: int = 2) -> list[ModuleContribution]:
        if n < 0:
            raise ValueError("n must be nonnegative")
        return sorted(self.contributions.values(), key=lambda item: item.contribution_score,
                      reverse=True)[:n]

    def get_negative_contributors(self) -> list[ModuleContribution]:
        return sorted((item for item in self.contributions.values()
                       if item.contribution_score < 0), key=lambda item: item.contribution_score)


class CausalAttributionEngine:
    """Estimate module credit through explicit leave-one-out interventions."""

    def __init__(self):
        self._reports: list[AttributionReport] = []

    @staticmethod
    def _scalar(value: Any) -> float:
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return float(value)
        if isinstance(value, Mapping):
            for key in ("score", "confidence", "resonance_score", "value"):
                if key in value:
                    return CausalAttributionEngine._scalar(value[key])
        for name in ("score", "confidence", "resonance_score", "value"):
            if hasattr(value, name):
                return CausalAttributionEngine._scalar(getattr(value, name))
        return 0.0

    @classmethod
    def _utility(cls, prediction: Any, outcome: Any) -> float:
        if isinstance(outcome, str) or isinstance(prediction, str):
            return 1.0 if prediction == outcome else 0.0
        if isinstance(outcome, bool):
            probability = min(1.0, max(0.0, cls._scalar(prediction)))
            return 1.0 - abs(probability - float(outcome))
        target, value = cls._scalar(outcome), cls._scalar(prediction)
        scale = max(1.0, abs(target), abs(value))
        return max(-1.0, 1.0 - abs(value - target) / scale)

    def attribute(
        self,
        module_outputs: Mapping[str, Any],
        final_decision: Any,
        outcome: Any,
        decision_fn: Callable[[Mapping[str, Any]], Any] | None = None,
    ) -> AttributionReport:
        if not module_outputs:
            report = AttributionReport({}, 0.0)
            self._reports.append(report)
            return report
        baseline = self._utility(final_decision, outcome)
        contributions: dict[str, ModuleContribution] = {}
        if decision_fn is None:
            raw = {name: self._utility(value, outcome) - baseline
                   for name, value in module_outputs.items()}
        else:
            raw = {}
            for name in module_outputs:
                intervened = dict(module_outputs)
                intervened.pop(name)
                counterfactual = decision_fn(intervened)
                raw[name] = baseline - self._utility(counterfactual, outcome)
        normalizer = max(1.0, sum(abs(value) for value in raw.values()))
        for name, value in raw.items():
            score = max(-1.0, min(1.0, value / normalizer))
            counterfactual = baseline - value
            contributions[name] = ModuleContribution(
                module_id=name,
                contribution_score=score,
                direction="positive" if score > 0 else "negative" if score < 0 else "neutral",
                baseline_utility=baseline,
                counterfactual_utility=counterfactual,
            )
        total = sum(item.contribution_score for item in contributions.values())
        report = AttributionReport(contributions, max(-1.0, min(1.0, total)))
        self._reports.append(report)
        return report

    def pop_last_report(self) -> None:
        """Drop the most recent report — transactional rollback support."""
        if self._reports:
            self._reports.pop()

    def get_attribution_statistics(self) -> dict[str, Any]:
        totals: dict[str, list[float]] = {}
        for report in self._reports:
            for name, contribution in report.contributions.items():
                totals.setdefault(name, []).append(contribution.contribution_score)
        return {
            "reports": len(self._reports),
            "module_mean_contribution": {
                name: sum(values) / len(values) for name, values in totals.items()
            },
        }

    def reset(self) -> None:
        self._reports.clear()
