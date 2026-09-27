"""Reference workloads and live timings.

The reference figures are the program's before/after step counts.
Live samples are whatever the caller records.
"""

from __future__ import annotations

from dataclasses import dataclass, field


REFERENCE = {
    "data_scientist": {"baseline_steps": 4, "unified_steps": 1, "increase": 3.0},
    "business_analyst": {"baseline_steps": 7, "unified_steps": 2, "increase": 2.5},
    "operations_overhead": {"baseline_units": 100, "unified_units": 20, "reduction": 0.8},
    "time_to_insight": {"baseline_seconds": 5.0, "unified_seconds": 1.0, "faster": 4.0},
    "risk_model_development": {"baseline_steps": 4, "unified_steps": 1, "reduction": 0.75},
    "regulatory_reporting": {"baseline_steps": 10, "unified_steps": 1, "reduction": 0.90},
}


@dataclass
class ProductivityMeter:
    samples: dict[str, list[float]] = field(default_factory=dict)

    def reference(self, name: str) -> dict:
        try:
            return dict(REFERENCE[name])
        except KeyError as exc:
            raise KeyError(f"unknown workload {name}") from exc

    def record(self, name: str, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("seconds must be >= 0")
        self.samples.setdefault(name, []).append(float(seconds))

    def mean(self, name: str) -> float:
        rows = self.samples.get(name) or []
        if not rows:
            raise KeyError(f"no samples for {name}")
        return sum(rows) / len(rows)
