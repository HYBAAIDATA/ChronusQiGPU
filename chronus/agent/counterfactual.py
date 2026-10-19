"""Finite admissible options; inaction/information/reversible choices remain visible."""

from dataclasses import dataclass
from fractions import Fraction
from ._contracts import ContractError, ratio, integer
from .alignment import check_alignment
from .value import agent_is_admissible, agent_value


@dataclass(frozen=True)
class Option:
    action: object
    value: object
    p_catastrophic: Fraction
    option_preservation: int
    information_gain: int
    kind: str

    def __post_init__(self):
        ratio(self.p_catastrophic)
        integer(self.option_preservation)
        integer(self.information_gain)
        if self.kind == "INACTION" and self.action is not None:
            raise ContractError("inaction cannot carry an executable action")
        if self.kind not in ("ACTION", "INFORMATION", "DECOMPOSITION", "INACTION"):
            raise ContractError("typed option kind required")


def counterfactual_plan(
    options, objective, permissions, *, level, now, option_weight, information_weight
):
    if type(options) is not tuple or not 1 <= len(options) <= 64:
        raise ContractError("finite immutable options required")
    if not any(o.kind == "INACTION" for o in options):
        raise ContractError("inaction option is mandatory")
    integer(option_weight)
    integer(information_weight)
    admitted = []
    for o in options:
        if o.kind == "INACTION":
            admitted.append(o)
        elif (
            check_alignment(o.action, objective).aligned
            and agent_is_admissible(
                o.value, objective.constraints, o.p_catastrophic, o.action.request
            )
            and permissions.permitted(o.action.request, level=level, now=now)
        ):
            admitted.append(o)
    return max(
        admitted,
        key=lambda o: agent_value(o.value)
        + option_weight * o.option_preservation
        + information_weight * o.information_gain,
    )
