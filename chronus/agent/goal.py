"""Explicit objective admission: ambiguity is represented, not silently inferred."""

from __future__ import annotations

from dataclasses import dataclass

from ._contracts import ContractError, text
from .value import Constraints


@dataclass(frozen=True)
class Objective:
    id: str
    surface_goal: str
    inferred_goal: str
    expected_state: str
    success_criteria: tuple[str, ...]
    constraints: Constraints
    stakeholders: tuple[str, ...]
    non_goals: tuple[str, ...]
    assumptions: tuple[str, ...]
    escalation_policy: str

    def __post_init__(self) -> None:
        for value in (
            self.id,
            self.surface_goal,
            self.inferred_goal,
            self.expected_state,
            self.escalation_policy,
        ):
            text(value)

        for values in (
            self.success_criteria,
            self.stakeholders,
            self.non_goals,
            self.assumptions,
        ):
            if type(values) is not tuple:
                raise ContractError("immutable objective context required")

        if not self.success_criteria:
            raise ContractError("explicit acceptance criteria required")

        for field_name, value in (
            ("surface_goal", self.surface_goal),
            ("inferred_goal", self.inferred_goal),
            ("expected_state", self.expected_state),
            ("escalation_policy", self.escalation_policy),
        ):
            if not str(value).strip():
                raise ContractError(f"{field_name} must be non-empty")


def infer_real_objective(objective: object, ledger: object, *, now: object) -> Objective:
    """Validate the objective before making an authority claim."""
    if not isinstance(objective, Objective):
        ledger.append(
            "clarification_requested",
            {"reason": "typed objective/acceptance criteria missing"},
            now=now,
        )
        raise ContractError("ambiguous objective; no automatic authority inferred")

    ledger.append(
        "objective_inferred",
        objective,
        now=now,
        rationale="declared host objective; natural-language intention not invented",
    )
    return objective
