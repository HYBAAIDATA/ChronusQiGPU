"""Risk register.

Defaults are the program's qualitative assessments.
Once failures are observed, the label follows the observed rate.
"""

from __future__ import annotations

from dataclasses import dataclass, field


DEFAULTS = {
    "integration_complexity": "Low",
    "performance_scalability": "Very Low",
    "user_adoption": "Low",
    "competitive_response": "High",
}


def _label(rate: float) -> str:
    if rate < 0.01:
        return "Very Low"
    if rate < 0.2:
        return "Low"
    if rate < 0.5:
        return "Medium"
    return "High"


@dataclass
class RiskRegister:
    assessments: dict[str, str] = field(default_factory=lambda: dict(DEFAULTS))
    _events: dict[str, list[bool]] = field(default_factory=dict)

    def probability(self, name: str) -> str:
        events = self._events.get(name)
        if not events:
            return self.assessments[name]
        rate = sum(1 for failed in events if failed) / len(events)
        return _label(rate)

    def observe(self, name: str, failed: bool) -> str:
        if name not in self.assessments:
            raise KeyError(f"unknown risk {name}")
        self._events.setdefault(name, []).append(bool(failed))
        return self.probability(name)
