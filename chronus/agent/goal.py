"""Explicit objective admission: ambiguity is represented, not silently inferred."""

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

    def __post_init__(self):
        for value in (
            self.id,
            self.surface_goal,
            self.inferred_goal,
            self.expected_state,
            self.escalation_policy,
        ):
            text(value)
        for values in (self.success_criteria, self.stakeholders, self.non_goals, self.assumptions):
            if type(values) is not tuple:
                raise ContractError("immutable objective context required")
        if not self.success_criteria:
            raise ContractError("explicit acceptance criteria required")


def infer_real_objective(objective, ledger, *, now):
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
