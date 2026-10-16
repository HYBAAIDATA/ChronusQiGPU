"""Exact explicit value costs; catastrophic risk is a nontradeable constraint."""

from dataclasses import dataclass
from fractions import Fraction
from ._contracts import integer, ratio, ContractError


@dataclass(frozen=True)
class Value:
    expected_value: int
    compute_cost: int
    money_cost: int
    human_cost: int
    time_cost: int
    failure_cost: int
    opportunity_cost: int

    def __post_init__(self):
        if type(self.expected_value) is not int:
            raise ContractError("exact common-unit value required")
        for name in (
            "compute_cost",
            "money_cost",
            "human_cost",
            "time_cost",
            "failure_cost",
            "opportunity_cost",
        ):
            integer(getattr(self, name))


@dataclass(frozen=True)
class Constraints:
    max_catastrophic_probability: Fraction
    max_compute_per_task: int
    max_money_per_task: int
    max_human_cost_per_task: int
    max_time_per_task: int
    allowed_data_classes: tuple[str, ...]
    allowed_jurisdictions: tuple[str, ...]

    def __post_init__(self):
        ratio(self.max_catastrophic_probability)
        for name in (
            "max_compute_per_task",
            "max_money_per_task",
            "max_human_cost_per_task",
            "max_time_per_task",
        ):
            integer(getattr(self, name))
        if (
            type(self.allowed_data_classes) is not tuple
            or type(self.allowed_jurisdictions) is not tuple
        ):
            raise ContractError("immutable data/jurisdiction constraints required")


def agent_value(value):
    return value.expected_value - sum(
        (
            value.compute_cost,
            value.money_cost,
            value.human_cost,
            value.failure_cost,
            value.opportunity_cost,
        )
    )


def agent_is_admissible(value, constraints, p_catastrophic, request):
    ratio(p_catastrophic)
    return (
        p_catastrophic < constraints.max_catastrophic_probability
        and value.compute_cost <= constraints.max_compute_per_task
        and value.money_cost <= constraints.max_money_per_task
        and value.human_cost <= constraints.max_human_cost_per_task
        and value.time_cost <= constraints.max_time_per_task
        and request.data_sensitivity in constraints.allowed_data_classes
        and request.jurisdiction in constraints.allowed_jurisdictions
    )
