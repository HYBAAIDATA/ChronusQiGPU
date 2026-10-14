import pytest
from chronus.agent._contracts import ContractError
from chronus.agent.resources import BudgetSet, BudgetMeter, allocate_resources


def test_atomic_reservation():
    m = BudgetMeter(BudgetSet(1, 1, 1, 1, 1))
    with pytest.raises(ContractError):
        m.reserve(dict(compute=1, money=2, time=1, attention=1, human=1))
    assert not any(m.used.values())
    assert allocate_resources(m, ((1, 1, dict(m.used)),)) == (0, "marginal_value_not_above_cost")
    with pytest.raises(ContractError):
        allocate_resources(m, iter(()))
