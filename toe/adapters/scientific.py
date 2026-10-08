"""Scientific / mathematical problems → Problem."""

from __future__ import annotations

from typing import Any, Mapping

from ..problem import Problem
from .base import ProblemAdapter
from .causal_system import CausalSystemAdapter


class RecurrenceAdapter(ProblemAdapter):
    """``sequence``: observed terms; ``steps``: how far to extrapolate.

    Whether the sequence obeys an integer recurrence, and therefore whether
    an exact extrapolation exists, is the backend's question — the adapter
    only hands over the terms."""

    name = "scientific.recurrence"

    def to_problem(self, raw: Mapping[str, Any]) -> Problem:
        return Problem(
            domain=str(raw.get("domain", self.name)),
            observation={"sequence": list(raw["sequence"])},
            forecast=int(raw["steps"]),
            metadata={"adapter": self.name},
        )


class LinearSystemAdapter(CausalSystemAdapter):
    """A physical/linear system with exact coefficients: same structural
    form as a causal system, physical vocabulary (``units`` maps node →
    unit label for interpretation)."""

    name = "scientific.linear_system"

    def to_problem(self, raw: Mapping[str, Any]) -> Problem:
        self.vocabulary = {k: f"{k} [{u}]" for k, u in (raw.get("units") or {}).items()}
        return super().to_problem({**raw, "domain": raw.get("domain", self.name)})


__all__ = ["LinearSystemAdapter", "RecurrenceAdapter"]
