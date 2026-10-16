"""Pre-reserved multi-resource budgets and finite marginal-value allocation."""

import threading
from dataclasses import dataclass
from ._contracts import ContractError, integer


@dataclass(frozen=True)
class BudgetSet:
    compute: int
    money: int
    time: int
    attention: int
    human: int

    def __post_init__(self):
        for value in self.__dict__.values():
            integer(value)


class BudgetMeter:
    def __init__(self, limits):
        self.limits = limits
        self._lock = threading.RLock()
        self.used = {key: 0 for key in limits.__dict__}

    def reserve(self, costs):
        with self._lock:
            if set(costs) != set(self.used):
                raise ContractError("all resource dimensions required")
            for key, value in costs.items():
                integer(value)
                if self.used[key] + value > getattr(self.limits, key):
                    raise ContractError("budget exhausted")
            for key, value in costs.items():
                self.used[key] += value


def allocate_resources(meter, marginal_units):
    if type(marginal_units) is not tuple or len(marginal_units) > 4096:
        raise ContractError("bounded explicit marginal curve required")
    consumed = 0
    for value, cost, resources in marginal_units:
        if type(value) is not int or type(cost) is not int:
            raise ContractError("exact marginal values required")
        if value <= cost:
            return consumed, "marginal_value_not_above_cost"
        try:
            meter.reserve(resources)
        except ContractError:
            return consumed, "budget_exhausted"
        consumed += 1
    return consumed, "supplied_curve_exhausted"
