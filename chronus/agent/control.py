"""Action-plane contracts and finite stopping outcomes. No governance key lives here."""

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from ._contracts import ContractError, integer, ratio, sha, text
from .permissions import ActionRequest
from .value import Value


class StoppingCondition(Enum):
    GOAL_ACHIEVED = "goal_achieved"
    CONFIDENCE_INSUFFICIENT = "confidence_insufficient"
    BUDGET_EXHAUSTED = "budget_exhausted"
    TIME_EXHAUSTED = "time_exhausted"
    PERMISSION_BOUNDARY = "permission_boundary"
    HUMAN_ESCALATION = "human_escalation"
    IRRECOVERABLE_FAILURE = "irrecoverable_failure"
    SAFETY_STOP = "safety_stop"
    ROLLBACK_COMPLETED = "rollback_completed"


@dataclass(frozen=True)
class Action:
    request: ActionRequest
    capability: str
    objective_id: str
    expected_state: str
    cognition_digest: str
    value: Value
    p_catastrophic: Fraction
    costs: tuple[tuple[str, int], ...]
    proxy_only: bool = False
    loophole: bool = False
    stakeholder_violation: bool = False
    goal_drift: bool = False

    def __post_init__(self):
        if not isinstance(self.request, ActionRequest) or not isinstance(self.value, Value):
            raise ContractError("typed action, value and permission request required")
        for x in (self.capability, self.objective_id, self.expected_state):
            text(x)
        sha(self.cognition_digest)
        ratio(self.p_catastrophic)
        if type(self.costs) is not tuple or len({k for k, v in self.costs}) != len(self.costs):
            raise ContractError("immutable distinct cost dimensions required")
        for k, v in self.costs:
            text(k)
            integer(v)
        for name in ("proxy_only", "loophole", "stakeholder_violation", "goal_drift"):
            if type(getattr(self, name)) is not bool:
                raise ContractError("typed alignment flags required")


@dataclass(frozen=True)
class ControlPolicy:
    max_iterations: int
    max_attempts: int
    deadline_ns: int
    max_observation_age: int
    confidence_floor: Fraction

    def __post_init__(self):
        integer(self.max_iterations, minimum=1, maximum=10000)
        integer(self.max_attempts, minimum=1, maximum=100)
        integer(self.deadline_ns)
        integer(self.max_observation_age)
        ratio(self.confidence_floor)


@dataclass(frozen=True)
class Plan:
    objective_id: str
    cognition_digest: str
    actions: tuple[Action, ...]
    policy: ControlPolicy

    def __post_init__(self):
        sha(self.cognition_digest)
        if type(self.actions) is not tuple or len(self.actions) > 10000:
            raise ContractError("finite immutable plan required")
        if any(
            a.cognition_digest != self.cognition_digest or a.objective_id != self.objective_id
            for a in self.actions
        ):
            raise ContractError("all actions must derive from the declared cognition/objective")


@dataclass(frozen=True)
class Outcome:
    stop: StoppingCondition
    reason: str
    iterations: int
    verification: object
    effects: tuple
    audit_id: str
    rollback_verified: bool

    @property
    def recovery_stop(self):
        return StoppingCondition.ROLLBACK_COMPLETED if self.rollback_verified else None


@dataclass(frozen=True)
class ExecutionReceipt:
    actual_costs: tuple[tuple[str, int], ...]
    output_evidence: str

    def __post_init__(self):
        sha(self.output_evidence)
        if type(self.actual_costs) is not tuple or len({k for k, v in self.actual_costs}) != len(
            self.actual_costs
        ):
            raise ContractError("distinct immutable measured costs required")
        for key, value in self.actual_costs:
            text(key)
            integer(value)
